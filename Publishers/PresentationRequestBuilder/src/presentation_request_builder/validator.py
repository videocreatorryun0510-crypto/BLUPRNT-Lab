"""Cross-contract validator for Presentation Request Version 1.0."""

from source_bundle_publisher import SourceBundle

from presentation_request_builder.models import (
    OutputFormat,
    PresentationProfile,
    PresentationRequest,
    PresentationType,
    PresentationValidationReport,
    RequestMode,
    ValidationIssue,
)


class PresentationRequestValidator:
    def validate(
        self,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        profile: PresentationProfile,
        expected_source_fingerprint: str,
    ) -> PresentationValidationReport:
        issues: list[ValidationIssue] = []
        claim_ids = {item.claim_id for item in source_bundle.claims}
        selected = set(request.content_policy.selected_claim_ids)
        key_messages = set(request.content_policy.key_message_claim_ids)
        source_diagrams = {item.request_id for item in source_bundle.diagram_requests}
        requested_diagrams = set(request.content_policy.diagram_request_ids)
        source_references = {item.source_id for item in source_bundle.references}
        requested_references = set(request.content_policy.reference_ids)

        if (
            request.presentation.presentation_type
            != PresentationType.PRESENTATION_DOCUMENT
        ):
            issues.append(
                _issue(
                    "presentation_type_not_enabled",
                    "presentation.presentation_type",
                    "MVPではpresentation_documentだけを生成できます。",
                )
            )
        if request.presentation.output_format != OutputFormat.STRUCTURED_JSON:
            issues.append(
                _issue(
                    "output_format_not_enabled",
                    "presentation.output_format",
                    "MVPではstructured_jsonだけを生成できます。",
                )
            )
        if (
            request.metadata.profile_id != profile.profile_id
            or request.metadata.profile_version != profile.profile_version
        ):
            issues.append(
                _issue(
                    "profile_version_not_found",
                    "metadata",
                    "Presentation Profile IDまたはVersionが一致しません。",
                )
            )
        if selected - claim_ids:
            issues.append(
                _issue(
                    "selected_claim_unknown",
                    "content_policy.selected_claim_ids",
                    "Source Bundleに存在しないClaimが選択されています。",
                )
            )
        if not key_messages.issubset(selected):
            issues.append(
                _issue(
                    "key_message_not_selected",
                    "content_policy.key_message_claim_ids",
                    "Key Messageはselected_claim_idsに含める必要があります。",
                )
            )
        if requested_diagrams - source_diagrams:
            issues.append(
                _issue(
                    "diagram_request_unknown",
                    "content_policy.diagram_request_ids",
                    "Source Bundleに存在しないDiagram Requestが指定されています。",
                )
            )
        if requested_references - source_references:
            issues.append(
                _issue(
                    "reference_unknown",
                    "content_policy.reference_ids",
                    "Source Bundleに存在しないReferenceが指定されています。",
                )
            )
        if request.source.source_fingerprint != expected_source_fingerprint:
            issues.append(
                _issue(
                    "fingerprint_mismatch",
                    "source.source_fingerprint",
                    "Source Fingerprintが最新の入力と一致しません。",
                )
            )
        if (
            request.request_mode == RequestMode.EXTERNAL
            and request.source.approval_state.value != "approved"
        ):
            issues.append(
                _issue(
                    "external_requires_approved",
                    "source.approval_state",
                    "External Requestはapprovedだけが生成できます。",
                )
            )
        if request.content_policy.allow_medical_rephrasing:
            issues.append(
                _issue(
                    "medical_rephrasing_not_allowed",
                    "content_policy.allow_medical_rephrasing",
                    "MVPでは医学的文章の言い換えを許可しません。",
                )
            )
        if request.content_policy.allow_medical_fact_addition:
            issues.append(
                _issue(
                    "medical_fact_addition_not_allowed",
                    "content_policy.allow_medical_fact_addition",
                    "MVPでは医学的事実の追加を許可しません。",
                )
            )
        if not request.validation_policy.require_claim_traceability:
            issues.append(
                _issue(
                    "claim_traceability_required",
                    "validation_policy.require_claim_traceability",
                    "Claim追跡を必須にしてください。",
                )
            )
        if not request.validation_policy.require_reference_traceability:
            issues.append(
                _issue(
                    "reference_traceability_required",
                    "validation_policy.require_reference_traceability",
                    "Reference追跡を必須にしてください。",
                )
            )
        if not request.validation_policy.prohibit_unapproved_medical_additions:
            issues.append(
                _issue(
                    "unapproved_additions_must_be_prohibited",
                    "validation_policy.prohibit_unapproved_medical_additions",
                    "未承認の医学的追加を禁止してください。",
                )
            )
        if request.content_policy.include_references and (
            requested_references != source_references
        ):
            issues.append(
                _issue(
                    "reference_policy_incomplete",
                    "content_policy.reference_ids",
                    "include_references=trueの場合は全Referenceを追跡してください。",
                )
            )
        return PresentationValidationReport(
            is_valid=not issues,
            issues=tuple(issues),
        )


def _issue(
    code: str,
    path: str,
    message: str = "Presentation Requestの値が契約に適合しません。",
) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)
