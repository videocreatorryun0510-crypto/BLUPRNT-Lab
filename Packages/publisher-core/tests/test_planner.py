from dataclasses import replace
from datetime import UTC, datetime

import pytest
from knowledge_contracts.registry_v10 import ClaimMergeRedirect, RegistryStatus
from pydantic import ValidationError

from publisher_core import (
    OutputKind,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanError,
    PublisherPlanner,
    TemplateRegistry,
    load_profile_catalog,
)


@pytest.mark.parametrize(
    ("template_id", "output_kind"),
    [
        ("template.national_exam_pdf", OutputKind.PDF),
        ("template.note_article", OutputKind.NOTE),
        ("template.training_video", OutputKind.TRAINING_VIDEO),
        ("template.national_exam", OutputKind.NATIONAL_EXAM),
    ],
)
def test_one_publisher_core_builds_all_four_output_plans(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
    template_id: str,
    output_kind: OutputKind,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id=f"request.{output_kind.value}",
            template_ref=ProfileReference(profile_id=template_id, version="1.0.0"),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    assert plan.output_kind == output_kind
    assert plan.content_sections
    assert plan.visuals
    assert plan.placements
    assert plan.theme_ref.profile_id == "theme.bluprnt_exam"


def test_planner_never_changes_knowledge_exam_or_registry(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")

    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.read_only_check",
            template_ref=ProfileReference(profile_id="template.national_exam_pdf", version="1.0.0"),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    assert publication_source.model_dump(mode="json") == before
    assert "assertion" not in plan.model_dump_json()
    assert {item.claim_key for item in plan.visuals[0].claim_refs} == {
        "ast.jscc",
        "ast.measurement.340nm",
    }


def test_content_profile_change_only_changes_selected_content(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base_template = next(
        item
        for item in catalog.templates
        if item.template_id == "template.national_exam_pdf" and item.version == "1.0.0"
    )
    base_content = next(
        item
        for item in catalog.content_profiles
        if item.profile_id == base_template.content_profile_ref.profile_id
    )
    definition = base_content.sections[0]
    changed_method = base_content.sections[1].model_copy(update={"selector": definition.selector})
    changed_content = base_content.model_copy(
        update={
            "version": "1.9.0",
            "sections": (
                base_content.sections[0],
                changed_method,
                *base_content.sections[2:],
            ),
        }
    )
    changed_template = base_template.model_copy(
        update={
            "version": "1.9.0",
            "content_profile_ref": ProfileReference(
                profile_id=changed_content.profile_id, version=changed_content.version
            ),
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            content_profiles=(*catalog.content_profiles, changed_content),
            templates=(*catalog.templates, changed_template),
        )
    )
    planner = PublisherPlanner(registry)
    base_plan = planner.build_plan(
        publication_source,
        _request("request.content_base", base_template.template_id, "1.0.0"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request("request.content_changed", changed_template.template_id, "1.9.0"),
    )

    assert base_plan.content_sections != changed_plan.content_sections
    assert base_plan.visuals == changed_plan.visuals
    assert base_plan.layout_profile_ref == changed_plan.layout_profile_ref
    assert base_plan.theme_ref == changed_plan.theme_ref


def test_visual_profile_change_only_changes_visual_plan(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base_template = next(
        item
        for item in catalog.templates
        if item.template_id == "template.national_exam_pdf" and item.version == "1.0.0"
    )
    base_visual = next(
        item
        for item in catalog.visual_profiles
        if item.profile_id == base_template.visual_profile_ref.profile_id
    )
    first_visual = base_visual.visuals[0].model_copy(
        update={"caption": "変更された図解キャプション"}
    )
    changed_visual = base_visual.model_copy(
        update={"version": "9.1.0", "visuals": (first_visual, *base_visual.visuals[1:])}
    )
    changed_template = base_template.model_copy(
        update={
            "version": "9.2.0",
            "visual_profile_ref": ProfileReference(
                profile_id=changed_visual.profile_id, version=changed_visual.version
            ),
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            visual_profiles=(*catalog.visual_profiles, changed_visual),
            templates=(*catalog.templates, changed_template),
        )
    )
    planner = PublisherPlanner(registry)
    base_plan = planner.build_plan(
        publication_source,
        _request("request.visual_base", base_template.template_id, "1.0.0"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request("request.visual_changed", changed_template.template_id, "9.2.0"),
    )

    assert base_plan.content_sections == changed_plan.content_sections
    assert base_plan.visuals != changed_plan.visuals
    assert base_plan.layout_profile_ref == changed_plan.layout_profile_ref
    assert base_plan.theme_ref == changed_plan.theme_ref


def test_layout_profile_change_only_changes_composition(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base_template = next(
        item
        for item in catalog.templates
        if item.template_id == "template.national_exam_pdf" and item.version == "1.0.0"
    )
    base_layout = next(
        item
        for item in catalog.layout_profiles
        if item.profile_id == base_template.layout_profile_ref.profile_id
    )
    moved_placement = base_layout.placements[0].model_copy(update={"order": 20})
    changed_layout = base_layout.model_copy(
        update={
            "version": "1.9.0",
            "placements": (moved_placement, *base_layout.placements[1:]),
        }
    )
    base_design = next(
        item
        for item in catalog.design_systems
        if item.profile_id == base_template.design_system_ref.profile_id
        and item.version == base_template.design_system_ref.version
    )
    changed_rules = tuple(
        rule.model_copy(
            update={
                "layout_ref": ProfileReference(
                    profile_id=changed_layout.profile_id,
                    version=changed_layout.version,
                )
            }
        )
        if rule.output_kind == OutputKind.PDF
        else rule
        for rule in base_design.composition_rules
    )
    changed_design = base_design.model_copy(
        update={"version": "1.9.0", "composition_rules": changed_rules}
    )
    changed_template = base_template.model_copy(
        update={
            "version": "1.9.0",
            "layout_profile_ref": ProfileReference(
                profile_id=changed_layout.profile_id, version=changed_layout.version
            ),
            "design_system_ref": ProfileReference(
                profile_id=changed_design.profile_id, version=changed_design.version
            ),
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            layout_profiles=(*catalog.layout_profiles, changed_layout),
            design_systems=(*catalog.design_systems, changed_design),
            templates=(*catalog.templates, changed_template),
        )
    )
    planner = PublisherPlanner(registry)
    base_plan = planner.build_plan(
        publication_source,
        _request("request.layout_base", base_template.template_id, "1.0.0"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request("request.layout_changed", changed_template.template_id, "1.9.0"),
    )

    assert base_plan.content_sections == changed_plan.content_sections
    assert base_plan.visuals == changed_plan.visuals
    assert base_plan.placements != changed_plan.placements
    assert base_plan.theme_ref == changed_plan.theme_ref


def test_theme_profile_change_keeps_content_visual_and_layout(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base_template = next(
        item
        for item in catalog.templates
        if item.template_id == "template.national_exam_pdf" and item.version == "1.0.0"
    )
    base_theme = next(
        item
        for item in catalog.themes
        if item.profile_id == base_template.theme_ref.profile_id
        and item.version == base_template.theme_ref.version
    )
    changed_primary = base_theme.colors[2].model_copy(update={"value": "#254F73"})
    changed_theme = base_theme.model_copy(
        update={
            "version": "1.1.0",
            "colors": (
                *base_theme.colors[:2],
                changed_primary,
                *base_theme.colors[3:],
            ),
        }
    )
    base_design = next(
        item
        for item in catalog.design_systems
        if item.profile_id == base_template.design_system_ref.profile_id
        and item.version == base_template.design_system_ref.version
    )
    changed_design = base_design.model_copy(
        update={
            "version": "1.2.0",
            "theme_ref": ProfileReference(
                profile_id=changed_theme.profile_id, version=changed_theme.version
            ),
        }
    )
    changed_template = base_template.model_copy(
        update={
            "version": "9.4.0",
            "theme_ref": ProfileReference(
                profile_id=changed_theme.profile_id, version=changed_theme.version
            ),
            "design_system_ref": ProfileReference(
                profile_id=changed_design.profile_id, version=changed_design.version
            ),
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            themes=(*catalog.themes, changed_theme),
            design_systems=(*catalog.design_systems, changed_design),
            templates=(*catalog.templates, changed_template),
        )
    )
    planner = PublisherPlanner(registry)
    base_plan = planner.build_plan(
        publication_source,
        _request("request.theme_base", base_template.template_id, "1.0.0"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request("request.theme_changed", changed_template.template_id, "9.4.0"),
    )

    assert base_plan.content_sections == changed_plan.content_sections
    assert base_plan.visuals == changed_plan.visuals
    assert base_plan.placements == changed_plan.placements
    assert base_plan.theme_ref != changed_plan.theme_ref


def test_required_draft_claim_stops_publication_plan(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    claims = tuple(
        claim.model_copy(update={"status": RegistryStatus.DRAFT})
        if claim.claim_key == "ast.measurement.340nm"
        else claim
        for claim in publication_source.registry.claims
    )
    changed_registry = publication_source.registry.model_copy(update={"claims": claims})
    changed_source = PublicationSourceBundle(
        knowledge=publication_source.knowledge,
        exam_metadata=publication_source.exam_metadata,
        registry=changed_registry,
    )

    with pytest.raises(PublisherPlanError, match="required Content section"):
        PublisherPlanner(template_registry).build_plan(
            changed_source,
            _request(
                "request.draft_claim",
                "template.national_exam_pdf",
                "1.0.0",
            ),
        )


def test_old_profile_claim_key_follows_registry_merge_redirect(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    old_claim = next(
        claim for claim in publication_source.registry.claims if claim.claim_key == "ast.jscc"
    )
    deprecated = old_claim.model_copy(update={"status": RegistryStatus.DEPRECATED})
    target = old_claim.model_copy(
        update={
            "claim_id": "clm_10000006",
            "claim_key": "ast.measurement.jscc_standard",
            "fact_payload": {
                "claim_id": "clm_10000006",
                "assertion": old_claim.assertion,
            },
        }
    )
    claims = [
        deprecated if claim.claim_id == old_claim.claim_id else claim
        for claim in publication_source.registry.claims
    ] + [target]
    redirect = ClaimMergeRedirect(
        source_claim_id=old_claim.claim_id,
        source_claim_key=old_claim.claim_key,
        target_claim_id=target.claim_id,
        target_claim_key=target.claim_key,
        merged_at=datetime(2026, 7, 17, tzinfo=UTC),
        actor="owner",
        comment="同義Claimを統合",
    )
    redirected_registry = publication_source.registry.model_copy(
        update={"claims": claims, "merge_redirects": [redirect]}
    )
    redirected_source = PublicationSourceBundle(
        knowledge=publication_source.knowledge,
        exam_metadata=publication_source.exam_metadata,
        registry=redirected_registry,
    )

    plan = PublisherPlanner(template_registry).build_plan(
        redirected_source,
        _request(
            "request.merge_redirect",
            "template.national_exam_pdf",
            "1.0.0",
        ),
    )

    method_section = next(
        item for item in plan.content_sections if item.section_id == "section.measurement_method"
    )
    assert method_section.claim_refs[0].claim_id == "clm_10000006"
    assert method_section.claim_refs[0].claim_key == "ast.measurement.jscc_standard"


def test_unapproved_knowledge_cannot_enter_publisher(
    publication_source: PublicationSourceBundle,
) -> None:
    draft_knowledge = publication_source.registry.knowledge.model_copy(
        update={"status": RegistryStatus.DRAFT}
    )
    draft_registry = publication_source.registry.model_copy(update={"knowledge": draft_knowledge})

    with pytest.raises(ValidationError, match="approved Knowledge"):
        PublicationSourceBundle(
            knowledge=publication_source.knowledge,
            exam_metadata=publication_source.exam_metadata,
            registry=draft_registry,
        )


def _request(request_id: str, template_id: str, version: str) -> PublicationRequest:
    return PublicationRequest(
        request_id=request_id,
        template_ref=ProfileReference(profile_id=template_id, version=version),
        knowledge_id="knw_ast_v10_example",
    )
