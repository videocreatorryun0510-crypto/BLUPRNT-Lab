"""Draw intentionally obvious placeholders instead of generating medical figures."""

from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from pdf_publisher.models import PdfTheme, Rect, RenderVisualBlock


class PlaceholderVisualRenderer:
    def draw(
        self,
        canvas: Canvas,
        visual: RenderVisualBlock,
        rect: Rect,
        theme: PdfTheme,
    ) -> None:
        inset = 3.5
        canvas.saveState()
        canvas.setFillColor(HexColor(theme.background_color))
        canvas.setStrokeColor(HexColor(theme.accent_color))
        canvas.setLineWidth(1.1)
        canvas.setDash(5, 3)
        canvas.roundRect(
            rect.x,
            rect.y,
            rect.width,
            rect.height,
            8,
            stroke=1,
            fill=1,
        )
        canvas.setDash()
        canvas.setFillColor(HexColor(theme.accent_color))
        canvas.setFont(theme.font_name, 6.7)
        canvas.drawString(rect.x + 9, rect.y + rect.height - 14, "VISUAL PLACEHOLDER")

        status = (
            "AI generation: required / not connected"
            if visual.requires_ai_generation
            else "Renderer: not connected"
        )
        representation = visual.representation.value.replace("_", " ").upper()
        text = (
            f"<b>{escape(visual.title)}</b><br/>"
            f"{escape(visual.caption or visual.visual_type)}<br/>"
            f"<font size='6.4'>{escape(representation)} / {escape(status)}</font>"
        )
        paragraph = Paragraph(
            text,
            ParagraphStyle(
                "visual-placeholder",
                fontName=theme.font_name,
                fontSize=10.5,
                leading=14,
                alignment=TA_CENTER,
                textColor=HexColor(theme.primary_color),
                wordWrap="CJK",
            ),
        )
        width = rect.width - 2 * inset - 18
        _, height = paragraph.wrap(width, rect.height - 30)
        paragraph.drawOn(
            canvas,
            rect.x + inset + 9,
            rect.y + max(18, (rect.height - height) / 2 - 1),
        )
        canvas.restoreState()
