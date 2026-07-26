from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from medical_pdf.application import generate_disease_sheet
from medical_pdf.infrastructure.pdf import LayoutOverflowError, ReportLabDiseaseSheetRenderer
from medical_pdf.infrastructure.sample_loader import load_disease_sheet


ROOT = Path(__file__).resolve().parents[2]


class LayoutLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sheet = load_disease_sheet(ROOT / "samples" / "phase1_type2_diabetes.json")
        self.renderer = ReportLabDiseaseSheetRenderer()

    def test_long_disease_name_still_fits_one_page(self) -> None:
        long_name = (
            "遺伝性インスリン作用異常による糖尿病"
            "（長い疾患名のレイアウト検証）"
        )
        sheet = replace(self.sheet, disease_name=long_name)

        with tempfile.TemporaryDirectory() as temp_directory:
            result = generate_disease_sheet(
                sheet,
                Path(temp_directory) / "long-title.pdf",
                self.renderer,
            )

            self.assertTrue(result.inspection.is_valid)
            normalized_title = "".join(long_name.split())
            normalized_pdf_text = "".join(result.inspection.extracted_text.split())
            self.assertIn(normalized_title, normalized_pdf_text)

    def test_excessive_content_fails_instead_of_clipping(self) -> None:
        excessive_item = "情報過多を検出するための長文です。" * 80
        sheet = replace(self.sheet, pathophysiology=(excessive_item,))

        with tempfile.TemporaryDirectory() as temp_directory:
            with self.assertRaises(LayoutOverflowError):
                self.renderer.render(sheet, Path(temp_directory) / "overflow.pdf")


if __name__ == "__main__":
    unittest.main()
