"""Provider-neutral Presentation Artifact Contract Version 1.0."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.v10.models import ClaimId, KnowledgeId
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
ArtifactId = Annotated[str, StringConstraints(pattern=r"^art_[a-f0-9]{32}$")]
SourceBundleId = Annotated[str, StringConstraints(pattern=r"^sbn_[a-f0-9]{32}$")]
BlockId = Annotated[str, StringConstraints(pattern=r"^blk_[a-f0-9]{16}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PageType(StrEnum):
    TITLE = "title"
    CONTENT = "content"
    DIAGRAM = "diagram"
    SUMMARY = "summary"
    REFERENCES = "references"


class BodyBlockType(StrEnum):
    CLAIM = "claim"
    KEY_MESSAGE = "key_message"
    EXAM_POINT = "exam_point"


class LayoutComposition(StrEnum):
    TITLE = "title"
    SINGLE_COLUMN = "single_column"
    TWO_COLUMN = "two_column"
    VISUAL_LEFT = "visual_left"
    VISUAL_RIGHT = "visual_right"
    DIAGRAM_FOCUS = "diagram_focus"
    SUMMARY = "summary"
    REFERENCES = "references"


class LayoutDensity(StrEnum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class ArtifactIdentity(FrozenModel):
    artifact_id: ArtifactId
    contract_version: Literal["1.0"] = "1.0"
    artifact_version: int = Field(default=1, ge=1)
    request_id: Annotated[str, StringConstraints(pattern=r"^prq_[a-f0-9]{32}$")]
    source_bundle_id: SourceBundleId
    presentation_profile: NonEmptyText


class ArtifactSource(FrozenModel):
    knowledge_id: KnowledgeId
    knowledge_version: int = Field(ge=1)
    source_bundle_schema_version: Literal["1.0"]
    source_fingerprint: Fingerprint


class ArtifactPresentationProfile(FrozenModel):
    profile_id: NonEmptyText
    profile_version: Literal["1.0"]
    presentation_type: NonEmptyText
    output_format: NonEmptyText
    target_audience: NonEmptyText
    learning_objective: NonEmptyText
    language: NonEmptyText
    page_or_slide_count: int = Field(ge=1, le=200)
    aspect_ratio: NonEmptyText
    orientation: NonEmptyText
    information_density: NonEmptyText
    visual_priority: NonEmptyText
    text_amount: NonEmptyText


class ArtifactClaim(FrozenModel):
    claim_id: ClaimId
    claim_key: NonEmptyText
    exact_text: NonEmptyText
    field_path: NonEmptyText
    reference_ids: tuple[str, ...] = Field(max_length=500)

    @model_validator(mode="after")
    def require_unique_references(self) -> Self:
        if len(self.reference_ids) != len(set(self.reference_ids)):
            raise ValueError("reference_ids must be unique")
        return self


class ArtifactReference(FrozenModel):
    reference_id: NonEmptyText
    title: NonEmptyText
    issuing_organization: str | None = None
    edition: str | None = None
    publication_year: int | None = Field(default=None, ge=1800)
    url: str | None = None
    doi: str | None = None
    pmid: str | None = None
    chapter: str | None = None
    pages: str | None = None
    supported_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=200)


class ArtifactBodyBlock(FrozenModel):
    block_id: BlockId
    block_type: BodyBlockType
    claim_id: ClaimId
    exact_text: NonEmptyText


class ArtifactDiagramItem(FrozenModel):
    request_id: NonEmptyText
    diagram_type: NonEmptyText
    title: NonEmptyText
    learning_goal: NonEmptyText
    source_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=30)


class DiagramInstruction(FrozenModel):
    items: tuple[ArtifactDiagramItem, ...] = Field(min_length=1, max_length=20)


class LayoutHint(FrozenModel):
    composition: LayoutComposition
    density: LayoutDensity
    region_order: tuple[
        Literal["headline", "learning_goal", "body", "diagram", "references"], ...
    ] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def require_unique_regions(self) -> Self:
        if len(self.region_order) != len(set(self.region_order)):
            raise ValueError("region_order must not contain duplicates")
        return self


class PresentationPage(FrozenModel):
    page_number: int = Field(ge=1, le=200)
    page_type: PageType
    headline: NonEmptyText
    learning_goal: NonEmptyText
    supporting_claim_ids: tuple[ClaimId, ...] = Field(max_length=500)
    body_blocks: tuple[ArtifactBodyBlock, ...] = Field(max_length=500)
    diagram_instruction: DiagramInstruction | None
    speaker_note: str = Field(default="", max_length=4000)
    reference_ids: tuple[str, ...] = Field(max_length=500)
    layout_hint: LayoutHint

    @model_validator(mode="after")
    def require_unique_page_references(self) -> Self:
        for field_name in ("supporting_claim_ids", "reference_ids"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must be unique")
        block_ids = [item.block_id for item in self.body_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("body block IDs must be unique within a page")
        return self


class ArtifactMetadata(FrozenModel):
    fingerprint: Fingerprint
    created_at: datetime
    builder_version: Literal["1.0.0"]
    artifact_version: int = Field(default=1, ge=1)


class PresentationArtifact(FrozenModel):
    identity: ArtifactIdentity
    source: ArtifactSource
    presentation_profile: ArtifactPresentationProfile
    claim_catalog: tuple[ArtifactClaim, ...] = Field(min_length=1, max_length=500)
    reference_catalog: tuple[ArtifactReference, ...] = Field(max_length=500)
    pages: tuple[PresentationPage, ...] = Field(min_length=1, max_length=200)
    metadata: ArtifactMetadata


class ArtifactValidationIssue(FrozenModel):
    code: str
    path: str
    message: NonEmptyText


class ArtifactValidationReport(FrozenModel):
    is_valid: bool
    issues: tuple[ArtifactValidationIssue, ...]


class ArtifactBuildResult(FrozenModel):
    status: Literal["success", "validation_failed"]
    artifact: PresentationArtifact | None
    output_path: str | None
    validation: ArtifactValidationReport
    audit_log_path: str


class ArtifactAuditRecord(FrozenModel):
    artifact_id: ArtifactId
    request_id: str
    knowledge_id: KnowledgeId
    artifact_version: int = Field(ge=1)
    validation_result: Literal["passed", "failed"]
    saved: bool
    timestamp: datetime


def presentation_artifact_json_schema() -> dict[str, object]:
    return PresentationArtifact.model_json_schema(mode="serialization")
