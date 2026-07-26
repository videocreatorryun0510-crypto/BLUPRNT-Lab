from pathlib import Path

import pdfplumber
import pytest
from publisher_core import (
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    ResolvedTemplate,
    TemplateRegistry,
)
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4

from pdf_publisher import (
    A4LayoutEngine,
    PdfExporter,
    PdfPublisherAdapter,
    PdfThemeEngine,
    PublicationPlanReader,
    PublicationPlanReadError,
)


def test_plan_reader_is_read_only_and_resolves_all_required_blocks(
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    before = publication_source.model_dump(mode="json")

    render_plan = PublicationPlanReader().resolve(
        publication_plan,
        publication_source,
        resolved_profiles,
    )

    assert publication_source.model_dump(mode="json") == before
    assert render_plan.title == "AST"
    assert {item.block_id for item in render_plan.content_blocks} >= {
        "section.definition",
        "section.measurement_method",
        "section.measurement_principle",
        "section.exam_points",
        "section.comparison",
    }
    assert {item.block_id for item in render_plan.visual_blocks} >= {
        "visual.reaction_diagram",
        "visual.comparison_table",
    }


def test_source_fingerprint_mismatch_stops_publication(
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    changed_registry = publication_source.registry.model_copy(
        update={
            "knowledge": publication_source.registry.knowledge.model_copy(
                update={"canonical_name": "変更されたAST"}
            )
        }
    )
    changed_source = publication_source.model_copy(update={"registry": changed_registry})

    with pytest.raises(PublicationPlanReadError, match="Fingerprint"):
        PublicationPlanReader().resolve(
            publication_plan,
            changed_source,
            resolved_profiles,
        )


def test_education_plan_stops_until_pdf_adapter_is_connected(
    publication_source: PublicationSourceBundle,
    registry: TemplateRegistry,
) -> None:
    template_ref = ProfileReference(
        profile_id="template.national_exam_pdf",
        version="1.1.0",
    )
    plan = PublisherPlanner(registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.education_pdf_guard",
            template_ref=template_ref,
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    with pytest.raises(PublicationPlanReadError, match="Education Plan"):
        PublicationPlanReader().resolve(
            plan,
            publication_source,
            registry.resolve(template_ref),
        )


def test_layout_profile_controls_placeholder_position(
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    render_plan = PublicationPlanReader().resolve(
        publication_plan,
        publication_source,
        resolved_profiles,
    )
    layout = A4LayoutEngine().layout(render_plan, resolved_profiles.layout_profile)
    positioned = {item.item_id: item for item in layout.blocks}

    reaction = positioned["visual.reaction_diagram"]
    comparison = positioned["visual.comparison_table"]
    assert reaction.region_id == "region.hero"
    assert reaction.rect.width > comparison.rect.width
    assert reaction.rect.y > comparison.rect.y


def test_theme_engine_changes_design_tokens_without_changing_layout(
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    render_plan = PublicationPlanReader().resolve(
        publication_plan,
        publication_source,
        resolved_profiles,
    )
    layout = A4LayoutEngine().layout(render_plan, resolved_profiles.layout_profile)
    base_theme = PdfThemeEngine().resolve(resolved_profiles.theme)
    changed_colors = tuple(
        color.model_copy(update={"value": "#6B2D5C"}) if color.token == "color.primary" else color
        for color in resolved_profiles.theme.colors
    )
    changed_theme_profile = resolved_profiles.theme.model_copy(update={"colors": changed_colors})
    changed_theme = PdfThemeEngine().resolve(changed_theme_profile)

    assert base_theme.primary_color != changed_theme.primary_color
    assert base_theme.font_name == changed_theme.font_name
    assert (
        layout.blocks
        == A4LayoutEngine().layout(render_plan, resolved_profiles.layout_profile).blocks
    )


def test_pdf_adapter_exports_one_a4_page_with_reviewable_placeholders(
    tmp_path: Path,
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    output_path = tmp_path / "ast.pdf"
    artifact = PdfPublisherAdapter(output_path).publish(
        publication_plan,
        publication_source,
        resolved_profiles,
    )

    reader = PdfReader(output_path)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert float(page.mediabox.width) == pytest.approx(A4[0], abs=0.1)
    assert float(page.mediabox.height) == pytest.approx(A4[1], abs=0.1)
    assert artifact.media_type == "application/pdf"
    assert artifact.plan_source_fingerprint == publication_plan.source_fingerprint

    with pdfplumber.open(output_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    for expected in (
        "AST",
        "測定法",
        "測定原理",
        "国家試験ポイント",
        "Reaction Diagram",
        "Comparison Table",
        "VISUAL PLACEHOLDER",
    ):
        assert expected in text


def test_same_plan_produces_the_same_pdf_hash(
    tmp_path: Path,
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    first = PdfPublisherAdapter(tmp_path / "first.pdf").publish(
        publication_plan,
        publication_source,
        resolved_profiles,
    )
    second = PdfPublisherAdapter(tmp_path / "second.pdf").publish(
        publication_plan,
        publication_source,
        resolved_profiles,
    )

    assert first.content_hash == second.content_hash


def test_exporter_rejects_content_overflow(
    tmp_path: Path,
    publication_plan,
    publication_source: PublicationSourceBundle,
    resolved_profiles: ResolvedTemplate,
) -> None:
    render_plan = PublicationPlanReader().resolve(
        publication_plan,
        publication_source,
        resolved_profiles,
    )
    first = render_plan.content_blocks[0]
    oversized = first.model_copy(update={"items": tuple("長い項目" * 100 for _ in range(30))})
    changed_plan = render_plan.model_copy(
        update={"content_blocks": (oversized, *render_plan.content_blocks[1:])}
    )
    layout = A4LayoutEngine().layout(changed_plan, resolved_profiles.layout_profile)
    theme = PdfThemeEngine().resolve(resolved_profiles.theme)

    from pdf_publisher import PdfExportError

    with pytest.raises(PdfExportError, match="A4一枚"):
        PdfExporter().export(changed_plan, layout, theme, tmp_path / "overflow.pdf")
