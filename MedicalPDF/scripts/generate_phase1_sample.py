#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from medical_pdf.cli import main  # noqa: E402


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(
            [
                str(ROOT / "samples" / "phase1_type2_diabetes.json"),
                str(ROOT / "output" / "pdf" / "medicalpdf-phase1-type2-diabetes.pdf"),
            ]
        )
    raise SystemExit(main())
