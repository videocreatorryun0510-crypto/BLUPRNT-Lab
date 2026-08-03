"""Provider-neutral Payload and traceable Response contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.approval_v10 import ApprovalState
from knowledge_contracts.v10.models import ClaimId, KnowledgeId
from presentation_request_builder import (
    InformationDensity,
    Orientation,
    OutputFormat,
    PresentationType,
    RequestMode,
    TextAmount,
    VisualPriority,
)
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
PayloadId = Annotated[str, StringConstraints(pattern=r"^ppd_[a-f0-9]{32}$")]
ResponseId = Annotated[str, StringConstraints(pattern=r"^prs_[a-f0-9]{32}$")]
RequestId = Annotated[str, StringConstraints(pattern=r"^prq_[a-f0-9]{32}$")]
ArtifactId = Annotated[str, StringConstraints(pattern=r"^art_[a-f0-9]{32}$")]
StableId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9_]+)+$",
        max_length=180,
    ),
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PayloadValidationStage(StrEnum):
    REQUEST = "request"
    SOURCE = "source"
    REGISTRY = "registry"
    APPROVAL = "approval"
    CLAIM = "claim"
    KEY_MESSAGE = "key_message"
    EXAM_METADATA = "exam_metadata"
    DIAGRAM = "diagram"
    REFERENCE = "reference"
    POLICY = "policy"
    FINGERPRINT = "fingerprint"


class PayloadValidationIssue(FrozenModel):
    stage: PayloadValidationStage
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    path: str = Field(min_length=1, max_length=300)
    message: NonEmptyText


class PayloadValidationReport(FrozenModel):
    is_valid: bool
    stale_check_result: bool
    approval_result: bool
    egress_policy_result: bool
    secret_scan_result: bool
    local_path_scan_result: bool
    personal_data_scan_result: bool
    fingerprint_result: bool
    issues: tuple[PayloadValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validity_matches_checks(self) -> Self:
        checks = (
            self.stale_check_result,
            self.approval_result,
            self.egress_policy_result,
            self.secret_scan_result,
            self.local_path_scan_result,
            self.personal_data_scan_result,
            self.fingerprint_result,
        )
        if self.is_valid != (all(checks) and not self.issues):
            raise ValueError("is_valid must match all policy checks and issues")
        return self


class PayloadIdentity(FrozenModel):
    payload_id: PayloadId
    payload_contract_version: Literal["1.0"] = "1.0"
    created_at: datetime


class PayloadRequest(FrozenModel):
    presentation_request_id: RequestId
    request_contract_version: Literal["1.0"] = "1.0"
    request_mode: RequestMode
    presentation_type: PresentationType
    output_format: OutputFormat


class PayloadSource(FrozenModel):
    knowledge_id: KnowledgeId
    knowledge_version: int = Field(ge=1)
    source_bundle_version: Literal["1.0"]
    source_fingerprint: Fingerprint
    presentation_request_fingerprint: Fingerprint
    approval_state: ApprovalState
    review_version: int = Field(ge=1)


class PayloadPresentation(FrozenModel):
    title: NonEmptyText
    target_audience: NonEmptyText
    learning_objective: NonEmptyText
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$", max_length=10)
    page_or_slide_count: int = Field(ge=1, le=200)
    aspect_ratio: NonEmptyText
    orientation: Orientation
    information_density: InformationDensity
    visual_priority: VisualPriority
    text_amount: TextAmount


class ResolvedClaim(FrozenModel):
    claim_id: ClaimId
    claim_key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:\.[a-z0-9_]+)+$")
    exact_text: NonEmptyText
    category_role: NonEmptyText
    source_reference_ids: tuple[str, ...] = Field(max_length=500)
    approval_state: Literal["approved"]
    claim_version: int = Field(ge=1)


class ResolvedKeyMessage(FrozenModel):
    claim_id: ClaimId
    exact_text: NonEmptyText
    priority: Literal["highest", "important", "supplementary"]
    source_reference_ids: tuple[str, ...] = Field(max_length=500)


class ResolvedExamMetadata(FrozenModel):
    exam_metadata_id: str = Field(min_length=3, max_length=180)
    importance_score: int | None = Field(default=None, ge=0, le=100)
    priority_claim_ids: tuple[ClaimId, ...] = Field(max_length=200)
    patterns: tuple[str, ...] = Field(max_length=20)
    frequent_errors: tuple[NonEmptyText, ...] = Field(max_length=100)
    source_exam_records: tuple[str, ...] = Field(max_length=1000)


class ReferenceLocator(FrozenModel):
    public_url: str | None = Field(default=None, max_length=2000)
    doi: str | None = Field(default=None, max_length=300)
    pmid: str | None = Field(default=None, max_length=20)
    chapter: str | None = Field(default=None, max_length=300)
    pages: str | None = Field(default=None, max_length=100)


class ResolvedReference(FrozenModel):
    reference_id: str = Field(min_length=3, max_length=180)
    title: NonEmptyText
    organization_or_author: str | None = Field(default=None, max_length=1000)
    publication_year: int | None = Field(default=None, ge=1800, le=2100)
    source_type: Literal["evidence_reference"] = "evidence_reference"
    locator: ReferenceLocator
    supported_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=200)


class ResolvedDiagramRequest(FrozenModel):
    diagram_request_id: StableId
    title: NonEmptyText
    educational_goal: NonEmptyText
    source_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=30)
    visual_type: StableId
    priority: Literal["high", "standard", "low"]
    provider_neutral_instruction: NonEmptyText


class PayloadMedicalContent(FrozenModel):
    selected_claims: tuple[ResolvedClaim, ...] = Field(min_length=1, max_length=500)
    key_messages: tuple[ResolvedKeyMessage, ...] = Field(max_length=30)
    exam_points: tuple[ResolvedExamMetadata, ...] = Field(max_length=10)
    references: tuple[ResolvedReference, ...] = Field(max_length=500)


class PayloadVisualContent(FrozenModel):
    diagram_requests: tuple[ResolvedDiagramRequest, ...] = Field(max_length=20)


class PayloadPolicies(FrozenModel):
    allow_medical_rephrasing: Literal[False] = False
    allow_medical_fact_addition: Literal[False] = False
    require_claim_traceability: Literal[True] = True
    require_reference_traceability: Literal[True] = True
    prohibit_unapproved_medical_additions: Literal[True] = True


class ClaimTraceEntry(FrozenModel):
    claim_id: ClaimId
    payload_path: str = Field(min_length=1, max_length=300)
    use_purposes: tuple[
        Literal["selected_claim", "key_message", "exam_point", "diagram_source"],
        ...,
    ] = Field(min_length=1, max_length=4)
    display_priority: int = Field(ge=1, le=500)


class DiagramTraceEntry(FrozenModel):
    diagram_request_id: StableId
    source_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=30)
    educational_goal: NonEmptyText


class ReferenceTraceEntry(FrozenModel):
    reference_id: str = Field(min_length=3, max_length=180)
    supported_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=200)


class PayloadTraceability(FrozenModel):
    claim_trace_map: tuple[ClaimTraceEntry, ...] = Field(min_length=1, max_length=500)
    diagram_trace_map: tuple[DiagramTraceEntry, ...] = Field(max_length=20)
    reference_trace_map: tuple[ReferenceTraceEntry, ...] = Field(max_length=500)


class PayloadMetadata(FrozenModel):
    resolver_id: Literal["bluprnt.provider_payload_resolver"]
    resolver_version: Literal["1.0.0"]
    profile_id: StableId
    profile_version: Literal["1.0"]
    payload_fingerprint: Fingerprint


class PresentationPayload(FrozenModel):
    identity: PayloadIdentity
    request: PayloadRequest
    source: PayloadSource
    presentation: PayloadPresentation
    medical_content: PayloadMedicalContent
    visual_content: PayloadVisualContent
    policies: PayloadPolicies
    traceability: PayloadTraceability
    metadata: PayloadMetadata


class PayloadBuildResult(FrozenModel):
    status: Literal["success", "blocked"]
    attempted_payload_id: PayloadId
    payload: PresentationPayload | None
    output_path: str | None
    validation: PayloadValidationReport
    external_use_allowed: bool
    stop_reasons: tuple[NonEmptyText, ...]
    audit_log_path: str
    external_ai_called: Literal[False] = False


class ExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TraceableResponseIdentity(FrozenModel):
    response_id: ResponseId
    response_contract_version: Literal["1.0"] = "1.0"
    created_at: datetime


class TraceableResponseRequest(FrozenModel):
    presentation_request_id: RequestId
    payload_id: PayloadId
    payload_fingerprint: Fingerprint


class TraceableResponseProvider(FrozenModel):
    provider_name: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    provider_version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?$"
    )
    provider_request_id: str = Field(min_length=3, max_length=180)


class TraceableResponseExecution(FrozenModel):
    status: ExecutionStatus
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None = Field(default=None, ge=0)


class UnsupportedTraceItem(FrozenModel):
    item_type: Literal["claim", "diagram_request", "reference"]
    item_id: str = Field(min_length=3, max_length=180)
    reason: NonEmptyText


class TraceableResponseTraceability(FrozenModel):
    used_claim_ids: tuple[ClaimId, ...] = Field(max_length=500)
    used_diagram_request_ids: tuple[StableId, ...] = Field(max_length=20)
    used_reference_ids: tuple[str, ...] = Field(max_length=500)
    omitted_claim_ids: tuple[ClaimId, ...] = Field(max_length=500)
    unsupported_items: tuple[UnsupportedTraceItem, ...] = Field(max_length=500)


class TraceableArtifact(FrozenModel):
    artifact_id: ArtifactId
    artifact_type: str = Field(min_length=2, max_length=100)
    mime_type: str = Field(min_length=3, max_length=200)
    local_or_remote_reference: str = Field(min_length=1, max_length=2000)
    checksum: Fingerprint


class TraceableResponseValidation(FrozenModel):
    is_valid: bool
    claim_traceability_result: bool
    reference_traceability_result: bool
    diagram_traceability_result: bool
    fingerprint_result: bool
    policy_result: bool
    issues: tuple[PayloadValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validity_matches_checks(self) -> Self:
        expected = (
            self.claim_traceability_result
            and self.reference_traceability_result
            and self.diagram_traceability_result
            and self.fingerprint_result
            and self.policy_result
            and not self.issues
        )
        if self.is_valid != expected:
            raise ValueError("Response validation is_valid must match checks")
        return self


class TraceablePresentationResponse(FrozenModel):
    identity: TraceableResponseIdentity
    request: TraceableResponseRequest
    provider: TraceableResponseProvider
    execution: TraceableResponseExecution
    traceability: TraceableResponseTraceability
    artifacts: tuple[TraceableArtifact, ...] = Field(max_length=100)
    validation: TraceableResponseValidation
    warnings: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)
    errors: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)


class TraceableResponseRunResult(FrozenModel):
    status: Literal["accepted", "rejected"]
    response: TraceablePresentationResponse
    output_path: str
    audit_log_path: str
    external_ai_called: Literal[False] = False


class PayloadAuditRecord(FrozenModel):
    audit_contract_version: Literal["1.0"] = "1.0"
    payload_id: PayloadId
    presentation_request_id: RequestId
    knowledge_id: KnowledgeId
    approval_state: ApprovalState
    payload_fingerprint: Fingerprint | None
    egress_policy_result: bool
    validation_result: Literal["passed", "failed"]
    result: Literal["generated", "blocked"]
    reason: NonEmptyText
    timestamp: datetime


class ResponseAuditRecord(FrozenModel):
    audit_contract_version: Literal["1.0"] = "1.0"
    response_id: ResponseId
    payload_id: PayloadId
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    status: ExecutionStatus
    fingerprint_result: bool
    claim_traceability_result: bool
    reference_traceability_result: bool
    result: Literal["accepted", "rejected"]
    timestamp: datetime


def presentation_payload_json_schema() -> dict[str, object]:
    return PresentationPayload.model_json_schema(mode="serialization")


def traceable_response_json_schema() -> dict[str, object]:
    return TraceablePresentationResponse.model_json_schema(mode="serialization")
