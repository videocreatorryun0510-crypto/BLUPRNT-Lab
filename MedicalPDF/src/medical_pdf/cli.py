from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_pdf.application import generate_disease_sheet
from medical_pdf.infrastructure.pdf import ReportLabDiseaseSheetRenderer
from medical_pdf.infrastructure.sample_loader import load_disease_sheet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and validate the MedicalPDF Phase 1 A4 sample."
    )
    parser.add_argument("input", type=Path, help="Path to a disease sheet JSON file")
    parser.add_argument("output", type=Path, help="Path for the generated PDF")
    parser.add_argument(
        "--font",
        type=Path,
        default=None,
        help="Optional Japanese TrueType/OpenType font path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    sheet = load_disease_sheet(args.input)
    renderer = ReportLabDiseaseSheetRenderer(font_path=args.font)
    result = generate_disease_sheet(sheet, args.output, renderer)
    summary = {
        "status": "success",
        "output_path": str(result.output_path.resolve()),
        "page_count": result.inspection.page_count,
        "page_size_mm": [
            round(result.inspection.page_width_mm, 1),
            round(result.inspection.page_height_mm, 1),
        ],
        "font_source": result.font_source,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
