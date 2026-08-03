"""Make both editable source trees importable even before installation."""

import sys
from pathlib import Path

REPOSITORY_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_DIR / "Packages" / "knowledge-contracts" / "src"))
sys.path.insert(
    0,
    str(REPOSITORY_DIR / "Publishers" / "SourceBundlePublisher" / "src"),
)
sys.path.insert(
    0,
    str(REPOSITORY_DIR / "Publishers" / "PresentationRequestBuilder" / "src"),
)
sys.path.insert(
    0,
    str(REPOSITORY_DIR / "Publishers" / "PresentationEngineAdapter" / "src"),
)
sys.path.insert(0, str(REPOSITORY_DIR / "Prototypes" / "KnowledgeWorkbench" / "src"))
