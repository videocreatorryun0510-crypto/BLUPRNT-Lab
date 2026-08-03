"""Provider-neutral Presentation Engine Adapter and Result contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.approval_v10 import ApprovalGateDecision
from presentation_request_builder import OutputFormat, PresentationType, RequestMode
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ProviderName = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_-]{1,79}$"),
]
ProviderVersion = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?$"),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
RequestId = Annotated[str, StringConstraints(pattern=r"^prq_[a-f0-9]{32}$")]
ArtifactId = Annotated[str, StringConstraints(pattern=r"^art_[a-f0-9]{32}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EngineExecutionStatus(StrEnum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    FAILED = "failed"


class ValidationStage(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    REGISTRY = "registry"
    APPROVAL_GATE = "approval_gate"


class AdapterDescriptor(FrozenModel):
    provider_name: ProviderName
    provider_version: ProviderVersion
    supports_preview: bool
    supports_external: bool


class AdapterValidationIssue(FrozenModel):
    stage: ValidationStage
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    path: str = Field(min_length=1, max_length=300)
    message: NonEmptyText


class AdapterValidationReport(FrozenModel):
    is_valid: bool
    issues: tuple[AdapterValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validity_matches_issues(self) -> Self:
        if self.is_valid == bool(self.issues):
            raise ValueError("is_valid must be true exactly when issues is empty")
        return self


class PresentationEnginePayload(FrozenModel):
    """Metadata-only normalized input; it contains no medical assertion text."""

    payload_contract_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    request_fingerprint: Fingerprint
    request_mode: RequestMode
    provider: ProviderName
    provider_version: ProviderVersion
    presentation_type: PresentationType
    output_format: OutputFormat
    expected_pages: int = Field(ge=1, le=200)
    claim_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    reference_ids: tuple[str, ...] = Field(max_length=500)


class PresentationEngineResponse(FrozenModel):
    """Normalized provider response metadata before contract validation."""

    response_contract_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    request_fingerprint: Fingerprint
    provider: ProviderName
    provider_version: ProviderVersion
    status: Literal["success", "failed"] = "success"
    pages: int = Field(ge=1, le=200)
    claims_used: int = Field(ge=0, le=500)
    diagram_requests: int = Field(ge=0, le=20)
    references: int = Field(ge=0, le=500)
    output_type: PresentationType
    created_at: datetime
    warnings: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)
    errors: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)


class GeneratedArtifact(FrozenModel):
    """Artifact metadata only; no generated or medical body is stored."""

    artifact_id: ArtifactId
    output_type: PresentationType
    pages: int = Field(ge=1, le=200)
    claims_used: int = Field(ge=0, le=500)
    diagram_requests: int = Field(ge=0, le=20)
    references: int = Field(ge=0, le=500)
    request_fingerprint: Fingerprint


class PresentationResultValidation(FrozenModel):
    is_valid: bool
    request_validation: AdapterValidationReport
    response_validation: AdapterValidationReport | None
    approval_gate_checked: bool
    approval_gate_required: bool
    approval_gate_allowed: bool


class PresentationResult(FrozenModel):
    result_contract_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    provider: ProviderName
    provider_version: ProviderVersion
    status: EngineExecutionStatus
    created_at: datetime
    validation_result: PresentationResultValidation
    generated_artifacts: tuple[GeneratedArtifact, ...] = Field(max_length=20)
    warnings: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)
    errors: tuple[NonEmptyText, ...] = Field(default=(), max_length=100)


class PresentationEngineRunOutcome(FrozenModel):
    result: PresentationResult
    adapter: AdapterDescriptor
    request_fingerprint: Fingerprint
    approval_gate: ApprovalGateDecision
    audit_log_path: str
    external_ai_called: Literal[False] = False


class PresentationEngineAuditRecord(FrozenModel):
    audit_contract_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    provider: ProviderName
    provider_version: ProviderVersion
    mode: RequestMode
    status: EngineExecutionStatus
    validation_result: Literal["passed", "failed", "not_run"]
    gate_result: bool
    timestamp: datetime


def presentation_result_json_schema() -> dict[str, object]:
    return PresentationResult.model_json_schema(mode="serialization")
