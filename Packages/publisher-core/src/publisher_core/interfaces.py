"""Exchangeable interfaces; Phase 3.0 deliberately provides no implementation."""

from typing import Protocol

from publisher_core.catalog import ResolvedTemplate
from publisher_core.models import (
    OutputKind,
    PlannedVisual,
    PublicationArtifact,
    PublicationPlan,
    VisualAssetReference,
)
from publisher_core.source import PublicationSourceBundle


class VisualGenerationProvider(Protocol):
    """Implemented later by GPT Image, Gemini, SVG generators, or other providers."""

    @property
    def provider_id(self) -> str: ...

    def supports(self, capability_id: str, representation: str) -> bool: ...

    def generate(
        self,
        visual: PlannedVisual,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
    ) -> VisualAssetReference: ...


class PublisherAdapter(Protocol):
    """Implemented later by PDF, note, TrainingVideo and NationalExam adapters."""

    @property
    def output_kind(self) -> OutputKind: ...

    def publish(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
        visual_assets: tuple[VisualAssetReference, ...],
    ) -> PublicationArtifact: ...
