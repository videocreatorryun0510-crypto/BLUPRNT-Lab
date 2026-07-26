"""Resolve presentation-only Theme tokens for ReportLab."""

import os
from pathlib import Path

from publisher_core import ThemeProfile
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from pdf_publisher.models import PdfTheme


class PdfThemeError(ValueError):
    """Raised when the selected Theme is incomplete for PDF rendering."""


class PdfThemeEngine:
    version = "1.0.0"

    def resolve(self, profile: ThemeProfile) -> PdfTheme:
        colors = {item.token: item.value for item in profile.colors}
        spacing = {item.token: item.value_rem * 12 for item in profile.spacing}
        required_colors = (
            "color.background",
            "color.surface",
            "color.primary",
            "color.accent",
            "color.warning",
            "color.text",
        )
        missing = set(required_colors) - set(colors)
        if missing:
            raise PdfThemeError(
                "PDF Themeに必要なColor Tokenがありません: " + ", ".join(sorted(missing))
            )
        font_name, font_source = _register_japanese_font()
        return PdfTheme(
            theme_engine_version=self.version,
            background_color=colors["color.background"],
            surface_color=colors["color.surface"],
            primary_color=colors["color.primary"],
            accent_color=colors["color.accent"],
            warning_color=colors["color.warning"],
            text_color=colors["color.text"],
            muted_color="#607080",
            border_color="#D4DEE7",
            font_name=font_name,
            font_source=font_source,
            spacing_small_points=spacing.get("space.sm", 6),
            spacing_medium_points=spacing.get("space.md", 12),
            spacing_large_points=spacing.get("space.lg", 18),
        )


def _register_japanese_font() -> tuple[str, str]:
    environment_path = os.environ.get("PDF_PUBLISHER_FONT_PATH")
    candidates = tuple(
        path
        for path in (
            Path(environment_path).expanduser() if environment_path else None,
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        )
        if path is not None
    )
    if environment_path and not candidates[0].is_file():
        raise PdfThemeError(f"日本語Fontが見つかりません: {candidates[0]}")
    for candidate in candidates:
        if candidate.is_file():
            font_name = "BluprntPdfSans"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
            return font_name, str(candidate)
    fallback_name = "HeiseiKakuGo-W5"
    if fallback_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
    return fallback_name, "ReportLab built-in Japanese CID font"
