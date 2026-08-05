"""Structural completeness evaluation for Presentation Artifacts."""

from typing import Literal

from presentation_artifact import PresentationArtifact, artifact_fingerprint

from presentation_artifact_registry.models import (
    ArtifactCompletenessReport,
    CompletenessSection,
)

_SECTION_SCORE = 12.5


def evaluate_artifact_completeness(
    artifact: PresentationArtifact,
) -> ArtifactCompletenessReport:
    page_numbers = [page.page_number for page in artifact.pages]
    claim_ids = {claim.claim_id for claim in artifact.claim_catalog}
    reference_ids = {reference.reference_id for reference in artifact.reference_catalog}
    all_page_claims = {
        claim_id for page in artifact.pages for claim_id in page.supporting_claim_ids
    }
    all_page_references = {
        reference_id for page in artifact.pages for reference_id in page.reference_ids
    }
    diagrams = [
        item
        for page in artifact.pages
        if page.diagram_instruction is not None
        for item in page.diagram_instruction.items
    ]

    checks: tuple[
        tuple[
            Literal[
                "page",
                "headline",
                "learning_goal",
                "claim",
                "diagram",
                "reference",
                "layout",
                "metadata",
            ],
            bool,
            str,
            str,
        ],
        ...,
    ] = (
        (
            "page",
            bool(artifact.pages)
            and page_numbers == list(range(1, len(artifact.pages) + 1)),
            "Pageが1から連続して登録されています。",
            "Page番号またはPage構成を確認してください。",
        ),
        (
            "headline",
            all(bool(page.headline.strip()) for page in artifact.pages),
            "全PageにHeadlineがあります。",
            "Headlineが不足しているPageがあります。",
        ),
        (
            "learning_goal",
            all(bool(page.learning_goal.strip()) for page in artifact.pages),
            "全PageにLearning Goalがあります。",
            "Learning Goalが不足しているPageがあります。",
        ),
        (
            "claim",
            bool(claim_ids) and claim_ids.issubset(all_page_claims),
            "全ClaimがPageから参照されています。",
            "未配置のClaimまたはClaim不足があります。",
        ),
        (
            "diagram",
            bool(diagrams)
            and all(bool(item.source_claim_ids) for item in diagrams),
            "根拠Claim付きDiagram Instructionがあります。",
            "Diagram Instructionまたは根拠Claimが不足しています。",
        ),
        (
            "reference",
            bool(reference_ids)
            and all_page_references.issubset(reference_ids)
            and bool(all_page_references),
            "PageのReferenceがCatalogへ登録されています。",
            "ReferenceまたはPageからのReference参照が不足しています。",
        ),
        (
            "layout",
            all(bool(page.layout_hint.region_order) for page in artifact.pages),
            "全PageにLayout Hintがあります。",
            "Layout Hintが不足しているPageがあります。",
        ),
        (
            "metadata",
            artifact.metadata.fingerprint == artifact_fingerprint(artifact)
            and artifact.identity.artifact_version
            == artifact.metadata.artifact_version,
            "MetadataとFingerprintが整合しています。",
            "Metadata、Version、Fingerprintを確認してください。",
        ),
    )
    sections = tuple(
        CompletenessSection(
            section=section,
            complete=complete,
            score=_SECTION_SCORE if complete else 0,
            message=success_message if complete else failure_message,
        )
        for section, complete, success_message, failure_message in checks
    )
    score = round(sum(section.score for section in sections), 1)
    return ArtifactCompletenessReport(
        score=score,
        is_complete=score == 100,
        sections=sections,
        improvement_candidates=tuple(
            section.message for section in sections if not section.complete
        ),
    )
