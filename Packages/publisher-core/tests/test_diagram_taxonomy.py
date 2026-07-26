from dataclasses import replace

import pytest
from pydantic import ValidationError

from publisher_core import (
    ClaimMappingResolver,
    DiagramIntentProfile,
    DiagramIntentType,
    DiagramTaxonomyProfile,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanError,
    PublisherPlanner,
    TemplateRegistry,
    TemplateRegistryError,
    load_profile_catalog,
)


def _request(version: str, request_id: str) -> PublicationRequest:
    return PublicationRequest(
        request_id=request_id,
        template_ref=ProfileReference(
            profile_id="template.national_exam_pdf",
            version=version,
        ),
        knowledge_id="knw_ast_v10_example",
    )


def test_ast_taxonomy_resolves_measurement_hierarchy(profile_root) -> None:
    taxonomy = load_profile_catalog(profile_root).diagram_taxonomies[0]

    assert taxonomy.lineage_ids("taxonomy.measurement.enzyme.absorbance") == (
        "taxonomy.measurement",
        "taxonomy.measurement.enzyme",
        "taxonomy.measurement.enzyme.absorbance",
    )
    assert [
        taxonomy.node(taxonomy_id).canonical_name
        for taxonomy_id in taxonomy.lineage_ids("taxonomy.measurement.enzyme.absorbance")
    ] == ["Measurement Principle", "Enzyme Assay", "UV Absorbance"]
    assert taxonomy.root_intent_type("taxonomy.measurement.enzyme.absorbance") == (
        DiagramIntentType.MEASUREMENT_PRINCIPLE
    )


def test_taxonomy_aware_intent_references_id_without_owning_classification(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")

    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("1.5.0", "request.ast_taxonomy_plan"),
    )

    assert publication_source.model_dump(mode="json") == before
    assert plan.plan_schema_version == "1.4"
    assert plan.diagram_taxonomy_ref == ProfileReference(
        profile_id="diagram_taxonomy.medical",
        version="1.0.0",
    )
    measurement = plan.diagram_intent_bindings[0]
    assert measurement.intent_type is None
    assert measurement.taxonomy_id == "taxonomy.measurement.enzyme.absorbance"
    taxonomy_binding = plan.diagram_taxonomy_bindings[0]
    assert taxonomy_binding.taxonomy_path == (
        "taxonomy.measurement",
        "taxonomy.measurement.enzyme",
        "taxonomy.measurement.enzyme.absorbance",
    )
    assert taxonomy_binding.root_intent_type == DiagramIntentType.MEASUREMENT_PRINCIPLE


def test_visual_grammar_only_references_taxonomy_without_classifying(
    template_registry: TemplateRegistry,
) -> None:
    resolved = template_registry.resolve(
        ProfileReference(
            profile_id="template.national_exam_pdf",
            version="1.5.0",
        )
    )

    assert resolved.visual_grammar_profile is not None
    grammar = resolved.visual_grammar_profile
    assert grammar.taxonomy_ref == ProfileReference(
        profile_id="diagram_taxonomy.medical",
        version="1.0.0",
    )
    reaction = next(
        item for item in grammar.rules if item.grammar_rule_id == "grammar.ast.reaction"
    )
    assert reaction.taxonomy_ids == ("taxonomy.measurement.enzyme",)


def test_semantic_blueprint_inherits_resolved_taxonomy_without_render_data(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("1.5.0", "request.ast_taxonomy_blueprint"),
    )

    bundle = ClaimMappingResolver().resolve(plan, publication_source)

    measurement = bundle.blueprints[0]
    assert measurement.schema_version == "1.1"
    assert measurement.intent_type == DiagramIntentType.MEASUREMENT_PRINCIPLE
    assert measurement.taxonomy_id == "taxonomy.measurement.enzyme.absorbance"
    assert measurement.taxonomy_path == (
        "taxonomy.measurement",
        "taxonomy.measurement.enzyme",
        "taxonomy.measurement.enzyme.absorbance",
    )
    payload = measurement.model_dump(mode="json")
    assert not {"x", "y", "color", "font", "svg", "prompt"}.intersection(payload)


def test_legacy_diagram_intent_and_blueprint_remain_compatible(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("1.4.0", "request.ast_legacy_blueprint"),
    )

    assert plan.plan_schema_version == "1.3"
    assert plan.diagram_taxonomy_ref is None
    assert plan.diagram_taxonomy_bindings == ()
    assert plan.diagram_intent_bindings[0].intent_type == (DiagramIntentType.MEASUREMENT_PRINCIPLE)
    legacy_blueprint = ClaimMappingResolver().resolve(plan, publication_source).blueprints[0]
    assert legacy_blueprint.schema_version == "1.0"


def test_planner_rejects_taxonomy_aware_intent_on_legacy_template(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    request = _request("1.4.0", "request.ast_taxonomy_mismatch")
    request = request.model_copy(
        update={
            "diagram_intent_profile_ref": ProfileReference(
                profile_id="diagram_intent.ast_learning",
                version="1.2.0",
            )
        }
    )

    with pytest.raises(PublisherPlanError, match="without Template Taxonomy"):
        PublisherPlanner(template_registry).build_plan(publication_source, request)


def test_taxonomy_rejects_orphan_and_cycle(profile_root) -> None:
    taxonomy = load_profile_catalog(profile_root).diagram_taxonomies[0]
    payload = taxonomy.model_dump(mode="json")
    payload["nodes"][1]["parent_taxonomy_id"] = "taxonomy.unknown"
    with pytest.raises(ValidationError, match="unknown parent"):
        DiagramTaxonomyProfile.model_validate(payload)

    payload = taxonomy.model_dump(mode="json")
    payload["nodes"][0]["parent_taxonomy_id"] = payload["nodes"][1]["taxonomy_id"]
    payload["nodes"][0]["intent_type"] = None
    with pytest.raises(ValidationError, match="cycle"):
        DiagramTaxonomyProfile.model_validate(payload)


def test_registry_rejects_unknown_intent_taxonomy_id(
    profile_root,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base_intent = next(item for item in catalog.diagram_intent_profiles if item.version == "1.2.0")
    payload = base_intent.model_dump(mode="json")
    payload["version"] = "9.6.0"
    payload["intents"][0]["taxonomy_id"] = "taxonomy.measurement.unknown"
    changed_intent = DiagramIntentProfile.model_validate(payload)
    base_template = next(item for item in catalog.templates if item.version == "1.5.0")
    changed_template = base_template.model_copy(
        update={
            "version": "9.6.0",
            "diagram_intent_profile_ref": ProfileReference(
                profile_id=changed_intent.profile_id,
                version=changed_intent.version,
            ),
        }
    )

    with pytest.raises(TemplateRegistryError, match="unknown or deprecated Taxonomy ID"):
        TemplateRegistry(
            replace(
                catalog,
                diagram_intent_profiles=(
                    *catalog.diagram_intent_profiles,
                    changed_intent,
                ),
                templates=(*catalog.templates, changed_template),
            )
        )


def test_flat_taxonomy_supports_more_than_one_thousand_nodes() -> None:
    nodes: list[dict[str, object]] = [
        {
            "taxonomy_id": "taxonomy.scale",
            "parent_taxonomy_id": None,
            "canonical_name": "Scale Root",
            "aliases": [],
            "intent_type": "comparison",
            "status": "active",
            "replacement_taxonomy_id": None,
        }
    ]
    nodes.extend(
        {
            "taxonomy_id": f"taxonomy.scale.item{i}",
            "parent_taxonomy_id": "taxonomy.scale",
            "canonical_name": f"Scale Item {i}",
            "aliases": [],
            "intent_type": None,
            "status": "active",
            "replacement_taxonomy_id": None,
        }
        for i in range(1000)
    )

    taxonomy = DiagramTaxonomyProfile.model_validate(
        {
            "schema_version": "1.0",
            "profile_id": "diagram_taxonomy.scale_test",
            "version": "1.0.0",
            "name": "Scale Test",
            "status": "active",
            "nodes": nodes,
        }
    )

    assert len(taxonomy.nodes) == 1001
    assert taxonomy.lineage_ids("taxonomy.scale.item999") == (
        "taxonomy.scale",
        "taxonomy.scale.item999",
    )
