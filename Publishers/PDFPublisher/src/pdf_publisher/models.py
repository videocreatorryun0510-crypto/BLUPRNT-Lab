"""Immutable render models used after the shared Publication Plan is resolved."""

from typing import Literal

from publisher_core import (
    PlacementKind,
    ProfileReference,
    VisualRepresentation,
)
from publisher_core.models import FrozenModel, SemanticVersion, StableKey
from pydantic import Field


class RenderContentBlock(FrozenModel):
    block_id: StableKey
    title: str = Field(min_length=1, max_length=180)
    items: tuple[str, ...] = Field(min_length=1, max_length=50)
    source_claim_ids: tuple[str, ...] = Field(default=(), max_length=100)


class RenderVisualBlock(FrozenModel):
    block_id: StableKey
    visual_type: StableKey
    title: str = Field(min_length=1, max_length=180)
    caption: str | None = Field(default=None, max_length=300)
    representation: VisualRepresentation
    claim_keys: tuple[str, ...] = Field(min_length=1, max_length=100)
    requires_ai_generation: bool


class RenderPlacement(FrozenModel):
    placement_id: StableKey
    item_kind: PlacementKind
    item_id: StableKey
    region_id: StableKey
    order: int = Field(ge=1, le=200)


class PdfRenderPlan(FrozenModel):
    render_plan_version: Literal["1.0"]
    request_id: StableKey
    title: str = Field(min_length=1, max_length=180)
    subtitle: str = Field(min_length=1, max_length=300)
    review_badge: str = Field(min_length=1, max_length=120)
    content_blocks: tuple[RenderContentBlock, ...]
    visual_blocks: tuple[RenderVisualBlock, ...]
    placements: tuple[RenderPlacement, ...]
    layout_profile_ref: ProfileReference
    theme_ref: ProfileReference
    design_system_ref: ProfileReference
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class Rect(FrozenModel):
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class PositionedBlock(FrozenModel):
    placement_id: StableKey
    item_kind: PlacementKind
    item_id: StableKey
    region_id: StableKey
    rect: Rect


class PdfLayout(FrozenModel):
    layout_engine_version: SemanticVersion
    page_width_points: float = Field(gt=0)
    page_height_points: float = Field(gt=0)
    blocks: tuple[PositionedBlock, ...]


class PdfTheme(FrozenModel):
    theme_engine_version: SemanticVersion
    background_color: str
    surface_color: str
    primary_color: str
    accent_color: str
    warning_color: str
    text_color: str
    muted_color: str
    border_color: str
    font_name: str
    font_source: str
    spacing_small_points: float = Field(ge=0)
    spacing_medium_points: float = Field(ge=0)
    spacing_large_points: float = Field(ge=0)
