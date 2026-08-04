"""Make editable BLUPRNT source packages importable."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for relative in (
    "Packages/knowledge-contracts/src",
    "Publishers/SourceBundlePublisher/src",
    "Publishers/PresentationRequestBuilder/src",
    "Publishers/ProviderPayloadResolver/src",
    "Publishers/PresentationPromptBuilder/src",
    "Prototypes/KnowledgeWorkbench/src",
):
    sys.path.insert(0, str(ROOT / relative))
