from __future__ import annotations

import json
from pathlib import Path

from medical_pdf.domain import DiseaseSheet


def load_disease_sheet(path: Path) -> DiseaseSheet:
    with path.open(encoding="utf-8") as source_file:
        payload = json.load(source_file)
    if not isinstance(payload, dict):
        raise ValueError("disease sheet JSON must be an object")
    return DiseaseSheet.from_mapping(payload)
