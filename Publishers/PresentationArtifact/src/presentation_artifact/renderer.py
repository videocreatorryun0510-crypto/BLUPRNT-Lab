"""Renderer boundary; concrete media renderers are intentionally deferred."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from presentation_artifact.models import PresentationArtifact


class RenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    renderer_name: str
    artifact_id: str
    output_paths: tuple[str, ...]


class Renderer(Protocol):
    """PowerPoint, PDF, HTML and other renderers implement this contract."""

    def render(self, artifact: PresentationArtifact) -> RenderResult: ...
