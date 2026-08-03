"""Presentation Engine request and normalized response validation."""

from presentation_request_builder import PresentationRequest, RequestMode

from presentation_engine_adapter.fingerprint import presentation_request_fingerprint
from presentation_engine_adapter.models import (
    AdapterValidationIssue,
    AdapterValidationReport,
    PresentationEnginePayload,
    PresentationEngineResponse,
    ValidationStage,
)


class PresentationEngineRequestValidator:
    def validate(
        self,
        request: PresentationRequest,
        *,
        supports_preview: bool,
        supports_external: bool,
    ) -> AdapterValidationReport:
        issues: list[AdapterValidationIssue] = []
        if request.request_mode == RequestMode.PREVIEW and not supports_preview:
            issues.append(
                _issue(
                    ValidationStage.REQUEST,
                    "preview_not_supported",
                    "request_mode",
                    "このAdapterはPreviewを実行できません。",
                )
            )
        if request.request_mode == RequestMode.EXTERNAL and not supports_external:
            issues.append(
                _issue(
                    ValidationStage.REQUEST,
                    "external_not_supported",
                    "request_mode",
                    "このAdapterはExternalを実行できません。",
                )
            )
        if request.content_policy.allow_medical_rephrasing:
            issues.append(
                _issue(
                    ValidationStage.REQUEST,
                    "medical_rephrasing_not_allowed",
                    "content_policy.allow_medical_rephrasing",
                    "Adapterは医学的な言い換えを許可できません。",
                )
            )
        if request.content_policy.allow_medical_fact_addition:
            issues.append(
                _issue(
                    ValidationStage.REQUEST,
                    "medical_fact_addition_not_allowed",
                    "content_policy.allow_medical_fact_addition",
                    "Adapterは医学的事実の追加を許可できません。",
                )
            )
        required_policies = {
            "require_claim_traceability": (request.validation_policy.require_claim_traceability),
            "require_reference_traceability": (
                request.validation_policy.require_reference_traceability
            ),
            "prohibit_unapproved_medical_additions": (
                request.validation_policy.prohibit_unapproved_medical_additions
            ),
            "require_source_fingerprint_match": (
                request.validation_policy.require_source_fingerprint_match
            ),
            "require_approval_gate": request.validation_policy.require_approval_gate,
        }
        for field_name, enabled in required_policies.items():
            if not enabled:
                issues.append(
                    _issue(
                        ValidationStage.REQUEST,
                        "required_safety_policy_disabled",
                        f"validation_policy.{field_name}",
                        "必須の安全Policyが無効です。",
                    )
                )
        return AdapterValidationReport(is_valid=not issues, issues=tuple(issues))


class PresentationEngineResponseValidator:
    def validate(
        self,
        request: PresentationRequest,
        payload: PresentationEnginePayload,
        response: PresentationEngineResponse,
    ) -> AdapterValidationReport:
        issues: list[AdapterValidationIssue] = []
        expected_fingerprint = presentation_request_fingerprint(request)
        expected_claims = len(request.content_policy.selected_claim_ids)
        expected_diagrams = len(request.content_policy.diagram_request_ids)
        expected_references = len(request.content_policy.reference_ids)
        comparisons = (
            (
                response.request_id == request.identity.presentation_request_id,
                "request_id_mismatch",
                "request_id",
                "ResponseのRequest IDが元Requestと一致しません。",
            ),
            (
                payload.request_fingerprint == expected_fingerprint
                and response.request_fingerprint == expected_fingerprint,
                "request_fingerprint_mismatch",
                "request_fingerprint",
                "ResponseのRequest Fingerprintが元Requestと一致しません。",
            ),
            (
                response.provider == payload.provider,
                "provider_mismatch",
                "provider",
                "ResponseのProviderが実行Adapterと一致しません。",
            ),
            (
                response.provider_version == payload.provider_version,
                "provider_version_mismatch",
                "provider_version",
                "ResponseのProvider Versionが実行Adapterと一致しません。",
            ),
            (
                response.claims_used == expected_claims,
                "claim_count_mismatch",
                "claims_used",
                "ResponseのClaim数がPresentation Requestと一致しません。",
            ),
            (
                response.diagram_requests == expected_diagrams,
                "diagram_request_count_mismatch",
                "diagram_requests",
                "ResponseのDiagram Request数がPresentation Requestと一致しません。",
            ),
            (
                response.references == expected_references,
                "reference_count_mismatch",
                "references",
                "ResponseのReference数がPresentation Requestと一致しません。",
            ),
            (
                response.pages == request.layout_policy.page_or_slide_count,
                "page_count_mismatch",
                "pages",
                "Responseのページ数がPresentation Requestと一致しません。",
            ),
            (
                response.output_type == request.presentation.presentation_type,
                "output_type_mismatch",
                "output_type",
                "Responseの成果物種別がPresentation Requestと一致しません。",
            ),
            (
                response.status == "success" and not response.errors,
                "provider_response_failed",
                "status",
                "Provider Responseが成功状態ではありません。",
            ),
        )
        for passed, code, path, message in comparisons:
            if not passed:
                issues.append(_issue(ValidationStage.RESPONSE, code, path, message))
        return AdapterValidationReport(is_valid=not issues, issues=tuple(issues))


def _issue(
    stage: ValidationStage,
    code: str,
    path: str,
    message: str,
) -> AdapterValidationIssue:
    return AdapterValidationIssue(
        stage=stage,
        code=code,
        path=path,
        message=message,
    )
