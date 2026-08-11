"""Evidence Intelligence orchestration for Gemini grounded citation candidates."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import HttpUrl, ValidationError

from knowledge_workbench.evidence_intelligence import (
    DefaultEvidenceDeduplicator,
    DefaultEvidenceRanker,
    EvidenceBundleBuilder,
    EvidenceIntelligenceError,
    stable_evidence_id,
)
from knowledge_workbench.gemini_grounded_search import (
    GeminiGroundedProviderResult,
    GeminiGroundedSearchError,
    GeminiGroundedSearchProvider,
)
from knowledge_workbench.grounded_evidence_models import (
    EvidenceDomainClass,
    GroundedEvidencePolicyDecision,
    GroundedEvidenceSearchAuditEntry,
    GroundedEvidenceSearchPreview,
    GroundedNormalizationResult,
    GroundedSearchErrorCode,
    GroundedSearchUsage,
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

JAPAN_OFFICIAL_PROFESSIONAL_DOMAINS = (
    "mhlw.go.jp",
    "pmda.go.jp",
    "info.pmda.go.jp",
    "jslm.org",
    "jamt.or.jp",
    "jstage.jst.go.jp",
)
INTERNATIONAL_OFFICIAL_DOMAINS = (
    "who.int",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
)
ACADEMIC_DOMAINS = (
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "doi.org",
    "nature.com",
    "springer.com",
    "sciencedirect.com",
    "wiley.com",
)
GUIDELINE_MARKERS = (
    "ガイドライン",
    "診療指針",
    "検査指針",
    "guideline",
    "recommendation",
)
CONTENT_NOT_ACQUIRED = (
    "Google Search GroundingのCitation Metadataのみ取得。Source本文は未取得。"
)


class GeminiGroundedEvidenceNormalizer:
    normalizer_name = "gemini_grounded_evidence_normalizer"
    normalizer_version = "1.0"

    def normalize(self, result: RawEvidenceSearchResult) -> EvidenceNormalizationResult:
        return self.normalize_with_policy(result).normalization

    def normalize_with_policy(
        self,
        result: RawEvidenceSearchResult,
    ) -> GroundedNormalizationResult:
        evidence: list[NormalizedEvidence] = []
        decisions: list[GroundedEvidencePolicyDecision] = []
        rejected: list[str] = []
        for record in result.records:
            try:
                payload = record.payload
                source_url = _required_text(payload.get("source_url"))
                title = _required_text(payload.get("title"))
                domain = _domain(source_url)
                publisher = _optional_text(payload.get("publisher")) or domain
                domain_class = classify_evidence_domain(domain)
                evidence_type = _evidence_type(domain, domain_class, title)
                evidence_level = _evidence_level(domain_class, title)
                priority = _information_priority(domain, domain_class)
                publication_date = _publication_date(payload.get("published_date"))
                doi = _doi(source_url, title)
                pmid = _pmid(source_url)
                snippet = _optional_text(payload.get("snippet")) or CONTENT_NOT_ACQUIRED
                evidence_id = stable_evidence_id(
                    doi=doi,
                    pmid=pmid,
                    url=source_url,
                    title=title,
                    publisher=publisher,
                    publication_date=(
                        publication_date.isoformat() if publication_date else None
                    ),
                )
                normalized = NormalizedEvidence(
                    evidence_id=evidence_id,
                    title=title,
                    publisher=publisher,
                    evidence_type=evidence_type,
                    evidence_level=evidence_level,
                    publication_date=publication_date,
                    url=HttpUrl(source_url),
                    doi=doi,
                    pmid=pmid,
                    language=_language(title),
                    abstract_or_snippet=snippet,
                    retrieved_at=record.retrieved_at,
                    provider=EvidenceProviderReference(
                        provider_name=record.provider_name,
                        provider_version=record.provider_version,
                        provider_record_id=record.provider_record_id,
                        retrieved_at=record.retrieved_at,
                    ),
                    information_priority_rank=priority,
                    citation=EvidenceCitation(formatted=f"{title} · {publisher}"),
                )
                evidence.append(normalized)
                decisions.append(
                    GroundedEvidencePolicyDecision(
                        evidence_id=evidence_id,
                        domain=domain,
                        domain_class=domain_class,
                        evidence_level=evidence_level.value,
                        information_priority_rank=priority,
                        classification_reasons=_classification_reasons(
                            domain,
                            domain_class,
                            evidence_level,
                        ),
                    )
                )
            except (TypeError, ValueError, ValidationError):
                rejected.append(record.provider_record_id)
        warnings = [*result.warnings]
        if rejected:
            warnings.append(f"Grounding Source {len(rejected)}件を標準化できませんでした。")
        normalization = EvidenceNormalizationResult(
            normalized_at=datetime.now(UTC),
            query=result.query,
            subject=result.subject,
            evidence=evidence,
            rejected_provider_record_ids=rejected,
            external_search_performed=True,
            search_duration_ms=result.duration_ms,
            warnings=warnings,
        )
        return GroundedNormalizationResult(
            normalization=normalization,
            policy_decisions=tuple(decisions),
        )


class JsonlGroundedEvidenceSearchAuditLog:
    """Metadata-only audit; response prose, Evidence body, and headers are excluded."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_success(
        self,
        provider_result: GeminiGroundedProviderResult,
        preview_bundle_id: str,
        *,
        accepted_count: int,
        excluded_count: int,
        deduplicated_count: int,
        evidence_level_counts: dict[str, int],
    ) -> GroundedEvidenceSearchAuditEntry:
        execution = provider_result.execution
        entry = GroundedEvidenceSearchAuditEntry(
            search_execution_id=execution.search_execution_id,
            bundle_id=preview_bundle_id,
            input_term=execution.query_plan.input_term,
            generated_queries=tuple(
                item.query for item in execution.query_plan.queries
            ),
            executed_queries=execution.executed_queries,
            model=execution.model,
            search_started_at=execution.search_started_at,
            completed_at=execution.completed_at,
            duration_ms=execution.duration_ms,
            raw_source_count=len(provider_result.raw.records),
            accepted_count=accepted_count,
            excluded_count=excluded_count,
            deduplicated_count=deduplicated_count,
            evidence_level_counts={
                "A": evidence_level_counts.get("A", 0),
                "B": evidence_level_counts.get("B", 0),
                "C": evidence_level_counts.get("C", 0),
            },
            usage=execution.usage,
            status="success",
        )
        self._append(entry)
        return entry

    def record_failure(
        self,
        error: GeminiGroundedSearchError,
    ) -> GroundedEvidenceSearchAuditEntry:
        usage = GroundedSearchUsage(
            request_count=error.attempt_count,
            attempt_count=error.attempt_count,
            search_grounding_used=False,
            estimated_cost_usd=None,
        )
        entry = GroundedEvidenceSearchAuditEntry(
            search_execution_id=error.search_execution_id,
            input_term=error.query_plan.input_term,
            generated_queries=tuple(item.query for item in error.query_plan.queries),
            executed_queries=error.executed_queries,
            model=error.model,
            search_started_at=error.started_at,
            completed_at=error.completed_at,
            duration_ms=max(
                0,
                int((error.completed_at - error.started_at).total_seconds() * 1000),
            ),
            raw_source_count=0,
            accepted_count=0,
            excluded_count=0,
            deduplicated_count=0,
            evidence_level_counts={"A": 0, "B": 0, "C": 0},
            usage=usage,
            status="failed",
            error_code=error.code,
        )
        self._append(entry)
        return entry

    def list(self, *, limit: int = 100) -> list[GroundedEvidenceSearchAuditEntry]:
        if not self.path.exists():
            return []
        try:
            events = [
                GroundedEvidenceSearchAuditEntry.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValidationError) as error:
            raise EvidenceIntelligenceError(
                "Gemini Grounded Search Auditを読み込めません。"
            ) from error
        return list(reversed(events[-limit:]))

    def _append(self, entry: GroundedEvidenceSearchAuditEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise EvidenceIntelligenceError(
                "Gemini Grounded Search Auditを保存できません。"
            ) from error


class GroundedEvidenceSearchService:
    def __init__(
        self,
        provider: GeminiGroundedSearchProvider,
        normalizer: GeminiGroundedEvidenceNormalizer,
        audit: JsonlGroundedEvidenceSearchAuditLog,
    ) -> None:
        self.provider = provider
        self.normalizer = normalizer
        self.audit = audit
        self.deduplicator = DefaultEvidenceDeduplicator()
        self.ranker = DefaultEvidenceRanker()
        self.bundle_builder = EvidenceBundleBuilder()

    def preview(self, term: str) -> GroundedEvidenceSearchPreview:
        request = EvidenceSearchRequest(theme=term)
        try:
            provider_result = self.provider.search_with_report(request)
        except GeminiGroundedSearchError as error:
            self.audit.record_failure(error)
            raise
        normalized = self.normalizer.normalize_with_policy(provider_result.raw)
        if not normalized.normalization.evidence:
            normalization_error = GeminiGroundedSearchError(
                GroundedSearchErrorCode.INVALID_RESPONSE,
                "標準化できるGrounding Sourceがありません。",
                search_execution_id=provider_result.execution.search_execution_id,
                model=provider_result.execution.model,
                query_plan=provider_result.execution.query_plan,
                started_at=provider_result.execution.search_started_at,
                completed_at=datetime.now(UTC),
                attempt_count=provider_result.execution.usage.attempt_count,
                executed_queries=provider_result.execution.executed_queries,
            )
            self.audit.record_failure(normalization_error)
            raise normalization_error
        deduplicated = self.deduplicator.deduplicate(normalized.normalization)
        ranked = self.ranker.rank(deduplicated)
        bundle = self.bundle_builder.build(
            normalized.normalization,
            deduplicated,
            ranked,
        )
        level_counts = Counter(
            item.evidence.evidence_level.value for item in bundle.evidence
        )
        audit = self.audit.record_success(
            provider_result,
            bundle.bundle_id,
            accepted_count=bundle.accepted_evidence_count,
            excluded_count=bundle.excluded_evidence_count,
            deduplicated_count=deduplicated.excluded_count,
            evidence_level_counts=dict(level_counts),
        )
        response_fingerprint = _fingerprint(
            {
                "execution_id": provider_result.execution.search_execution_id,
                "bundle_fingerprint": bundle.fingerprint,
                "policy": [
                    item.model_dump(mode="json")
                    for item in normalized.policy_decisions
                ],
            }
        )
        return GroundedEvidenceSearchPreview(
            search_execution_id=provider_result.execution.search_execution_id,
            input_term=provider_result.execution.query_plan.input_term,
            model=provider_result.execution.model,
            generated_queries=provider_result.execution.query_plan.queries,
            executed_queries=provider_result.execution.executed_queries,
            evidence_bundle=bundle,
            policy_decisions=normalized.policy_decisions,
            search_audit=audit,
            response_fingerprint=response_fingerprint,
        )


def classify_evidence_domain(domain: str) -> EvidenceDomainClass:
    normalized = domain.lower().rstrip(".")
    if _matches_domain(normalized, JAPAN_OFFICIAL_PROFESSIONAL_DOMAINS):
        return EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL
    # PubMed / PMC are scholarly indexes hosted under NCBI.  Check the
    # specific academic hosts before the broader official NCBI domain.
    if _matches_domain(normalized, ACADEMIC_DOMAINS):
        return EvidenceDomainClass.ACADEMIC
    if _matches_domain(normalized, INTERNATIONAL_OFFICIAL_DOMAINS):
        return EvidenceDomainClass.INTERNATIONAL_OFFICIAL
    return EvidenceDomainClass.OTHER


def _evidence_level(
    domain_class: EvidenceDomainClass,
    title: str,
) -> PipelineEvidenceLevel:
    guideline = any(marker in title.lower() for marker in GUIDELINE_MARKERS)
    if guideline and domain_class in {
        EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL,
        EvidenceDomainClass.INTERNATIONAL_OFFICIAL,
    }:
        return PipelineEvidenceLevel.A
    if domain_class is not EvidenceDomainClass.OTHER:
        return PipelineEvidenceLevel.B
    return PipelineEvidenceLevel.C


def _information_priority(
    domain: str,
    domain_class: EvidenceDomainClass,
) -> int:
    if _matches_domain(domain, ("mhlw.go.jp",)):
        return 1
    if _matches_domain(domain, ("jamt.or.jp",)):
        return 2
    if domain_class in {
        EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL,
        EvidenceDomainClass.INTERNATIONAL_OFFICIAL,
    }:
        return 3
    if domain_class is EvidenceDomainClass.ACADEMIC:
        return 6
    return 7


def _evidence_type(
    domain: str,
    domain_class: EvidenceDomainClass,
    title: str,
) -> EvidenceType:
    if any(marker in title.lower() for marker in GUIDELINE_MARKERS):
        return EvidenceType.GUIDELINE
    if _matches_domain(
        domain,
        ("mhlw.go.jp", "pmda.go.jp", "who.int", "cdc.gov", "nih.gov"),
    ):
        return EvidenceType.GOVERNMENT
    if domain_class in {
        EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL,
        EvidenceDomainClass.INTERNATIONAL_OFFICIAL,
        EvidenceDomainClass.ACADEMIC,
    }:
        return EvidenceType.JOURNAL_ARTICLE
    return EvidenceType.OTHER


def _classification_reasons(
    domain: str,
    domain_class: EvidenceDomainClass,
    level: PipelineEvidenceLevel,
) -> tuple[str, ...]:
    return (
        f"domain={domain}",
        f"domain_class={domain_class.value}",
        f"evidence_level={level.value}: domain metadata policy; Gemini評価不使用",
    )


def _matches_domain(domain: str, candidates: tuple[str, ...]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in candidates)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("required text is missing")
    return value.strip()


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _domain(url: str) -> str:
    parsed = urlsplit(url)
    return (parsed.hostname or "unknown").lower()


def _publication_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return date.fromisoformat(value.strip())


def _doi(url: str, title: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.hostname and parsed.hostname.lower().endswith("doi.org"):
        value = parsed.path.strip("/")
        return value or None
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", title)
    return match.group(0) if match else None


def _pmid(url: str) -> str | None:
    parsed = urlsplit(url)
    if not parsed.hostname or "ncbi.nlm.nih.gov" not in parsed.hostname.lower():
        return None
    match = re.search(r"/(?:pubmed/)?(\d{7,9})/?$", parsed.path)
    return match.group(1) if match else None


def _language(value: str) -> EvidenceLanguage:
    return (
        EvidenceLanguage.JA
        if any("\u3040" <= character <= "\u30ff" for character in value)
        else EvidenceLanguage.EN
    )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
