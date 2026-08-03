"""Traceable, provider-neutral response creation and validation."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from provider_payload_resolver.audit import JsonlResponseAuditLogger
from provider_payload_resolver.models import (
    ExecutionStatus,
    PayloadValidationIssue,
    PayloadValidationStage,
    PresentationPayload,
    ResponseAuditRecord,
    TraceablePresentationResponse,
    TraceableResponseExecution,
    TraceableResponseIdentity,
    TraceableResponseProvider,
    TraceableResponseRequest,
    TraceableResponseRunResult,
    TraceableResponseTraceability,
    TraceableResponseValidation,
)
from provider_payload_resolver.writer import TraceableResponseJsonWriter


def build_dummy_traceable_response(
    payload: PresentationPayload,
    *,
    provider_name: str = "dummy",
    provider_version: str = "1.0.0",
    executed_at: datetime | None = None,
) -> TraceablePresentationResponse:
    timestamp = executed_at or datetime.now(UTC)
    selected_ids = tuple(
        item.claim_id for item in payload.medical_content.selected_claims
    )
    diagram_ids = tuple(
        item.diagram_request_id for item in payload.visual_content.diagram_requests
    )
    reference_ids = tuple(
        item.reference_id for item in payload.medical_content.references
    )
    validation = TraceableResponseValidation(
        is_valid=True,
        claim_traceability_result=True,
        reference_traceability_result=True,
        diagram_traceability_result=True,
        fingerprint_result=True,
        policy_result=True,
    )
    return TraceablePresentationResponse(
        identity=TraceableResponseIdentity(
            response_id=f"prs_{uuid4().hex}",
            created_at=timestamp,
        ),
        request=TraceableResponseRequest(
            presentation_request_id=payload.request.presentation_request_id,
            payload_id=payload.identity.payload_id,
            payload_fingerprint=payload.metadata.payload_fingerprint,
        ),
        provider=TraceableResponseProvider(
            provider_name=provider_name,
            provider_version=provider_version,
            provider_request_id=f"dummy_{uuid4().hex}",
        ),
        execution=TraceableResponseExecution(
            status=ExecutionStatus.COMPLETED,
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=0,
        ),
        traceability=TraceableResponseTraceability(
            used_claim_ids=selected_ids,
            used_diagram_request_ids=diagram_ids,
            used_reference_ids=reference_ids,
            omitted_claim_ids=(),
            unsupported_items=(),
        ),
        artifacts=(),
        validation=validation,
    )


class TraceableResponseValidator:
    def validate(
        self,
        payload: PresentationPayload,
        response: TraceablePresentationResponse,
    ) -> TraceableResponseValidation:
        issues: list[PayloadValidationIssue] = []
        selected = {
            item.claim_id for item in payload.medical_content.selected_claims
        }
        diagrams = {
            item.diagram_request_id for item in payload.visual_content.diagram_requests
        }
        references = {
            item.reference_id for item in payload.medical_content.references
        }
        used_claims = set(response.traceability.used_claim_ids)
        omitted_claims = set(response.traceability.omitted_claim_ids)
        used_diagrams = set(response.traceability.used_diagram_request_ids)
        used_references = set(response.traceability.used_reference_ids)

        fingerprint_ok = (
            response.request.payload_id == payload.identity.payload_id
            and response.request.presentation_request_id
            == payload.request.presentation_request_id
            and response.request.payload_fingerprint
            == payload.metadata.payload_fingerprint
        )
        if not fingerprint_ok:
            issues.append(_issue("response_fingerprint_mismatch", "request"))
        claim_ok = (
            used_claims.issubset(selected)
            and omitted_claims.issubset(selected)
            and used_claims.isdisjoint(omitted_claims)
            and used_claims | omitted_claims == selected
        )
        if not claim_ok:
            issues.append(_issue("claim_traceability_mismatch", "traceability.used_claim_ids"))
        diagram_ok = used_diagrams.issubset(diagrams)
        if not diagram_ok:
            issues.append(
                _issue(
                    "diagram_traceability_mismatch",
                    "traceability.used_diagram_request_ids",
                )
            )
        reference_ok = used_references.issubset(references)
        if not reference_ok:
            issues.append(
                _issue(
                    "reference_traceability_mismatch",
                    "traceability.used_reference_ids",
                )
            )
        policy_ok = (
            not response.traceability.unsupported_items
            and response.execution.status == ExecutionStatus.COMPLETED
            and not response.errors
        )
        if not policy_ok:
            issues.append(_issue("response_policy_failed", "execution.status"))
        return TraceableResponseValidation(
            is_valid=not issues,
            claim_traceability_result=claim_ok,
            reference_traceability_result=reference_ok,
            diagram_traceability_result=diagram_ok,
            fingerprint_result=fingerprint_ok,
            policy_result=policy_ok,
            issues=tuple(issues),
        )


class TraceableResponseService:
    """Validate, persist and audit response metadata without artifact bodies."""

    def __init__(
        self,
        writer: TraceableResponseJsonWriter,
        audit_logger: JsonlResponseAuditLogger,
        validator: TraceableResponseValidator | None = None,
    ) -> None:
        self._writer = writer
        self._audit_logger = audit_logger
        self._validator = validator or TraceableResponseValidator()

    @classmethod
    def from_directories(
        cls,
        output_directory: Path,
        audit_log_path: Path,
    ) -> "TraceableResponseService":
        return cls(
            TraceableResponseJsonWriter(output_directory),
            JsonlResponseAuditLogger(audit_log_path),
        )

    @property
    def audit_log_path(self) -> str:
        return str(self._audit_logger.output_path)

    def accept(
        self,
        payload: PresentationPayload,
        response: TraceablePresentationResponse,
        *,
        validated_at: datetime | None = None,
    ) -> TraceableResponseRunResult:
        timestamp = validated_at or datetime.now(UTC)
        validation = self._validator.validate(payload, response)
        validated_response = response.model_copy(update={"validation": validation})
        output_path = self._writer.write(validated_response)
        self._audit_logger.write(
            ResponseAuditRecord(
                response_id=validated_response.identity.response_id,
                payload_id=payload.identity.payload_id,
                provider=validated_response.provider.provider_name,
                status=validated_response.execution.status,
                fingerprint_result=validation.fingerprint_result,
                claim_traceability_result=validation.claim_traceability_result,
                reference_traceability_result=(
                    validation.reference_traceability_result
                ),
                result="accepted" if validation.is_valid else "rejected",
                timestamp=timestamp,
            )
        )
        return TraceableResponseRunResult(
            status="accepted" if validation.is_valid else "rejected",
            response=validated_response,
            output_path=str(output_path),
            audit_log_path=self.audit_log_path,
        )


def _issue(code: str, path: str) -> PayloadValidationIssue:
    return PayloadValidationIssue(
        stage=PayloadValidationStage.POLICY,
        code=code,
        path=path,
        message="Traceable ResponseがProvider Payloadと一致しません。",
    )
