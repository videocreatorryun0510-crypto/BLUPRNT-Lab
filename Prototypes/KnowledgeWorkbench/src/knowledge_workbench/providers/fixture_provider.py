"""Deterministic non-AI provider for the five approved prototype test themes."""

import json
from pathlib import Path

from knowledge_workbench.errors import ProviderGenerationError
from knowledge_workbench.generation_models import GeneratedKnowledgeDraft
from knowledge_workbench.providers.base import GenerationResult


class FixtureKnowledgeProvider:
    """Never used as an AI provider; this exists for offline verification only."""

    provider_name = "test_fixture"
    model = "five-themes-v0.3"

    def __init__(self) -> None:
        fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "five_themes_v0.3.json"
        self._fixtures: dict[str, object] = json.loads(fixture_path.read_text(encoding="utf-8"))

    def generate(self, term: str) -> GenerationResult:
        raw = self._fixtures.get(term)
        if raw is None:
            supported = "、".join(self._fixtures)
            raise ProviderGenerationError(
                f"固定テストでは「{supported}」だけ確認できます。OpenAIモードでは任意の用語を入力できます。"
            )
        return GenerationResult(
            draft=GeneratedKnowledgeDraft.model_validate(raw),
            provider=self.provider_name,
            model=self.model,
            provider_request_id=f"fixture-{term}",
        )
