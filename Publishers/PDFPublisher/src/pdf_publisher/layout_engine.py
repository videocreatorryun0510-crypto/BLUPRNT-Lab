"""Map abstract Layout Profile regions to the A4 Version 1 canvas."""

from collections import defaultdict

from publisher_core import LayoutProfile, PlacementKind
from reportlab.lib.pagesizes import A4

from pdf_publisher.models import (
    PdfLayout,
    PdfRenderPlan,
    PositionedBlock,
    Rect,
    RenderPlacement,
)


class PdfLayoutError(ValueError):
    """Raised when the selected Layout cannot fit the A4 Version 1 canvas."""


REGION_RECTS = {
    "region.title": Rect(x=34, y=698, width=527, height=54),
    "region.hero": Rect(x=34, y=548, width=527, height=140),
    "region.explanation": Rect(x=34, y=329, width=252, height=207),
    "region.comparison": Rect(x=298, y=329, width=263, height=207),
    "region.exam_points": Rect(x=34, y=72, width=252, height=245),
    "region.summary": Rect(x=298, y=72, width=263, height=245),
}


class A4LayoutEngine:
    version = "1.0.0"

    def layout(self, plan: PdfRenderPlan, profile: LayoutProfile) -> PdfLayout:
        if profile.profile_id != plan.layout_profile_ref.profile_id:
            raise PdfLayoutError("Render PlanとLayout Profileが一致しません。")
        region_ids = {item.region_id for item in profile.regions}
        missing_geometry = region_ids - set(REGION_RECTS)
        if missing_geometry:
            raise PdfLayoutError(
                "A4 Version 1に未定義のLayout領域があります: " + ", ".join(sorted(missing_geometry))
            )
        content_ids = {item.block_id for item in plan.content_blocks}
        visual_ids = {item.block_id for item in plan.visual_blocks}
        grouped: dict[str, list[RenderPlacement]] = defaultdict(list)
        for placement in sorted(plan.placements, key=lambda item: item.order):
            known = content_ids if placement.item_kind == PlacementKind.CONTENT else visual_ids
            if placement.item_id not in known:
                continue
            grouped[placement.region_id].append(placement)

        blocks: list[PositionedBlock] = []
        gap = 7.0
        for region_id, placements in grouped.items():
            outer = REGION_RECTS[region_id]
            if not placements:
                continue
            available_height = outer.height - gap * (len(placements) - 1)
            block_height = available_height / len(placements)
            if block_height < 42:
                raise PdfLayoutError(f"Layout領域が不足しています: {region_id}")
            cursor_top = outer.y + outer.height
            for placement in placements:
                block_y = cursor_top - block_height
                blocks.append(
                    PositionedBlock(
                        placement_id=placement.placement_id,
                        item_kind=placement.item_kind,
                        item_id=placement.item_id,
                        region_id=region_id,
                        rect=Rect(
                            x=outer.x,
                            y=block_y,
                            width=outer.width,
                            height=block_height,
                        ),
                    )
                )
                cursor_top = block_y - gap
        return PdfLayout(
            layout_engine_version=self.version,
            page_width_points=float(A4[0]),
            page_height_points=float(A4[1]),
            blocks=tuple(blocks),
        )
