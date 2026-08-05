"""Official Registry-to-Renderer access boundary."""

from typing import Protocol

from presentation_artifact import Renderer, RenderResult

from presentation_artifact_registry.eligibility import (
    KnowledgeArtifactSourceSnapshot,
)
from presentation_artifact_registry.sqlite_registry import (
    SQLitePresentationArtifactRegistry,
)


class ArtifactSourceSnapshotProvider(Protocol):
    """Trusted boundary that reads the current Knowledge Registry state."""

    def snapshot_for(
        self,
        artifact_id: str,
        artifact_version: int | None,
    ) -> KnowledgeArtifactSourceSnapshot: ...


class ArtifactRendererGateway:
    """Prevent official Renderer flows from reading raw builder JSON."""

    def __init__(
        self,
        registry: SQLitePresentationArtifactRegistry,
        source_provider: ArtifactSourceSnapshotProvider,
    ) -> None:
        self._registry = registry
        self._source_provider = source_provider

    def render(
        self,
        artifact_id: str,
        renderer: Renderer,
        *,
        artifact_version: int | None = None,
    ) -> RenderResult:
        source_snapshot = self._source_provider.snapshot_for(
            artifact_id,
            artifact_version,
        )
        artifact = self._registry.get_approved_for_render(
            artifact_id,
            source_snapshot=source_snapshot,
            artifact_version=artifact_version,
        )
        return renderer.render(artifact)
