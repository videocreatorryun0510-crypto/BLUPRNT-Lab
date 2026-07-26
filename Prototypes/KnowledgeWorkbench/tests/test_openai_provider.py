from types import SimpleNamespace

from knowledge_workbench.generation_models import GeneratedKnowledgeDraft
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.providers.openai_provider import OpenAIKnowledgeProvider


class FakeResponses:
    def __init__(self, draft: GeneratedKnowledgeDraft) -> None:
        self.draft = draft
        self.call: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.call = kwargs
        return SimpleNamespace(id="response_test_123", output_parsed=self.draft)


def test_openai_adapter_uses_structured_output_without_leaking_openai_types() -> None:
    draft = FixtureKnowledgeProvider().generate("AST").draft
    responses = FakeResponses(draft)
    client = SimpleNamespace(responses=responses)
    provider = OpenAIKnowledgeProvider(api_key="", model="test-model", client=client)

    result = provider.generate("AST")

    assert result.draft == draft
    assert result.provider == "openai"
    assert result.model == "test-model"
    assert result.provider_request_id == "response_test_123"
    assert responses.call["text_format"] is GeneratedKnowledgeDraft
