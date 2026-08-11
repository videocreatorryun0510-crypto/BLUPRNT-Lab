"""Offline fixtures that prove the Pipeline without search or LLM communication."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

from knowledge_contracts.v10 import KnowledgeRecord
from pydantic import HttpUrl, ValidationError

from knowledge_workbench.authoring_models import AuthoringCategory, AuthoringSemanticSlot
from knowledge_workbench.evidence_intelligence import stable_evidence_id
from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    EvidenceBundle,
    EvidenceCitation,
    EvidenceLanguage,
    EvidenceNormalizationResult,
    EvidenceProviderReference,
    EvidenceSearchRequest,
    EvidenceSubject,
    EvidenceType,
    NormalizedEvidence,
    PipelineClaim,
    PipelineClaimType,
    PipelineEvidenceLevel,
    RawEvidenceRecord,
    RawEvidenceSearchResult,
)


class FixturePipelineThemeError(ValueError):
    """Raised when the offline provider does not have a reviewed local fixture."""


@dataclass(frozen=True)
class _FixtureClaim:
    assertion: str
    claim_type: PipelineClaimType
    semantic_slot: AuthoringSemanticSlot
    source_claim_id: str


@dataclass(frozen=True)
class _FixtureSubject:
    key: str
    record: KnowledgeRecord
    claims: tuple[_FixtureClaim, ...]
    evidence_claims: dict[str, tuple[_FixtureClaim, ...]]


class FixturePipelineCatalog:
    """Reads existing local Knowledge examples; it never searches or invents facts."""

    def __init__(self, repository_root: Path) -> None:
        examples = repository_root / "Docs" / "examples" / "knowledge-json-v1.0"
        self._subjects = {
            "ferritin": self._load("ferritin", examples / "laboratory-test-item.example.json"),
            "iron_deficiency_anemia": self._load(
                "iron_deficiency_anemia", examples / "disease.example.json"
            ),
            "gram_stain": self._load("gram_stain", examples / "staining-method.example.json"),
        }
        self._lookup: dict[str, str] = {}
        for key, subject in self._subjects.items():
            names = [subject.record.term.canonical_name, *subject.record.term.aliases]
            for name in names:
                self._lookup[_normalized(name)] = key

    def resolve(self, theme: str) -> _FixtureSubject:
        key = self._lookup.get(_normalized(theme))
        if key is None:
            supported = "、".join(self.supported_themes())
            raise FixturePipelineThemeError(
                f"Sandboxでは「{supported}」を確認できます。任意用語は実Provider接続後に対応します。"
            )
        return self._subjects[key]

    def supported_themes(self) -> list[str]:
        return [subject.record.term.canonical_name for subject in self._subjects.values()]

    @staticmethod
    def _load(key: str, path: Path) -> _FixtureSubject:
        record = KnowledgeRecord.model_validate_json(path.read_text(encoding="utf-8"))
        raw = record.model_dump(mode="json")
        definitions = raw["core_facts"]["definitions"]
        selected: list[_FixtureClaim] = []
        if definitions:
            selected.append(
                _FixtureClaim(
                    assertion=definitions[0]["assertion"],
                    claim_type=PipelineClaimType.DEFINITION,
                    semantic_slot=AuthoringSemanticSlot.DEFINITION,
                    source_claim_id=definitions[0]["claim_id"],
                )
            )
        category = record.classification.term_type
        if category in {"laboratory_test_item", "disease"}:
            overview = raw["category_content"][category]["overview"]
            if overview:
                selected.append(
                    _FixtureClaim(
                        assertion=overview[0]["assertion"],
                        claim_type=PipelineClaimType.OVERVIEW,
                        semantic_slot=AuthoringSemanticSlot.OVERVIEW,
                        source_claim_id=overview[0]["claim_id"],
                    )
                )
        evidence_claims: dict[str, tuple[_FixtureClaim, ...]] = {}
        for reference in record.evidence:
            supported = tuple(
                claim
                for claim in selected
                if claim.source_claim_id in reference.supported_claim_ids
            )
            if supported:
                evidence_claims[reference.source_id] = supported
        return _FixtureSubject(
            key=key,
            record=record,
            claims=tuple(selected),
            evidence_claims=evidence_claims,
        )


class FixtureEvidenceSearchProvider:
    provider_name = "local_fixture_evidence"
    provider_version = "1.0"

    def __init__(self, catalog: FixturePipelineCatalog) -> None:
        self.catalog = catalog

    def search(self, request: EvidenceSearchRequest) -> RawEvidenceSearchResult:
        started_at = perf_counter()
        searched_at = datetime.now(UTC)
        subject = self.catalog.resolve(request.theme)
        reference_by_id = {item.source_id: item for item in subject.record.evidence}
        records: list[RawEvidenceRecord] = []
        for source_id, claims in subject.evidence_claims.items():
            reference = reference_by_id[source_id]
            formatted = " · ".join(
                item
                for item in (
                    reference.title,
                    reference.issuing_organization,
                    str(reference.publication_year) if reference.publication_year else None,
                )
                if item
            )
            records.append(
                RawEvidenceRecord(
                    provider_name=self.provider_name,
                    provider_version=self.provider_version,
                    provider_record_id=f"fixture:{source_id}",
                    retrieved_at=searched_at,
                    payload={
                        "title": reference.title,
                        "url": str(reference.url) if reference.url else None,
                        "publisher": (
                            reference.issuing_organization or "発行団体未登録"
                        ),
                        "information_priority_rank": reference.source_priority_rank,
                        "evidence_level": PipelineEvidenceLevel.C.value,
                        "publication_date": (
                            date(reference.publication_year, 1, 1).isoformat()
                            if reference.publication_year
                            else None
                        ),
                        "language": EvidenceLanguage.JA.value,
                        "evidence_type": _evidence_type(
                            reference.title,
                            reference.issuing_organization,
                        ).value,
                        "abstract_or_snippet": "\n".join(
                            claim.assertion for claim in claims
                        ),
                        "doi": reference.doi,
                        "pmid": reference.pmid,
                        "citation": {
                            "formatted": formatted,
                            "edition": reference.edition,
                            "chapter": reference.chapter,
                            "pages": reference.pages,
                        },
                    },
                )
            )
        return RawEvidenceSearchResult(
            search_provider_name=self.provider_name,
            search_provider_version=self.provider_version,
            searched_at=searched_at,
            duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
            query=request,
            subject=EvidenceSubject(
                canonical_name=subject.record.term.canonical_name,
                aliases=subject.record.term.aliases,
                category=AuthoringCategory(subject.record.classification.term_type),
            ),
            records=records,
            external_search_performed=False,
            warnings=[
                "外部検索は実行していません。既存のローカルKnowledge例をPipeline確認用に使用しています。",
                "Evidence Levelは医学監修前のため保守的にCとしています。",
            ],
        )


class FixtureEvidenceNormalizer:
    """Provider-specific mapping kept behind the common Normalizer interface."""

    normalizer_name = "local_fixture_normalizer"
    normalizer_version = "1.0"

    def normalize(
        self,
        result: RawEvidenceSearchResult,
    ) -> EvidenceNormalizationResult:
        evidence: list[NormalizedEvidence] = []
        rejected: list[str] = []
        for record in result.records:
            try:
                payload = record.payload
                publication_date = (
                    date.fromisoformat(str(payload["publication_date"]))
                    if payload.get("publication_date")
                    else None
                )
                title = str(payload["title"])
                publisher = str(payload["publisher"])
                doi = str(payload["doi"]) if payload.get("doi") else None
                pmid = str(payload["pmid"]) if payload.get("pmid") else None
                url = str(payload["url"]) if payload.get("url") else None
                evidence.append(
                    NormalizedEvidence(
                        evidence_id=stable_evidence_id(
                            doi=doi,
                            pmid=pmid,
                            url=url,
                            title=title,
                            publisher=publisher,
                            publication_date=(
                                publication_date.isoformat()
                                if publication_date
                                else None
                            ),
                        ),
                        title=title,
                        publisher=publisher,
                        evidence_type=EvidenceType(str(payload["evidence_type"])),
                        evidence_level=PipelineEvidenceLevel(
                            str(payload["evidence_level"])
                        ),
                        publication_date=publication_date,
                        url=HttpUrl(url) if url else None,
                        doi=doi,
                        pmid=pmid,
                        language=EvidenceLanguage(str(payload["language"])),
                        abstract_or_snippet=str(payload["abstract_or_snippet"]),
                        retrieved_at=record.retrieved_at,
                        provider=EvidenceProviderReference(
                            provider_name=record.provider_name,
                            provider_version=record.provider_version,
                            provider_record_id=record.provider_record_id,
                            retrieved_at=record.retrieved_at,
                        ),
                        information_priority_rank=int(
                            str(payload["information_priority_rank"])
                        ),
                        citation=EvidenceCitation.model_validate(payload["citation"]),
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError):
                rejected.append(record.provider_record_id)
        warnings = list(result.warnings)
        if rejected:
            warnings.append(f"Normalizerで{len(rejected)}件を除外しました。")
        return EvidenceNormalizationResult(
            normalized_at=datetime.now(UTC),
            query=result.query,
            subject=result.subject,
            evidence=evidence,
            rejected_provider_record_ids=rejected,
            external_search_performed=result.external_search_performed,
            search_duration_ms=result.duration_ms,
            warnings=warnings,
        )


class FixtureClaimBuilder:
    builder_name = "local_fixture_claim_builder"
    builder_version = "1.0"

    def __init__(self, catalog: FixturePipelineCatalog) -> None:
        self.catalog = catalog

    def build(
        self,
        subject_key: str,
        evidence: EvidenceBundle,
    ) -> ClaimBuildResult:
        subject = self.catalog.resolve(subject_key)
        available_evidence = {item.evidence.evidence_id for item in evidence.evidence}
        source_to_evidence = {
            source_id: _reference_evidence_id(subject, source_id)
            for source_id in subject.evidence_claims
        }
        claims: list[PipelineClaim] = []
        for source_claim in subject.claims:
            stable_claim_source = f"{subject.key}:{source_claim.source_claim_id}"
            evidence_ids = sorted(
                evidence_id
                for source_id, evidence_id in source_to_evidence.items()
                if source_claim in subject.evidence_claims[source_id]
                and evidence_id in available_evidence
            )
            if not evidence_ids:
                continue
            claims.append(
                PipelineClaim(
                    claim_id=f"clm_pipe_{_digest(stable_claim_source)[:16]}",
                    assertion=source_claim.assertion,
                    claim_type=source_claim.claim_type,
                    semantic_slot=source_claim.semantic_slot,
                    evidence_ids=evidence_ids,
                    confidence=1.0,
                )
            )
        return ClaimBuildResult(
            builder_name=self.builder_name,
            builder_version=self.builder_version,
            claims=claims,
            llm_called=False,
            warnings=["LLMは呼び出していません。既存FixtureのClaim本文を変更せず使用しています。"],
        )


def _evidence_type(title: str, publisher: str | None) -> EvidenceType:
    combined = f"{title} {publisher or ''}".lower()
    if "pmda" in combined or "電子添文" in combined:
        return EvidenceType.PRODUCT_LABEL
    if "ガイドライン" in combined:
        return EvidenceType.GUIDELINE
    if "厚生労働" in combined:
        return EvidenceType.GOVERNMENT
    if "jstage" in combined or "性能評価" in combined:
        return EvidenceType.JOURNAL_ARTICLE
    return EvidenceType.OTHER


def _reference_evidence_id(subject: _FixtureSubject, source_id: str) -> str:
    reference = next(
        item for item in subject.record.evidence if item.source_id == source_id
    )
    return stable_evidence_id(
        doi=reference.doi,
        pmid=reference.pmid,
        url=str(reference.url) if reference.url else None,
        title=reference.title,
        publisher=reference.issuing_organization or "発行団体未登録",
        publication_date=(
            date(reference.publication_year, 1, 1).isoformat()
            if reference.publication_year
            else None
        ),
    )


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).lower()
        if character.isalnum()
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
