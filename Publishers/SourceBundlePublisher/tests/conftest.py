"""Make Publisher, contracts and Workbench test helpers importable."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(
        REPOSITORY_ROOT
        / "Publishers"
        / "SourceBundlePublisher"
        / "src"
    ),
)
sys.path.insert(
    0,
    str(REPOSITORY_ROOT / "Packages" / "knowledge-contracts" / "src"),
)
sys.path.insert(
    0,
    str(REPOSITORY_ROOT / "Prototypes" / "KnowledgeWorkbench" / "src"),
)
