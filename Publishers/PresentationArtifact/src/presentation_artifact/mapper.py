"""Provider-neutral draft-to-artifact mapping boundary for future AI drafts."""

from datetime import datetime
from typing import Annotated, Protocol

from presentation_request_builder import PresentationRequest
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from source_bundle_publisher import SourceBundle

from presentation_artifact.models import PresentationArtifact


class DraftPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int = Field(ge=1, le=200)
    headline: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    selected_claim_ids: tuple[str, ...]
    diagram_request_ids: tuple[str, ...]


class PresentationDraft(BaseModel):
    """Provider output normalized before it can become the SSOT Artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    created_at: datetime
    pages: tuple[DraftPage, ...] = Field(min_length=1, max_length=200)


class ArtifactMapper(Protocol):
    def map(
        self,
        draft: PresentationDraft,
        request: PresentationRequest,
        source_bundle: SourceBundle,
    ) -> PresentationArtifact: ...
