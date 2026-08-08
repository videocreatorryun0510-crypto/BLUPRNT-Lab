"""Workbench-owned contracts for fast, pre-Registry Knowledge authoring."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from knowledge_contracts.v10 import KnowledgeRecord
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

DraftId = Annotated[str, StringConstraints(pattern=r"^kad_[a-z0-9][a-z0-9_-]{7,63}$")]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")]
SourceId = Annotated[str, StringConstraints(pattern=r"^src_[a-z0-9][a-z0-9_-]{7,63}$")]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
OptionalShortText = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthoringCategory(StrEnum):
    TEST_ITEM = "test_item"
    STAINING_METHOD = "staining_method"
    SPECIMEN = "specimen"
    REAGENT = "reagent"
    BIOLOGICAL_STRUCTURE = "biological_structure"
    DISEASE = "disease"
    LABORATORY_TEST_ITEM = "laboratory_test_item"


class DifficultyLevel(StrEnum):
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class AuthoringExamImportance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class ReferenceRole(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"


class AuthoringMetadata(StrictModel):
    category: AuthoringCategory
    title: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    difficulty: DifficultyLevel
    exam_importance: AuthoringExamImportance


class AuthoringClaim(StrictModel):
    claim_id: ClaimId
    assertion: MediumText
    position: int = Field(ge=1, le=500)
    semantic_slot: Literal["unassigned"] = "unassigned"


class AuthoringReference(StrictModel):
    source_id: SourceId
    evidence_level: EvidenceLevel
    evidence_role: ReferenceRole
    title: ShortText
    issuing_organization: OptionalShortText = None
    edition: OptionalShortText = None
    publication_year: int | None = Field(default=None, ge=1800, le=2200)
    url: HttpUrl | None = None
    doi: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/\S+$"),
    ] = None
    pmid: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{1,12}$"),
    ] = None
    accessed_at: date | None = None
    chapter: OptionalShortText = None
    pages: OptionalShortText = None
    supported_claim_ids: list[ClaimId] = Field(default_factory=list, max_length=200)


class AuthoringReviewInfo(StrictModel):
    state: Literal["draft"] = "draft"
    review_version: None = None
    medical_review_performed: Literal[False] = False


class KnowledgeAuthoringDraft(StrictModel):
    authoring_version: Literal["1.0"] = "1.0"
    target_knowledge_contract_version: Literal["1.0"] = "1.0"
    draft_id: DraftId
    created_at: datetime
    updated_at: datetime
    metadata: AuthoringMetadata
    knowledge: KnowledgeRecord
    claims: list[AuthoringClaim] = Field(default_factory=list, max_length=500)
    references: list[AuthoringReference] = Field(default_factory=list, max_length=500)
    relations: list[dict[str, Any]] = Field(default_factory=list, max_length=0)
    review: AuthoringReviewInfo = Field(default_factory=AuthoringReviewInfo)

    @model_validator(mode="after")
    def validate_draft_references(self) -> Self:
        if self.knowledge.classification.term_type != self.metadata.category.value:
            raise ValueError("metadata.category must match Knowledge classification")
        if self.knowledge.term.canonical_name != self.metadata.title:
            raise ValueError("metadata.title must match Knowledge canonical_name")
        if self.knowledge.term.aliases != self.metadata.aliases:
            raise ValueError("metadata.aliases must match Knowledge aliases")
        if _knowledge_claim_ids(self.knowledge.model_dump(mode="json")):
            raise ValueError("Skeleton Knowledge must keep Claims in the authoring list")
        if self.knowledge.evidence:
            raise ValueError("Skeleton Knowledge must keep References in the authoring list")

        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique in an authoring draft")
        positions = [claim.position for claim in self.claims]
        if positions != list(range(1, len(self.claims) + 1)):
            raise ValueError("Claim positions must be contiguous and ordered from 1")

        source_ids = [reference.source_id for reference in self.references]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique in an authoring draft")
        known_claim_ids = set(claim_ids)
        for reference in self.references:
            if len(reference.supported_claim_ids) != len(set(reference.supported_claim_ids)):
                raise ValueError(f"Reference {reference.source_id} contains duplicate Claim IDs")
            unknown = sorted(set(reference.supported_claim_ids) - known_claim_ids)
            if unknown:
                raise ValueError(
                    f"Reference {reference.source_id} contains unknown Claim IDs: "
                    + ", ".join(unknown)
                )
        return self


class CreateAuthoringDraftRequest(StrictModel):
    category: AuthoringCategory
    title: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    difficulty: DifficultyLevel
    exam_importance: AuthoringExamImportance


class AddAuthoringClaimRequest(StrictModel):
    assertion: MediumText


class UpdateAuthoringClaimRequest(AddAuthoringClaimRequest):
    pass


class ReorderAuthoringClaimsRequest(StrictModel):
    claim_ids: list[ClaimId] = Field(min_length=1, max_length=500)


class AddAuthoringReferenceRequest(StrictModel):
    evidence_level: EvidenceLevel
    evidence_role: ReferenceRole = ReferenceRole.SUPPORTING
    title: ShortText
    issuing_organization: OptionalShortText = None
    edition: OptionalShortText = None
    publication_year: int | None = Field(default=None, ge=1800, le=2200)
    url: HttpUrl | None = None
    doi: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/\S+$"),
    ] = None
    pmid: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{1,12}$"),
    ] = None
    accessed_at: date | None = None
    chapter: OptionalShortText = None
    pages: OptionalShortText = None
    supported_claim_ids: list[ClaimId] = Field(default_factory=list, max_length=200)


class UpdateAuthoringReferenceRequest(AddAuthoringReferenceRequest):
    pass


class ImportAuthoringDraftRequest(StrictModel):
    draft: dict[str, Any]


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AuthoringValidationIssue(StrictModel):
    code: str
    severity: ValidationSeverity
    path: str
    message: str


class AuthoringValidationReport(StrictModel):
    schema_valid: bool
    knowledge_schema_valid: bool
    required_fields_valid: bool
    reference_integrity_valid: bool
    claim_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    relation_count: int = Field(ge=0)
    completeness_score: int = Field(ge=0, le=100)
    save_allowed: bool
    issues: list[AuthoringValidationIssue]


class AuthoringDraftSummary(StrictModel):
    draft_id: DraftId
    knowledge_id: str
    title: str
    category: AuthoringCategory
    difficulty: DifficultyLevel
    exam_importance: AuthoringExamImportance
    claim_count: int
    reference_count: int
    review_state: Literal["draft"]
    updated_at: datetime


def _knowledge_claim_ids(value: Any) -> list[str]:
    found: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "claim_id" and isinstance(child, str):
                    found.append(child)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return found
