"""Make local BLUPRNT packages importable during contract tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for relative in (
    "Publishers/PresentationArtifact/src",
    "Publishers/PresentationRequestBuilder/src",
    "Publishers/SourceBundlePublisher/src",
    "Packages/knowledge-contracts/src",
    "Prototypes/KnowledgeWorkbench/src",
):
    sys.path.insert(0, str(ROOT / relative))
