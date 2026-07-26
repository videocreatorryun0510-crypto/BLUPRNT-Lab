from dataclasses import replace

import pytest
from pydantic import ValidationError

from publisher_core import (
    DiagramEducationalGoal,
    DiagramIntentProfile,
    DiagramIntentType,
    MissingConceptPolicy,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    SemanticConceptType,
    TemplateRegistry,
    TemplateRegistryError,
    load_profile_catalog,
)


def _request(
    request_id: str,
    *,
    intent_ref: ProfileReference | None = None,
) -> PublicationRequest:
    return PublicationRequest(
        request_id=request_id,
        template_ref=ProfileReference(
            profile_id="template.national_exam_pdf",
            version="1.3.0",
        ),
        knowledge_id="knw_ast_v10_example",
        diagram_intent_profile_ref=intent_ref,
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def test_ast_diagram_intent_builds_three_semantic_bindings(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")

    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("request.ast_diagram_intent_v1"),
    )

    assert publication_source.model_dump(mode="json") == before
    assert plan.plan_schema_version == "1.3"
    assert plan.diagram_intent_profile_ref == ProfileReference(
        profile_id="diagram_intent.ast_learning",
        version="1.0.0",
    )
    assert [item.intent_type for item in plan.diagram_intent_bindings] == [
        DiagramIntentType.MEASUREMENT_PRINCIPLE,
        DiagramIntentType.COMPARISON,
        DiagramIntentType.DISEASE_MECHANISM,
    ]
    measurement = plan.diagram_intent_bindings[0]
    assert measurement.grammar_rule_id == "grammar.ast.reaction"
    assert [step.concept_id for step in measurement.semantic_sequences[0].steps] == [
        "concept.measurement.sample",
        "concept.measurement.reaction",
        "concept.measurement.detection",
        "concept.measurement.result",
    ]
    assert {item.concept_type for item in measurement.concepts} == {
        SemanticConceptType.SAMPLE,
        SemanticConceptType.ANALYTE,
        SemanticConceptType.REAGENT,
        SemanticConceptType.REACTION,
        SemanticConceptType.DETECTION,
        SemanticConceptType.RESULT,
    }
    assert measurement.claim_mapping_strategy.missing_required_concept_policy == (
        MissingConceptPolicy.REPORT_AND_BLOCK_BLUEPRINT
    )
    intent_payload = [item.model_dump(mode="json") for item in plan.diagram_intent_bindings]
    assert "claim_id" not in _all_keys(intent_payload)
    assert "assertion" not in _all_keys(intent_payload)
    assert all(
        not rule.source_claim_key_prefixes
        for item in plan.diagram_intent_bindings
        for rule in item.claim_mapping_strategy.concept_rules
    )


def test_only_diagram_intent_changes_semantic_plan(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base = catalog.diagram_intent_profiles[0]
    payload = base.model_dump(mode="json")
    payload["version"] = "9.1.0"
    payload["intents"][0]["educational_goals"] = ["understand_principle"]
    changed = DiagramIntentProfile.model_validate(payload)
    registry = TemplateRegistry(
        replace(
            catalog,
            diagram_intent_profiles=(*catalog.diagram_intent_profiles, changed),
        )
    )
    planner = PublisherPlanner(registry)
    before = publication_source.model_dump(mode="json")
    base_plan = planner.build_plan(
        publication_source,
        _request("request.intent_base"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request(
            "request.intent_changed",
            intent_ref=ProfileReference(
                profile_id=changed.profile_id,
                version=changed.version,
            ),
        ),
    )

    assert publication_source.model_dump(mode="json") == before
    assert base_plan.content_sections == changed_plan.content_sections
    assert base_plan.education_blocks == changed_plan.education_blocks
    assert base_plan.visuals == changed_plan.visuals
    assert base_plan.visual_grammar_bindings == changed_plan.visual_grammar_bindings
    assert base_plan.placements == changed_plan.placements
    assert base_plan.layout_profile_ref == changed_plan.layout_profile_ref
    assert base_plan.theme_ref == changed_plan.theme_ref
    assert base_plan.diagram_intent_profile_ref != changed_plan.diagram_intent_profile_ref
    assert base_plan.diagram_intent_bindings != changed_plan.diagram_intent_bindings
    assert changed_plan.diagram_intent_bindings[0].educational_goals == (
        DiagramEducationalGoal.UNDERSTAND_PRINCIPLE,
    )


def test_diagram_intent_rejects_prompt_and_medical_prose(profile_root) -> None:
    profile = load_profile_catalog(profile_root).diagram_intent_profiles[0]
    payload = profile.model_dump(mode="json")
    payload["intents"][0]["prompt"] = "AIへ送る文章"
    payload["intents"][0]["medical_text"] = "医学本文"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DiagramIntentProfile.model_validate(payload)


def test_required_concepts_need_claim_mapping_rules(profile_root) -> None:
    profile = load_profile_catalog(profile_root).diagram_intent_profiles[0]
    payload = profile.model_dump(mode="json")
    payload["intents"][0]["claim_mapping_strategy"]["concept_rules"] = payload["intents"][0][
        "claim_mapping_strategy"
    ]["concept_rules"][1:]

    with pytest.raises(ValidationError, match="required intent concept needs"):
        DiagramIntentProfile.model_validate(payload)


def test_registry_rejects_missing_diagram_intent_coverage(profile_root) -> None:
    catalog = load_profile_catalog(profile_root)
    base = catalog.diagram_intent_profiles[0]
    payload = base.model_dump(mode="json")
    payload["version"] = "9.7.0"
    payload["intents"] = payload["intents"][:-1]
    incomplete = DiagramIntentProfile.model_validate(payload)
    template = next(item for item in catalog.templates if item.version == "1.3.0")
    broken_template = template.model_copy(
        update={
            "version": "9.3.0",
            "diagram_intent_profile_ref": ProfileReference(
                profile_id=incomplete.profile_id,
                version=incomplete.version,
            ),
        }
    )

    with pytest.raises(TemplateRegistryError, match="does not cover Visual Profile types"):
        TemplateRegistry(
            replace(
                catalog,
                diagram_intent_profiles=(*catalog.diagram_intent_profiles, incomplete),
                templates=(*catalog.templates, broken_template),
            )
        )


def test_registry_rejects_incompatible_visual_grammar(profile_root) -> None:
    catalog = load_profile_catalog(profile_root)
    base = catalog.diagram_intent_profiles[0]
    payload = base.model_dump(mode="json")
    payload["version"] = "1.3.0"
    payload["intents"][0]["compatible_grammar_rule_ids"] = ["grammar.ast.comparison"]
    incompatible = DiagramIntentProfile.model_validate(payload)
    template = next(item for item in catalog.templates if item.version == "1.3.0")
    broken_template = template.model_copy(
        update={
            "version": "9.4.0",
            "diagram_intent_profile_ref": ProfileReference(
                profile_id=incompatible.profile_id,
                version=incompatible.version,
            ),
        }
    )

    with pytest.raises(TemplateRegistryError, match="incompatible with Visual Grammar"):
        TemplateRegistry(
            replace(
                catalog,
                diagram_intent_profiles=(*catalog.diagram_intent_profiles, incompatible),
                templates=(*catalog.templates, broken_template),
            )
        )


def test_phase_33_plan_12_remains_without_diagram_intent(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.phase33_compatibility",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.2.0",
            ),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    assert plan.plan_schema_version == "1.2"
    assert plan.diagram_intent_profile_ref is None
    assert plan.diagram_intent_bindings == ()
