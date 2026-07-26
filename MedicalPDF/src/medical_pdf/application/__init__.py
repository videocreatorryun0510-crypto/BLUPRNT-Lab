"""Application use cases for MedicalPDF."""

from medical_pdf.application.generate_disease_sheet import (
    DiseaseSheetGenerationResult,
    generate_disease_sheet,
)

__all__ = ["DiseaseSheetGenerationResult", "generate_disease_sheet"]
