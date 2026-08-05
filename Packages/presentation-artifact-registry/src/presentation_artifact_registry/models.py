"""Presentation Artifact Registry Version 1.0 contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from presentation_artifact import PresentationArtifact
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
ArtifactId = Annotated[str, StringConstraints(pattern=r"^art_[a-f0-9]{32}$")]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactApprovalState(StrEnum):
    DRAFT = "draft"
    OWNER_REVIEW = "owner_review"
    EDUCATION_REVIEW = "education_review"
    APPROVED = "approved"
    PUBLISHED = "published"


class ArtifactRegistryStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ArtifactHistoryEventType(StrEnum):
    VERSION_CREATED = "version_created"
    APPROVAL_TRANSITION = "approval_transition"
    DEPRECATED = "deprecated"


class ArtifactRegistryEntry(FrozenModel):
    artifact_id: ArtifactId
    artifact_version: int = Field(ge=1)
    source_bundle_id: str
    presentation_request_id: str
    knowledge_id: str
    knowledge_version: int = Field(ge=1)
    profile_id: str
    profile_version: str
    fingerprint: Fingerprint
    approval_state: ArtifactApprovalState
    created_at: datetime
    updated_at: datetime
    owner: NonEmptyText
    review_comment: str = Field(default="", max_length=4000)
    status: ArtifactRegistryStatus
    immutable: bool


class ArtifactVersionRecord(FrozenModel):
    entry: ArtifactRegistryEntry
    artifact: PresentationArtifact


class ArtifactHistoryEvent(FrozenModel):
    history_id: int = Field(ge=1)
    artifact_id: ArtifactId
    artifact_version: int = Field(ge=1)
    event_type: ArtifactHistoryEventType
    changed_at: datetime
    changed_by: NonEmptyText
    review_comment: str = Field(default="", max_length=4000)
    fingerprint: Fingerprint
    from_approval_state: ArtifactApprovalState | None
    to_approval_state: ArtifactApprovalState


class ArtifactRegistryView(FrozenModel):
    current: ArtifactRegistryEntry
    versions: tuple[ArtifactRegistryEntry, ...]
    history: tuple[ArtifactHistoryEvent, ...]


class HeadlineChange(FrozenModel):
    page_number: int = Field(ge=1)
    before: str
    after: str


class PageFieldChange(FrozenModel):
    page_number: int = Field(ge=1)
    before: dict[str, object] | None
    after: dict[str, object] | None


class ArtifactDiffReport(FrozenModel):
    artifact_id: ArtifactId
    from_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    headline_changes: tuple[HeadlineChange, ...]
    pages_added: tuple[int, ...]
    pages_removed: tuple[int, ...]
    claim_ids_added: tuple[str, ...]
    claim_ids_removed: tuple[str, ...]
    reference_ids_added: tuple[str, ...]
    reference_ids_removed: tuple[str, ...]
    diagram_changes: tuple[PageFieldChange, ...]
    layout_changes: tuple[PageFieldChange, ...]
    has_changes: bool


class CompletenessSection(FrozenModel):
    section: Literal[
        "page",
        "headline",
        "learning_goal",
        "claim",
        "diagram",
        "reference",
        "layout",
        "metadata",
    ]
    complete: bool
    score: float = Field(ge=0, le=12.5)
    message: NonEmptyText


class ArtifactCompletenessReport(FrozenModel):
    score: float = Field(ge=0, le=100)
    is_complete: bool
    sections: tuple[CompletenessSection, ...] = Field(min_length=8, max_length=8)
    improvement_candidates: tuple[str, ...]
    disclaimer: Literal[
        "Completeness 100%は構造上の充足を示し、教育品質を保証しません。"
    ] = "Completeness 100%は構造上の充足を示し、教育品質を保証しません。"


class RegistryValidationIssue(FrozenModel):
    code: str
    artifact_id: str | None
    artifact_version: int | None
    message: NonEmptyText


class ArtifactRegistryValidationReport(FrozenModel):
    is_valid: bool
    issues: tuple[RegistryValidationIssue, ...]


class ApprovalTransitionRequest(FrozenModel):
    target_state: ArtifactApprovalState
    actor: NonEmptyText
    review_comment: NonEmptyText


class ArtifactRegistrySnapshot(FrozenModel):
    registry_version: Literal["1.0"] = "1.0"
    artifacts: tuple[ArtifactRegistryEntry, ...]

    @model_validator(mode="after")
    def require_unique_artifacts(self) -> Self:
        ids = [item.artifact_id for item in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("artifact_id values must be unique")
        return self


def artifact_registry_json_schema() -> dict[str, object]:
    return ArtifactRegistrySnapshot.model_json_schema(mode="serialization")
