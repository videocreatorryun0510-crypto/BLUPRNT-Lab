"""Cross-contract validation for Presentation Artifact Version 1.0."""

from typing import Any

from knowledge_contracts.v10 import KnowledgeRecord
from presentation_request_builder import PresentationRequest
from source_bundle_publisher import SourceBundle

from presentation_artifact.fingerprint import artifact_fingerprint, source_bundle_id
from presentation_artifact.models import (
    ArtifactValidationIssue,
    ArtifactValidationReport,
    LayoutComposition,
    PageType,
    PresentationArtifact,
)

_FORBIDDEN_PROVIDER_KEYS = {
    "api",
    "api_key",
    "endpoint",
    "gemini",
    "model",
    "provider",
    "provider_name",
    "provider_version",
}


class PresentationArtifactValidator:
    """Verify source traceability and renderer-neutral structural integrity."""

    def validate(
        self,
        artifact: PresentationArtifact,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        knowledge: KnowledgeRecord,
    ) -> ArtifactValidationReport:
        issues: list[ArtifactValidationIssue] = []

        page_numbers = [page.page_number for page in artifact.pages]
        self._check(
            len(page_numbers) == len(set(page_numbers)),
            issues,
            "duplicate_page_number",
            "pages",
            "Page番号は重複できません。",
        )
        self._check(
            page_numbers == list(range(1, len(artifact.pages) + 1)),
            issues,
            "page_number_sequence_invalid",
            "pages",
            "Page番号は1から連続している必要があります。",
        )
        self._check(
            len(artifact.pages) == request.layout_policy.page_or_slide_count,
            issues,
            "page_count_mismatch",
            "pages",
            "Presentation Requestのページ数と一致しません。",
        )

        bundle_claims = {item.claim_id: item for item in source_bundle.claims}
        knowledge_claims = _knowledge_claim_texts(knowledge)
        catalog_claims = {item.claim_id: item for item in artifact.claim_catalog}
        selected_claims = set(request.content_policy.selected_claim_ids)
        used_claims: set[str] = set()
        for page in artifact.pages:
            if not page.headline.strip():
                issues.append(
                    _issue(
                        "headline_required",
                        f"pages.{page.page_number}.headline",
                        "Headlineは必須です。",
                    )
                )
            used_claims.update(page.supporting_claim_ids)
            for block in page.body_blocks:
                used_claims.add(block.claim_id)
                catalog = catalog_claims.get(block.claim_id)
                self._check(
                    catalog is not None and block.exact_text == catalog.exact_text,
                    issues,
                    "body_claim_text_mismatch",
                    f"pages.{page.page_number}.body_blocks.{block.block_id}",
                    "Body BlockはClaim本文を変更せず保持する必要があります。",
                )
            self._validate_layout(page, issues)

        self._check(
            set(catalog_claims) == selected_claims,
            issues,
            "claim_catalog_mismatch",
            "claim_catalog",
            "Claim CatalogはPresentation Requestの選択Claimと一致する必要があります。",
        )
        self._check(
            selected_claims.issubset(used_claims),
            issues,
            "selected_claim_not_used",
            "pages",
            "選択されたClaimが全てページへ配置されていません。",
        )
        for claim_id, claim in catalog_claims.items():
            bundle_claim = bundle_claims.get(claim_id)
            self._check(
                bundle_claim is not None
                and claim.exact_text == bundle_claim.assertion
                and claim.field_path == bundle_claim.field_path
                and claim.claim_key == bundle_claim.claim_key,
                issues,
                "source_bundle_claim_mismatch",
                f"claim_catalog.{claim_id}",
                "Claim CatalogがSource BundleのClaimと一致しません。",
            )
            self._check(
                knowledge_claims.get(claim_id) == claim.exact_text,
                issues,
                "knowledge_claim_mismatch",
                f"claim_catalog.{claim_id}",
                "Claim本文がKnowledge正本と一致しません。",
            )

        bundle_references = {item.source_id: item for item in source_bundle.references}
        catalog_references = {item.reference_id: item for item in artifact.reference_catalog}
        expected_reference_ids = set(request.content_policy.reference_ids)
        self._check(
            set(catalog_references) == expected_reference_ids,
            issues,
            "reference_catalog_mismatch",
            "reference_catalog",
            "Reference CatalogはPresentation Requestの参照と一致する必要があります。",
        )
        for reference_id, reference in catalog_references.items():
            source_reference = bundle_references.get(reference_id)
            self._check(
                source_reference is not None
                and reference.title == source_reference.title
                and set(reference.supported_claim_ids)
                == set(source_reference.supported_claim_ids),
                issues,
                "reference_source_mismatch",
                f"reference_catalog.{reference_id}",
                "ReferenceがSource Bundleと一致しません。",
            )
        for page in artifact.pages:
            for reference_id in page.reference_ids:
                self._check(
                    reference_id in catalog_references,
                    issues,
                    "unknown_reference_id",
                    f"pages.{page.page_number}.reference_ids",
                    f"未登録Referenceです: {reference_id}",
                )

        expected_diagrams = {
            item.request_id: item for item in source_bundle.diagram_requests
            if item.request_id in request.content_policy.diagram_request_ids
        }
        actual_diagrams = {
            item.request_id: item
            for page in artifact.pages
            if page.diagram_instruction is not None
            for item in page.diagram_instruction.items
        }
        self._check(
            set(actual_diagrams) == set(expected_diagrams),
            issues,
            "diagram_instruction_mismatch",
            "pages.diagram_instruction",
            "Diagram InstructionがPresentation Requestと一致しません。",
        )
        for request_id, diagram in actual_diagrams.items():
            source_diagram = expected_diagrams.get(request_id)
            self._check(
                source_diagram is not None
                and diagram.diagram_type == source_diagram.diagram_type
                and diagram.source_claim_ids == source_diagram.source_claim_ids,
                issues,
                "diagram_source_mismatch",
                f"pages.diagram_instruction.{request_id}",
                "Diagram Instructionの根拠ClaimがSource Bundleと一致しません。",
            )

        self._check(
            artifact.identity.request_id == request.identity.presentation_request_id,
            issues,
            "request_id_mismatch",
            "identity.request_id",
            "Presentation Request IDが一致しません。",
        )
        self._check(
            artifact.identity.source_bundle_id
            == source_bundle_id(source_bundle.metadata.source_fingerprint),
            issues,
            "source_bundle_id_mismatch",
            "identity.source_bundle_id",
            "Source Bundle IDが一致しません。",
        )
        self._check(
            artifact.source.knowledge_id == knowledge.knowledge_id
            and artifact.source.knowledge_version == source_bundle.metadata.version
            and artifact.source.source_fingerprint
            == source_bundle.metadata.source_fingerprint,
            issues,
            "source_identity_mismatch",
            "source",
            "KnowledgeまたはSource Bundleの版・Fingerprintが一致しません。",
        )
        self._check(
            artifact.identity.artifact_version == artifact.metadata.artifact_version,
            issues,
            "artifact_version_mismatch",
            "metadata.artifact_version",
            "Artifact VersionがIdentityとMetadataで一致しません。",
        )
        self._check(
            artifact.metadata.fingerprint == artifact_fingerprint(artifact),
            issues,
            "artifact_fingerprint_mismatch",
            "metadata.fingerprint",
            "Artifact Fingerprintが内容と一致しません。",
        )
        self._check(
            not _contains_forbidden_provider_key(artifact.model_dump(mode="json")),
            issues,
            "provider_specific_field_forbidden",
            "$",
            "Presentation ArtifactにProvider固有フィールドは保存できません。",
        )
        return ArtifactValidationReport(is_valid=not issues, issues=tuple(issues))

    @staticmethod
    def _validate_layout(page: Any, issues: list[ArtifactValidationIssue]) -> None:
        composition = page.layout_hint.composition
        has_diagram = page.diagram_instruction is not None
        diagram_layouts = {
            LayoutComposition.VISUAL_LEFT,
            LayoutComposition.VISUAL_RIGHT,
            LayoutComposition.DIAGRAM_FOCUS,
        }
        if has_diagram and composition not in diagram_layouts:
            issues.append(
                _issue(
                    "diagram_layout_inconsistent",
                    f"pages.{page.page_number}.layout_hint",
                    "図解を持つPageには図解対応Layoutが必要です。",
                )
            )
        if not has_diagram and composition in diagram_layouts:
            issues.append(
                _issue(
                    "layout_requires_diagram",
                    f"pages.{page.page_number}.layout_hint",
                    "図解対応LayoutにはDiagram Instructionが必要です。",
                )
            )
        if page.page_type == PageType.TITLE and composition != LayoutComposition.TITLE:
            issues.append(
                _issue(
                    "title_layout_inconsistent",
                    f"pages.{page.page_number}.layout_hint",
                    "Title Pageにはtitle Layoutが必要です。",
                )
            )

    @staticmethod
    def _check(
        condition: bool,
        issues: list[ArtifactValidationIssue],
        code: str,
        path: str,
        message: str,
    ) -> None:
        if not condition:
            issues.append(_issue(code, path, message))


def _issue(code: str, path: str, message: str) -> ArtifactValidationIssue:
    return ArtifactValidationIssue(code=code, path=path, message=message)


def _knowledge_claim_texts(knowledge: KnowledgeRecord) -> dict[str, str]:
    result: dict[str, str] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            claim_id = value.get("claim_id")
            assertion = value.get("assertion")
            if isinstance(claim_id, str) and isinstance(assertion, str):
                result[claim_id] = assertion
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(knowledge.model_dump(mode="json"))
    return result


def _contains_forbidden_provider_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in _FORBIDDEN_PROVIDER_KEYS
            or _contains_forbidden_provider_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_provider_key(item) for item in value)
    return False
