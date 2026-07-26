from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from medical_pdf.domain import DiseaseSheet, SourceReference


NAVY = HexColor("#17324D")
TEAL = HexColor("#168C88")
TEAL_LIGHT = HexColor("#E8F5F3")
BLUE_LIGHT = HexColor("#EEF4F8")
RED = HexColor("#B5413E")
RED_LIGHT = HexColor("#FBEDEC")
GOLD = HexColor("#C98A14")
GOLD_LIGHT = HexColor("#FFF6DE")
INK = HexColor("#22313F")
MUTED = HexColor("#61717D")
BORDER = HexColor("#D6E0E6")
PAPER = HexColor("#FFFFFF")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 12 * mm
COLUMN_GAP = 8 * mm
CONTENT_BOTTOM = 56 * mm
REFERENCE_BOTTOM = 16 * mm
REFERENCE_HEIGHT = 36 * mm


class LayoutOverflowError(ValueError):
    """Raised when content cannot fit without clipping or unsafe shrinking."""


class ReportLabDiseaseSheetRenderer:
    def __init__(self, font_path: Path | None = None) -> None:
        self.font_name, self.font_source = _register_japanese_font(font_path)
        self.styles = _build_styles(self.font_name)

    def render(self, sheet: DiseaseSheet, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf = Canvas(str(output_path), pagesize=A4, pageCompression=1)
        pdf.setTitle(f"{sheet.disease_name} - MedicalPDF")
        pdf.setAuthor("BLUPRNT Lab")
        pdf.setSubject("Medical education draft sheet")
        pdf.setKeywords("medical education, BLUPRNT Lab, draft")

        self._draw_page_background(pdf)
        content_top = self._draw_header(pdf, sheet)
        self._draw_columns(pdf, sheet, content_top)
        self._draw_references(pdf, sheet.references)
        self._draw_footer(pdf, sheet)
        pdf.showPage()
        pdf.save()
        return output_path

    def _draw_page_background(self, pdf: Canvas) -> None:
        pdf.setFillColor(PAPER)
        pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)
        pdf.setFillColor(NAVY)
        pdf.rect(0, PAGE_HEIGHT - 5 * mm, PAGE_WIDTH, 5 * mm, stroke=0, fill=1)

    def _draw_header(self, pdf: Canvas, sheet: DiseaseSheet) -> float:
        top = PAGE_HEIGHT - MARGIN
        pdf.setFillColor(TEAL)
        pdf.setFont(self.font_name, 7.4)
        pdf.drawString(MARGIN, top - 1 * mm, "BLUPRNT LAB  /  MEDICAL PDF")

        badge_text = f"教育用ドラフト  |  {sheet.review_status.display_name}"
        badge_width = 51 * mm
        badge_height = 7 * mm
        badge_x = PAGE_WIDTH - MARGIN - badge_width
        badge_y = top - 5 * mm
        pdf.setFillColor(RED_LIGHT)
        pdf.roundRect(badge_x, badge_y, badge_width, badge_height, 3 * mm, stroke=0, fill=1)
        pdf.setFillColor(RED)
        pdf.setFont(self.font_name, 7.3)
        pdf.drawCentredString(badge_x + badge_width / 2, badge_y + 2.2 * mm, badge_text)

        title_top = top - 10 * mm
        title = Paragraph(escape(sheet.disease_name), self.styles["title"])
        title_width = PAGE_WIDTH - 2 * MARGIN
        _, title_height = title.wrap(title_width, 18 * mm)
        if title_height > 18 * mm:
            raise LayoutOverflowError("disease name exceeds the two-line title area")
        title.drawOn(pdf, MARGIN, title_top - title_height)

        subtitle_parts = [sheet.english_name]
        if sheet.aliases:
            subtitle_parts.append("別名: " + " / ".join(sheet.aliases))
        subtitle_text = "   |   ".join(subtitle_parts)
        subtitle = Paragraph(escape(subtitle_text), self.styles["subtitle"])
        _, subtitle_height = subtitle.wrap(title_width, 9 * mm)
        subtitle_y = title_top - title_height - 1.5 * mm - subtitle_height
        subtitle.drawOn(pdf, MARGIN, subtitle_y)

        summary_top = top - 35 * mm
        summary_height = self._measure_summary(sheet.one_line_summary)
        summary_bottom = summary_top - summary_height
        pdf.setFillColor(TEAL_LIGHT)
        pdf.roundRect(
            MARGIN,
            summary_bottom,
            PAGE_WIDTH - 2 * MARGIN,
            summary_height,
            3 * mm,
            stroke=0,
            fill=1,
        )
        pdf.setFillColor(TEAL)
        pdf.setFont(self.font_name, 8.5)
        pdf.drawString(MARGIN + 4 * mm, summary_top - 5.2 * mm, "ひとことで理解")
        summary = Paragraph(escape(sheet.one_line_summary), self.styles["summary"])
        summary_width = PAGE_WIDTH - 2 * MARGIN - 8 * mm
        _, paragraph_height = summary.wrap(summary_width, summary_height)
        summary.drawOn(pdf, MARGIN + 4 * mm, summary_bottom + 3.4 * mm)
        return summary_bottom - 4 * mm

    def _measure_summary(self, text: str) -> float:
        width = PAGE_WIDTH - 2 * MARGIN - 8 * mm
        paragraph = Paragraph(escape(text), self.styles["summary"])
        _, height = paragraph.wrap(width, 25 * mm)
        measured = height + 12 * mm
        if measured > 26 * mm:
            raise LayoutOverflowError("one-line summary is too long for the reserved area")
        return max(18 * mm, measured)

    def _draw_columns(self, pdf: Canvas, sheet: DiseaseSheet, content_top: float) -> None:
        column_width = (PAGE_WIDTH - 2 * MARGIN - COLUMN_GAP) / 2
        left_x = MARGIN
        right_x = MARGIN + column_width + COLUMN_GAP

        left_sections = (
            ("病態・原因", sheet.pathophysiology, NAVY, BLUE_LIGHT),
            ("症状・所見", sheet.symptoms_and_signs, TEAL, TEAL_LIGHT),
            ("検査・診断", sheet.diagnosis, NAVY, BLUE_LIGHT),
        )
        right_sections = (
            ("治療・管理", sheet.treatment, TEAL, TEAL_LIGHT),
            ("Red Flags", sheet.red_flags, RED, RED_LIGHT),
            ("国家試験ポイント", sheet.learning_points, GOLD, GOLD_LIGHT),
        )

        self._draw_section_column(pdf, left_x, column_width, content_top, left_sections)
        self._draw_section_column(pdf, right_x, column_width, content_top, right_sections)

    def _draw_section_column(
        self,
        pdf: Canvas,
        x: float,
        width: float,
        content_top: float,
        sections: tuple[tuple[str, tuple[str, ...], object, object], ...],
    ) -> None:
        minimum_heights = [self._measure_card(width, items) for _, items, _, _ in sections]
        total_gap = 3 * mm * (len(sections) - 1)
        available_height = content_top - CONTENT_BOTTOM
        minimum_total = sum(minimum_heights) + total_gap
        if minimum_total > available_height:
            raise LayoutOverflowError("section column exceeds the printable content area")

        distributable_height = available_height - minimum_total
        content_height = sum(minimum_heights)
        card_heights = [
            height + distributable_height * (height / content_height)
            for height in minimum_heights
        ]

        y = content_top
        for (title, items, accent, background), card_height in zip(
            sections,
            card_heights,
            strict=True,
        ):
            card_bottom = y - card_height
            self._draw_card(
                pdf,
                x=x,
                bottom=card_bottom,
                width=width,
                height=card_height,
                title=title,
                items=items,
                accent=accent,
                background=background,
            )
            y = card_bottom - 3 * mm

    def _measure_card(self, width: float, items: tuple[str, ...]) -> float:
        body_width = width - 8 * mm
        body_height = 0.0
        for item in items:
            paragraph = Paragraph("・" + escape(item), self.styles["body"])
            _, item_height = paragraph.wrap(body_width, 80 * mm)
            body_height += item_height + 1.2 * mm
        return 14 * mm + body_height

    def _draw_card(
        self,
        pdf: Canvas,
        *,
        x: float,
        bottom: float,
        width: float,
        height: float,
        title: str,
        items: tuple[str, ...],
        accent: object,
        background: object,
    ) -> None:
        pdf.setFillColor(background)
        pdf.setStrokeColor(BORDER)
        pdf.setLineWidth(0.5)
        pdf.roundRect(x, bottom, width, height, 2.5 * mm, stroke=1, fill=1)
        pdf.setFillColor(accent)
        pdf.roundRect(x, bottom, 2.2 * mm, height, 1.1 * mm, stroke=0, fill=1)
        pdf.setFont(self.font_name, 10)
        pdf.drawString(x + 4 * mm, bottom + height - 6.5 * mm, title)

        cursor = bottom + height - 11.8 * mm
        body_width = width - 8 * mm
        for item in items:
            paragraph = Paragraph("・" + escape(item), self.styles["body"])
            _, item_height = paragraph.wrap(body_width, 80 * mm)
            cursor -= item_height
            paragraph.drawOn(pdf, x + 4 * mm, cursor)
            cursor -= 1.2 * mm

    def _draw_references(
        self,
        pdf: Canvas,
        references: tuple[SourceReference, ...],
    ) -> None:
        width = PAGE_WIDTH - 2 * MARGIN
        pdf.setFillColor(HexColor("#F7F9FA"))
        pdf.setStrokeColor(BORDER)
        pdf.roundRect(
            MARGIN,
            REFERENCE_BOTTOM,
            width,
            REFERENCE_HEIGHT,
            2.5 * mm,
            stroke=1,
            fill=1,
        )
        pdf.setFillColor(NAVY)
        pdf.setFont(self.font_name, 9)
        pdf.drawString(MARGIN + 4 * mm, REFERENCE_BOTTOM + REFERENCE_HEIGHT - 6 * mm, "出典")

        cursor = REFERENCE_BOTTOM + REFERENCE_HEIGHT - 11 * mm
        body_width = width - 8 * mm
        for reference in references:
            text = (
                f"[{escape(reference.source_id)}] {escape(reference.publisher)}: "
                f"{escape(reference.title)} ({reference.published_year})  {escape(reference.url)}"
            )
            paragraph = Paragraph(text, self.styles["reference"])
            _, height = paragraph.wrap(body_width, 20 * mm)
            cursor -= height
            if cursor < REFERENCE_BOTTOM + 3 * mm:
                raise LayoutOverflowError("references exceed the reserved area")
            paragraph.drawOn(pdf, MARGIN + 4 * mm, cursor)
            cursor -= 1.2 * mm

    def _draw_footer(self, pdf: Canvas, sheet: DiseaseSheet) -> None:
        y = 9.5 * mm
        pdf.setStrokeColor(BORDER)
        pdf.line(MARGIN, y + 3 * mm, PAGE_WIDTH - MARGIN, y + 3 * mm)
        pdf.setFillColor(MUTED)
        pdf.setFont(self.font_name, 6.8)
        left_text = (
            f"文書ID: {sheet.document_id}  |  版: {sheet.content_version}  |  "
            f"生成: {sheet.generated_at.isoformat(timespec='minutes')}"
        )
        pdf.drawString(MARGIN, y, left_text)
        pdf.drawRightString(
            PAGE_WIDTH - MARGIN,
            y,
            "教育用資料です。患者個人の診療判断には"
            "使用しないでください。",
        )


def _build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName=font_name,
            fontSize=21,
            leading=24,
            textColor=NAVY,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=font_name,
            fontSize=7.8,
            leading=10,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "summary": ParagraphStyle(
            "summary",
            fontName=font_name,
            fontSize=9.3,
            leading=13,
            textColor=INK,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body",
            fontName=font_name,
            fontSize=8.2,
            leading=11.2,
            textColor=INK,
            wordWrap="CJK",
            splitLongWords=True,
        ),
        "reference": ParagraphStyle(
            "reference",
            fontName=font_name,
            fontSize=6.6,
            leading=8.6,
            textColor=MUTED,
            wordWrap="CJK",
            splitLongWords=True,
        ),
    }


def _register_japanese_font(font_path: Path | None) -> tuple[str, str]:
    explicit_path = font_path or _font_path_from_environment()
    candidates = tuple(
        path
        for path in (
            explicit_path,
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        )
        if path is not None
    )

    if explicit_path is not None and not explicit_path.is_file():
        raise FileNotFoundError(f"Japanese font not found: {explicit_path}")

    for candidate in candidates:
        if candidate.is_file():
            font_name = "MedicalPDFSans"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
            return font_name, str(candidate)

    fallback_name = "HeiseiKakuGo-W5"
    if fallback_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
    return fallback_name, "ReportLab built-in Japanese CID font"


def _font_path_from_environment() -> Path | None:
    value = os.environ.get("MEDICALPDF_FONT_PATH")
    return Path(value).expanduser() if value else None
