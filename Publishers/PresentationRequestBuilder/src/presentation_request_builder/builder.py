"""Source Bundle to provider-neutral Presentation Request builder."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

from knowledge_contracts.approval_v10 import (
    ApprovalGateDecision,
    approval_snapshot_from_registry,
    evaluate_approval_gate,
)
from knowledge_contracts.approval_v10.models import ApprovalGateAction
from knowledge_contracts.registry_v10 import RegistryKnowledgeView
from source_bundle_publisher import SourceBundle

from presentation_request_builder.audit import JsonlPresentationAuditLogger
from presentation_request_builder.models import (
    ContentPolicy,
    LayoutPolicy,
    PresentationAuditRecord,
    PresentationBuildDecision,
    PresentationBuildResult,
    PresentationDefinition,
    PresentationIdentity,
    PresentationMetadata,
    PresentationProfile,
    PresentationReasonCode,
    PresentationRequest,
    PresentationSource,
    PresentationValidationReport,
    RequestMode,
    SourceFreshnessReport,
    ValidationPolicy,
)
from presentation_request_builder.profiles import PresentationProfileCatalog
from presentation_request_builder.validator import PresentationRequestValidator
from presentation_request_builder.writer import PresentationRequestJsonWriter


class ExternalAiApprovalGate(Protocol):
    def can_send_to_external_ai(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision: ...


class PresentationRequestBuilderError(ValueError):
    """Raised when the Presentation Contract cannot be constructed."""


class PresentationRequestBuilder:
    """Build generation conditions without copying or changing medical assertions."""

    builder_id = "bluprnt.presentation_request_builder"
    builder_version = "1.0.0"

    def __init__(
        self,
        catalog: PresentationProfileCatalog,
        writer: PresentationRequestJsonWriter,
        audit_logger: JsonlPresentationAuditLogger,
        external_ai_gate: ExternalAiApprovalGate,
    ) -> None:
        self._catalog = catalog
        self._writer = writer
        self._audit_logger = audit_logger
        self._external_ai_gate = external_ai_gate
        self._validator = PresentationRequestValidator()

    @classmethod
    def from_directories(
        cls,
        profile_directory: Path,
        output_directory: Path,
        audit_log_path: Path,
        external_ai_gate: ExternalAiApprovalGate,
    ) -> "PresentationRequestBuilder":
        return cls(
            PresentationProfileCatalog.from_directory(profile_directory),
            PresentationRequestJsonWriter(output_directory),
            JsonlPresentationAuditLogger(audit_log_path),
            external_ai_gate,
        )

    @property
    def supported_profile_ids(self) -> tuple[str, ...]:
        return self._catalog.profile_ids

    @property
    def audit_log_path(self) -> Path:
        return self._audit_logger.output_path

    def build(
        self,
        source_bundle: SourceBundle,
        registry: RegistryKnowledgeView,
        *,
        expected_source_fingerprint: str,
        profile_id: str = "presentation_document_basic_v1",
        profile_version: Literal["1.0"] = "1.0",
        request_mode: RequestMode = RequestMode.PREVIEW,
        created_at: datetime | None = None,
    ) -> PresentationBuildResult:
        timestamp = created_at or datetime.now(UTC)
        request_id = f"prq_{uuid4().hex}"
        try:
            profile = self._catalog.resolve(profile_id, profile_version)
        except KeyError as error:
            raise PresentationRequestBuilderError(
                f"Presentation Profileが見つかりません: {profile_id} v{profile_version}"
            ) from error

        validated_bundle = SourceBundle.model_validate(source_bundle.model_dump(mode="json"))
        snapshot = approval_snapshot_from_registry(registry.knowledge)
        freshness = _evaluate_freshness(
            validated_bundle,
            registry,
            expected_source_fingerprint,
        )
        external_decision = self._external_decision(
            registry,
            request_mode,
            timestamp,
        )
        gate_reason = _gate_failure(request_mode, snapshot.approval_state.value)
        if not freshness.is_current:
            reason_code = _primary_freshness_reason(freshness)
            return self._blocked(
                request_id=request_id,
                bundle=validated_bundle,
                profile=profile,
                request_mode=request_mode,
                timestamp=timestamp,
                freshness=freshness,
                reason_code=reason_code,
                reason=_freshness_message(reason_code),
                external_allowed=external_decision.allowed,
            )
        if gate_reason is not None:
            reason_code, reason = gate_reason
            return self._blocked(
                request_id=request_id,
                bundle=validated_bundle,
                profile=profile,
                request_mode=request_mode,
                timestamp=timestamp,
                freshness=freshness,
                reason_code=reason_code,
                reason=reason,
                external_allowed=external_decision.allowed,
            )
        if request_mode == RequestMode.EXTERNAL and not external_decision.allowed:
            return self._blocked(
                request_id=request_id,
                bundle=validated_bundle,
                profile=profile,
                request_mode=request_mode,
                timestamp=timestamp,
                freshness=freshness,
                reason_code=cast(
                    PresentationReasonCode,
                    external_decision.reason_code,
                ),
                reason=external_decision.reason,
                external_allowed=False,
            )

        request = _build_contract(
            validated_bundle,
            profile,
            request_id,
            request_mode,
            timestamp,
        )
        validation = self._validator.validate(
            request,
            validated_bundle,
            profile,
            expected_source_fingerprint,
        )
        if not validation.is_valid:
            return self._blocked(
                request_id=request_id,
                bundle=validated_bundle,
                profile=profile,
                request_mode=request_mode,
                timestamp=timestamp,
                freshness=freshness,
                reason_code="validation_failed",
                reason="Presentation Request Validationが成功しませんでした。",
                external_allowed=external_decision.allowed,
                validation=validation,
            )

        output_path = self._writer.write(request)
        decision = PresentationBuildDecision(
            allowed=True,
            reason_code="request_ready",
            reason=(
                "レビュー用Preview Requestを生成できます。"
                if request_mode == RequestMode.PREVIEW
                else "承認済みKnowledgeからExternal Requestを生成できます。"
            ),
            external_use_allowed=external_decision.allowed,
            freshness=freshness,
        )
        self._audit(
            request_id=request_id,
            bundle=validated_bundle,
            profile=profile,
            request_mode=request_mode,
            timestamp=timestamp,
            fingerprint_check=True,
            gate_result=True,
            validation_result="passed",
            result="generated",
            reason=decision.reason,
        )
        return PresentationBuildResult(
            status="success",
            request=request,
            output_path=str(output_path),
            decision=decision,
            validation=validation,
            audit_log_path=str(self.audit_log_path),
        )

    def _external_decision(
        self,
        registry: RegistryKnowledgeView,
        request_mode: RequestMode,
        timestamp: datetime,
    ) -> ApprovalGateDecision:
        if request_mode == RequestMode.EXTERNAL:
            return self._external_ai_gate.can_send_to_external_ai(
                registry,
                evaluated_at=timestamp,
            )
        return evaluate_approval_gate(
            approval_snapshot_from_registry(registry.knowledge),
            ApprovalGateAction.EXTERNAL_AI_SEND,
            evaluated_at=timestamp,
        )

    def _blocked(
        self,
        *,
        request_id: str,
        bundle: SourceBundle,
        profile: PresentationProfile,
        request_mode: RequestMode,
        timestamp: datetime,
        freshness: SourceFreshnessReport,
        reason_code: PresentationReasonCode,
        reason: str,
        external_allowed: bool,
        validation: PresentationValidationReport | None = None,
    ) -> PresentationBuildResult:
        decision = PresentationBuildDecision.model_validate(
            {
                "allowed": False,
                "reason_code": reason_code,
                "reason": reason,
                "external_use_allowed": external_allowed,
                "freshness": freshness,
            }
        )
        self._audit(
            request_id=request_id,
            bundle=bundle,
            profile=profile,
            request_mode=request_mode,
            timestamp=timestamp,
            fingerprint_check=freshness.fingerprint_match,
            gate_result=False,
            validation_result=(
                "failed" if validation is not None and not validation.is_valid else "not_run"
            ),
            result="blocked",
            reason=reason,
        )
        return PresentationBuildResult(
            status="blocked",
            request=None,
            output_path=None,
            decision=decision,
            validation=validation,
            audit_log_path=str(self.audit_log_path),
        )

    def _audit(
        self,
        *,
        request_id: str,
        bundle: SourceBundle,
        profile: PresentationProfile,
        request_mode: RequestMode,
        timestamp: datetime,
        fingerprint_check: bool,
        gate_result: bool,
        validation_result: str,
        result: str,
        reason: str,
    ) -> None:
        self._audit_logger.write(
            PresentationAuditRecord.model_validate(
                {
                    "presentation_request_id": request_id,
                    "knowledge_id": bundle.metadata.knowledge_id,
                    "knowledge_version": bundle.metadata.version,
                    "request_mode": request_mode,
                    "presentation_type": profile.presentation_type,
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                    "approval_state": bundle.metadata.approval_state,
                    "fingerprint_check": fingerprint_check,
                    "gate_result": gate_result,
                    "validation_result": validation_result,
                    "result": result,
                    "reason": reason,
                    "timestamp": timestamp,
                }
            )
        )


def _build_contract(
    bundle: SourceBundle,
    profile: PresentationProfile,
    request_id: str,
    request_mode: RequestMode,
    timestamp: datetime,
) -> PresentationRequest:
    all_claim_ids = tuple(item.claim_id for item in bundle.claims)
    key_message_ids = tuple(item.claim_id for item in bundle.key_messages)
    selected_claim_ids = all_claim_ids if profile.use_all_claims else key_message_ids
    return PresentationRequest(
        identity=PresentationIdentity(
            presentation_request_id=request_id,
            created_at=timestamp,
        ),
        request_mode=request_mode,
        source=PresentationSource(
            knowledge_id=bundle.metadata.knowledge_id,
            knowledge_version=bundle.metadata.version,
            source_bundle_version=bundle.schema_version,
            source_fingerprint=bundle.metadata.source_fingerprint,
            approval_state=bundle.metadata.approval_state,
            review_version=bundle.metadata.review_version,
        ),
        presentation=PresentationDefinition(
            presentation_type=profile.presentation_type,
            title=bundle.title,
            target_audience=profile.target_audience,
            learning_objective=bundle.learning_objective,
            language=profile.language,
            output_format=profile.output_format,
        ),
        content_policy=ContentPolicy(
            use_all_claims=profile.use_all_claims,
            selected_claim_ids=selected_claim_ids,
            key_message_claim_ids=key_message_ids,
            diagram_request_ids=tuple(item.request_id for item in bundle.diagram_requests),
            reference_ids=(
                tuple(item.source_id for item in bundle.references)
                if profile.include_references
                else ()
            ),
            include_references=profile.include_references,
            include_exam_points=profile.include_exam_points,
            allow_medical_rephrasing=profile.allow_medical_rephrasing,
            allow_medical_fact_addition=profile.allow_medical_fact_addition,
            allow_non_medical_presentation_text=(profile.allow_non_medical_presentation_text),
        ),
        layout_policy=LayoutPolicy(
            page_or_slide_count=profile.page_or_slide_count,
            aspect_ratio=profile.aspect_ratio,
            orientation=profile.orientation,
            information_density=profile.information_density,
            visual_priority=profile.visual_priority,
            text_amount=profile.text_amount,
            notes=profile.notes,
        ),
        validation_policy=ValidationPolicy(
            require_claim_traceability=profile.require_claim_traceability,
            require_reference_traceability=profile.require_reference_traceability,
            prohibit_unapproved_medical_additions=(profile.prohibit_unapproved_medical_additions),
            require_source_fingerprint_match=profile.require_source_fingerprint_match,
            require_approval_gate=profile.require_approval_gate,
        ),
        metadata=PresentationMetadata(
            builder_id="bluprnt.presentation_request_builder",
            builder_version="1.0.0",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
        ),
    )


def _evaluate_freshness(
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    expected_fingerprint: str,
) -> SourceFreshnessReport:
    snapshot = approval_snapshot_from_registry(registry.knowledge)
    knowledge_match = (
        bundle.metadata.knowledge_id == registry.knowledge.knowledge_id
        and bundle.metadata.version == registry.knowledge.knowledge_version
    )
    fingerprint_match = bundle.metadata.source_fingerprint == expected_fingerprint
    approval_match = bundle.metadata.approval_state == snapshot.approval_state
    review_match = bundle.metadata.review_version == snapshot.review_version
    failure_codes: list[str] = []
    if not knowledge_match:
        failure_codes.append("knowledge_version_mismatch")
    if not fingerprint_match:
        failure_codes.append("fingerprint_mismatch")
    if not approval_match:
        failure_codes.append("approval_state_changed")
    if not review_match:
        failure_codes.append("review_version_mismatch")
    if failure_codes:
        failure_codes.insert(0, "source_bundle_stale")
    return SourceFreshnessReport.model_validate(
        {
            "is_current": not failure_codes,
            "fingerprint_match": fingerprint_match,
            "knowledge_version_match": knowledge_match,
            "approval_state_match": approval_match,
            "review_version_match": review_match,
            "failure_codes": failure_codes,
        }
    )


def _primary_freshness_reason(
    report: SourceFreshnessReport,
) -> PresentationReasonCode:
    return cast(
        PresentationReasonCode,
        next(
            (item for item in report.failure_codes if item != "source_bundle_stale"),
            "source_bundle_stale",
        ),
    )


def _freshness_message(reason_code: PresentationReasonCode) -> str:
    return {
        "knowledge_version_mismatch": (
            "Source BundleのKnowledge VersionがRegistry最新版と一致しません。"
        ),
        "fingerprint_mismatch": ("Source Bundle Fingerprintが現在の正本データと一致しません。"),
        "approval_state_changed": ("Source Bundle生成後にApproval Stateが変更されています。"),
        "review_version_mismatch": (
            "Source BundleのReview VersionがRegistry最新版と一致しません。"
        ),
        "source_bundle_stale": "Source Bundleが最新状態ではありません。",
    }[reason_code]


def _gate_failure(
    mode: RequestMode,
    approval_state: str,
) -> tuple[PresentationReasonCode, str] | None:
    if approval_state == "deprecated":
        return (
            "knowledge_deprecated",
            "廃止済みKnowledgeからPresentation Requestは生成できません。",
        )
    if approval_state == "published":
        return (
            "published_state_not_enabled",
            "published状態の再利用は将来の運用で定義します。",
        )
    if mode == RequestMode.EXTERNAL and approval_state != "approved":
        return (
            "approval_required",
            (
                f"現在の承認状態は{approval_state}です。"
                "approvedになるまでExternal Requestは生成できません。"
            ),
        )
    return None
