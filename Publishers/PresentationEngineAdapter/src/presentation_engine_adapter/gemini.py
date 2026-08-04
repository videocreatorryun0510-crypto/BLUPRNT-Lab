"""Gemini Interactions API Sandbox Adapter.

Gemini-specific prompt conversion and HTTP details stay in this module. The
provider-neutral Presentation Prompt Builder has no dependency on this package.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import ClassVar, Literal

from presentation_prompt_builder import (
    PresentationPrompt,
    presentation_prompt_fingerprint,
)
from provider_payload_resolver import (
    PresentationPayload,
    TraceableResponseJsonWriter,
    presentation_payload_fingerprint,
)

from presentation_engine_adapter.gemini_audit import JsonlGeminiSandboxAuditLogger
from presentation_engine_adapter.gemini_mapper import (
    GeminiResponseMapper,
    GeminiResponseMappingError,
    parse_json_object,
)
from presentation_engine_adapter.gemini_models import (
    GeminiAdapterConfig,
    GeminiErrorCode,
    GeminiProviderRequest,
    GeminiSandboxAuditRecord,
    GeminiSandboxExecutionReport,
    GeminiSandboxRunResult,
    GeminiTokenUsage,
)
from presentation_engine_adapter.gemini_transport import (
    GeminiTransport,
    GeminiTransportNetworkError,
    GeminiTransportTimeout,
    HttpxGeminiTransport,
)


class GeminiSandboxAdapter:
    provider_name: ClassVar[Literal["gemini"]] = "gemini"
    adapter_version: ClassVar[Literal["1.0.0"]] = "1.0.0"
    mode: ClassVar[Literal["sandbox"]] = "sandbox"

    def __init__(
        self,
        config: GeminiAdapterConfig,
        response_writer: TraceableResponseJsonWriter,
        audit_logger: JsonlGeminiSandboxAuditLogger,
        transport: GeminiTransport | None = None,
        mapper: GeminiResponseMapper | None = None,
    ) -> None:
        self.config = config
        self._writer = response_writer
        self._audit = audit_logger
        self._transport = transport or HttpxGeminiTransport()
        self._mapper = mapper or GeminiResponseMapper()

    @classmethod
    def from_directories(
        cls,
        config: GeminiAdapterConfig,
        response_output_directory: Path,
        audit_log_path: Path,
        *,
        transport: GeminiTransport | None = None,
    ) -> "GeminiSandboxAdapter":
        return cls(
            config,
            TraceableResponseJsonWriter(response_output_directory),
            JsonlGeminiSandboxAuditLogger(audit_log_path),
            transport=transport,
        )

    @property
    def audit_log_path(self) -> str:
        return str(self._audit.output_path)

    def build_provider_request(
        self,
        prompt: PresentationPrompt,
    ) -> GeminiProviderRequest:
        gemini_prompt = _gemini_prompt(prompt)
        return GeminiProviderRequest(
            endpoint=self.config.endpoint,
            model=self.config.model,
            prompt_text=gemini_prompt,
            body={
                "model": self.config.model,
                "store": False,
                "input": gemini_prompt,
                "system_instruction": (
                    "Return only the requested JSON trace summary. Do not add, "
                    "rewrite, diagnose, or infer medical facts."
                ),
                "generation_config": {
                    "temperature": 0,
                    "thinking_level": "low",
                },
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _trace_schema(prompt),
                },
            },
        )

    def execute(
        self,
        payload: PresentationPayload,
        prompt: PresentationPrompt,
        *,
        started_at: datetime | None = None,
    ) -> GeminiSandboxRunResult:
        started = started_at or datetime.now(UTC)
        clock_start = monotonic()
        external_called = False
        attempts = 0
        usage = GeminiTokenUsage()
        error_code: GeminiErrorCode | None = None
        error_message: str | None = None
        provider_request_id: str | None = None

        preflight = self._preflight(payload, prompt)
        if preflight is not None:
            error_code, error_message = preflight
            completed = datetime.now(UTC)
            response = self._mapper.build_failure(
                payload,
                error_code=error_code,
                message=error_message,
                started_at=started,
                completed_at=completed,
            )
        else:
            request = self.build_provider_request(prompt)
            response = None
            for attempt in range(self.config.retry_limit + 1):
                attempts = attempt + 1
                external_called = True
                try:
                    http_response = self._transport.post(
                        request,
                        api_key=self.config.api_key,
                        timeout_seconds=self.config.timeout_seconds,
                    )
                except GeminiTransportTimeout:
                    error_code = GeminiErrorCode.TIMEOUT
                    error_message = "Gemini APIが制限時間内に応答しませんでした。"
                    if attempt < self.config.retry_limit:
                        continue
                    break
                except GeminiTransportNetworkError:
                    error_code = GeminiErrorCode.NETWORK
                    error_message = "Gemini APIへ接続できませんでした。"
                    if attempt < self.config.retry_limit:
                        continue
                    break
                if http_response.status_code in (401, 403):
                    error_code = GeminiErrorCode.AUTHENTICATION
                    error_message = "Gemini APIの認証に失敗しました。"
                    break
                if http_response.status_code == 429:
                    error_code = GeminiErrorCode.RATE_LIMIT
                    error_message = "Gemini APIの利用上限に達しました。"
                    if attempt < self.config.retry_limit:
                        continue
                    break
                if http_response.status_code >= 500:
                    error_code = GeminiErrorCode.SERVER
                    error_message = "Gemini APIで一時的なサーバーエラーが発生しました。"
                    if attempt < self.config.retry_limit:
                        continue
                    break
                if http_response.status_code >= 400:
                    error_code = GeminiErrorCode.REQUEST
                    error_message = "Gemini APIがSandbox Requestを受け付けませんでした。"
                    break
                try:
                    response_data = parse_json_object(http_response.content)
                    raw_id = response_data.get("id")
                    provider_request_id = raw_id if isinstance(raw_id, str) else None
                    completed = datetime.now(UTC)
                    response, usage = self._mapper.parse_success(
                        payload,
                        prompt,
                        response_data,
                        started_at=started,
                        completed_at=completed,
                        config=self.config,
                    )
                    error_code = None
                    error_message = None
                except GeminiResponseMappingError as error:
                    error_code = error.code
                    error_message = str(error)
                break
            if response is None:
                completed = datetime.now(UTC)
                final_code = error_code or GeminiErrorCode.REQUEST
                final_message = error_message or "Gemini Sandboxを実行できませんでした。"
                response = self._mapper.build_failure(
                    payload,
                    error_code=final_code,
                    message=final_message,
                    started_at=started,
                    completed_at=completed,
                    provider_request_id=provider_request_id,
                )

        assert response is not None
        duration_ms = max(0, int((monotonic() - clock_start) * 1000))
        output_path = self._writer.write(response)
        self._audit.write(
            GeminiSandboxAuditRecord(
                presentation_request_id=payload.request.presentation_request_id,
                payload_id=payload.identity.payload_id,
                prompt_id=prompt.identity.prompt_id,
                payload_fingerprint=payload.metadata.payload_fingerprint,
                prompt_fingerprint=prompt.metadata.prompt_fingerprint,
                prompt_builder_version=prompt.metadata.builder_version,
                provider=self.provider_name,
                model=self.config.model,
                adapter_version=self.adapter_version,
                mode=self.mode,
                request_mode="external",
                timestamp=started,
                status=response.execution.status.value,
                error_code=error_code,
                external_ai_called=external_called,
                attempt_count=attempts,
                duration_ms=duration_ms,
                usage=usage,
            )
        )
        report = GeminiSandboxExecutionReport(
            model=self.config.model,
            status=response.execution.status.value,
            error_code=error_code,
            error_message=error_message,
            external_ai_called=external_called,
            attempt_count=attempts,
            duration_ms=duration_ms,
            usage=usage,
            payload_fingerprint=payload.metadata.payload_fingerprint,
            prompt_fingerprint=prompt.metadata.prompt_fingerprint,
            response_output_path=str(output_path),
            audit_log_path=self.audit_log_path,
        )
        return GeminiSandboxRunResult(
            response=response,
            report=report,
            gemini_prompt_debug=(
                self.build_provider_request(prompt).prompt_text
                if self.config.debug_prompt
                else None
            ),
        )

    def _preflight(
        self,
        payload: PresentationPayload,
        prompt: PresentationPrompt,
    ) -> tuple[GeminiErrorCode, str] | None:
        if (
            getattr(
                payload.source.approval_state,
                "value",
                payload.source.approval_state,
            )
            != "approved"
            or prompt.source.approval_state != "approved"
            or payload.request.request_mode.value != "external"
            or prompt.source.request_mode.value != "external"
        ):
            return (
                GeminiErrorCode.APPROVAL,
                "approvedかつExternal RequestだけがGemini Sandboxを利用できます。",
            )
        if payload.metadata.payload_fingerprint != presentation_payload_fingerprint(
            payload
        ):
            return (
                GeminiErrorCode.FINGERPRINT,
                "Provider PayloadのFingerprintが一致しません。",
            )
        if prompt.metadata.prompt_fingerprint != presentation_prompt_fingerprint(
            prompt
        ):
            return (
                GeminiErrorCode.FINGERPRINT,
                "Presentation PromptのFingerprintが一致しません。",
            )
        if (
            prompt.source.payload_id != payload.identity.payload_id
            or prompt.source.payload_fingerprint
            != payload.metadata.payload_fingerprint
            or prompt.source.presentation_request_id
            != payload.request.presentation_request_id
        ):
            return (
                GeminiErrorCode.FINGERPRINT,
                "Presentation PromptとProvider Payloadが一致しません。",
            )
        if not self.config.api_key.strip():
            return (
                GeminiErrorCode.AUTHENTICATION,
                "GEMINI_API_KEYが.envへ設定されていません。",
            )
        return None


def _gemini_prompt(prompt: PresentationPrompt) -> str:
    provider_neutral = prompt.model_dump(mode="json")
    instructions: Mapping[str, object] = {
        "task": "Validate a presentation plan using only the supplied facts.",
        "rules": [
            "Keep every medical claim exactly as provided.",
            "Do not add or infer medical facts.",
            "Account for every selected claim as used or omitted.",
            "Use only supplied claim, diagram, and reference IDs.",
            "Return metadata only; do not return presentation prose.",
        ],
        "presentation_prompt": provider_neutral,
    }
    return json.dumps(instructions, ensure_ascii=False, sort_keys=True)


def _trace_schema(prompt: PresentationPrompt) -> dict[str, object]:
    claim_ids = list(prompt.content_policy.selected_claim_ids)
    diagram_ids = list(prompt.content_policy.diagram_request_ids)
    reference_ids = list(prompt.content_policy.reference_ids)

    def id_array(ids: list[str], maximum: int) -> dict[str, object]:
        items: dict[str, object] = {"type": "string"}
        if ids:
            items["enum"] = ids
        return {
            "type": "array",
            "items": items,
            "maxItems": maximum,
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "presentation_request_id": {
                "type": "string",
                "enum": [prompt.source.presentation_request_id],
            },
            "payload_id": {
                "type": "string",
                "enum": [prompt.source.payload_id],
            },
            "payload_fingerprint": {
                "type": "string",
                "enum": [prompt.source.payload_fingerprint],
            },
            "status": {"type": "string", "enum": ["completed"]},
            "pages": {
                "type": "integer",
                "minimum": 1,
                "maximum": prompt.layout_policy.page_or_slide_count,
            },
            "used_claim_ids": id_array(claim_ids, len(claim_ids)),
            "omitted_claim_ids": id_array(claim_ids, len(claim_ids)),
            "used_diagram_request_ids": id_array(diagram_ids, len(diagram_ids)),
            "used_reference_ids": id_array(reference_ids, len(reference_ids)),
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 30,
            },
        },
        "required": [
            "presentation_request_id",
            "payload_id",
            "payload_fingerprint",
            "status",
            "pages",
            "used_claim_ids",
            "omitted_claim_ids",
            "used_diagram_request_ids",
            "used_reference_ids",
            "warnings",
        ],
    }
