"""OpenAI adapter. No OpenAI types escape this module."""

from typing import Any

from knowledge_workbench.errors import ProviderConfigurationError, ProviderGenerationError
from knowledge_workbench.generation_models import GeneratedKnowledgeDraft
from knowledge_workbench.prompt_loader import load_knowledge_prompt
from knowledge_workbench.providers.base import GenerationResult


class OpenAIKnowledgeProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key and client is None:
            raise ProviderConfigurationError(
                "OpenAI APIキーが未設定です。OPENAI_API_KEYを設定してから再起動してください。"
            )
        self.model = model
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
        self._client = client

    def generate(self, term: str) -> GenerationResult:
        try:
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "developer", "content": load_knowledge_prompt()},
                    {
                        "role": "user",
                        "content": f"医療用語: {term}",
                    },
                ],
                text_format=GeneratedKnowledgeDraft,
            )
        except Exception as error:
            raise ProviderGenerationError(_safe_openai_error(error)) from error

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            if _contains_refusal(response):
                raise ProviderGenerationError(
                    "AIがこの入力への回答を生成しませんでした。別の医療用語で再実行してください。"
                )
            raise ProviderGenerationError(
                "AIから構造化されたJSONを受け取れませんでした。入力を確認して再実行してください。"
            )

        try:
            draft = (
                parsed
                if isinstance(parsed, GeneratedKnowledgeDraft)
                else GeneratedKnowledgeDraft.model_validate(parsed)
            )
        except Exception as error:
            message = "AIの回答をKnowledge JSONへ変換できませんでした。"
            raise ProviderGenerationError(message) from error

        return GenerationResult(
            draft=draft,
            provider=self.provider_name,
            model=self.model,
            provider_request_id=str(getattr(response, "id", "")),
        )


def _safe_openai_error(error: Exception) -> str:
    name = type(error).__name__
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return "OpenAI APIキーを確認してください。キーが無効、またはモデルの利用権限がありません。"
    if name == "RateLimitError":
        return "OpenAIの利用上限に達しました。少し待つか、API利用状況を確認してください。"
    if name in {"APITimeoutError", "APIConnectionError"}:
        return "OpenAIへ接続できませんでした。通信環境を確認して再実行してください。"
    return "OpenAIで生成できませんでした。時間を置いて再実行してください。"


def _contains_refusal(response: Any) -> bool:
    for output in getattr(response, "output", []):
        for item in getattr(output, "content", []):
            if getattr(item, "type", "") == "refusal":
                return True
    return False
