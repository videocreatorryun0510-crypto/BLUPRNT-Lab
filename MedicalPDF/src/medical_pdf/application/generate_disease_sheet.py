from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from medical_pdf.domain import DiseaseSheet
from medical_pdf.validation import PdfInspectionResult, inspect_pdf


class DiseaseSheetRenderer(Protocol):
    font_source: str

    def render(self, sheet: DiseaseSheet, output_path: Path) -> Path: ...


@dataclass(frozen=True, slots=True)
class DiseaseSheetGenerationResult:
    output_path: Path
    inspection: PdfInspectionResult
    font_source: str


def generate_disease_sheet(
    sheet: DiseaseSheet,
    output_path: Path,
    renderer: DiseaseSheetRenderer,
) -> DiseaseSheetGenerationResult:
    rendered_path = renderer.render(sheet, output_path)
    inspection = inspect_pdf(rendered_path, sheet.required_pdf_labels)
    inspection.ensure_valid()
    return DiseaseSheetGenerationResult(
        output_path=rendered_path,
        inspection=inspection,
        font_source=renderer.font_source,
    )
