"""Offline fixtures that prove the Pipeline without search or LLM communication."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from knowledge_contracts.v10 import KnowledgeRecord

from knowledge_workbench.authoring_models import AuthoringCategory, AuthoringSemanticSlot
from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    EvidenceCitation,
    EvidenceItem,
    EvidenceLanguage,
    EvidenceRankingResult,
    EvidenceSearchRequest,
    EvidenceSearchResult,
    EvidenceSubject,
    EvidenceType,
    PipelineClaim,
    PipelineClaimType,
    PipelineEvidenceLevel,
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

    def search(self, request: EvidenceSearchRequest) -> EvidenceSearchResult:
        subject = self.catalog.resolve(request.theme)
        reference_by_id = {item.source_id: item for item in subject.record.evidence}
        evidence: list[EvidenceItem] = []
        for source_id, claims in subject.evidence_claims.items():
            reference = reference_by_id[source_id]
            evidence_id = f"evd_{_digest(subject.key + ':' + source_id)[:16]}"
            formatted = " · ".join(
                item
                for item in (
                    reference.title,
                    reference.issuing_organization,
                    str(reference.publication_year) if reference.publication_year else None,
                )
                if item
            )
            evidence.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    title=reference.title,
                    url=reference.url,
                    publisher=reference.issuing_organization or "発行団体未登録",
                    source_priority_rank=reference.source_priority_rank,
                    evidence_level=PipelineEvidenceLevel.C,
                    publication_date=(
                        date(reference.publication_year, 1, 1)
                        if reference.publication_year
                        else None
                    ),
                    language=EvidenceLanguage.JA,
                    evidence_type=_evidence_type(reference.title, reference.issuing_organization),
                    snippet="\n".join(claim.assertion for claim in claims),
                    citation=EvidenceCitation(
                        formatted=formatted,
                        doi=reference.doi,
                        pmid=reference.pmid,
                        edition=reference.edition,
                        chapter=reference.chapter,
                        pages=reference.pages,
                    ),
                )
            )
        return EvidenceSearchResult(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            searched_at=datetime.now(UTC),
            query=request,
            subject=EvidenceSubject(
                canonical_name=subject.record.term.canonical_name,
                aliases=subject.record.term.aliases,
                category=AuthoringCategory(subject.record.classification.term_type),
            ),
            evidence=evidence,
            external_search_performed=False,
            warnings=[
                "外部検索は実行していません。既存のローカルKnowledge例をPipeline確認用に使用しています。",
                "Evidence Levelは医学監修前のため保守的にCとしています。",
            ],
        )


class FixtureClaimBuilder:
    builder_name = "local_fixture_claim_builder"
    builder_version = "1.0"

    def __init__(self, catalog: FixturePipelineCatalog) -> None:
        self.catalog = catalog

    def build(
        self,
        subject_key: str,
        evidence: EvidenceRankingResult,
    ) -> ClaimBuildResult:
        subject = self.catalog.resolve(subject_key)
        available_evidence = {item.evidence.evidence_id for item in evidence.ranked_evidence}
        source_to_evidence = {
            source_id: f"evd_{_digest(subject.key + ':' + source_id)[:16]}"
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


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).lower()
        if character.isalnum()
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
