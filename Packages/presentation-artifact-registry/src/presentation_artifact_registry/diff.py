"""Structured version comparison for Presentation Artifacts."""

from presentation_artifact import DiagramInstruction, PresentationArtifact

from presentation_artifact_registry.models import (
    ArtifactDiffReport,
    HeadlineChange,
    PageFieldChange,
)


def compare_artifacts(
    before: PresentationArtifact,
    after: PresentationArtifact,
) -> ArtifactDiffReport:
    if before.identity.artifact_id != after.identity.artifact_id:
        raise ValueError("異なるartifact_id同士は比較できません。")
    before_pages = {page.page_number: page for page in before.pages}
    after_pages = {page.page_number: page for page in after.pages}
    shared_pages = sorted(set(before_pages) & set(after_pages))

    headlines = tuple(
        HeadlineChange(
            page_number=page_number,
            before=before_pages[page_number].headline,
            after=after_pages[page_number].headline,
        )
        for page_number in shared_pages
        if before_pages[page_number].headline != after_pages[page_number].headline
    )
    diagram_changes = tuple(
        PageFieldChange(
            page_number=page_number,
            before=_dump(before_pages[page_number].diagram_instruction),
            after=_dump(after_pages[page_number].diagram_instruction),
        )
        for page_number in shared_pages
        if before_pages[page_number].diagram_instruction
        != after_pages[page_number].diagram_instruction
    )
    layout_changes = tuple(
        PageFieldChange(
            page_number=page_number,
            before=before_pages[page_number].layout_hint.model_dump(mode="json"),
            after=after_pages[page_number].layout_hint.model_dump(mode="json"),
        )
        for page_number in shared_pages
        if before_pages[page_number].layout_hint
        != after_pages[page_number].layout_hint
    )
    before_claims = {item.claim_id for item in before.claim_catalog}
    after_claims = {item.claim_id for item in after.claim_catalog}
    before_references = {item.reference_id for item in before.reference_catalog}
    after_references = {item.reference_id for item in after.reference_catalog}
    pages_added = tuple(sorted(set(after_pages) - set(before_pages)))
    pages_removed = tuple(sorted(set(before_pages) - set(after_pages)))
    claims_added = tuple(sorted(after_claims - before_claims))
    claims_removed = tuple(sorted(before_claims - after_claims))
    references_added = tuple(sorted(after_references - before_references))
    references_removed = tuple(sorted(before_references - after_references))
    has_changes = any(
        (
            headlines,
            pages_added,
            pages_removed,
            claims_added,
            claims_removed,
            references_added,
            references_removed,
            diagram_changes,
            layout_changes,
        )
    )
    return ArtifactDiffReport(
        artifact_id=before.identity.artifact_id,
        from_version=before.identity.artifact_version,
        to_version=after.identity.artifact_version,
        headline_changes=headlines,
        pages_added=pages_added,
        pages_removed=pages_removed,
        claim_ids_added=claims_added,
        claim_ids_removed=claims_removed,
        reference_ids_added=references_added,
        reference_ids_removed=references_removed,
        diagram_changes=diagram_changes,
        layout_changes=layout_changes,
        has_changes=has_changes,
    )


def _dump(value: DiagramInstruction | None) -> dict[str, object] | None:
    if value is None:
        return None
    return value.model_dump(mode="json")
