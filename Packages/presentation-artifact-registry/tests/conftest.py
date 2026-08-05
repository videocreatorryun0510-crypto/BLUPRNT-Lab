"""Make local BLUPRNT packages importable during Registry tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for relative in (
    "Packages/presentation-artifact-registry/src",
    "Packages/knowledge-contracts/src",
    "Publishers/PresentationArtifact/src",
    "Publishers/PresentationRequestBuilder/src",
    "Publishers/SourceBundlePublisher/src",
    "Prototypes/KnowledgeWorkbench/src",
):
    sys.path.insert(0, str(ROOT / relative))
