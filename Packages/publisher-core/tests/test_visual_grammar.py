from dataclasses import replace

import pytest
from pydantic import ValidationError

from publisher_core import (
    CompositionPattern,
    DiagramType,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    TemplateRegistry,
    TemplateRegistryError,
    VisualGrammarProfile,
    load_profile_catalog,
)


def _request(
    request_id: str,
    *,
    grammar_ref: ProfileReference | None = None,
) -> PublicationRequest:
    return PublicationRequest(
        request_id=request_id,
        template_ref=ProfileReference(
            profile_id="template.national_exam_pdf",
            version="1.2.0",
        ),
        knowledge_id="knw_ast_v10_example",
        visual_grammar_profile_ref=grammar_ref,
    )


def test_ast_visual_grammar_builds_three_provider_neutral_bindings(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")

    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("request.ast_visual_grammar_v1"),
    )

    assert publication_source.model_dump(mode="json") == before
    assert plan.plan_schema_version == "1.2"
    assert plan.visual_grammar_profile_ref == ProfileReference(
        profile_id="visual_grammar.ast_learning",
        version="1.0.0",
    )
    assert [item.diagram_type for item in plan.visual_grammar_bindings] == [
        DiagramType.REACTION_DIAGRAM,
        DiagramType.COMPARISON_TABLE,
        DiagramType.DISEASE_MECHANISM,
    ]
    assert [item.composition.pattern for item in plan.visual_grammar_bindings] == [
        CompositionPattern.LEFT_TO_RIGHT,
        CompositionPattern.COMPARISON_TWO_COLUMN,
        CompositionPattern.STEPPED,
    ]
    assert all(item.nodes for item in plan.visual_grammar_bindings)
    assert all(item.label_rule.claim_reference_required for item in plan.visual_grammar_bindings)
    assert plan.illustration_library_hook is not None
    assert plan.illustration_library_hook.resolver_capability_id == "illustration.resolve_by_id"
    assert plan.illustration_library_hook.store_assets_in_knowledge is False
    assert "assertion" not in plan.model_dump_json()


def test_only_visual_grammar_changes_internal_diagram_structure(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base = catalog.visual_grammar_profiles[0]
    payload = base.model_dump(mode="json")
    payload["version"] = "9.1.0"
    payload["rules"][0]["composition"]["pattern"] = "top_to_bottom"
    changed = VisualGrammarProfile.model_validate(payload)
    registry = TemplateRegistry(
        replace(
            catalog,
            visual_grammar_profiles=(*catalog.visual_grammar_profiles, changed),
        )
    )
    planner = PublisherPlanner(registry)
    before = publication_source.model_dump(mode="json")
    base_plan = planner.build_plan(
        publication_source,
        _request("request.grammar_base"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request(
            "request.grammar_changed",
            grammar_ref=ProfileReference(
                profile_id=changed.profile_id,
                version=changed.version,
            ),
        ),
    )

    assert publication_source.model_dump(mode="json") == before
    assert base_plan.content_profile_ref == changed_plan.content_profile_ref
    assert base_plan.education_profile_ref == changed_plan.education_profile_ref
    assert base_plan.visual_profile_ref == changed_plan.visual_profile_ref
    assert base_plan.layout_profile_ref == changed_plan.layout_profile_ref
    assert base_plan.theme_ref == changed_plan.theme_ref
    assert base_plan.design_system_ref == changed_plan.design_system_ref
    assert base_plan.content_sections == changed_plan.content_sections
    assert base_plan.visuals == changed_plan.visuals
    assert base_plan.placements == changed_plan.placements
    assert base_plan.visual_grammar_profile_ref != changed_plan.visual_grammar_profile_ref
    assert base_plan.visual_grammar_bindings != changed_plan.visual_grammar_bindings
    assert changed_plan.visual_grammar_bindings[0].composition.pattern == (
        CompositionPattern.TOP_TO_BOTTOM
    )


def test_visual_grammar_rejects_theme_and_layout_properties(profile_root) -> None:
    profile = load_profile_catalog(profile_root).visual_grammar_profiles[0]
    payload = profile.model_dump(mode="json")
    payload["rules"][0]["composition"]["color"] = "#007A78"
    payload["rules"][0]["composition"]["x"] = 10

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualGrammarProfile.model_validate(payload)


def test_registry_rejects_visual_types_without_grammar(profile_root) -> None:
    catalog = load_profile_catalog(profile_root)
    base = catalog.visual_grammar_profiles[0]
    payload = base.model_dump(mode="json")
    payload["version"] = "1.2.0"
    payload["rules"] = payload["rules"][:-1]
    incomplete = VisualGrammarProfile.model_validate(payload)
    template = next(item for item in catalog.templates if item.version == "1.2.0")
    broken_template = template.model_copy(
        update={
            "version": "9.2.0",
            "visual_grammar_profile_ref": ProfileReference(
                profile_id=incomplete.profile_id,
                version=incomplete.version,
            ),
        }
    )

    with pytest.raises(TemplateRegistryError, match="does not cover Visual Profile types"):
        TemplateRegistry(
            replace(
                catalog,
                visual_grammar_profiles=(*catalog.visual_grammar_profiles, incomplete),
                templates=(*catalog.templates, broken_template),
            )
        )


def test_phase_32_plan_11_remains_without_visual_grammar(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.phase32_compatibility",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.1.0",
            ),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    assert plan.plan_schema_version == "1.1"
    assert plan.visual_grammar_profile_ref is None
    assert plan.visual_grammar_bindings == ()
    assert plan.illustration_library_hook is None
