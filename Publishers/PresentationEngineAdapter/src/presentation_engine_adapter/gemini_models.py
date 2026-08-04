"""Gemini Sandbox local contracts without medical response bodies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from presentation_prompt_builder import PresentationPrompt
from provider_payload_resolver import PresentationPayload, TraceablePresentationResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GeminiErrorCode(StrEnum):
    TIMEOUT = "timeout_error"
    RATE_LIMIT = "rate_limit_error"
    SERVER = "provider_server_error"
    NETWORK = "network_error"
    AUTHENTICATION = "authentication_error"
    JSON = "json_error"
    APPROVAL = "approval_error"
    FINGERPRINT = "fingerprint_error"
    PROVIDER_REQUEST_ID = "provider_request_id_error"
    CLAIM_TRACEABILITY = "claim_traceability_error"
    REFERENCE_TRACEABILITY = "reference_traceability_error"
    MEDICAL_ADDITION = "medical_addition_error"
    REQUEST = "request_error"


class GeminiTokenUsage(FrozenModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    thought_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    cost_status: Literal["calculated", "not_calculated"] = "not_calculated"


class GeminiSandboxAuditRecord(FrozenModel):
    execution_id: str = Field(pattern=r"^gex_[a-f0-9]{32}$")
    request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    response_id: str = Field(pattern=r"^prs_[a-f0-9]{32}$")
    provider: Literal["gemini"]
    model: str = Field(min_length=3, max_length=120)
    sandbox: Literal[True] = True
    fixture_mode: bool
    started_at: datetime
    completed_at: datetime
    duration: int = Field(ge=0, description="Elapsed milliseconds")
    token_usage: GeminiTokenUsage
    retry_count: int = Field(ge=0, le=1)
    transport_result: Literal["success", "failed", "not_called"]
    validation_result: Literal["passed", "failed", "not_run"]
    final_result: Literal["success", "validation_failed", "failed"]
    error_code: GeminiErrorCode | None = None


class GeminiSandboxExecutionReport(FrozenModel):
    execution_id: str = Field(pattern=r"^gex_[a-f0-9]{32}$")
    execution_environment: Literal["sandbox"] = "sandbox"
    fixture_mode: bool = False
    provider: Literal["gemini"] = "gemini"
    model: str = Field(min_length=3, max_length=120)
    adapter_version: Literal["1.0.1"] = "1.0.1"
    mode: Literal["sandbox"] = "sandbox"
    status: str = Field(min_length=3, max_length=40)
    final_result: Literal["success", "validation_failed", "failed"]
    transport_result: Literal["success", "failed", "not_called"]
    validation_result: Literal["passed", "failed", "not_run"]
    error_code: GeminiErrorCode | None = None
    error_message: NonEmptyText | None = None
    external_ai_called: bool
    attempt_count: int = Field(ge=0, le=2)
    retry_count: int = Field(ge=0, le=1)
    http_status: int | None = Field(default=None, ge=100, le=599)
    provider_request_id: str | None = Field(default=None, min_length=3, max_length=180)
    duration_ms: int = Field(ge=0)
    usage: GeminiTokenUsage
    max_output_tokens: int = Field(ge=64, le=4096)
    prompt_builder_version: Literal["1.0.0"] = "1.0.0"
    payload_fingerprint: Fingerprint
    prompt_fingerprint: Fingerprint
    response_output_path: str
    audit_log_path: str


class GeminiSandboxRunResult(FrozenModel):
    response: TraceablePresentationResponse
    report: GeminiSandboxExecutionReport
    gemini_prompt_debug: str | None = Field(default=None, max_length=500_000)


class GeminiTraceSummary(FrozenModel):
    presentation_request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    payload_fingerprint: Fingerprint
    status: Literal["completed"]
    pages: int = Field(ge=1, le=200)
    title: NonEmptyText
    sections: tuple[GeminiTraceSection, ...] = Field(min_length=1, max_length=3)
    source_claim_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    source_reference_ids: tuple[str, ...] = Field(max_length=500)
    omitted_claim_ids: tuple[str, ...] = Field(max_length=500)
    used_diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    warnings: tuple[str, ...] = Field(default=(), max_length=0)


class GeminiTraceSection(FrozenModel):
    heading: str = Field(pattern=r"^要点[1-3]$")
    exact_claim_texts: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=500)
    source_claim_ids: tuple[str, ...] = Field(min_length=1, max_length=500)


class GeminiLegacyTraceSummary(FrozenModel):
    """Phase 5.18 metadata-only response retained for backward compatibility."""

    presentation_request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    payload_fingerprint: Fingerprint
    status: Literal["completed"]
    pages: int = Field(ge=1, le=200)
    used_claim_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    omitted_claim_ids: tuple[str, ...] = Field(max_length=500)
    used_diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    used_reference_ids: tuple[str, ...] = Field(max_length=500)
    warnings: tuple[str, ...] = Field(default=(), max_length=20)


@dataclass(frozen=True)
class GeminiAdapterConfig:
    api_key: str
    model: str = DEFAULT_GEMINI_MODEL
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    timeout_seconds: float = 30.0
    retry_limit: int = 1
    max_output_tokens: int = 512
    debug_prompt: bool = False
    input_cost_per_million_tokens: float | None = None
    output_cost_per_million_tokens: float | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_limit not in (0, 1):
            raise ValueError("retry_limit must be 0 or 1")
        if not 64 <= self.max_output_tokens <= 4096:
            raise ValueError("max_output_tokens must be between 64 and 4096")
        if not self.model.strip():
            raise ValueError("model is required")


@dataclass(frozen=True)
class GeminiProviderRequest:
    endpoint: str
    model: str
    body: dict[str, object]
    prompt_text: str


@dataclass(frozen=True)
class GeminiHttpResponse:
    status_code: int
    content: bytes


@dataclass(frozen=True)
class GeminiExecutionContext:
    payload: PresentationPayload
    prompt: PresentationPrompt
