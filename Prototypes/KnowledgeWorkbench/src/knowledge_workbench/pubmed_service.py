"""Formal PubMed Evidence orchestration, metadata audit, and human selection."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import HttpUrl, ValidationError

from knowledge_workbench.discovery_interfaces import FormalEvidenceAcquisitionRequest
from knowledge_workbench.evidence_intelligence import (
    DefaultEvidenceDeduplicator,
    DefaultEvidenceRanker,
    EvidenceBundleBuilder,
    stable_evidence_id,
)
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceCitation,
    EvidenceLanguage,
    EvidenceNormalizationResult,
    EvidenceProviderReference,
    EvidenceSearchRequest,
    EvidenceType,
    NormalizedEvidence,
    PipelineEvidenceLevel,
    RawEvidenceSearchResult,
)
from knowledge_workbench.providers.pubmed_provider import (
    PubMedEvidenceError,
    PubMedEvidenceProvider,
    PubMedEvidenceProviderResult,
)
from knowledge_workbench.pubmed_models import (
    PubMedEvidenceSelectionEntry,
    PubMedEvidenceSelectionRequest,
    PubMedFormalEvidenceMetadata,
    PubMedFormalEvidencePreview,
    PubMedSearchAuditEntry,
    PubMedSearchStatus,
)


class PubMedEvidenceServiceError(RuntimeError):
    pass


class PubMedEvidenceNormalizer:
    normalizer_name = "pubmed_evidence_normalizer"
    normalizer_version = "1.0"

    def normalize(
        self,
        result: RawEvidenceSearchResult,
    ) -> EvidenceNormalizationResult:
        if result.search_provider_name != "pubmed":
            raise PubMedEvidenceServiceError(
                "PubMed NormalizerはPubMed Recordだけを受け付けます。"
            )
        evidence: list[NormalizedEvidence] = []
        rejected: list[str] = []
        warnings = list(result.warnings)
        abstract_truncated = 0
        for record in result.records:
            try:
                if record.provider_name != "pubmed":
                    raise ValueError("provider mismatch")
                payload = record.payload
                pmid = str(payload["pmid"])
                if pmid != record.provider_record_id or not pmid.isdigit():
                    raise ValueError("PMID mismatch")
                title = str(payload["title"])
                journal = str(payload["journal"])
                publication_type_values = payload.get("publication_types", [])
                if not isinstance(publication_type_values, list):
                    raise ValueError("publication_types must be a list")
                publication_types = tuple(
                    str(item) for item in publication_type_values
                )
                evidence_type, evidence_level = _evidence_policy(publication_types)
                abstract_value = payload.get("abstract")
                abstract = (
                    str(abstract_value)
                    if isinstance(abstract_value, str) and abstract_value.strip()
                    else "PubMed Abstractは収載されていません。"
                )
                if len(abstract) > 6000:
                    abstract = abstract[:5997] + "..."
                    abstract_truncated += 1
                doi = str(payload["doi"]) if payload.get("doi") else None
                publication_date = _optional_date(payload.get("publication_date"))
                author_values = payload.get("authors", [])
                if not isinstance(author_values, list):
                    raise ValueError("authors must be a list")
                authors = [str(item) for item in author_values]
                language = _language(str(payload.get("language", "und")))
                url = str(payload["url"])
                evidence.append(
                    NormalizedEvidence(
                        evidence_id=stable_evidence_id(
                            doi=None,
                            pmid=pmid,
                            url=url,
                            title=title,
                            publisher=journal,
                            publication_date=(
                                publication_date.isoformat()
                                if publication_date is not None
                                else None
                            ),
                        ),
                        title=title,
                        publisher=journal,
                        evidence_type=evidence_type,
                        evidence_level=evidence_level,
                        publication_date=publication_date,
                        url=HttpUrl(url),
                        doi=doi,
                        pmid=pmid,
                        language=language,
                        abstract_or_snippet=abstract,
                        retrieved_at=record.retrieved_at,
                        provider=EvidenceProviderReference(
                            provider_name="pubmed",
                            provider_version=record.provider_version,
                            provider_record_id=pmid,
                            retrieved_at=record.retrieved_at,
                        ),
                        information_priority_rank=6,
                        citation=EvidenceCitation(
                            formatted=_citation(
                                title=title,
                                journal=journal,
                                authors=authors,
                                publication_date=publication_date,
                                pmid=pmid,
                                doi=doi,
                            )
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError):
                rejected.append(record.provider_record_id)
        if rejected:
            warnings.append(f"PubMed Normalizerで{len(rejected)}件を除外しました。")
        if abstract_truncated:
            warnings.append(
                "Evidence Contract上限に合わせ"
                f"Abstract {abstract_truncated}件を表示用に短縮しました。"
            )
        return EvidenceNormalizationResult(
            normalized_at=datetime.now(UTC),
            query=result.query,
            subject=result.subject,
            evidence=evidence,
            rejected_provider_record_ids=rejected,
            external_search_performed=True,
            search_duration_ms=result.duration_ms,
            warnings=warnings,
        )


class JsonlPubMedSearchAuditLog:
    """Metadata-only search audit. Abstract, secret, and raw XML are excluded."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_success(
        self,
        result: PubMedEvidenceProviderResult,
        preview: PubMedFormalEvidencePreview,
    ) -> PubMedSearchAuditEntry:
        bundle = preview.evidence_bundle
        entry = PubMedSearchAuditEntry(
            execution_id=result.execution.execution_id,
            bundle_id=bundle.bundle_id,
            input_term=result.execution.input_term,
            query=result.execution.query,
            retrieved_pmids=result.execution.returned_pmids,
            returned_record_count=len(result.records),
            accepted_count=bundle.accepted_evidence_count,
            excluded_count=bundle.excluded_evidence_count,
            deduplicated_count=len(bundle.deduplication_decisions),
            duration_ms=result.execution.duration_ms,
            request_count=result.execution.request_count,
            retry_count=result.execution.retry_count,
            api_key_used=result.execution.api_key_used,
            rate_limit_mode=result.execution.rate_limit_mode,
            status=result.execution.status,
            retrieved_at=result.execution.completed_at,
        )
        self._append(entry)
        return entry

    def record_failure(self, error: PubMedEvidenceError) -> PubMedSearchAuditEntry:
        entry = PubMedSearchAuditEntry(
            execution_id=error.execution_id,
            input_term=error.input_term,
            query=error.query,
            returned_record_count=0,
            accepted_count=0,
            excluded_count=0,
            deduplicated_count=0,
            duration_ms=max(
                0,
                round((error.completed_at - error.started_at).total_seconds() * 1000),
            ),
            request_count=error.request_count,
            retry_count=error.retry_count,
            api_key_used=error.api_key_used,
            rate_limit_mode=error.rate_limit_mode,
            status=PubMedSearchStatus.FAILED,
            error_code=error.code,
            retrieved_at=error.completed_at,
        )
        self._append(entry)
        return entry

    def list(self, *, limit: int = 100) -> list[PubMedSearchAuditEntry]:
        if not self.path.exists():
            return []
        try:
            entries = [
                PubMedSearchAuditEntry.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValidationError) as error:
            raise PubMedEvidenceServiceError(
                "PubMed Search Auditを読み込めません。"
            ) from error
        return list(reversed(entries[-limit:]))

    def _append(self, entry: PubMedSearchAuditEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise PubMedEvidenceServiceError(
                "PubMed Search Auditを保存できません。"
            ) from error


class JsonlPubMedSelectionRepository:
    """Append-only human evidence selection, separate from Medical Review."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        request: PubMedEvidenceSelectionRequest,
        *,
        known_evidence_ids: set[str],
    ) -> PubMedEvidenceSelectionEntry:
        if request.evidence_id not in known_evidence_ids:
            raise PubMedEvidenceServiceError(
                "Evidence IDが対象Evidence Bundleにありません。"
            )
        entry = PubMedEvidenceSelectionEntry(
            selection_id=f"pes_{uuid4().hex[:20]}",
            bundle_id=request.bundle_id,
            evidence_id=request.evidence_id,
            decision=request.decision,
            operator=request.operator,
            timestamp=datetime.now(UTC),
            comment=request.comment,
        )
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise PubMedEvidenceServiceError(
                "Evidence Selectionを保存できません。"
            ) from error
        return entry

    def list(self, *, limit: int = 100) -> list[PubMedEvidenceSelectionEntry]:
        if not self.path.exists():
            return []
        try:
            entries = [
                PubMedEvidenceSelectionEntry.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValidationError) as error:
            raise PubMedEvidenceServiceError(
                "Evidence Selection履歴を読み込めません。"
            ) from error
        return list(reversed(entries[-limit:]))


class PubMedFormalEvidenceService:
    def __init__(
        self,
        *,
        provider: PubMedEvidenceProvider,
        normalizer: PubMedEvidenceNormalizer,
        search_audit: JsonlPubMedSearchAuditLog,
        selections: JsonlPubMedSelectionRepository,
        deduplicator: DefaultEvidenceDeduplicator | None = None,
        ranker: DefaultEvidenceRanker | None = None,
        bundle_builder: EvidenceBundleBuilder | None = None,
    ) -> None:
        self.provider = provider
        self.normalizer = normalizer
        self.search_audit = search_audit
        self.selections = selections
        self.deduplicator = deduplicator or DefaultEvidenceDeduplicator()
        self.ranker = ranker or DefaultEvidenceRanker()
        self.bundle_builder = bundle_builder or EvidenceBundleBuilder()
        self._pending: dict[str, PubMedFormalEvidencePreview] = {}

    def direct_preview(
        self,
        term: str,
        *,
        aliases: tuple[str, ...] = (),
        max_records: int | None = None,
    ) -> PubMedFormalEvidencePreview:
        request = EvidenceSearchRequest(
            theme=term,
            preferred_languages=[EvidenceLanguage.EN],
        )
        try:
            provider_result = self.provider.search_with_report(
                request,
                aliases=aliases,
                max_records=max_records,
            )
        except PubMedEvidenceError as error:
            self.search_audit.record_failure(error)
            raise
        return self._build_preview(provider_result)

    def handoff_preview(
        self,
        request: FormalEvidenceAcquisitionRequest,
    ) -> PubMedFormalEvidencePreview:
        try:
            provider_result = self.provider.acquire_with_report(request)
        except PubMedEvidenceError as error:
            self.search_audit.record_failure(error)
            raise
        return self._build_preview(provider_result)

    def select(
        self,
        request: PubMedEvidenceSelectionRequest,
    ) -> PubMedEvidenceSelectionEntry:
        preview = self._pending.get(request.bundle_id)
        if preview is None:
            raise PubMedEvidenceServiceError(
                "Evidence Bundleが見つかりません。もう一度PubMed検索してください。"
            )
        evidence_ids = {
            item.evidence.evidence_id for item in preview.evidence_bundle.evidence
        }
        return self.selections.save(request, known_evidence_ids=evidence_ids)

    def _build_preview(
        self,
        provider_result: PubMedEvidenceProviderResult,
    ) -> PubMedFormalEvidencePreview:
        normalization = self.normalizer.normalize(provider_result.raw)
        if not normalization.evidence:
            error = PubMedEvidenceServiceError(
                "標準化できるPubMed Evidenceがありません。"
            )
            raise error
        deduplication = self.deduplicator.deduplicate(normalization)
        ranking = self.ranker.rank(deduplication)
        bundle = self.bundle_builder.build(
            normalization,
            deduplication,
            ranking,
        )
        normalized_by_pmid = {
            item.pmid: item for item in normalization.evidence if item.pmid
        }
        accepted_evidence_ids = {
            item.evidence.evidence_id for item in bundle.evidence
        }
        metadata = tuple(
            PubMedFormalEvidenceMetadata(
                evidence_id=normalized_by_pmid[record.pmid].evidence_id,
                pmid=record.pmid,
                title=record.title,
                authors=record.authors,
                journal=record.journal,
                publication_date=record.publication_date,
                publication_types=record.publication_types,
                doi=record.doi,
                language=record.language,
                mesh_terms=record.mesh_terms,
                abstract_available=record.abstract is not None,
                evidence_level=normalized_by_pmid[
                    record.pmid
                ].evidence_level.value,
                retrieved_at=record.retrieved_at,
            )
            for record in provider_result.records
            if record.pmid in normalized_by_pmid
            and normalized_by_pmid[record.pmid].evidence_id
            in accepted_evidence_ids
        )
        provisional = PubMedFormalEvidencePreview(
            preview_id=f"pfp_{_fingerprint(bundle.fingerprint)[:20]}",
            mode=provider_result.execution.mode,
            input_term=provider_result.execution.input_term,
            query=provider_result.execution.query,
            evidence_bundle=bundle,
            formal_evidence_metadata=metadata,
            search_audit=PubMedSearchAuditEntry(
                execution_id=provider_result.execution.execution_id,
                bundle_id=bundle.bundle_id,
                input_term=provider_result.execution.input_term,
                query=provider_result.execution.query,
                retrieved_pmids=provider_result.execution.returned_pmids,
                returned_record_count=len(provider_result.records),
                accepted_count=bundle.accepted_evidence_count,
                excluded_count=bundle.excluded_evidence_count,
                deduplicated_count=len(bundle.deduplication_decisions),
                duration_ms=provider_result.execution.duration_ms,
                request_count=provider_result.execution.request_count,
                retry_count=provider_result.execution.retry_count,
                api_key_used=provider_result.execution.api_key_used,
                rate_limit_mode=provider_result.execution.rate_limit_mode,
                status=provider_result.execution.status,
                retrieved_at=provider_result.execution.completed_at,
            ),
        )
        audit = self.search_audit.record_success(provider_result, provisional)
        preview = provisional.model_copy(update={"search_audit": audit})
        self._pending[bundle.bundle_id] = preview
        return preview


def _evidence_policy(
    publication_types: tuple[str, ...],
) -> tuple[EvidenceType, PipelineEvidenceLevel]:
    normalized = {item.strip().lower() for item in publication_types}
    if normalized & {"guideline", "practice guideline"}:
        return EvidenceType.GUIDELINE, PipelineEvidenceLevel.B
    if normalized & {"meta-analysis", "systematic review"}:
        return EvidenceType.JOURNAL_ARTICLE, PipelineEvidenceLevel.B
    return EvidenceType.JOURNAL_ARTICLE, PipelineEvidenceLevel.C


def _optional_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value))


def _language(value: str) -> EvidenceLanguage:
    normalized = value.strip().lower()
    if normalized in {"eng", "en"}:
        return EvidenceLanguage.EN
    if normalized in {"jpn", "ja"}:
        return EvidenceLanguage.JA
    return EvidenceLanguage.OTHER


def _citation(
    *,
    title: str,
    journal: str,
    authors: list[str],
    publication_date: date | None,
    pmid: str,
    doi: str | None,
) -> str:
    author_text = ", ".join(authors[:3])
    if len(authors) > 3:
        author_text += ", et al."
    values = [
        author_text or None,
        title,
        journal,
        str(publication_date.year) if publication_date else None,
        f"PMID: {pmid}",
        f"DOI: {doi}" if doi else None,
    ]
    return " · ".join(item for item in values if item)[:1000]


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
