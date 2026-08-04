"""Provider-neutral Presentation Prompt contracts."""

from datetime import datetime
from typing import Annotated, Literal, Self

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
from provider_payload_resolver import PresentationPayload
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=6000),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
PromptId = Annotated[str, StringConstraints(pattern=r"^pmt_[a-f0-9]{32}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptValidationIssue(FrozenModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    path: str = Field(min_length=1, max_length=300)
    message: NonEmptyText


class PromptValidationReport(FrozenModel):
    is_valid: bool
    approval_result: bool
    payload_fingerprint_result: bool
    exact_claim_result: bool
    provider_neutral_result: bool
    issues: tuple[PromptValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validity_matches_checks(self) -> Self:
        expected = (
            self.approval_result
            and self.payload_fingerprint_result
            and self.exact_claim_result
            and self.provider_neutral_result
            and not self.issues
        )
        if self.is_valid != expected:
            raise ValueError("Prompt validation is_valid must match checks")
        return self


class PromptIdentity(FrozenModel):
    prompt_id: PromptId
    prompt_contract_version: Literal["1.0"] = "1.0"
    created_at: datetime


class PromptSource(FrozenModel):
    presentation_request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    payload_fingerprint: Fingerprint
    knowledge_id: KnowledgeId
    knowledge_version: int = Field(ge=1)
    approval_state: Literal["approved"]
    request_mode: RequestMode


class PromptClaim(FrozenModel):
    claim_id: ClaimId
    claim_key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:\.[a-z0-9_]+)+$")
    exact_text: NonEmptyText
    category_role: NonEmptyText
    reference_ids: tuple[str, ...] = Field(max_length=500)
    claim_version: int = Field(ge=1)


class PromptKeyMessage(FrozenModel):
    claim_id: ClaimId
    exact_text: NonEmptyText
    priority: Literal["highest", "important", "supplementary"]


class PromptDiagramRequest(FrozenModel):
    diagram_request_id: str = Field(min_length=3, max_length=180)
    title: NonEmptyText
    educational_goal: NonEmptyText
    source_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=30)
    visual_type: str = Field(min_length=3, max_length=180)
    priority: Literal["high", "standard", "low"]
    provider_neutral_instruction: NonEmptyText


class PromptReference(FrozenModel):
    reference_id: str = Field(min_length=3, max_length=180)
    title: NonEmptyText
    organization_or_author: str | None = Field(default=None, max_length=1000)
    publication_year: int | None = Field(default=None, ge=1800, le=2100)
    doi: str | None = Field(default=None, max_length=300)
    pmid: str | None = Field(default=None, max_length=20)
    chapter: str | None = Field(default=None, max_length=300)
    pages: str | None = Field(default=None, max_length=100)
    supported_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=200)


class PromptContentPolicy(FrozenModel):
    selected_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=500)
    key_message_claim_ids: tuple[ClaimId, ...] = Field(max_length=30)
    diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    reference_ids: tuple[str, ...] = Field(max_length=500)
    allow_medical_rephrasing: Literal[False] = False
    allow_medical_fact_addition: Literal[False] = False
    require_source_attribution: Literal[True] = True


class PromptLayoutPolicy(FrozenModel):
    presentation_type: PresentationType
    output_format: OutputFormat
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$", max_length=10)
    page_or_slide_count: int = Field(ge=1, le=200)
    aspect_ratio: NonEmptyText
    orientation: Orientation
    information_density: InformationDensity
    visual_priority: VisualPriority
    text_amount: TextAmount


class PromptValidationPolicy(FrozenModel):
    expected_payload_fingerprint: Fingerprint
    require_exact_claim_text: Literal[True] = True
    require_all_claims_accounted_for: Literal[True] = True
    require_known_claim_ids_only: Literal[True] = True
    require_known_diagram_ids_only: Literal[True] = True
    require_known_reference_ids_only: Literal[True] = True
    prohibit_medical_body_in_result: Literal[True] = True


class PromptMetadata(FrozenModel):
    builder_id: Literal["bluprnt.presentation_prompt_builder"]
    builder_version: Literal["1.0.0"]
    prompt_fingerprint: Fingerprint


class PresentationPrompt(FrozenModel):
    identity: PromptIdentity
    source: PromptSource
    title: NonEmptyText
    learning_objective: NonEmptyText
    target_audience: NonEmptyText
    claims: tuple[PromptClaim, ...] = Field(min_length=1, max_length=500)
    key_messages: tuple[PromptKeyMessage, ...] = Field(max_length=30)
    diagram_requests: tuple[PromptDiagramRequest, ...] = Field(max_length=20)
    references: tuple[PromptReference, ...] = Field(max_length=500)
    content_policy: PromptContentPolicy
    layout_policy: PromptLayoutPolicy
    validation_policy: PromptValidationPolicy
    metadata: PromptMetadata


class PromptBuildResult(FrozenModel):
    status: Literal["success", "blocked"]
    attempted_prompt_id: PromptId
    prompt: PresentationPrompt | None
    output_path: str | None
    validation: PromptValidationReport
    stop_reasons: tuple[NonEmptyText, ...]
    audit_log_path: str
    provider_called: Literal[False] = False


class PromptAuditRecord(FrozenModel):
    audit_contract_version: Literal["1.0"] = "1.0"
    prompt_id: PromptId
    presentation_request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    payload_fingerprint: Fingerprint
    prompt_fingerprint: Fingerprint | None
    builder_version: Literal["1.0.0"]
    mode: RequestMode
    status: Literal["generated", "blocked"]
    error_code: str | None = Field(default=None, max_length=80)
    timestamp: datetime


def presentation_prompt_json_schema() -> dict[str, object]:
    return PresentationPrompt.model_json_schema(mode="serialization")


def payload_exact_texts(payload: PresentationPayload) -> tuple[str, ...]:
    """Expose an explicit comparison target for tests and validators."""

    return tuple(item.exact_text for item in payload.medical_content.selected_claims)
