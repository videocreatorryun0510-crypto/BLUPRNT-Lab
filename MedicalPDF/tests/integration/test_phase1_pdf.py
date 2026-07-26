from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from medical_pdf.application import generate_disease_sheet
from medical_pdf.infrastructure.pdf import ReportLabDiseaseSheetRenderer
from medical_pdf.infrastructure.sample_loader import load_disease_sheet


ROOT = Path(__file__).resolve().parents[2]


class Phase1PdfIntegrationTest(unittest.TestCase):
    def test_sample_generates_valid_single_page_a4_pdf(self) -> None:
        sheet = load_disease_sheet(ROOT / "samples" / "phase1_type2_diabetes.json")
        renderer = ReportLabDiseaseSheetRenderer()

        with tempfile.TemporaryDirectory() as temp_directory:
            output_path = Path(temp_directory) / "phase1.pdf"
            result = generate_disease_sheet(sheet, output_path, renderer)

            self.assertTrue(result.output_path.is_file())
            self.assertTrue(result.inspection.is_valid)
            self.assertEqual(result.inspection.page_count, 1)
            self.assertAlmostEqual(result.inspection.page_width_mm, 210.0, delta=0.5)
            self.assertAlmostEqual(result.inspection.page_height_mm, 297.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
