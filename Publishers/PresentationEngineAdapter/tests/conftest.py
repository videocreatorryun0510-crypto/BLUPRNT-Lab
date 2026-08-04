"""Make editable BLUPRNT source trees importable without installation."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
for source in (
    REPOSITORY_ROOT / "Packages" / "knowledge-contracts" / "src",
    REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "src",
    REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "src",
    REPOSITORY_ROOT / "Publishers" / "PresentationPromptBuilder" / "src",
    REPOSITORY_ROOT / "Publishers" / "ProviderPayloadResolver" / "src",
    REPOSITORY_ROOT / "Publishers" / "PresentationEngineAdapter" / "src",
    REPOSITORY_ROOT / "Prototypes" / "KnowledgeWorkbench" / "src",
):
    sys.path.insert(0, str(source))
