"""Approval-gated execution coordinator for Presentation Engine Adapters."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from knowledge_contracts.approval_v10 import ApprovalGateDecision
from knowledge_contracts.registry_v10 import RegistryKnowledgeView
from presentation_request_builder import PresentationRequest, RequestMode

from presentation_engine_adapter.audit import JsonlPresentationEngineAuditLogger
from presentation_engine_adapter.fingerprint import presentation_request_fingerprint
from presentation_engine_adapter.interface import PresentationEngineAdapter
from presentation_engine_adapter.models import (
    AdapterDescriptor,
    AdapterValidationIssue,
    AdapterValidationReport,
    EngineExecutionStatus,
    GeneratedArtifact,
    PresentationEngineAuditRecord,
    PresentationEngineRunOutcome,
    PresentationResult,
    PresentationResultValidation,
    ValidationStage,
)


class ExternalAiApprovalGate(Protocol):
    def can_send_to_external_ai(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision: ...


class PresentationEngineRunner:
    """Apply Registry and Approval checks before any Adapter execution."""

    def __init__(
        self,
        approval_gate: ExternalAiApprovalGate,
        audit_logger: JsonlPresentationEngineAuditLogger,
    ) -> None:
        self._approval_gate = approval_gate
        self._audit_logger = audit_logger

    @classmethod
    def from_audit_path(
        cls,
        approval_gate: ExternalAiApprovalGate,
        audit_log_path: Path,
    ) -> "PresentationEngineRunner":
        return cls(
            approval_gate,
            JsonlPresentationEngineAuditLogger(audit_log_path),
        )

    @property
    def audit_log_path(self) -> str:
        return str(self._audit_logger.output_path)

    def run(
        self,
        request: PresentationRequest,
        registry: RegistryKnowledgeView,
        adapter: PresentationEngineAdapter,
        *,
        executed_at: datetime | None = None,
    ) -> PresentationEngineRunOutcome:
        timestamp = executed_at or datetime.now(UTC)
        descriptor = AdapterDescriptor(
            provider_name=adapter.provider_name,
            provider_version=adapter.provider_version,
            supports_preview=adapter.supports_preview,
            supports_external=adapter.supports_external,
        )
        request_fingerprint = presentation_request_fingerprint(request)
        approval_decision = self._approval_gate.can_send_to_external_ai(
            registry,
            evaluated_at=timestamp,
        )
        adapter_validation = adapter.validate_request(request)
        registry_validation = _validate_registry(request, registry)
        request_validation = _combine_reports(adapter_validation, registry_validation)
        gate_required = request.request_mode == RequestMode.EXTERNAL

        if not request_validation.is_valid:
            return self._finish(
                request=request,
                descriptor=descriptor,
                request_fingerprint=request_fingerprint,
                approval_decision=approval_decision,
                request_validation=request_validation,
                response_validation=None,
                status=EngineExecutionStatus.BLOCKED,
                timestamp=timestamp,
                errors=("Presentation RequestまたはRegistry整合性の検証に失敗しました。",),
            )
        if gate_required and not approval_decision.allowed:
            gate_issue = AdapterValidationIssue(
                stage=ValidationStage.APPROVAL_GATE,
                code=approval_decision.reason_code,
                path="approval_gate",
                message=approval_decision.reason,
            )
            return self._finish(
                request=request,
                descriptor=descriptor,
                request_fingerprint=request_fingerprint,
                approval_decision=approval_decision,
                request_validation=AdapterValidationReport(
                    is_valid=False,
                    issues=(*request_validation.issues, gate_issue),
                ),
                response_validation=None,
                status=EngineExecutionStatus.BLOCKED,
                timestamp=timestamp,
                errors=(approval_decision.reason,),
            )

        payload = adapter.build_payload(request)
        response = adapter.execute(payload)
        response_validation = adapter.validate_response(request, payload, response)
        if not response_validation.is_valid:
            return self._finish(
                request=request,
                descriptor=descriptor,
                request_fingerprint=request_fingerprint,
                approval_decision=approval_decision,
                request_validation=request_validation,
                response_validation=response_validation,
                status=EngineExecutionStatus.FAILED,
                timestamp=timestamp,
                warnings=response.warnings,
                errors=("Presentation Result Validationに失敗しました。",),
            )

        artifact = GeneratedArtifact(
            artifact_id=f"art_{uuid4().hex}",
            output_type=response.output_type,
            pages=response.pages,
            claims_used=response.claims_used,
            diagram_requests=response.diagram_requests,
            references=response.references,
            request_fingerprint=response.request_fingerprint,
        )
        return self._finish(
            request=request,
            descriptor=descriptor,
            request_fingerprint=request_fingerprint,
            approval_decision=approval_decision,
            request_validation=request_validation,
            response_validation=response_validation,
            status=EngineExecutionStatus.SUCCESS,
            timestamp=timestamp,
            artifacts=(artifact,),
            warnings=response.warnings,
            errors=response.errors,
        )

    def _finish(
        self,
        *,
        request: PresentationRequest,
        descriptor: AdapterDescriptor,
        request_fingerprint: str,
        approval_decision: ApprovalGateDecision,
        request_validation: AdapterValidationReport,
        response_validation: AdapterValidationReport | None,
        status: EngineExecutionStatus,
        timestamp: datetime,
        artifacts: tuple[GeneratedArtifact, ...] = (),
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
    ) -> PresentationEngineRunOutcome:
        gate_required = request.request_mode == RequestMode.EXTERNAL
        valid = (
            request_validation.is_valid
            and response_validation is not None
            and response_validation.is_valid
            and (not gate_required or approval_decision.allowed)
        )
        validation_result = PresentationResultValidation(
            is_valid=valid,
            request_validation=request_validation,
            response_validation=response_validation,
            approval_gate_checked=True,
            approval_gate_required=gate_required,
            approval_gate_allowed=approval_decision.allowed,
        )
        result = PresentationResult(
            request_id=request.identity.presentation_request_id,
            provider=descriptor.provider_name,
            provider_version=descriptor.provider_version,
            status=status,
            created_at=timestamp,
            validation_result=validation_result,
            generated_artifacts=artifacts,
            warnings=warnings,
            errors=errors,
        )
        self._audit_logger.write(
            PresentationEngineAuditRecord(
                request_id=result.request_id,
                provider=result.provider,
                provider_version=result.provider_version,
                mode=request.request_mode,
                status=result.status,
                validation_result=(
                    "passed"
                    if validation_result.is_valid
                    else "failed"
                    if response_validation is not None or request_validation.issues
                    else "not_run"
                ),
                gate_result=approval_decision.allowed,
                timestamp=timestamp,
            )
        )
        return PresentationEngineRunOutcome(
            result=result,
            adapter=descriptor,
            request_fingerprint=request_fingerprint,
            approval_gate=approval_decision,
            audit_log_path=self.audit_log_path,
        )


def _validate_registry(
    request: PresentationRequest,
    registry: RegistryKnowledgeView,
) -> AdapterValidationReport:
    issues: list[AdapterValidationIssue] = []
    source = request.source
    knowledge = registry.knowledge
    comparisons = (
        (
            source.knowledge_id == knowledge.knowledge_id,
            "knowledge_id_mismatch",
            "source.knowledge_id",
            "Presentation RequestのKnowledge IDがRegistryと一致しません。",
        ),
        (
            source.knowledge_version == knowledge.knowledge_version,
            "knowledge_version_mismatch",
            "source.knowledge_version",
            "Presentation RequestのKnowledge VersionがRegistryと一致しません。",
        ),
        (
            source.approval_state == knowledge.status,
            "approval_state_changed",
            "source.approval_state",
            "Presentation Request生成後にApproval Stateが変更されています。",
        ),
        (
            source.review_version == knowledge.knowledge_version,
            "review_version_mismatch",
            "source.review_version",
            "Presentation RequestのReview VersionがRegistryと一致しません。",
        ),
    )
    for passed, code, path, message in comparisons:
        if not passed:
            issues.append(
                AdapterValidationIssue(
                    stage=ValidationStage.REGISTRY,
                    code=code,
                    path=path,
                    message=message,
                )
            )
    return AdapterValidationReport(is_valid=not issues, issues=tuple(issues))


def _combine_reports(
    *reports: AdapterValidationReport,
) -> AdapterValidationReport:
    issues = tuple(issue for report in reports for issue in report.issues)
    return AdapterValidationReport(is_valid=not issues, issues=issues)
