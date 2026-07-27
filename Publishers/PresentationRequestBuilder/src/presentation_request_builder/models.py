"""Provider-neutral Presentation Contract Version 1.0."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.registry_v10 import ApprovalState
from knowledge_contracts.v10.models import ClaimId, KnowledgeId
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ProfileId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9_]+)+$",
        max_length=180,
    ),
]
Fingerprint = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{64}$"),
]
PresentationRequestId = Annotated[
    str,
    StringConstraints(pattern=r"^prq_[a-f0-9]{32}$"),
]
PresentationReasonCode = Literal[
    "request_ready",
    "approval_required",
    "published_state_not_enabled",
    "knowledge_deprecated",
    "source_bundle_stale",
    "knowledge_version_mismatch",
    "fingerprint_mismatch",
    "approval_state_changed",
    "review_version_mismatch",
    "validation_failed",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PresentationType(StrEnum):
    PRESENTATION_DOCUMENT = "presentation_document"
    PDF_MATERIAL = "pdf_material"
    INSTAGRAM_SLIDES = "instagram_slides"
    TRAINING_MATERIAL = "training_material"
    DIAGRAM = "diagram"
    NOTEBOOK_MATERIAL = "notebook_material"


class OutputFormat(StrEnum):
    STRUCTURED_JSON = "structured_json"
    PDF = "pdf"
    PPTX = "pptx"
    PNG_SEQUENCE = "png_sequence"
    HTML = "html"
    MARKDOWN = "markdown"


class RequestMode(StrEnum):
    PREVIEW = "preview"
    EXTERNAL = "external"


class InformationDensity(StrEnum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class VisualPriority(StrEnum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class TextAmount(StrEnum):
    SHORT = "short"
    STANDARD = "standard"
    DETAILED = "detailed"


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class PresentationIdentity(FrozenModel):
    presentation_request_id: PresentationRequestId
    contract_version: Literal["1.0"] = "1.0"
    created_at: datetime


class PresentationSource(FrozenModel):
    knowledge_id: KnowledgeId
    knowledge_version: int = Field(ge=1)
    source_bundle_version: Literal["1.0"]
    source_fingerprint: Fingerprint
    approval_state: ApprovalState
    review_version: int = Field(ge=1)


class PresentationDefinition(FrozenModel):
    presentation_type: PresentationType
    title: NonEmptyText
    target_audience: NonEmptyText
    learning_objective: NonEmptyText
    language: Annotated[
        str,
        StringConstraints(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$", max_length=10),
    ]
    output_format: OutputFormat


class ContentPolicy(FrozenModel):
    use_all_claims: bool
    selected_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=500)
    key_message_claim_ids: tuple[ClaimId, ...] = Field(max_length=30)
    diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    reference_ids: tuple[str, ...] = Field(max_length=500)
    include_references: bool
    include_exam_points: bool
    allow_medical_rephrasing: bool = False
    allow_medical_fact_addition: bool = False
    allow_non_medical_presentation_text: bool = True

    @model_validator(mode="after")
    def require_unique_references(self) -> Self:
        for field_name in (
            "selected_claim_ids",
            "key_message_claim_ids",
            "diagram_request_ids",
            "reference_ids",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} values must be unique")
        return self


class LayoutPolicy(FrozenModel):
    page_or_slide_count: int = Field(ge=1, le=200)
    aspect_ratio: NonEmptyText
    orientation: Orientation
    information_density: InformationDensity
    visual_priority: VisualPriority
    text_amount: TextAmount
    notes: str = Field(default="", max_length=2000)


class ValidationPolicy(FrozenModel):
    require_claim_traceability: bool = True
    require_reference_traceability: bool = True
    prohibit_unapproved_medical_additions: bool = True
    require_source_fingerprint_match: bool = True
    require_approval_gate: bool = True


class PresentationMetadata(FrozenModel):
    builder_id: Literal["bluprnt.presentation_request_builder"]
    builder_version: Literal["1.0.0"]
    profile_id: ProfileId
    profile_version: Literal["1.0"]


class PresentationRequest(FrozenModel):
    identity: PresentationIdentity
    request_mode: RequestMode
    source: PresentationSource
    presentation: PresentationDefinition
    content_policy: ContentPolicy
    layout_policy: LayoutPolicy
    validation_policy: ValidationPolicy
    metadata: PresentationMetadata


class PresentationProfile(FrozenModel):
    profile_id: ProfileId
    profile_version: Literal["1.0"]
    presentation_type: PresentationType
    output_format: OutputFormat
    target_audience: NonEmptyText
    language: Annotated[
        str,
        StringConstraints(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$", max_length=10),
    ]
    page_or_slide_count: int = Field(ge=1, le=200)
    aspect_ratio: NonEmptyText
    orientation: Orientation
    information_density: InformationDensity
    visual_priority: VisualPriority
    text_amount: TextAmount
    notes: str = Field(default="", max_length=2000)
    use_all_claims: bool = True
    include_references: bool = True
    include_exam_points: bool = True
    allow_medical_rephrasing: bool = False
    allow_medical_fact_addition: bool = False
    allow_non_medical_presentation_text: bool = True
    require_claim_traceability: bool = True
    require_reference_traceability: bool = True
    prohibit_unapproved_medical_additions: bool = True
    require_source_fingerprint_match: bool = True
    require_approval_gate: bool = True


class ValidationIssue(FrozenModel):
    code: str
    path: str
    message: NonEmptyText


class PresentationValidationReport(FrozenModel):
    is_valid: bool
    issues: tuple[ValidationIssue, ...]


class SourceFreshnessReport(FrozenModel):
    is_current: bool
    fingerprint_match: bool
    knowledge_version_match: bool
    approval_state_match: bool
    review_version_match: bool
    failure_codes: tuple[
        Literal[
            "source_bundle_stale",
            "knowledge_version_mismatch",
            "fingerprint_mismatch",
            "approval_state_changed",
            "review_version_mismatch",
        ],
        ...,
    ]


class PresentationBuildDecision(FrozenModel):
    allowed: bool
    reason_code: PresentationReasonCode
    reason: NonEmptyText
    external_use_allowed: bool
    freshness: SourceFreshnessReport


class PresentationBuildResult(FrozenModel):
    status: Literal["success", "blocked"]
    request: PresentationRequest | None
    output_path: str | None
    decision: PresentationBuildDecision
    validation: PresentationValidationReport | None
    audit_log_path: str


class PresentationAuditRecord(FrozenModel):
    presentation_request_id: PresentationRequestId
    knowledge_id: KnowledgeId
    knowledge_version: int = Field(ge=1)
    request_mode: RequestMode
    presentation_type: PresentationType
    profile_id: ProfileId
    profile_version: Literal["1.0"]
    approval_state: ApprovalState
    fingerprint_check: bool
    gate_result: bool
    validation_result: Literal["passed", "failed", "not_run"]
    result: Literal["generated", "blocked"]
    reason: NonEmptyText
    timestamp: datetime


def presentation_request_json_schema() -> dict[str, object]:
    return PresentationRequest.model_json_schema(mode="serialization")
