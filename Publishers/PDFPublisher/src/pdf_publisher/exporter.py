"""ReportLab A4 exporter driven only by PdfRenderPlan, Layout and Theme."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from pdf_publisher.models import PdfLayout, PdfRenderPlan, PdfTheme, Rect, RenderContentBlock
from pdf_publisher.visual_renderer import PlaceholderVisualRenderer


class PdfExportError(ValueError):
    """Raised when content does not fit the one-page PDF contract."""


class PdfExporter:
    def __init__(self, visual_renderer: PlaceholderVisualRenderer | None = None) -> None:
        self._visual_renderer = visual_renderer or PlaceholderVisualRenderer()

    def export(
        self,
        plan: PdfRenderPlan,
        layout: PdfLayout,
        theme: PdfTheme,
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas = Canvas(
            str(output_path),
            pagesize=(layout.page_width_points, layout.page_height_points),
            pageCompression=1,
            invariant=1,
        )
        canvas.setTitle(f"{plan.title} - National Exam PDF Version 1")
        canvas.setAuthor("BLUPRNT Lab")
        canvas.setSubject("Clinical laboratory technologist national exam review material")
        self._draw_background(canvas, layout, theme)
        self._draw_header(canvas, plan, layout, theme)
        content = {item.block_id: item for item in plan.content_blocks}
        visuals = {item.block_id: item for item in plan.visual_blocks}
        for positioned in layout.blocks:
            if positioned.item_kind.value == "content":
                block = content.get(positioned.item_id)
                if block is not None:
                    self._draw_content_block(canvas, block, positioned.rect, theme)
            else:
                visual = visuals.get(positioned.item_id)
                if visual is not None:
                    self._visual_renderer.draw(canvas, visual, positioned.rect, theme)
        self._draw_footer(canvas, plan, layout, theme)
        canvas.showPage()
        canvas.save()
        return output_path

    def _draw_background(self, canvas: Canvas, layout: PdfLayout, theme: PdfTheme) -> None:
        canvas.setFillColor(HexColor(theme.background_color))
        canvas.rect(
            0,
            0,
            layout.page_width_points,
            layout.page_height_points,
            stroke=0,
            fill=1,
        )
        canvas.setFillColor(HexColor(theme.primary_color))
        canvas.rect(
            0,
            layout.page_height_points - 15,
            layout.page_width_points,
            15,
            stroke=0,
            fill=1,
        )

    def _draw_header(
        self, canvas: Canvas, plan: PdfRenderPlan, layout: PdfLayout, theme: PdfTheme
    ) -> None:
        top = layout.page_height_points - 30
        canvas.setFillColor(HexColor(theme.accent_color))
        canvas.setFont(theme.font_name, 7.2)
        canvas.drawString(34, top, "BLUPRNT LAB / NATIONAL EXAM PDF / VERSION 1")

        badge_width = 156
        badge_height = 19
        badge_x = layout.page_width_points - 34 - badge_width
        badge_y = top - 5
        canvas.setFillColor(HexColor("#FFF2D9"))
        canvas.roundRect(badge_x, badge_y, badge_width, badge_height, 9, stroke=0, fill=1)
        canvas.setFillColor(HexColor(theme.warning_color))
        canvas.setFont(theme.font_name, 6.5)
        canvas.drawCentredString(badge_x + badge_width / 2, badge_y + 6.5, plan.review_badge)

        canvas.setFillColor(HexColor(theme.primary_color))
        canvas.setFont(theme.font_name, 27)
        canvas.drawString(34, top - 39, plan.title)
        canvas.setFillColor(HexColor(theme.muted_color))
        canvas.setFont(theme.font_name, 7.2)
        canvas.drawString(34, top - 55, plan.subtitle)

    def _draw_content_block(
        self,
        canvas: Canvas,
        block: RenderContentBlock,
        rect: Rect,
        theme: PdfTheme,
    ) -> None:
        canvas.setFillColor(HexColor(theme.surface_color))
        canvas.setStrokeColor(HexColor(theme.border_color))
        canvas.setLineWidth(0.6)
        canvas.roundRect(
            rect.x,
            rect.y,
            rect.width,
            rect.height,
            7,
            stroke=1,
            fill=1,
        )
        canvas.setFillColor(HexColor(theme.accent_color))
        canvas.roundRect(rect.x, rect.y, 4, rect.height, 2, stroke=0, fill=1)
        canvas.setFillColor(HexColor(theme.primary_color))
        canvas.setFont(theme.font_name, 9.2)
        canvas.drawString(rect.x + 12, rect.y + rect.height - 18, block.title)

        body_style = ParagraphStyle(
            "content-body",
            fontName=theme.font_name,
            fontSize=7.4,
            leading=10.2,
            textColor=HexColor(theme.text_color),
            alignment=TA_LEFT,
            wordWrap="CJK",
            splitLongWords=True,
        )
        cursor = rect.y + rect.height - 31
        available_width = rect.width - 25
        for item in block.items:
            paragraph = Paragraph("・" + escape(item), body_style)
            _, height = paragraph.wrap(available_width, rect.height)
            cursor -= height
            if cursor < rect.y + 9:
                raise PdfExportError(f"A4一枚に収まりません: {block.block_id}")
            paragraph.drawOn(canvas, rect.x + 13, cursor)
            cursor -= 4

    def _draw_footer(
        self, canvas: Canvas, plan: PdfRenderPlan, layout: PdfLayout, theme: PdfTheme
    ) -> None:
        y = 33
        canvas.setStrokeColor(HexColor(theme.border_color))
        canvas.line(34, y + 10, layout.page_width_points - 34, y + 10)
        canvas.setFillColor(HexColor(theme.muted_color))
        canvas.setFont(theme.font_name, 5.8)
        canvas.drawString(
            34,
            y,
            f"Plan: {plan.request_id} / Source: {plan.source_fingerprint[:12]}",
        )
        canvas.drawRightString(
            layout.page_width_points - 34,
            y,
            "構造レビュー用資料です。公開前に医学監修と出典確認が必要です。",
        )
