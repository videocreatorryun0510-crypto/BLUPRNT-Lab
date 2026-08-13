"""Provider-neutral contracts for human medical review records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=180),
]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
RequiredComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class StrictReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REVISION_REQUIRED = "revision_required"
    REJECTED = "rejected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ClaimReviewDecision(StrEnum):
    APPROVED = "approved"
    REVISION_REQUIRED = "revision_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class EvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class EvidenceSupport(StrEnum):
    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONFLICTS = "conflicts"
    DOES_NOT_SUPPORT = "does_not_support"


class ChecklistResultValue(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    NOT_REVIEWED = "not_reviewed"


class ChecklistSeverity(StrEnum):
    BLOCKER = "blocker"
    REQUIRED = "required"
    ADVISORY = "advisory"


class ReviewValidity(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"


class ReviewerRole(StrEnum):
    MEDICAL_REVIEWER = "medical_reviewer"
    FINAL_APPROVER = "final_approver"


class ReviewerProfile(StrictReviewModel):
    reviewer_id: Identifier
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    roles: list[ReviewerRole] = Field(min_length=1)
    specialty_categories: list[str] = Field(min_length=1)
    identity_provider: Identifier
    identity_assurance: Literal["mvp_fixture", "verified_identity_provider"]
    active: bool = True


class ChecklistDefinition(StrictReviewModel):
    item_id: Identifier
    severity: ChecklistSeverity
    label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    category: str | None = None


class ChecklistItemReviewInput(StrictReviewModel):
    item_id: Identifier
    result: ChecklistResultValue
    reason: Comment = ""

    @model_validator(mode="after")
    def require_not_applicable_reason(self) -> ChecklistItemReviewInput:
        if self.result == ChecklistResultValue.NOT_APPLICABLE and not self.reason:
            raise ValueError("not_applicableには理由が必要です")
        return self


class ChecklistItemReview(StrictReviewModel):
    item_id: Identifier
    severity: ChecklistSeverity
    result: ChecklistResultValue
    reason: Comment = ""
    reviewed_by: Identifier
    reviewed_at: datetime


class EvidenceAssessmentInput(StrictReviewModel):
    evidence_id: Identifier
    exists_confirmed: bool
    current_confirmed: bool
    directly_supports: bool
    evidence_level: EvidenceLevel
    support: EvidenceSupport
    locator: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    comment: Comment = ""


class EvidenceAssessment(StrictReviewModel):
    assessment_id: Identifier
    evidence_id: Identifier
    evidence_fingerprint: Identifier
    exists_confirmed: bool
    current_confirmed: bool
    directly_supports: bool
    evidence_level: EvidenceLevel
    evidence_source: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    support: EvidenceSupport
    locator: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    pmid: str | None = None
    doi: str | None = None
    reviewed_by: Identifier
    reviewed_at: datetime
    comment: Comment = ""


class ClaimReviewInput(StrictReviewModel):
    claim_id: Identifier
    evidence_assessments: list[EvidenceAssessmentInput] = Field(default_factory=list)
    decision: ClaimReviewDecision
    comment: Comment = ""


class ClaimReview(StrictReviewModel):
    claim_id: Identifier
    claim_key: Identifier
    claim_version: int = Field(ge=1)
    claim_fingerprint: Identifier
    evidence_ids: list[Identifier]
    evidence_assessments: list[EvidenceAssessment]
    decision: ClaimReviewDecision
    comment: Comment = ""
    reviewed_by: Identifier
    reviewed_at: datetime


class KnowledgeReviewSnapshot(StrictReviewModel):
    category: Identifier
    definition_present: bool
    schema_valid: bool
    completeness_score: int = Field(ge=0, le=100)
    completeness_threshold_met: bool
    completeness_profile_id: Identifier
    active_claim_count: int = Field(ge=0)
    reviewed_claim_count: int = Field(ge=0)
    approved_claim_count: int = Field(ge=0)
    evidence_supported_claim_count: int = Field(ge=0)


class CreateMedicalReviewRequest(StrictReviewModel):
    knowledge_id: Identifier
    reviewer_id: Identifier
    reviewer_role: ReviewerRole
    review_scope: Literal["knowledge_and_claims"] = "knowledge_and_claims"
    claim_reviews: list[ClaimReviewInput]
    checklist_results: list[ChecklistItemReviewInput]
    decision: ReviewDecision
    comments: RequiredComment
    valid_until: datetime


class MedicalReviewRecord(StrictReviewModel):
    contract_version: Literal["1.0"] = "1.0"
    review_id: Identifier
    review_version: int = Field(ge=1)
    knowledge_id: Identifier
    knowledge_version: int = Field(ge=1)
    knowledge_fingerprint: Identifier
    reviewer_id: Identifier
    reviewer_role: ReviewerRole
    review_scope: Literal["knowledge_and_claims"]
    checklist_id: Literal["medical_review_checklist_v1"]
    checklist_version: Literal["1.0"]
    evidence_policy_version: Literal["1.0"]
    claim_reviews: list[ClaimReview]
    checklist_results: list[ChecklistItemReview]
    knowledge_review: KnowledgeReviewSnapshot
    decision: ReviewDecision
    comments: RequiredComment
    reviewed_at: datetime
    valid_until: datetime
    status: Literal["completed"] = "completed"
    record_fingerprint: Identifier

    @model_validator(mode="after")
    def validate_times(self) -> MedicalReviewRecord:
        if self.valid_until <= self.reviewed_at:
            raise ValueError("valid_untilはreviewed_atより後である必要があります")
        return self


class ApprovalEligibilityCheck(StrictReviewModel):
    code: Identifier
    passed: bool
    message: str


class MedicalApprovalEligibility(StrictReviewModel):
    knowledge_id: Identifier
    review_id: Identifier | None
    review_version: int | None = Field(default=None, ge=1)
    validity: ReviewValidity | None
    eligible_for_final_approval: bool
    reasons: list[Identifier]
    checks: list[ApprovalEligibilityCheck]
    evaluated_at: datetime


class MedicalReviewQueueEntry(StrictReviewModel):
    knowledge_id: Identifier
    knowledge_name: str
    category: str
    knowledge_version: int = Field(ge=1)
    review_version: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    reviewed_claim_count: int = Field(ge=0)
    unreviewed_claim_count: int = Field(ge=0)
    evidence_coverage: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)
    current_decision: ReviewDecision | None
    review_deadline: datetime | None
    review_validity: ReviewValidity | None
    eligible_for_final_approval: bool


class MedicalReviewKnowledgeContext(StrictReviewModel):
    queue_entry: MedicalReviewQueueEntry
    claims: list[dict[str, object]]
    checklist: list[ChecklistDefinition]
    reviewers: list[ReviewerProfile]
    latest_review: MedicalReviewRecord | None
    eligibility: MedicalApprovalEligibility


def medical_review_record_json_schema() -> dict[str, object]:
    return MedicalReviewRecord.model_json_schema()
