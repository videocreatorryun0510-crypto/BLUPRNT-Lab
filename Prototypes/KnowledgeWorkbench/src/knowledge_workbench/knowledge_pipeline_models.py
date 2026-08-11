"""Provider-neutral contracts for the Phase 5.24 AI Knowledge Pipeline."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from knowledge_workbench.authoring_models import (
    AuthoringCategory,
    AuthoringReference,
    AuthoringSemanticSlot,
    KnowledgeAuthoringDraft,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineEvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class EvidenceType(StrEnum):
    GOVERNMENT = "government"
    GUIDELINE = "guideline"
    EXAM_STANDARD = "exam_standard"
    JOURNAL_ARTICLE = "journal_article"
    PRODUCT_LABEL = "product_label"
    TEXTBOOK = "textbook"
    OTHER = "other"


class EvidenceLanguage(StrEnum):
    JA = "ja"
    EN = "en"
    OTHER = "other"


class EvidenceCitation(StrictModel):
    formatted: ShortText
    doi: str | None = None
    pmid: str | None = None
    edition: str | None = None
    chapter: str | None = None
    pages: str | None = None


class EvidenceItem(StrictModel):
    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    title: ShortText
    url: HttpUrl | None
    publisher: ShortText
    source_priority_rank: int = Field(ge=1, le=6)
    evidence_level: PipelineEvidenceLevel
    publication_date: date | None
    language: EvidenceLanguage
    evidence_type: EvidenceType
    snippet: LongText
    citation: EvidenceCitation


class EvidenceSubject(StrictModel):
    canonical_name: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    category: AuthoringCategory


class EvidenceSearchRequest(StrictModel):
    theme: ShortText
    preferred_languages: list[EvidenceLanguage] = Field(
        default_factory=lambda: [EvidenceLanguage.JA], max_length=3
    )


class EvidenceSearchResult(StrictModel):
    search_contract_version: Literal["1.0"] = "1.0"
    provider_name: str
    provider_version: str
    searched_at: datetime
    query: EvidenceSearchRequest
    subject: EvidenceSubject
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=200)
    external_search_performed: bool
    warnings: list[str] = Field(default_factory=list)


class RankedEvidence(StrictModel):
    evidence: EvidenceItem
    rank: int = Field(ge=1)
    rank_score: int = Field(ge=0, le=100)
    ranking_reasons: list[str]


class EvidenceRankingResult(StrictModel):
    ranking_version: Literal["1.0"] = "1.0"
    ranked_evidence: list[RankedEvidence]


class PipelineClaimType(StrEnum):
    DEFINITION = "definition"
    OVERVIEW = "overview"
    FACT = "fact"
    CAUTION = "caution"


class PipelineClaim(StrictModel):
    claim_id: str = Field(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")
    assertion: LongText
    claim_type: PipelineClaimType
    semantic_slot: AuthoringSemanticSlot
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    confidence: float = Field(ge=0, le=1)


class ClaimBuildResult(StrictModel):
    claim_builder_version: Literal["1.0"] = "1.0"
    builder_name: str
    builder_version: str
    claims: list[PipelineClaim] = Field(default_factory=list, max_length=500)
    llm_called: bool
    warnings: list[str] = Field(default_factory=list)


class KnowledgePipelinePreview(StrictModel):
    pipeline_version: Literal["1.0"] = "1.0"
    pipeline_id: str = Field(pattern=r"^kpp_[a-z0-9][a-z0-9_-]{7,63}$")
    theme: ShortText
    created_at: datetime
    evidence_search: EvidenceSearchResult
    evidence_ranking: EvidenceRankingResult
    claim_build: ClaimBuildResult
    references: list[AuthoringReference]
    authoring_draft: KnowledgeAuthoringDraft
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoring_draft_saved: Literal[False] = False
    registry_mutated: Literal[False] = False
    external_ai_called: bool
    external_search_called: bool


class SavePipelineDraftResult(StrictModel):
    pipeline_id: str
    saved_at: datetime
    draft: KnowledgeAuthoringDraft
    fingerprint: str
    registry_mutated: Literal[False] = False
    promotion_performed: Literal[False] = False
