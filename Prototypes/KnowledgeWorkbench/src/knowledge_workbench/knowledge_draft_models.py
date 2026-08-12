"""Provider-neutral contracts for the pre-Promotion Knowledge Draft boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from knowledge_workbench.authoring_models import (
    AuthoringCategory,
    AuthoringExamImportance,
    AuthoringSemanticSlot,
    DifficultyLevel,
    EvidenceLevel,
    ReferenceRole,
)

KnowledgeDraftId = Annotated[
    str, StringConstraints(pattern=r"^kdr_[a-z0-9][a-z0-9_-]{7,63}$")
]
TemporaryKnowledgeId = Annotated[
    str, StringConstraints(pattern=r"^tmp_knw_[a-z0-9][a-z0-9_-]{7,63}$")
]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")]
SourceId = Annotated[str, StringConstraints(pattern=r"^src_[a-z0-9][a-z0-9_-]{7,63}$")]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
]
MediumText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)
]
OptionalShortText = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    | None
)
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class FrozenContract(BaseModel):
    """Forbid implicit fields and make assembled output immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeDraftClaim(FrozenContract):
    """Lossless copy of one human-reviewed Authoring Claim."""

    claim_id: ClaimId
    assertion: MediumText
    position: int = Field(ge=1, le=500)
    semantic_slot: AuthoringSemanticSlot
    reference_ids: tuple[SourceId, ...] = Field(default_factory=tuple, max_length=500)


class KnowledgeDraftReference(FrozenContract):
    """Lossless bibliographic data selected by the human author."""

    source_id: SourceId
    evidence_level: EvidenceLevel
    evidence_role: ReferenceRole
    source_priority_rank: int | None = Field(default=None, ge=1, le=6)
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
    supported_claim_ids: tuple[ClaimId, ...] = Field(default_factory=tuple, max_length=200)


class KnowledgeDraftSection(FrozenContract):
    """Category structure expressed only as ordered Claim references."""

    section_key: AuthoringSemanticSlot
    claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=500)


class KnowledgeDraftMetadata(FrozenContract):
    source_authoring_draft_id: str
    source_authoring_fingerprint: Fingerprint
    difficulty: DifficultyLevel
    exam_importance: AuthoringExamImportance
    assembler_id: Literal["deterministic_knowledge_assembler"] = (
        "deterministic_knowledge_assembler"
    )
    assembler_version: Literal["1.0.0"] = "1.0.0"
    assembled_at: datetime


class KnowledgeDraftReview(FrozenContract):
    approval_state: Literal["draft"] = "draft"
    medical_review_performed: Literal[False] = False
    promotion_performed: Literal[False] = False
    registry_mutated: Literal[False] = False


class KnowledgeDraftCompleteness(FrozenContract):
    """Mechanical assembly completeness; it is not a medical quality score."""

    score: int = Field(ge=0, le=100)
    missing_items: tuple[str, ...] = Field(default_factory=tuple)
    claim_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    linked_claim_count: int = Field(ge=0)
    unassigned_claim_count: int = Field(ge=0)


class KnowledgeDraft(FrozenContract):
    """The reviewable output between Authoring and Promotion."""

    knowledge_draft_version: Literal["1.0"] = "1.0"
    knowledge_draft_id: KnowledgeDraftId
    temporary_knowledge_id: TemporaryKnowledgeId
    category: AuthoringCategory
    title: ShortText
    summary: MediumText
    summary_source_claim_id: ClaimId | None
    claims: tuple[KnowledgeDraftClaim, ...] = Field(default_factory=tuple, max_length=500)
    references: tuple[KnowledgeDraftReference, ...] = Field(
        default_factory=tuple, max_length=500
    )
    category_structure: tuple[KnowledgeDraftSection, ...] = Field(
        default_factory=tuple, max_length=50
    )
    metadata: KnowledgeDraftMetadata
    review: KnowledgeDraftReview = Field(default_factory=KnowledgeDraftReview)
    completeness: KnowledgeDraftCompleteness
    fingerprint: Fingerprint


class KnowledgeDraftValidationIssue(FrozenContract):
    code: str
    path: str
    message: str


class KnowledgeDraftValidationReport(FrozenContract):
    schema_valid: bool
    claim_order_valid: bool
    unique_claim_ids_valid: bool
    reference_integrity_valid: bool
    category_valid: bool
    fingerprint_valid: bool
    metadata_valid: bool
    lossless_claims_valid: bool
    references_unchanged: bool
    summary_traceable: bool
    save_allowed: bool
    issues: tuple[KnowledgeDraftValidationIssue, ...] = Field(default_factory=tuple)


class AssembleKnowledgeDraftRequest(FrozenContract):
    authoring_draft_id: str


class KnowledgeDraftSummary(FrozenContract):
    knowledge_draft_id: KnowledgeDraftId
    temporary_knowledge_id: TemporaryKnowledgeId
    source_authoring_draft_id: str
    title: str
    category: AuthoringCategory
    completeness_score: int
    fingerprint: Fingerprint
    assembled_at: datetime


def knowledge_draft_fingerprint(value: KnowledgeDraft | dict[str, Any]) -> str:
    """Return the canonical SHA-256 fingerprint excluding the fingerprint field."""

    payload = value.model_dump(mode="json") if isinstance(value, KnowledgeDraft) else dict(value)
    payload.pop("fingerprint", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

