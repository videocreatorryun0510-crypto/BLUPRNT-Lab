"""Make Presentation, Source Bundle, Registry and Workbench sources importable."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
for source_path in (
    REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "src",
    REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "src",
    REPOSITORY_ROOT / "Packages" / "knowledge-contracts" / "src",
    REPOSITORY_ROOT / "Prototypes" / "KnowledgeWorkbench" / "src",
):
    sys.path.insert(0, str(source_path))
