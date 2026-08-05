"""Presentation Artifact Registry public API."""

from presentation_artifact_registry.completeness import (
    evaluate_artifact_completeness,
)
from presentation_artifact_registry.diff import compare_artifacts
from presentation_artifact_registry.eligibility import (
    ClaimApprovalResult,
    KnowledgeArtifactSourceSnapshot,
    RendererBlockReason,
    RendererEligibility,
    SourceClaimSnapshot,
    evaluate_renderer_eligibility,
)
from presentation_artifact_registry.errors import (
    ArtifactApprovalError,
    ArtifactImmutableError,
    ArtifactNotFoundError,
    ArtifactRegistryError,
)
from presentation_artifact_registry.gateway import (
    ArtifactRendererGateway,
    ArtifactSourceSnapshotProvider,
)
from presentation_artifact_registry.models import (
    ApprovalTransitionRequest,
    ArtifactApprovalState,
    ArtifactCompletenessReport,
    ArtifactDiffReport,
    ArtifactGateAuditRecord,
    ArtifactHistoryEvent,
    ArtifactHistoryEventType,
    ArtifactRegistryEntry,
    ArtifactRegistrySnapshot,
    ArtifactRegistryStatus,
    ArtifactRegistryValidationReport,
    ArtifactRegistryView,
    ArtifactVersionRecord,
    CompletenessSection,
    HeadlineChange,
    PageFieldChange,
    RegistryValidationIssue,
    artifact_registry_json_schema,
)
from presentation_artifact_registry.sqlite_registry import (
    SQLitePresentationArtifactRegistry,
)

__all__ = [
    "ApprovalTransitionRequest",
    "ArtifactApprovalError",
    "ArtifactApprovalState",
    "ArtifactCompletenessReport",
    "ArtifactDiffReport",
    "ArtifactGateAuditRecord",
    "ArtifactHistoryEvent",
    "ArtifactHistoryEventType",
    "ArtifactImmutableError",
    "ArtifactNotFoundError",
    "ArtifactRegistryEntry",
    "ArtifactRegistryError",
    "ArtifactRegistrySnapshot",
    "ArtifactRegistryStatus",
    "ArtifactRegistryValidationReport",
    "ArtifactRegistryView",
    "ArtifactRendererGateway",
    "ArtifactSourceSnapshotProvider",
    "ArtifactVersionRecord",
    "ClaimApprovalResult",
    "CompletenessSection",
    "HeadlineChange",
    "KnowledgeArtifactSourceSnapshot",
    "PageFieldChange",
    "RegistryValidationIssue",
    "RendererBlockReason",
    "RendererEligibility",
    "SQLitePresentationArtifactRegistry",
    "SourceClaimSnapshot",
    "artifact_registry_json_schema",
    "compare_artifacts",
    "evaluate_artifact_completeness",
    "evaluate_renderer_eligibility",
]
