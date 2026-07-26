from __future__ import annotations

import unittest
from pathlib import Path

from medical_pdf.domain import DiseaseSheet
from medical_pdf.infrastructure.sample_loader import load_disease_sheet


ROOT = Path(__file__).resolve().parents[2]


class DiseaseSheetModelTest(unittest.TestCase):
    def test_phase1_sample_loads_as_typed_model(self) -> None:
        sheet = load_disease_sheet(ROOT / "samples" / "phase1_type2_diabetes.json")

        self.assertIsInstance(sheet, DiseaseSheet)
        self.assertEqual(sheet.disease_name, "2型糖尿病")
        self.assertEqual(len(sheet.references), 3)
        self.assertIn("医学監修前", sheet.required_pdf_labels)

    def test_less_than_two_references_is_rejected(self) -> None:
        sheet = load_disease_sheet(ROOT / "samples" / "phase1_type2_diabetes.json")
        payload = {
            field_name: getattr(sheet, field_name)
            for field_name in sheet.__dataclass_fields__
        }
        payload["references"] = sheet.references[:1]

        with self.assertRaisesRegex(ValueError, "at least two sources"):
            DiseaseSheet(**payload)


if __name__ == "__main__":
    unittest.main()
