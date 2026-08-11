"""Provider-neutral contracts for Knowledge and Evidence Intelligence Pipelines."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    StringConstraints,
    model_validator,
)

from knowledge_workbench.authoring_models import (
    AuthoringCategory,
    AuthoringReference,
    AuthoringSemanticSlot,
    KnowledgeAuthoringDraft,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
MediumText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)
]
DeduplicationReason = Literal["doi", "pmid", "url", "title_similarity"]


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
    formatted: MediumText
    edition: str | None = None
    chapter: str | None = None
    pages: str | None = None


class EvidenceSubject(StrictModel):
    canonical_name: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    category: AuthoringCategory


class EvidenceSearchRequest(StrictModel):
    theme: ShortText
    preferred_languages: list[EvidenceLanguage] = Field(
        default_factory=lambda: [EvidenceLanguage.JA], max_length=3
    )


class RawEvidenceRecord(StrictModel):
    """Provider-owned response retained only inside the Intelligence Layer."""

    provider_name: ShortText
    provider_version: ShortText
    provider_record_id: ShortText
    retrieved_at: datetime
    payload: dict[str, JsonValue]


class RawEvidenceSearchResult(StrictModel):
    raw_contract_version: Literal["1.0"] = "1.0"
    search_provider_name: ShortText
    search_provider_version: ShortText
    searched_at: datetime
    duration_ms: int = Field(ge=0)
    query: EvidenceSearchRequest
    subject: EvidenceSubject
    records: list[RawEvidenceRecord] = Field(default_factory=list, max_length=1000)
    external_search_performed: bool
    warnings: list[str] = Field(default_factory=list)


class EvidenceProviderReference(StrictModel):
    provider_name: ShortText
    provider_version: ShortText
    provider_record_id: ShortText
    retrieved_at: datetime


class NormalizedEvidence(StrictModel):
    """Provider-independent Evidence Contract Version 1.0."""

    evidence_contract_version: Literal["1.0"] = "1.0"
    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    title: ShortText
    publisher: ShortText
    evidence_type: EvidenceType
    evidence_level: PipelineEvidenceLevel
    publication_date: date | None
    url: HttpUrl | None
    doi: str | None = None
    pmid: str | None = None
    language: EvidenceLanguage
    abstract_or_snippet: LongText
    retrieved_at: datetime
    provider: EvidenceProviderReference
    information_priority_rank: int = Field(ge=1, le=99)
    citation: EvidenceCitation


class EvidenceNormalizationResult(StrictModel):
    normalization_version: Literal["1.0"] = "1.0"
    normalized_at: datetime
    query: EvidenceSearchRequest
    subject: EvidenceSubject
    evidence: list[NormalizedEvidence] = Field(default_factory=list, max_length=1000)
    rejected_provider_record_ids: list[str] = Field(default_factory=list)
    external_search_performed: bool
    search_duration_ms: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class BundledEvidence(StrictModel):
    """One unique Evidence item with every provider provenance retained."""

    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    title: ShortText
    publisher: ShortText
    evidence_type: EvidenceType
    evidence_level: PipelineEvidenceLevel
    publication_date: date | None
    url: HttpUrl | None
    doi: str | None = None
    pmid: str | None = None
    language: EvidenceLanguage
    abstract_or_snippet: LongText
    retrieved_at: datetime
    providers: list[EvidenceProviderReference] = Field(min_length=1, max_length=50)
    information_priority_rank: int = Field(ge=1, le=99)
    citation: EvidenceCitation


class EvidenceDeduplicationDecision(StrictModel):
    retained_evidence_id: str
    merged_provider_record_ids: list[str] = Field(min_length=1)
    reasons: list[DeduplicationReason] = Field(min_length=1)


class EvidenceDeduplicationResult(StrictModel):
    deduplicator_version: Literal["1.0"] = "1.0"
    evidence: list[BundledEvidence]
    input_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    excluded_provider_record_ids: list[str]
    decisions: list[EvidenceDeduplicationDecision]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.unique_count != len(self.evidence):
            raise ValueError("unique_count must match evidence length")
        if self.input_count != self.unique_count + self.excluded_count:
            raise ValueError("input_count must equal unique_count plus excluded_count")
        return self


class RankedEvidence(StrictModel):
    evidence: BundledEvidence
    rank: int = Field(ge=1)
    evidence_level_order: int = Field(ge=1, le=3)
    information_priority_rank: int = Field(ge=1, le=99)
    ranking_reasons: list[str]


class EvidenceRankingResult(StrictModel):
    ranking_version: Literal["1.0"] = "1.0"
    ranked_evidence: list[RankedEvidence]

    @model_validator(mode="after")
    def validate_ranks(self) -> Self:
        expected = list(range(1, len(self.ranked_evidence) + 1))
        if [item.rank for item in self.ranked_evidence] != expected:
            raise ValueError("Evidence ranks must be contiguous from 1")
        return self


class EvidenceBundle(StrictModel):
    """The only Evidence object exposed to Workbench and Claim Builders."""

    evidence_bundle_version: Literal["1.0"] = "1.0"
    bundle_id: str = Field(pattern=r"^evb_[a-z0-9][a-z0-9_-]{7,63}$")
    query: EvidenceSearchRequest
    subject: EvidenceSubject
    created_at: datetime
    providers: list[str]
    evidence: list[RankedEvidence]
    input_record_count: int = Field(ge=0)
    normalized_evidence_count: int = Field(ge=0)
    accepted_evidence_count: int = Field(ge=0)
    excluded_evidence_count: int = Field(ge=0)
    excluded_provider_record_ids: list[str]
    deduplication_decisions: list[EvidenceDeduplicationDecision]
    external_search_performed: bool
    search_duration_ms: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        if self.accepted_evidence_count != len(self.evidence):
            raise ValueError("accepted_evidence_count must match evidence length")
        if self.input_record_count < self.normalized_evidence_count:
            raise ValueError("input_record_count cannot be below normalized count")
        if self.input_record_count != (
            self.accepted_evidence_count + self.excluded_evidence_count
        ):
            raise ValueError("input count must equal accepted plus excluded")
        if len(self.providers) != len(set(self.providers)):
            raise ValueError("providers must be unique")
        evidence_ids = [item.evidence.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence Bundle IDs must be unique")
        return self


class SearchAuditProviderCount(StrictModel):
    provider: ShortText
    retrieved_count: int = Field(ge=0)


class EvidenceSearchAuditEntry(StrictModel):
    audit_version: Literal["1.0"] = "1.0"
    event_id: str = Field(pattern=r"^esa_[a-z0-9][a-z0-9_-]{7,63}$")
    bundle_id: str
    search_query: ShortText
    providers: list[SearchAuditProviderCount]
    retrieved_count: int = Field(ge=0)
    accepted_evidence_ids: list[str]
    excluded_provider_record_ids: list[str]
    searched_at: datetime
    duration_ms: int = Field(ge=0)
    status: Literal["success", "failed"]


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
    pipeline_version: Literal["1.1"] = "1.1"
    pipeline_id: str = Field(pattern=r"^kpp_[a-z0-9][a-z0-9_-]{7,63}$")
    theme: ShortText
    created_at: datetime
    evidence_bundle: EvidenceBundle
    claim_build: ClaimBuildResult
    references: list[AuthoringReference]
    authoring_draft: KnowledgeAuthoringDraft
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    search_audit_recorded: bool
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
