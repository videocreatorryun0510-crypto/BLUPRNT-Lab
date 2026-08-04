"""Map Gemini metadata-only output to the unchanged Traceable Response contract."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from presentation_prompt_builder import PresentationPrompt
from provider_payload_resolver import (
    ExecutionStatus,
    PresentationPayload,
    TraceablePresentationResponse,
    TraceableResponseValidator,
)
from provider_payload_resolver.models import (
    TraceableResponseExecution,
    TraceableResponseIdentity,
    TraceableResponseProvider,
    TraceableResponseRequest,
    TraceableResponseTraceability,
    TraceableResponseValidation,
)
from pydantic import ValidationError

from presentation_engine_adapter.gemini_models import (
    GeminiAdapterConfig,
    GeminiErrorCode,
    GeminiLegacyTraceSummary,
    GeminiTokenUsage,
    GeminiTraceSummary,
)


class GeminiResponseMappingError(RuntimeError):
    def __init__(self, code: GeminiErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class GeminiResponseMapper:
    provider_name = "gemini"
    adapter_version = "1.0.1"

    def __init__(self) -> None:
        self._validator = TraceableResponseValidator()

    def parse_success(
        self,
        payload: PresentationPayload,
        prompt: PresentationPrompt,
        response_data: Mapping[str, object],
        *,
        started_at: datetime,
        completed_at: datetime,
        config: GeminiAdapterConfig,
        fixture_mode: bool = False,
    ) -> tuple[TraceablePresentationResponse, GeminiTokenUsage]:
        output_text = _extract_output_text(response_data)
        try:
            summary: GeminiTraceSummary | GeminiLegacyTraceSummary = (
                GeminiTraceSummary.model_validate_json(output_text)
            )
        except (ValidationError, ValueError) as structured_error:
            if fixture_mode:
                raise GeminiResponseMappingError(
                    GeminiErrorCode.JSON,
                    "Geminiの受入テスト用構造化レスポンスを検証できません。",
                ) from structured_error
            try:
                summary = GeminiLegacyTraceSummary.model_validate_json(output_text)
            except (ValidationError, ValueError) as legacy_error:
                raise GeminiResponseMappingError(
                    GeminiErrorCode.JSON,
                    "Geminiの構造化レスポンスを検証できません。",
                ) from legacy_error
        if (
            summary.presentation_request_id
            != payload.request.presentation_request_id
            or summary.payload_id != payload.identity.payload_id
            or summary.payload_fingerprint != payload.metadata.payload_fingerprint
            or prompt.source.payload_fingerprint != summary.payload_fingerprint
        ):
            raise GeminiResponseMappingError(
                GeminiErrorCode.FINGERPRINT,
                "GeminiレスポンスのFingerprintが送信Payloadと一致しません。",
            )
        provider_request_id = response_data.get("id")
        if not isinstance(provider_request_id, str) or not provider_request_id.strip():
            raise GeminiResponseMappingError(
                GeminiErrorCode.PROVIDER_REQUEST_ID,
                "GeminiレスポンスにProvider Request IDがありません。",
            )
        if isinstance(summary, GeminiTraceSummary):
            _validate_structured_content(payload, prompt, summary)
            used_claim_ids = summary.source_claim_ids
            used_reference_ids = summary.source_reference_ids
        else:
            used_claim_ids = summary.used_claim_ids
            used_reference_ids = summary.used_reference_ids
        response = self._build_response(
            payload,
            provider_request_id=provider_request_id,
            status=ExecutionStatus.COMPLETED,
            used_claim_ids=used_claim_ids,
            omitted_claim_ids=summary.omitted_claim_ids,
            used_diagram_ids=summary.used_diagram_request_ids,
            used_reference_ids=used_reference_ids,
            started_at=started_at,
            completed_at=completed_at,
            errors=(),
            warnings=(
                ("execution_environment=sandbox", "fixture_mode=true")
                if fixture_mode
                else ()
            ),
        )
        validation = self._validator.validate(payload, response)
        response = response.model_copy(update={"validation": validation})
        if not validation.is_valid:
            raise GeminiResponseMappingError(
                GeminiErrorCode.FINGERPRINT,
                "Geminiレスポンスの追跡情報がProvider Payloadと一致しません。",
            )
        return response, _usage(response_data, config)

    def build_failure(
        self,
        payload: PresentationPayload,
        *,
        error_code: GeminiErrorCode,
        message: str,
        started_at: datetime,
        completed_at: datetime,
        provider_request_id: str | None = None,
        fixture_mode: bool = False,
    ) -> TraceablePresentationResponse:
        response = self._build_response(
            payload,
            provider_request_id=provider_request_id or f"gemini_{uuid4().hex}",
            status=ExecutionStatus.FAILED,
            used_claim_ids=(),
            omitted_claim_ids=tuple(
                item.claim_id for item in payload.medical_content.selected_claims
            ),
            used_diagram_ids=(),
            used_reference_ids=(),
            started_at=started_at,
            completed_at=completed_at,
            errors=(f"{error_code.value}: {message}",),
            warnings=(
                ("execution_environment=sandbox", "fixture_mode=true")
                if fixture_mode
                else ()
            ),
        )
        return response.model_copy(
            update={"validation": self._validator.validate(payload, response)}
        )

    def _build_response(
        self,
        payload: PresentationPayload,
        *,
        provider_request_id: str,
        status: ExecutionStatus,
        used_claim_ids: tuple[str, ...],
        omitted_claim_ids: tuple[str, ...],
        used_diagram_ids: tuple[str, ...],
        used_reference_ids: tuple[str, ...],
        started_at: datetime,
        completed_at: datetime,
        errors: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> TraceablePresentationResponse:
        duration_ms = max(
            0,
            int((completed_at - started_at).total_seconds() * 1000),
        )
        return TraceablePresentationResponse(
            identity=TraceableResponseIdentity(
                response_id=f"prs_{uuid4().hex}",
                created_at=completed_at,
            ),
            request=TraceableResponseRequest(
                presentation_request_id=payload.request.presentation_request_id,
                payload_id=payload.identity.payload_id,
                payload_fingerprint=payload.metadata.payload_fingerprint,
            ),
            provider=TraceableResponseProvider(
                provider_name=self.provider_name,
                provider_version=self.adapter_version,
                provider_request_id=provider_request_id,
            ),
            execution=TraceableResponseExecution(
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            ),
            traceability=TraceableResponseTraceability(
                used_claim_ids=used_claim_ids,
                used_diagram_request_ids=used_diagram_ids,
                used_reference_ids=used_reference_ids,
                omitted_claim_ids=omitted_claim_ids,
                unsupported_items=(),
            ),
            artifacts=(),
            validation=TraceableResponseValidation(
                is_valid=True,
                claim_traceability_result=True,
                reference_traceability_result=True,
                diagram_traceability_result=True,
                fingerprint_result=True,
                policy_result=True,
            ),
            warnings=warnings,
            errors=errors,
        )


def _extract_output_text(response_data: Mapping[str, object]) -> str:
    direct = response_data.get("outputText") or response_data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    steps = response_data.get("steps")
    if isinstance(steps, list):
        text_parts: list[str] = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        if text_parts:
            return "".join(text_parts)
    raise GeminiResponseMappingError(
        GeminiErrorCode.JSON,
        "Geminiレスポンスに構造化テキストがありません。",
    )


def _usage(
    response_data: Mapping[str, object],
    config: GeminiAdapterConfig,
) -> GeminiTokenUsage:
    raw = response_data.get("usage")
    usage = raw if isinstance(raw, dict) else {}
    prompt = _int_value(usage, "totalInputTokens", "total_input_tokens")
    completion = _int_value(usage, "totalOutputTokens", "total_output_tokens")
    total = _int_value(usage, "totalTokens", "total_tokens")
    thoughts = _int_value(usage, "totalThoughtTokens", "total_thought_tokens")
    cost: float | None = None
    cost_status: Literal["calculated", "not_calculated"] = "not_calculated"
    if (
        prompt is not None
        and completion is not None
        and config.input_cost_per_million_tokens is not None
        and config.output_cost_per_million_tokens is not None
    ):
        cost = round(
            prompt / 1_000_000 * config.input_cost_per_million_tokens
            + completion / 1_000_000 * config.output_cost_per_million_tokens,
            8,
        )
        cost_status = "calculated"
    return GeminiTokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        thought_tokens=thoughts,
        estimated_cost_usd=cost,
        cost_status=cost_status,
    )


def _int_value(mapping: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _validate_structured_content(
    payload: PresentationPayload,
    prompt: PresentationPrompt,
    summary: GeminiTraceSummary,
) -> None:
    if summary.title != prompt.title:
        raise GeminiResponseMappingError(
            GeminiErrorCode.MEDICAL_ADDITION,
            "Geminiレスポンスのtitleが承認済みPromptと一致しません。",
        )

    claims = {
        item.claim_id: item.exact_text
        for item in payload.medical_content.selected_claims
    }
    requested_claim_ids = set(summary.source_claim_ids)
    if not requested_claim_ids.issubset(claims):
        raise GeminiResponseMappingError(
            GeminiErrorCode.CLAIM_TRACEABILITY,
            "GeminiレスポンスにPayload外のClaim IDがあります。",
        )
    omitted = set(summary.omitted_claim_ids)
    if (
        not omitted.issubset(claims)
        or requested_claim_ids.isdisjoint(omitted) is False
        or requested_claim_ids | omitted != set(claims)
    ):
        raise GeminiResponseMappingError(
            GeminiErrorCode.CLAIM_TRACEABILITY,
            "GeminiレスポンスがすべてのClaimを一意に追跡できていません。",
        )

    section_claim_ids: list[str] = []
    for index, section in enumerate(summary.sections, start=1):
        if section.heading != f"要点{index}":
            raise GeminiResponseMappingError(
                GeminiErrorCode.MEDICAL_ADDITION,
                "Geminiレスポンスの見出しが許可された固定形式ではありません。",
            )
        if len(section.source_claim_ids) != len(section.exact_claim_texts):
            raise GeminiResponseMappingError(
                GeminiErrorCode.CLAIM_TRACEABILITY,
                "Section内のClaim IDと本文の件数が一致しません。",
            )
        for claim_id, exact_text in zip(
            section.source_claim_ids,
            section.exact_claim_texts,
            strict=True,
        ):
            if claims.get(claim_id) != exact_text:
                raise GeminiResponseMappingError(
                    GeminiErrorCode.MEDICAL_ADDITION,
                    "Geminiレスポンスに追加・言い換えられた文章があります。",
                )
            section_claim_ids.append(claim_id)
    if set(section_claim_ids) != requested_claim_ids:
        raise GeminiResponseMappingError(
            GeminiErrorCode.CLAIM_TRACEABILITY,
            "Sectionとsource_claim_idsの対応が一致しません。",
        )

    references = {
        item.reference_id for item in payload.medical_content.references
    }
    if set(summary.source_reference_ids) != references:
        raise GeminiResponseMappingError(
            GeminiErrorCode.REFERENCE_TRACEABILITY,
            "GeminiレスポンスのReference IDがPayloadと一致しません。",
        )


def parse_json_object(content: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeminiResponseMappingError(
            GeminiErrorCode.JSON,
            "Gemini APIレスポンスがJSONではありません。",
        ) from error
    if not isinstance(value, dict):
        raise GeminiResponseMappingError(
            GeminiErrorCode.JSON,
            "Gemini APIレスポンスがJSON Objectではありません。",
        )
    return value
