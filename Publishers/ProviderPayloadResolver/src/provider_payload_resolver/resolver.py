"""Resolve approved SSOT references into a provider-neutral Payload."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from knowledge_contracts.approval_v10 import ApprovalGateDecision
from knowledge_contracts.exam_v10 import ExamMetadataRecord
from knowledge_contracts.registry_v10 import (
    ClaimRegistryEntry,
    RegistryKnowledgeView,
    RegistryStatus,
)
from presentation_request_builder import PresentationRequest
from source_bundle_publisher import SourceBundle

from provider_payload_resolver.audit import JsonlPayloadAuditLogger
from provider_payload_resolver.fingerprint import (
    presentation_payload_fingerprint,
    presentation_request_fingerprint,
)
from provider_payload_resolver.models import (
    ClaimTraceEntry,
    DiagramTraceEntry,
    PayloadAuditRecord,
    PayloadBuildResult,
    PayloadIdentity,
    PayloadMedicalContent,
    PayloadMetadata,
    PayloadPolicies,
    PayloadPresentation,
    PayloadRequest,
    PayloadSource,
    PayloadTraceability,
    PayloadValidationIssue,
    PayloadValidationReport,
    PayloadValidationStage,
    PayloadVisualContent,
    PresentationPayload,
    ReferenceLocator,
    ReferenceTraceEntry,
    ResolvedClaim,
    ResolvedDiagramRequest,
    ResolvedExamMetadata,
    ResolvedKeyMessage,
    ResolvedReference,
)
from provider_payload_resolver.policy import DataEgressPolicyValidator, DataEgressScan
from provider_payload_resolver.writer import PresentationPayloadJsonWriter


class ExternalAiApprovalGate(Protocol):
    def can_send_to_external_ai(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision: ...


class ProviderPayloadResolver:
    """Copy only approved, selected SSOT facts without medical transformation."""

    resolver_id = "bluprnt.provider_payload_resolver"
    resolver_version = "1.0.0"

    def __init__(
        self,
        approval_gate: ExternalAiApprovalGate,
        writer: PresentationPayloadJsonWriter,
        audit_logger: JsonlPayloadAuditLogger,
        policy_validator: DataEgressPolicyValidator | None = None,
    ) -> None:
        self._approval_gate = approval_gate
        self._writer = writer
        self._audit_logger = audit_logger
        self._policy_validator = policy_validator or DataEgressPolicyValidator()

    @classmethod
    def from_directories(
        cls,
        approval_gate: ExternalAiApprovalGate,
        output_directory: Path,
        audit_log_path: Path,
    ) -> "ProviderPayloadResolver":
        return cls(
            approval_gate,
            PresentationPayloadJsonWriter(output_directory),
            JsonlPayloadAuditLogger(audit_log_path),
        )

    @property
    def audit_log_path(self) -> str:
        return str(self._audit_logger.output_path)

    def resolve(
        self,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        registry: RegistryKnowledgeView,
        exam_metadata: ExamMetadataRecord | None,
        *,
        expected_source_fingerprint: str,
        created_at: datetime | None = None,
        include_public_urls: bool = False,
    ) -> PayloadBuildResult:
        timestamp = created_at or datetime.now(UTC)
        payload_id = f"ppd_{uuid4().hex}"
        request_fingerprint = presentation_request_fingerprint(request)
        issues: list[PayloadValidationIssue] = []
        stale_issues = _validate_freshness(
            request,
            source_bundle,
            registry,
            expected_source_fingerprint,
        )
        issues.extend(stale_issues)
        approval_decision = self._approval_gate.can_send_to_external_ai(
            registry,
            evaluated_at=timestamp,
        )
        approval_ok = approval_decision.allowed
        if not approval_ok:
            issues.append(
                _issue(
                    PayloadValidationStage.APPROVAL,
                    approval_decision.reason_code,
                    "approval_gate",
                    approval_decision.reason,
                )
            )

        resolved_claims, claim_issues = _resolve_claims(
            request,
            source_bundle,
            registry,
        )
        issues.extend(claim_issues)
        if stale_issues or not approval_ok or claim_issues:
            return self._blocked(
                payload_id,
                request,
                registry,
                timestamp,
                issues,
                stale_ok=not stale_issues,
                approval_ok=approval_ok,
            )

        selected_ids = tuple(item.claim_id for item in resolved_claims)
        key_messages, key_issues = _resolve_key_messages(
            request,
            source_bundle,
            registry,
            resolved_claims,
        )
        diagrams, diagram_issues = _resolve_diagrams(
            request,
            source_bundle,
            registry,
            selected_ids,
        )
        references, reference_issues = _resolve_references(
            request,
            source_bundle,
            registry,
            selected_ids,
            include_public_urls=include_public_urls,
        )
        exam_points, exam_issues = _resolve_exam_metadata(
            request,
            source_bundle,
            registry,
            exam_metadata,
            selected_ids,
        )
        issues.extend((*key_issues, *diagram_issues, *reference_issues, *exam_issues))
        if issues:
            return self._blocked(
                payload_id,
                request,
                registry,
                timestamp,
                issues,
                stale_ok=True,
                approval_ok=True,
            )

        claim_trace_map = _claim_trace_map(
            resolved_claims,
            key_messages,
            diagrams,
            exam_points,
        )
        provisional = PresentationPayload(
            identity=PayloadIdentity(payload_id=payload_id, created_at=timestamp),
            request=PayloadRequest(
                presentation_request_id=request.identity.presentation_request_id,
                request_mode=request.request_mode,
                presentation_type=request.presentation.presentation_type,
                output_format=request.presentation.output_format,
            ),
            source=PayloadSource(
                knowledge_id=request.source.knowledge_id,
                knowledge_version=request.source.knowledge_version,
                source_bundle_version=request.source.source_bundle_version,
                source_fingerprint=request.source.source_fingerprint,
                presentation_request_fingerprint=request_fingerprint,
                approval_state=request.source.approval_state,
                review_version=request.source.review_version,
            ),
            presentation=PayloadPresentation(
                title=request.presentation.title,
                target_audience=request.presentation.target_audience,
                learning_objective=request.presentation.learning_objective,
                language=request.presentation.language,
                page_or_slide_count=request.layout_policy.page_or_slide_count,
                aspect_ratio=request.layout_policy.aspect_ratio,
                orientation=request.layout_policy.orientation,
                information_density=request.layout_policy.information_density,
                visual_priority=request.layout_policy.visual_priority,
                text_amount=request.layout_policy.text_amount,
            ),
            medical_content=PayloadMedicalContent(
                selected_claims=resolved_claims,
                key_messages=key_messages,
                exam_points=exam_points,
                references=references,
            ),
            visual_content=PayloadVisualContent(diagram_requests=diagrams),
            policies=PayloadPolicies(),
            traceability=PayloadTraceability(
                claim_trace_map=claim_trace_map,
                diagram_trace_map=tuple(
                    DiagramTraceEntry(
                        diagram_request_id=item.diagram_request_id,
                        source_claim_ids=item.source_claim_ids,
                        educational_goal=item.educational_goal,
                    )
                    for item in diagrams
                ),
                reference_trace_map=tuple(
                    ReferenceTraceEntry(
                        reference_id=item.reference_id,
                        supported_claim_ids=item.supported_claim_ids,
                    )
                    for item in references
                ),
            ),
            metadata=PayloadMetadata(
                resolver_id="bluprnt.provider_payload_resolver",
                resolver_version="1.0.0",
                profile_id=request.metadata.profile_id,
                profile_version=request.metadata.profile_version,
                payload_fingerprint="0" * 64,
            ),
        )
        fingerprint = presentation_payload_fingerprint(provisional)
        payload = provisional.model_copy(
            update={
                "metadata": provisional.metadata.model_copy(
                    update={"payload_fingerprint": fingerprint}
                )
            }
        )
        scan = self._policy_validator.validate(payload)
        issues.extend(scan.issues)
        validation = _validation_report(
            issues,
            stale_ok=True,
            approval_ok=True,
            scan=scan,
        )
        if not validation.is_valid:
            return self._blocked(
                payload_id,
                request,
                registry,
                timestamp,
                issues,
                stale_ok=True,
                approval_ok=True,
                scan=scan,
                fingerprint=fingerprint,
            )
        output_path = self._writer.write(payload)
        self._audit(
            PayloadAuditRecord(
                payload_id=payload.identity.payload_id,
                presentation_request_id=request.identity.presentation_request_id,
                knowledge_id=request.source.knowledge_id,
                approval_state=request.source.approval_state,
                payload_fingerprint=fingerprint,
                egress_policy_result=True,
                validation_result="passed",
                result="generated",
                reason="承認済み正本からProvider Payloadを生成しました。",
                timestamp=timestamp,
            )
        )
        return PayloadBuildResult(
            status="success",
            attempted_payload_id=payload.identity.payload_id,
            payload=payload,
            output_path=str(output_path),
            validation=validation,
            external_use_allowed=True,
            stop_reasons=(),
            audit_log_path=self.audit_log_path,
        )

    def _blocked(
        self,
        payload_id: str,
        request: PresentationRequest,
        registry: RegistryKnowledgeView,
        timestamp: datetime,
        issues: list[PayloadValidationIssue],
        *,
        stale_ok: bool,
        approval_ok: bool,
        scan: DataEgressScan | None = None,
        fingerprint: str | None = None,
    ) -> PayloadBuildResult:
        validation = _validation_report(
            issues,
            stale_ok=stale_ok,
            approval_ok=approval_ok,
            scan=scan,
        )
        reasons = tuple(dict.fromkeys(item.message for item in issues)) or (
            "Provider Payloadの安全検証に失敗しました。",
        )
        self._audit(
            PayloadAuditRecord(
                payload_id=payload_id,
                presentation_request_id=request.identity.presentation_request_id,
                knowledge_id=request.source.knowledge_id,
                approval_state=registry.knowledge.status,
                payload_fingerprint=fingerprint,
                egress_policy_result=(scan.egress_policy_result if scan else False),
                validation_result="failed",
                result="blocked",
                reason=" / ".join(reasons)[:4000],
                timestamp=timestamp,
            )
        )
        return PayloadBuildResult(
            status="blocked",
            attempted_payload_id=payload_id,
            payload=None,
            output_path=None,
            validation=validation,
            external_use_allowed=False,
            stop_reasons=reasons,
            audit_log_path=self.audit_log_path,
        )

    def _audit(self, record: PayloadAuditRecord) -> None:
        self._audit_logger.write(record)


def _validate_freshness(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    expected_source_fingerprint: str,
) -> list[PayloadValidationIssue]:
    checks = (
        (
            request.source.knowledge_id == bundle.metadata.knowledge_id
            == registry.knowledge.knowledge_id,
            "knowledge_id_mismatch",
            "source.knowledge_id",
        ),
        (
            request.source.knowledge_version == bundle.metadata.version
            == registry.knowledge.knowledge_version,
            "knowledge_version_mismatch",
            "source.knowledge_version",
        ),
        (
            request.source.source_bundle_version == bundle.schema_version,
            "source_bundle_version_mismatch",
            "source.source_bundle_version",
        ),
        (
            request.source.source_fingerprint
            == bundle.metadata.source_fingerprint
            == expected_source_fingerprint,
            "source_fingerprint_mismatch",
            "source.source_fingerprint",
        ),
        (
            request.source.approval_state == bundle.metadata.approval_state
            == registry.knowledge.status,
            "approval_state_changed",
            "source.approval_state",
        ),
        (
            request.source.review_version == bundle.metadata.review_version
            == registry.knowledge.knowledge_version,
            "review_version_mismatch",
            "source.review_version",
        ),
    )
    return [
        _issue(
            PayloadValidationStage.SOURCE,
            code,
            path,
            "Presentation Request・Source Bundle・Registryの最新版が一致しません。",
        )
        for passed, code, path in checks
        if not passed
    ]


def _resolve_claims(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
) -> tuple[tuple[ResolvedClaim, ...], list[PayloadValidationIssue]]:
    issues: list[PayloadValidationIssue] = []
    claims = {item.claim_id: item for item in registry.claims}
    redirects = {
        item.source_claim_id: item.target_claim_id for item in registry.merge_redirects
    }
    bundle_ids = {item.claim_id for item in bundle.claims}
    resolved: list[ResolvedClaim] = []
    seen: set[str] = set()
    for position, requested_id in enumerate(request.content_policy.selected_claim_ids):
        current_id = _redirect(requested_id, redirects)
        claim = claims.get(current_id)
        if requested_id not in bundle_ids and current_id not in bundle_ids:
            issues.append(
                _issue(
                    PayloadValidationStage.CLAIM,
                    "claim_outside_source_bundle",
                    f"content_policy.selected_claim_ids.{position}",
                    "選択ClaimがSource Bundleに存在しません。",
                )
            )
            continue
        if claim is None or claim.is_deleted:
            issues.append(
                _issue(
                    PayloadValidationStage.CLAIM,
                    "claim_unresolved",
                    f"content_policy.selected_claim_ids.{position}",
                    "選択ClaimをRegistry最新版へ解決できません。",
                )
            )
            continue
        if claim.status == RegistryStatus.DEPRECATED:
            issues.append(
                _issue(
                    PayloadValidationStage.CLAIM,
                    "deprecated_claim_unresolved",
                    f"content_policy.selected_claim_ids.{position}",
                    "deprecated Claimの現行Claimを解決できません。",
                )
            )
            continue
        if claim.status != RegistryStatus.APPROVED:
            issues.append(
                _issue(
                    PayloadValidationStage.CLAIM,
                    "claim_not_approved",
                    f"content_policy.selected_claim_ids.{position}",
                    "未承認ClaimはProvider Payloadへ含められません。",
                )
            )
            continue
        if current_id in seen:
            issues.append(
                _issue(
                    PayloadValidationStage.CLAIM,
                    "claim_redirect_duplicate",
                    f"content_policy.selected_claim_ids.{position}",
                    "Claim Redirect後に選択Claimが重複しました。",
                )
            )
            continue
        seen.add(current_id)
        reference_ids = tuple(
            item.source_id
            for item in bundle.references
            if requested_id in item.supported_claim_ids
            or current_id in item.supported_claim_ids
        )
        resolved.append(_claim_payload(claim, reference_ids))
    return tuple(resolved), issues


def _resolve_key_messages(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    selected: tuple[ResolvedClaim, ...],
) -> tuple[tuple[ResolvedKeyMessage, ...], list[PayloadValidationIssue]]:
    issues: list[PayloadValidationIssue] = []
    selected_by_id = {item.claim_id: item for item in selected}
    redirects = {
        item.source_claim_id: item.target_claim_id for item in registry.merge_redirects
    }
    bundle_keys = {item.claim_id for item in bundle.key_messages}
    resolved: list[ResolvedKeyMessage] = []
    for position, requested_id in enumerate(request.content_policy.key_message_claim_ids):
        current_id = _redirect(requested_id, redirects)
        claim = selected_by_id.get(current_id)
        if requested_id not in bundle_keys and current_id not in bundle_keys:
            issues.append(
                _issue(
                    PayloadValidationStage.KEY_MESSAGE,
                    "key_message_outside_source_bundle",
                    f"content_policy.key_message_claim_ids.{position}",
                    "Key MessageがSource Bundleで指定されていません。",
                )
            )
            continue
        if claim is None:
            issues.append(
                _issue(
                    PayloadValidationStage.KEY_MESSAGE,
                    "key_message_not_selected",
                    f"content_policy.key_message_claim_ids.{position}",
                    "Key Messageはselected_claims内に必要です。",
                )
            )
            continue
        resolved.append(
            ResolvedKeyMessage(
                claim_id=claim.claim_id,
                exact_text=claim.exact_text,
                priority="highest" if position == 0 else "important",
                source_reference_ids=claim.source_reference_ids,
            )
        )
    return tuple(resolved), issues


def _resolve_diagrams(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    selected_ids: tuple[str, ...],
) -> tuple[tuple[ResolvedDiagramRequest, ...], list[PayloadValidationIssue]]:
    issues: list[PayloadValidationIssue] = []
    catalog = {item.request_id: item for item in bundle.diagram_requests}
    redirects = {
        item.source_claim_id: item.target_claim_id for item in registry.merge_redirects
    }
    selected = set(selected_ids)
    resolved: list[ResolvedDiagramRequest] = []
    for position, request_id in enumerate(request.content_policy.diagram_request_ids):
        diagram = catalog.get(request_id)
        if diagram is None:
            issues.append(
                _issue(
                    PayloadValidationStage.DIAGRAM,
                    "diagram_request_unresolved",
                    f"content_policy.diagram_request_ids.{position}",
                    "Diagram RequestをSource Bundleへ解決できません。",
                )
            )
            continue
        source_ids = tuple(_redirect(item, redirects) for item in diagram.source_claim_ids)
        if not set(source_ids).issubset(selected):
            issues.append(
                _issue(
                    PayloadValidationStage.DIAGRAM,
                    "diagram_source_claim_invalid",
                    f"diagram_requests.{request_id}.source_claim_ids",
                    "Diagram Requestが未選択Claimを参照しています。",
                )
            )
            continue
        resolved.append(
            ResolvedDiagramRequest(
                diagram_request_id=diagram.request_id,
                title=diagram.title,
                educational_goal=diagram.learning_goal,
                source_claim_ids=source_ids,
                visual_type=diagram.diagram_type,
                priority="high" if position == 0 else "standard",
                provider_neutral_instruction=diagram.learning_goal,
            )
        )
    return tuple(resolved), issues


def _resolve_references(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    selected_ids: tuple[str, ...],
    *,
    include_public_urls: bool,
) -> tuple[tuple[ResolvedReference, ...], list[PayloadValidationIssue]]:
    issues: list[PayloadValidationIssue] = []
    catalog = {item.source_id: item for item in bundle.references}
    redirects = {
        item.source_claim_id: item.target_claim_id for item in registry.merge_redirects
    }
    selected = set(selected_ids)
    resolved: list[ResolvedReference] = []
    for position, reference_id in enumerate(request.content_policy.reference_ids):
        reference = catalog.get(reference_id)
        if reference is None:
            issues.append(
                _issue(
                    PayloadValidationStage.REFERENCE,
                    "reference_unresolved",
                    f"content_policy.reference_ids.{position}",
                    "ReferenceをSource Bundleへ解決できません。",
                )
            )
            continue
        supported = tuple(
            dict.fromkeys(_redirect(item, redirects) for item in reference.supported_claim_ids)
        )
        if not supported or not set(supported).issubset(selected):
            issues.append(
                _issue(
                    PayloadValidationStage.REFERENCE,
                    "reference_claim_link_broken",
                    f"references.{reference_id}.supported_claim_ids",
                    "Referenceのsupported_claim_idsが選択Claimと一致しません。",
                )
            )
            continue
        public_url = str(reference.url) if include_public_urls and reference.url else None
        resolved.append(
            ResolvedReference(
                reference_id=reference.source_id,
                title=reference.title,
                organization_or_author=reference.issuing_organization,
                publication_year=reference.publication_year,
                locator=ReferenceLocator(
                    public_url=public_url,
                    doi=reference.doi,
                    pmid=reference.pmid,
                    chapter=reference.chapter,
                    pages=reference.pages,
                ),
                supported_claim_ids=supported,
            )
        )
    return tuple(resolved), issues


def _resolve_exam_metadata(
    request: PresentationRequest,
    bundle: SourceBundle,
    registry: RegistryKnowledgeView,
    exam_metadata: ExamMetadataRecord | None,
    selected_ids: tuple[str, ...],
) -> tuple[tuple[ResolvedExamMetadata, ...], list[PayloadValidationIssue]]:
    if (
        not request.content_policy.include_exam_points
        or exam_metadata is None
        or not bundle.exam_points
    ):
        return (), []
    issues: list[PayloadValidationIssue] = []
    if exam_metadata.knowledge_id != request.source.knowledge_id:
        return (), [
            _issue(
                PayloadValidationStage.EXAM_METADATA,
                "exam_metadata_knowledge_mismatch",
                "exam_metadata.knowledge_id",
                "Exam Metadataが異なるKnowledgeを参照しています。",
            )
        ]
    redirects = {
        item.source_claim_id: item.target_claim_id for item in registry.merge_redirects
    }
    selected = set(selected_ids)
    priority_ids = tuple(
        _redirect(item.claim_id, redirects) for item in exam_metadata.priority_claims
    )
    source_bundle_exam_ids = {item.claim_id for item in bundle.exam_points}
    if not set(priority_ids).issubset(selected) or not {
        item.claim_id for item in exam_metadata.priority_claims
    }.issubset(source_bundle_exam_ids):
        issues.append(
            _issue(
                PayloadValidationStage.EXAM_METADATA,
                "exam_priority_claim_invalid",
                "exam_metadata.priority_claims",
                "Exam Metadataの重要Claimが選択ClaimまたはSource Bundleにありません。",
            )
        )
        return (), issues
    return (
        ResolvedExamMetadata(
            exam_metadata_id=exam_metadata.metadata_id,
            importance_score=(
                exam_metadata.importance.importance_score
                if exam_metadata.importance is not None
                else None
            ),
            priority_claim_ids=priority_ids,
            patterns=tuple(item.pattern.value for item in exam_metadata.question_patterns),
            frequent_errors=tuple(
                item.misconception for item in exam_metadata.common_errors
            ),
            source_exam_records=tuple(item.occurrence_id for item in exam_metadata.history),
        ),
    ), issues


def _claim_payload(
    claim: ClaimRegistryEntry,
    reference_ids: tuple[str, ...],
) -> ResolvedClaim:
    return ResolvedClaim(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        exact_text=claim.assertion,
        category_role=claim.field_path,
        source_reference_ids=reference_ids,
        approval_state="approved",
        claim_version=claim.claim_version,
    )


def _claim_trace_map(
    claims: tuple[ResolvedClaim, ...],
    key_messages: tuple[ResolvedKeyMessage, ...],
    diagrams: tuple[ResolvedDiagramRequest, ...],
    exam_points: tuple[ResolvedExamMetadata, ...],
) -> tuple[ClaimTraceEntry, ...]:
    key_ids = {item.claim_id for item in key_messages}
    diagram_ids = {
        claim_id for item in diagrams for claim_id in item.source_claim_ids
    }
    exam_ids = {
        claim_id for item in exam_points for claim_id in item.priority_claim_ids
    }
    trace: list[ClaimTraceEntry] = []
    for position, claim in enumerate(claims, start=1):
        purposes: list[str] = ["selected_claim"]
        if claim.claim_id in key_ids:
            purposes.append("key_message")
        if claim.claim_id in exam_ids:
            purposes.append("exam_point")
        if claim.claim_id in diagram_ids:
            purposes.append("diagram_source")
        trace.append(
            ClaimTraceEntry.model_validate(
                {
                    "claim_id": claim.claim_id,
                    "payload_path": (
                        f"medical_content.selected_claims.{position - 1}"
                    ),
                    "use_purposes": purposes,
                    "display_priority": position,
                }
            )
        )
    return tuple(trace)


def _redirect(claim_id: str, redirects: dict[str, str]) -> str:
    current = claim_id
    seen: set[str] = set()
    while current in redirects and current not in seen:
        seen.add(current)
        current = redirects[current]
    return current


def _validation_report(
    issues: list[PayloadValidationIssue],
    *,
    stale_ok: bool,
    approval_ok: bool,
    scan: DataEgressScan | None,
) -> PayloadValidationReport:
    egress_ok = scan.egress_policy_result if scan else False
    secret_ok = scan.secret_scan_result if scan else True
    path_ok = scan.local_path_scan_result if scan else True
    personal_ok = scan.personal_data_scan_result if scan else True
    fingerprint_ok = scan.fingerprint_result if scan else False
    valid = (
        stale_ok
        and approval_ok
        and egress_ok
        and secret_ok
        and path_ok
        and personal_ok
        and fingerprint_ok
        and not issues
    )
    return PayloadValidationReport(
        is_valid=valid,
        stale_check_result=stale_ok,
        approval_result=approval_ok,
        egress_policy_result=egress_ok,
        secret_scan_result=secret_ok,
        local_path_scan_result=path_ok,
        personal_data_scan_result=personal_ok,
        fingerprint_result=fingerprint_ok,
        issues=tuple(issues),
    )


def _issue(
    stage: PayloadValidationStage,
    code: str,
    path: str,
    message: str,
) -> PayloadValidationIssue:
    return PayloadValidationIssue(stage=stage, code=code, path=path, message=message)
