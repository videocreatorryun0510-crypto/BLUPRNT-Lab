"""Gemini Interactions adapter for provider-neutral Claim candidate extraction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from knowledge_workbench.claim_candidate_models import (
    ClaimAdapterResult,
    ClaimAdapterUsage,
    ClaimGenerationErrorCode,
    ClaimGenerationRequest,
    StructuredClaimCandidateResponse,
)
from knowledge_workbench.claim_generation_interfaces import ClaimGenerationAdapterError
from knowledge_workbench.claim_prompt_builder import (
    ClaimGenerationPrompt,
    EvidenceGroundedClaimPromptBuilder,
)


@dataclass(frozen=True)
class GeminiClaimAdapterConfig:
    api_key: str
    model: str = "gemini-3.6-flash"
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    timeout_seconds: float = 30.0
    retry_limit: int = 1
    max_output_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Gemini Claim model is required")
        if self.timeout_seconds <= 0:
            raise ValueError("Gemini Claim timeout must be positive")
        if self.retry_limit not in (0, 1):
            raise ValueError("Gemini Claim retry_limit must be 0 or 1")
        if not 256 <= self.max_output_tokens <= 8192:
            raise ValueError("Gemini Claim max_output_tokens must be 256-8192")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme != "https" or parsed.netloc != "generativelanguage.googleapis.com":
            raise ValueError("Gemini Claim endpoint must use the official Google HTTPS host")


@dataclass(frozen=True)
class GeminiClaimHttpResponse:
    status_code: int
    content: bytes


class GeminiClaimTransportTimeout(RuntimeError):
    pass


class GeminiClaimTransportNetworkError(RuntimeError):
    pass


class GeminiClaimTransport(Protocol):
    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GeminiClaimHttpResponse: ...


class HttpxGeminiClaimTransport:
    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GeminiClaimHttpResponse:
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "x-goog-api-key": api_key,
                        "content-type": "application/json",
                        "Api-Revision": "2026-05-20",
                    },
                    json=body,
                )
        except httpx.TimeoutException as error:
            raise GeminiClaimTransportTimeout from error
        except httpx.NetworkError as error:
            raise GeminiClaimTransportNetworkError from error
        return GeminiClaimHttpResponse(
            status_code=response.status_code,
            content=response.content,
        )


class GeminiClaimGenerationAdapter:
    provider_name = "gemini"
    provider_version = "1.0"
    adapter_version = "1.0"

    def __init__(
        self,
        config: GeminiClaimAdapterConfig,
        *,
        prompt_builder: EvidenceGroundedClaimPromptBuilder | None = None,
        transport: GeminiClaimTransport | None = None,
    ) -> None:
        self.config = config
        self.model = config.model
        self.prompt_builder = prompt_builder or EvidenceGroundedClaimPromptBuilder()
        self.transport = transport or HttpxGeminiClaimTransport()

    def build_provider_payload(
        self,
        request: ClaimGenerationRequest,
    ) -> tuple[ClaimGenerationPrompt, dict[str, object]]:
        prompt = self.prompt_builder.build(request)
        body: dict[str, object] = {
            "model": self.config.model,
            "store": False,
            "input": prompt.prompt_text,
            "system_instruction": (
                "Extract facts only from the provided evidence. Never use outside medical "
                "knowledge. Return only schema-valid JSON."
            ),
            "generation_config": {
                "temperature": 0,
                "thinking_level": "low",
                "max_output_tokens": self.config.max_output_tokens,
            },
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": StructuredClaimCandidateResponse.model_json_schema(),
            },
        }
        return prompt, body

    def generate(self, request: ClaimGenerationRequest) -> ClaimAdapterResult:
        if not self.config.api_key.strip():
            raise ClaimGenerationAdapterError(
                ClaimGenerationErrorCode.AUTHENTICATION,
                "Gemini Claim APIキーが設定されていません。",
            )
        prompt, body = self.build_provider_payload(request)
        del prompt
        started = monotonic()
        response: GeminiClaimHttpResponse | None = None
        attempts = 0
        final_error: tuple[ClaimGenerationErrorCode, str] | None = None
        for attempt in range(self.config.retry_limit + 1):
            attempts = attempt + 1
            try:
                response = self.transport.post(
                    endpoint=self.config.endpoint,
                    api_key=self.config.api_key,
                    body=body,
                    timeout_seconds=self.config.timeout_seconds,
                )
            except GeminiClaimTransportTimeout:
                final_error = (
                    ClaimGenerationErrorCode.TIMEOUT,
                    "Gemini Claim生成が制限時間内に応答しませんでした。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            except GeminiClaimTransportNetworkError:
                final_error = (
                    ClaimGenerationErrorCode.NETWORK,
                    "Gemini Claim生成へ接続できませんでした。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            if response.status_code in (401, 403):
                final_error = (
                    ClaimGenerationErrorCode.AUTHENTICATION,
                    "Gemini Claim APIの認証に失敗しました。",
                )
                break
            if response.status_code == 429:
                final_error = (
                    ClaimGenerationErrorCode.RATE_LIMIT,
                    "Gemini Claim APIの利用上限に達しました。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            if response.status_code >= 500:
                final_error = (
                    ClaimGenerationErrorCode.PROVIDER_SERVER,
                    "Gemini Claim APIで一時的なサーバーエラーが発生しました。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            if response.status_code >= 400:
                final_error = (
                    ClaimGenerationErrorCode.REQUEST,
                    "Gemini Claim APIがRequestを受け付けませんでした。",
                )
                break
            break

        if response is None or response.status_code >= 400:
            code, message = final_error or (
                ClaimGenerationErrorCode.REQUEST,
                "Gemini Claim生成を実行できませんでした。",
            )
            raise ClaimGenerationAdapterError(
                code,
                message,
                retry_count=max(0, attempts - 1),
            )

        try:
            response_data = json.loads(response.content)
            if not isinstance(response_data, dict):
                raise ValueError("response must be an object")
            output_text = _extract_output_text(response_data)
            structured = StructuredClaimCandidateResponse.model_validate_json(output_text)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, ValidationError) as error:
            raise ClaimGenerationAdapterError(
                ClaimGenerationErrorCode.INVALID_RESPONSE,
                "Gemini Claim生成の構造化応答を検証できませんでした。",
                retry_count=max(0, attempts - 1),
            ) from error
        if len(structured.candidates) > request.max_candidates:
            raise ClaimGenerationAdapterError(
                ClaimGenerationErrorCode.INVALID_RESPONSE,
                "Gemini Claim候補数がRequest上限を超えました。",
                retry_count=max(0, attempts - 1),
            )
        usage = _extract_usage(response_data)
        request_id = response_data.get("id")
        return ClaimAdapterResult(
            provider=self.provider_name,
            model=self.config.model,
            provider_request_id=request_id if isinstance(request_id, str) else None,
            generator_id="evidence_grounded_claim_builder",
            generator_version=self.adapter_version,
            response=structured,
            usage=usage,
            duration_ms=max(0, round((monotonic() - started) * 1000)),
            retry_count=max(0, attempts - 1),
        )


def _extract_output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text") or response.get("outputText")
    if isinstance(direct, str) and direct.strip():
        return direct
    steps = response.get("steps")
    if isinstance(steps, list):
        for step in reversed(steps):
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            values: list[str] = []
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                value = item.get("text")
                if isinstance(value, str):
                    values.append(value)
            if values:
                return "".join(values)
    raise ValueError("Gemini output text is missing")


def _extract_usage(response: Mapping[str, Any]) -> ClaimAdapterUsage:
    raw = response.get("usage")
    usage = raw if isinstance(raw, dict) else {}
    prompt = _int_value(usage, "prompt_tokens", "total_input_tokens", "totalInputTokens")
    completion = _int_value(
        usage,
        "completion_tokens",
        "total_output_tokens",
        "totalOutputTokens",
    )
    total = _int_value(usage, "total_tokens", "totalTokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return ClaimAdapterUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
    )


def _int_value(values: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    return None
