"""Presentation Engine Adapter Contract public API."""

from presentation_engine_adapter.audit import JsonlPresentationEngineAuditLogger
from presentation_engine_adapter.dummy import DummyPresentationEngineAdapter
from presentation_engine_adapter.fingerprint import presentation_request_fingerprint
from presentation_engine_adapter.gemini import GeminiSandboxAdapter
from presentation_engine_adapter.gemini_audit import JsonlGeminiSandboxAuditLogger
from presentation_engine_adapter.gemini_mapper import GeminiResponseMapper
from presentation_engine_adapter.gemini_models import (
    DEFAULT_GEMINI_MODEL,
    GeminiAdapterConfig,
    GeminiErrorCode,
    GeminiSandboxExecutionReport,
    GeminiSandboxRunResult,
    GeminiTokenUsage,
)
from presentation_engine_adapter.interface import PresentationEngineAdapter
from presentation_engine_adapter.models import (
    AdapterDescriptor,
    AdapterValidationIssue,
    AdapterValidationReport,
    EngineExecutionStatus,
    GeneratedArtifact,
    PresentationEngineAuditRecord,
    PresentationEnginePayload,
    PresentationEngineResponse,
    PresentationEngineRunOutcome,
    PresentationResult,
    PresentationResultValidation,
    ValidationStage,
    presentation_result_json_schema,
)
from presentation_engine_adapter.runner import PresentationEngineRunner
from presentation_engine_adapter.validator import (
    PresentationEngineRequestValidator,
    PresentationEngineResponseValidator,
)

__all__ = [
    "AdapterDescriptor",
    "AdapterValidationIssue",
    "AdapterValidationReport",
    "DummyPresentationEngineAdapter",
    "DEFAULT_GEMINI_MODEL",
    "EngineExecutionStatus",
    "GeneratedArtifact",
    "GeminiAdapterConfig",
    "GeminiErrorCode",
    "GeminiResponseMapper",
    "GeminiSandboxAdapter",
    "GeminiSandboxExecutionReport",
    "GeminiSandboxRunResult",
    "GeminiTokenUsage",
    "JsonlGeminiSandboxAuditLogger",
    "JsonlPresentationEngineAuditLogger",
    "PresentationEngineAdapter",
    "PresentationEngineAuditRecord",
    "PresentationEnginePayload",
    "PresentationEngineRequestValidator",
    "PresentationEngineResponse",
    "PresentationEngineResponseValidator",
    "PresentationEngineRunOutcome",
    "PresentationEngineRunner",
    "PresentationResult",
    "PresentationResultValidation",
    "ValidationStage",
    "presentation_request_fingerprint",
    "presentation_result_json_schema",
]
