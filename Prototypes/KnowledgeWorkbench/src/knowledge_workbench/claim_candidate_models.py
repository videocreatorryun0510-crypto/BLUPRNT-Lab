"""Provider-neutral contracts for evidence-grounded Claim candidate authoring."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from knowledge_workbench.authoring_models import (
    AuthoringCategory,
    AuthoringExamImportance,
    DifficultyLevel,
    KnowledgeAuthoringDraft,
)

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]
MediumText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1200),
]
ClaimText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=800),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class FrozenClaimModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimCandidateType(StrEnum):
    DEFINITION = "definition"
    OVERVIEW = "overview"
    FACT = "fact"
    CAUTION = "caution"


class ClaimSupportLevel(StrEnum):
    DIRECT = "direct"
    PARTIAL = "partial"
    INDIRECT = "indirect"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"


class ClaimSupportScopeType(StrEnum):
    FULL_CLAIM = "full_claim"
    CLAIM_PART = "claim_part"
    CONTEXT_ONLY = "context_only"
    NO_SUPPORT = "no_support"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class SourceLocatorType(StrEnum):
    ABSTRACT = "abstract"
    ABSTRACT_SECTION = "abstract_section"
    SENTENCE = "sentence"
    PASSAGE = "passage"
    SECTION = "section"
    PAGE = "page"


class ClaimDuplicateClassification(StrEnum):
    EXACT = "exact_duplicate"
    POSSIBLE = "possible_duplicate"
    DISTINCT = "distinct"


class HumanClaimDecision(StrEnum):
    ACCEPTED = "accepted"
    REVISED = "revised"
    EXCLUDED = "excluded"
    HOLD = "hold"


class ClaimGenerationErrorCode(StrEnum):
    TIMEOUT = "llm_timeout"
    AUTHENTICATION = "authentication_error"
    RATE_LIMIT = "rate_limit_error"
    PROVIDER_SERVER = "provider_server_error"
    NETWORK = "network_error"
    INVALID_RESPONSE = "invalid_structured_response"
    EVIDENCE_ID_HALLUCINATION = "evidence_id_hallucination"
    LOCATOR_MISMATCH = "locator_mismatch"
    EMPTY_CANDIDATES = "empty_candidate_set"
    FINGERPRINT = "fingerprint_mismatch"
    REQUEST = "request_error"


class FormalEvidenceClaimInput(FrozenClaimModel):
    """The only evidence body exposed to the Claim generation boundary."""

    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    title: ShortText
    abstract_or_snippet: str = Field(min_length=1, max_length=6000)
    citation: MediumText
    pmid: str | None = Field(default=None, pattern=r"^[0-9]{1,12}$")
    doi: ShortText | None = None
    provider_names: tuple[ShortText, ...] = Field(min_length=1, max_length=20)
    formal_evidence: Literal[True] = True
    human_selection: Literal["accepted"] = "accepted"


class FormalEvidenceSelectionSet(FrozenClaimModel):
    selection_contract_version: Literal["1.0"] = "1.0"
    selection_set_id: str = Field(pattern=r"^fes_[0-9a-f]{20}$")
    knowledge_term: ShortText
    evidence_bundle_id: str = Field(pattern=r"^evb_[a-z0-9][a-z0-9_-]{7,63}$")
    evidence_bundle_fingerprint: Fingerprint
    evidence: tuple[FormalEvidenceClaimInput, ...] = Field(min_length=1, max_length=10)
    formal_evidence_only: Literal[True] = True
    human_selection_required: Literal[True] = True
    discovery_candidate_included: Literal[False] = False
    excluded_evidence_included: Literal[False] = False
    pending_evidence_included: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> Self:
        values = [item.evidence_id for item in self.evidence]
        if len(values) != len(set(values)):
            raise ValueError("Formal Evidence Selection IDs must be unique")
        expected = formal_selection_set_id(
            self.knowledge_term,
            self.evidence_bundle_id,
            self.evidence_bundle_fingerprint,
            values,
        )
        if self.selection_set_id != expected:
            raise ValueError("Formal Evidence Selection fingerprint mismatch")
        return self


class ClaimSourceLocator(FrozenClaimModel):
    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    locator_type: SourceLocatorType
    locator_value: MediumText
    quote_excerpt: str = Field(min_length=1, max_length=240)
    pmid: str | None = Field(default=None, pattern=r"^[0-9]{1,12}$")
    doi: ShortText | None = None

    @model_validator(mode="after")
    def keep_quote_minimal(self) -> Self:
        words = self.quote_excerpt.split()
        if len(words) > 25:
            raise ValueError("Evidence quote must not exceed 25 words")
        return self


class ClaimSupportScope(FrozenClaimModel):
    scope_type: ClaimSupportScopeType
    explanation: MediumText
    supported_fragment: ClaimText | None = None
    unsupported_fragment: ClaimText | None = None


class ClaimConflictObservation(FrozenClaimModel):
    evidence_a_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    evidence_b_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    difference: MediumText

    @model_validator(mode="after")
    def validate_distinct_evidence(self) -> Self:
        if self.evidence_a_id == self.evidence_b_id:
            raise ValueError("Conflicting Evidence IDs must be different")
        return self


class ClaimSupportAssessment(FrozenClaimModel):
    assessment_version: Literal["1.0"] = "1.0"
    support_level: ClaimSupportLevel
    assessed_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=30)
    rationale: MediumText
    conflicts: tuple[ClaimConflictObservation, ...] = Field(default=(), max_length=20)
    ai_confidence_is_separate: Literal[True] = True
    medical_review_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_conflicts(self) -> Self:
        if self.support_level is ClaimSupportLevel.CONFLICTING and not self.conflicts:
            raise ValueError("Conflicting assessment requires a conflict observation")
        if self.support_level is not ClaimSupportLevel.CONFLICTING and self.conflicts:
            raise ValueError("Only conflicting assessment may contain conflicts")
        assessed = set(self.assessed_evidence_ids)
        conflict_ids = {
            evidence_id
            for conflict in self.conflicts
            for evidence_id in (conflict.evidence_a_id, conflict.evidence_b_id)
        }
        if not conflict_ids.issubset(assessed):
            raise ValueError("Conflict observations must use assessed Evidence IDs")
        return self


class ClaimDuplicateMatch(FrozenClaimModel):
    matched_id: ShortText
    matched_source: Literal["candidate", "registry"]
    classification: Literal["exact_duplicate", "possible_duplicate"]
    similarity: float = Field(ge=0, le=1)


class ClaimDuplicateAssessment(FrozenClaimModel):
    classification: ClaimDuplicateClassification
    matches: tuple[ClaimDuplicateMatch, ...] = Field(default=(), max_length=100)
    automatic_merge_performed: Literal[False] = False


class ClaimCandidate(FrozenClaimModel):
    candidate_contract_version: Literal["1.0"] = "1.0"
    candidate_claim_id: str = Field(pattern=r"^ccl_[0-9a-f]{20}$")
    knowledge_term: ShortText
    claim_text: ClaimText
    claim_type: ClaimCandidateType
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=30)
    source_locators: tuple[ClaimSourceLocator, ...] = Field(min_length=1, max_length=30)
    support_level: ClaimSupportLevel
    support_scope: ClaimSupportScope
    support_assessment: ClaimSupportAssessment
    confidence: float = Field(ge=0, le=1)
    generator_id: ShortText
    generator_version: ShortText
    generated_at: datetime
    candidate_fingerprint: Fingerprint
    duplicate_assessment: ClaimDuplicateAssessment
    ai_generated_candidate: Literal[True] = True
    formal_claim_id_issued: Literal[False] = False

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        supporting = set(self.supporting_evidence_ids)
        if supporting != set(self.support_assessment.assessed_evidence_ids):
            raise ValueError("Support Assessment Evidence IDs must match Claim Evidence IDs")
        if self.support_level is not self.support_assessment.support_level:
            raise ValueError("Claim and assessment support levels must match")
        if not {item.evidence_id for item in self.source_locators}.issubset(supporting):
            raise ValueError("Source Locator must reference supporting Evidence")
        expected = candidate_fingerprint(self)
        if self.candidate_fingerprint != expected:
            raise ValueError("Candidate fingerprint mismatch")
        return self


class ClaimValidationIssue(FrozenClaimModel):
    code: ShortText
    severity: Literal["error", "warning", "info"]
    candidate_claim_id: str | None = None
    path: ShortText
    message: MediumText


class ClaimCandidateValidationReport(FrozenClaimModel):
    schema_valid: bool
    evidence_ids_valid: bool
    accepted_evidence_only: bool
    locators_valid: bool
    fingerprints_valid: bool
    provider_neutral: bool
    candidate_count: int = Field(ge=0, le=100)
    direct_count: int = Field(ge=0, le=100)
    partial_count: int = Field(ge=0, le=100)
    indirect_count: int = Field(ge=0, le=100)
    unsupported_count: int = Field(ge=0, le=100)
    conflicting_count: int = Field(ge=0, le=100)
    authoring_eligible_count: int = Field(ge=0, le=100)
    validation_passed: bool
    issues: tuple[ClaimValidationIssue, ...] = Field(default=(), max_length=500)


class ClaimGenerationKpi(FrozenClaimModel):
    evidence_search_duration_ms: int = Field(ge=0)
    claim_generation_duration_ms: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    direct_rate: float = Field(ge=0, le=1)
    unsupported_rate: float = Field(ge=0, le=1)
    human_revision_rate: float | None = Field(default=None, ge=0, le=1)
    human_exclusion_rate: float | None = Field(default=None, ge=0, le=1)
    claim_review_duration_ms: int | None = Field(default=None, ge=0)


class ClaimCandidateSet(FrozenClaimModel):
    candidate_set_version: Literal["1.0"] = "1.0"
    candidate_set_id: str = Field(pattern=r"^ccs_[0-9a-f]{20}$")
    knowledge_term: ShortText
    evidence_selection: FormalEvidenceSelectionSet
    candidates: tuple[ClaimCandidate, ...] = Field(max_length=100)
    validation: ClaimCandidateValidationReport
    kpi: ClaimGenerationKpi
    generator_id: ShortText
    generator_version: ShortText
    generated_at: datetime
    candidate_set_fingerprint: Fingerprint
    ai_generated_candidate: Literal[True] = True
    medical_approval: Literal[False] = False
    registry_changed: Literal[False] = False
    promotion_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        candidate_ids = [item.candidate_claim_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Claim Candidate IDs must be unique")
        if self.knowledge_term != self.evidence_selection.knowledge_term:
            raise ValueError("Candidate Set and Evidence knowledge terms must match")
        expected = claim_candidate_set_fingerprint(
            self.evidence_selection.selection_set_id,
            [item.candidate_fingerprint for item in self.candidates],
        )
        if self.candidate_set_fingerprint != expected:
            raise ValueError("Claim Candidate Set fingerprint mismatch")
        if self.candidate_set_id != f"ccs_{expected[:20]}":
            raise ValueError("Claim Candidate Set ID fingerprint mismatch")
        return self


class HumanClaimReviewRequest(FrozenClaimModel):
    candidate_set_id: str = Field(pattern=r"^ccs_[0-9a-f]{20}$")
    candidate_claim_id: str = Field(pattern=r"^ccl_[0-9a-f]{20}$")
    decision: HumanClaimDecision
    operator: ShortText
    comment: ShortText | None = None
    revised_claim_text: ClaimText | None = None
    review_duration_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        if self.decision is HumanClaimDecision.REVISED and self.revised_claim_text is None:
            raise ValueError("Revised decision requires revised_claim_text")
        if self.decision is not HumanClaimDecision.REVISED and self.revised_claim_text:
            raise ValueError("Only revised decision may contain revised_claim_text")
        return self


class HumanClaimReviewEntry(FrozenClaimModel):
    review_version: Literal["1.0"] = "1.0"
    review_id: str = Field(pattern=r"^hcr_[0-9a-f]{20}$")
    candidate_set_id: str
    candidate_claim_id: str
    decision: HumanClaimDecision
    operator: ShortText
    timestamp: datetime
    comment: ShortText | None = None
    original_claim_text: ClaimText
    revised_claim_text: ClaimText | None = None
    support_level: ClaimSupportLevel
    review_duration_ms: int | None = Field(default=None, ge=0)
    medical_approval_performed: Literal[False] = False
    registry_changed: Literal[False] = False


class CreateGroundedAuthoringDraftRequest(FrozenClaimModel):
    candidate_set_id: str = Field(pattern=r"^ccs_[0-9a-f]{20}$")
    category: AuthoringCategory
    difficulty: DifficultyLevel = DifficultyLevel.STANDARD
    exam_importance: AuthoringExamImportance = AuthoringExamImportance.MEDIUM
    operator: ShortText


class GroundedAuthoringDraftResult(FrozenClaimModel):
    candidate_set_id: str
    draft: KnowledgeAuthoringDraft
    candidate_to_claim_id: dict[str, str]
    adopted_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    saved_at: datetime
    promotion_performed: Literal[False] = False
    registry_changed: Literal[False] = False
    approval_performed: Literal[False] = False


class ClaimGenerationAuditEntry(FrozenClaimModel):
    audit_version: Literal["1.0"] = "1.0"
    execution_id: str = Field(pattern=r"^cge_[0-9a-f]{32}$")
    knowledge_term: ShortText
    evidence_bundle_id: str
    selected_evidence_ids: tuple[str, ...]
    provider: ShortText
    model: ShortText
    candidate_count: int = Field(ge=0)
    direct_count: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)
    conflicting_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    status: Literal["success", "validation_failed", "failed"]
    error_code: ClaimGenerationErrorCode | None = None
    generated_at: datetime
    medical_body_stored: Literal[False] = False
    api_key_stored: Literal[False] = False


class GeneratedClaimDraft(FrozenClaimModel):
    """Provider-neutral structured response before IDs and fingerprints are issued."""

    claim_text: ClaimText
    claim_type: ClaimCandidateType
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=30)
    source_locators: tuple[ClaimSourceLocator, ...] = Field(min_length=1, max_length=30)
    support_level: ClaimSupportLevel
    support_scope: ClaimSupportScope
    support_assessment: ClaimSupportAssessment
    confidence: float = Field(ge=0, le=1)


class StructuredClaimCandidateResponse(FrozenClaimModel):
    candidates: tuple[GeneratedClaimDraft, ...] = Field(min_length=1, max_length=20)


class ClaimGenerationRequest(FrozenClaimModel):
    request_version: Literal["1.0"] = "1.0"
    evidence_selection: FormalEvidenceSelectionSet
    max_candidates: int = Field(default=10, ge=1, le=20)
    outside_knowledge_allowed: Literal[False] = False
    discovery_input_allowed: Literal[False] = False


class ClaimAdapterUsage(FrozenClaimModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ClaimAdapterResult(FrozenClaimModel):
    provider: ShortText
    model: ShortText
    provider_request_id: ShortText | None = None
    generator_id: ShortText
    generator_version: ShortText
    response: StructuredClaimCandidateResponse
    usage: ClaimAdapterUsage
    duration_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0, le=1)
    provider_body_persisted: Literal[False] = False


def formal_selection_set_id(
    knowledge_term: str,
    bundle_id: str,
    bundle_fingerprint: str,
    evidence_ids: list[str],
) -> str:
    payload = {
        "knowledge_term": knowledge_term.strip(),
        "bundle_id": bundle_id,
        "bundle_fingerprint": bundle_fingerprint,
        "evidence_ids": sorted(evidence_ids),
    }
    return f"fes_{_fingerprint(payload)[:20]}"


def candidate_fingerprint(candidate: ClaimCandidate) -> str:
    return generated_claim_fingerprint(
        candidate.knowledge_term,
        GeneratedClaimDraft(
            claim_text=candidate.claim_text,
            claim_type=candidate.claim_type,
            supporting_evidence_ids=candidate.supporting_evidence_ids,
            source_locators=candidate.source_locators,
            support_level=candidate.support_level,
            support_scope=candidate.support_scope,
            support_assessment=candidate.support_assessment,
            confidence=candidate.confidence,
        ),
    )


def generated_claim_fingerprint(
    knowledge_term: str,
    candidate: GeneratedClaimDraft,
) -> str:
    return _fingerprint(
        {
            "knowledge_term": knowledge_term,
            "claim_text": candidate.claim_text,
            "claim_type": candidate.claim_type.value,
            "supporting_evidence_ids": sorted(candidate.supporting_evidence_ids),
            "source_locators": [
                item.model_dump(mode="json") for item in candidate.source_locators
            ],
            "support_level": candidate.support_level.value,
            "support_scope": candidate.support_scope.model_dump(mode="json"),
            "support_assessment": candidate.support_assessment.model_dump(mode="json"),
        }
    )


def claim_candidate_set_fingerprint(
    selection_set_id: str,
    candidate_fingerprints: list[str],
) -> str:
    return _fingerprint(
        {
            "selection_set_id": selection_set_id,
            "candidate_fingerprints": candidate_fingerprints,
        }
    )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
