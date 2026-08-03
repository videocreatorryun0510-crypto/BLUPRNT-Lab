"""Presentation Engine Adapter Contract public API."""

from presentation_engine_adapter.audit import JsonlPresentationEngineAuditLogger
from presentation_engine_adapter.dummy import DummyPresentationEngineAdapter
from presentation_engine_adapter.fingerprint import presentation_request_fingerprint
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
    "EngineExecutionStatus",
    "GeneratedArtifact",
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
