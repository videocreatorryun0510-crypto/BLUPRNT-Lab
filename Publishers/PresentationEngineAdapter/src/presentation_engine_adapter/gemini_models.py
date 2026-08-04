"""Gemini Sandbox local contracts without medical response bodies."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from presentation_prompt_builder import PresentationPrompt
from provider_payload_resolver import PresentationPayload, TraceablePresentationResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
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
    REQUEST = "request_error"


class GeminiTokenUsage(FrozenModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    thought_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class GeminiSandboxAuditRecord(FrozenModel):
    audit_contract_version: Literal["1.0"] = "1.0"
    presentation_request_id: str = Field(pattern=r"^prq_[a-f0-9]{32}$")
    payload_id: str = Field(pattern=r"^ppd_[a-f0-9]{32}$")
    prompt_id: str = Field(pattern=r"^pmt_[a-f0-9]{32}$")
    payload_fingerprint: Fingerprint
    prompt_fingerprint: Fingerprint
    prompt_builder_version: Literal["1.0.0"]
    provider: Literal["gemini"]
    model: str = Field(min_length=3, max_length=120)
    adapter_version: Literal["1.0.0"]
    mode: Literal["sandbox"]
    request_mode: Literal["external"]
    timestamp: datetime
    status: str = Field(min_length=3, max_length=40)
    error_code: GeminiErrorCode | None = None
    external_ai_called: bool
    attempt_count: int = Field(ge=0, le=2)
    duration_ms: int = Field(ge=0)
    usage: GeminiTokenUsage


class GeminiSandboxExecutionReport(FrozenModel):
    provider: Literal["gemini"] = "gemini"
    model: str = Field(min_length=3, max_length=120)
    adapter_version: Literal["1.0.0"] = "1.0.0"
    mode: Literal["sandbox"] = "sandbox"
    status: str = Field(min_length=3, max_length=40)
    error_code: GeminiErrorCode | None = None
    error_message: NonEmptyText | None = None
    external_ai_called: bool
    attempt_count: int = Field(ge=0, le=2)
    duration_ms: int = Field(ge=0)
    usage: GeminiTokenUsage
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
    used_claim_ids: tuple[str, ...] = Field(max_length=500)
    omitted_claim_ids: tuple[str, ...] = Field(max_length=500)
    used_diagram_request_ids: tuple[str, ...] = Field(max_length=20)
    used_reference_ids: tuple[str, ...] = Field(max_length=500)
    warnings: tuple[str, ...] = Field(default=(), max_length=30)


@dataclass(frozen=True)
class GeminiAdapterConfig:
    api_key: str
    model: str = "gemini-3.6-flash"
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    timeout_seconds: float = 30.0
    retry_limit: int = 1
    debug_prompt: bool = False
    input_cost_per_million_tokens: float | None = None
    output_cost_per_million_tokens: float | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_limit not in (0, 1):
            raise ValueError("retry_limit must be 0 or 1")
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
