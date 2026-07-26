from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pdfplumber
from pypdf import PdfReader


POINTS_PER_MM = 72 / 25.4
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0


class PdfValidationError(ValueError):
    """Raised when a generated PDF fails Phase 1 quality gates."""


@dataclass(frozen=True, slots=True)
class PdfInspectionResult:
    path: Path
    page_count: int
    page_width_mm: float
    page_height_mm: float
    extracted_text: str
    missing_labels: tuple[str, ...]
    out_of_bounds_character_count: int
    has_replacement_glyph: bool

    @property
    def is_single_page(self) -> bool:
        return self.page_count == 1

    @property
    def is_a4_portrait(self) -> bool:
        return (
            abs(self.page_width_mm - A4_WIDTH_MM) <= 0.5
            and abs(self.page_height_mm - A4_HEIGHT_MM) <= 0.5
        )

    @property
    def is_valid(self) -> bool:
        return (
            self.is_single_page
            and self.is_a4_portrait
            and not self.missing_labels
            and self.out_of_bounds_character_count == 0
            and not self.has_replacement_glyph
        )

    def ensure_valid(self) -> None:
        failures: list[str] = []
        if not self.is_single_page:
            failures.append(f"expected one page, got {self.page_count}")
        if not self.is_a4_portrait:
            failures.append(
                f"expected A4 portrait, got {self.page_width_mm:.1f} x "
                f"{self.page_height_mm:.1f} mm"
            )
        if self.missing_labels:
            failures.append("missing labels: " + ", ".join(self.missing_labels))
        if self.out_of_bounds_character_count:
            failures.append(
                f"{self.out_of_bounds_character_count} text glyphs are outside the page"
            )
        if self.has_replacement_glyph:
            failures.append("replacement or unreadable glyph detected")
        if failures:
            raise PdfValidationError("; ".join(failures))


def inspect_pdf(path: Path, required_labels: Iterable[str] = ()) -> PdfInspectionResult:
    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfValidationError("PDF contains no pages")

    first_page = reader.pages[0]
    width_points = float(first_page.mediabox.width)
    height_points = float(first_page.mediabox.height)

    extracted_pages: list[str] = []
    out_of_bounds = 0
    with pdfplumber.open(path) as document:
        for page in document.pages:
            extracted_pages.append(page.extract_text() or "")
            for character in page.chars:
                if (
                    float(character["x0"]) < -0.5
                    or float(character["x1"]) > float(page.width) + 0.5
                    or float(character["top"]) < -0.5
                    or float(character["bottom"]) > float(page.height) + 0.5
                ):
                    out_of_bounds += 1

    extracted_text = "\n".join(extracted_pages)
    normalized_text = _without_whitespace(extracted_text)
    missing_labels = tuple(
        label for label in required_labels if _without_whitespace(label) not in normalized_text
    )
    return PdfInspectionResult(
        path=path,
        page_count=page_count,
        page_width_mm=width_points / POINTS_PER_MM,
        page_height_mm=height_points / POINTS_PER_MM,
        extracted_text=extracted_text,
        missing_labels=missing_labels,
        out_of_bounds_character_count=out_of_bounds,
        has_replacement_glyph="\ufffd" in extracted_text or "■" in extracted_text,
    )


def _without_whitespace(value: str) -> str:
    return "".join(value.split())
