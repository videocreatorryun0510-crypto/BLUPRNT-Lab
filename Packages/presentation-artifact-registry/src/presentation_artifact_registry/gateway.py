"""Official Registry-to-Renderer access boundary."""

from presentation_artifact import Renderer, RenderResult

from presentation_artifact_registry.sqlite_registry import (
    SQLitePresentationArtifactRegistry,
)


class ArtifactRendererGateway:
    """Prevent official Renderer flows from reading raw builder JSON."""

    def __init__(self, registry: SQLitePresentationArtifactRegistry) -> None:
        self._registry = registry

    def render(
        self,
        artifact_id: str,
        renderer: Renderer,
        *,
        artifact_version: int | None = None,
    ) -> RenderResult:
        artifact = self._registry.get_approved_for_render(
            artifact_id,
            artifact_version=artifact_version,
        )
        return renderer.render(artifact)
