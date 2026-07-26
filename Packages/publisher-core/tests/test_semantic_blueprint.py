import pytest
from knowledge_contracts.registry_v10 import RegistryStatus
from pydantic import ValidationError

from publisher_core import (
    ClaimMappingError,
    ClaimMappingResolver,
    ClaimMatchCriterion,
    DiagramIntentType,
    MissingConceptOrigin,
    MissingConceptReason,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    SemanticBlueprint,
    SemanticRelation,
    TemplateRegistry,
)


def _plan(
    registry: TemplateRegistry,
    source: PublicationSourceBundle,
    request_id: str = "request.ast_semantic_blueprint_test",
):
    return PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id=request_id,
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.4.0",
            ),
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def _missing_ids(blueprint) -> set[str]:
    return {item.concept_id for item in blueprint.missing_concepts}


def test_ast_resolver_generates_three_semantic_blueprints_without_render_data(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")
    plan = _plan(template_registry, publication_source)

    bundle = ClaimMappingResolver().resolve(plan, publication_source)

    assert publication_source.model_dump(mode="json") == before
    assert [item.intent_type for item in bundle.blueprints] == [
        DiagramIntentType.MEASUREMENT_PRINCIPLE,
        DiagramIntentType.COMPARISON,
        DiagramIntentType.DISEASE_MECHANISM,
    ]
    measurement, comparison, mechanism = bundle.blueprints
    assert measurement.is_complete is False
    assert _missing_ids(measurement) == {
        "concept.measurement.sample",
        "concept.measurement.reagent",
    }
    assert comparison.is_complete is True
    assert comparison.missing_concepts == ()
    assert mechanism.is_complete is False
    assert _missing_ids(mechanism) == {
        "concept.mechanism.cause",
        "concept.mechanism.tissue",
    }
    approved_ids = {
        item.claim_id
        for item in publication_source.registry.claims
        if item.status == RegistryStatus.APPROVED and not item.is_deleted
    }
    assert all(
        mapping.claim_ref.claim_id in approved_ids
        for blueprint in bundle.blueprints
        for mapping in blueprint.mapped_claims
    )
    assert all(
        mapping.matched_by == ClaimMatchCriterion.CLAIM_KEY_PREFIX
        for blueprint in bundle.blueprints
        for mapping in blueprint.mapped_claims
    )
    forbidden = {
        "assertion",
        "x",
        "y",
        "color",
        "font",
        "svg",
        "prompt",
        "provider_id",
    }
    assert not forbidden.intersection(_all_keys(bundle.model_dump(mode="json")))


def test_missing_report_distinguishes_knowledge_shortage(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    bundle = ClaimMappingResolver().resolve(
        _plan(template_registry, publication_source),
        publication_source,
    )
    sample = next(
        item
        for item in bundle.blueprints[0].missing_concepts
        if item.concept_id == "concept.measurement.sample"
    )

    assert sample.origin == MissingConceptOrigin.KNOWLEDGE
    assert sample.reason == MissingConceptReason.NO_MATCHING_CLAIM
    assert sample.required_minimum_claims == 1
    assert sample.matched_approved_claims == 0


def test_resolver_does_not_infer_from_assertion_text(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    base = publication_source.registry.claims[0]
    unrelated = base.model_copy(
        update={
            "claim_id": "clm_99999999",
            "claim_key": "ast.unrelated.specimen_text",
            "field_path": "category_content.test_item.purposes",
            "assertion": "血清検体を使用する。",
            "fact_payload": {
                "claim_id": "clm_99999999",
                "assertion": "血清検体を使用する。",
            },
        }
    )
    registry = publication_source.registry.model_copy(
        update={"claims": [*publication_source.registry.claims, unrelated]}
    )
    source = publication_source.model_copy(update={"registry": registry})

    bundle = ClaimMappingResolver().resolve(_plan(template_registry, source), source)

    assert "concept.measurement.sample" in _missing_ids(bundle.blueprints[0])
    assert all(
        item.claim_ref.claim_id != "clm_99999999"
        for blueprint in bundle.blueprints
        for item in blueprint.mapped_claims
    )


def test_missing_report_identifies_unapproved_candidate(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    base = publication_source.registry.claims[0]
    draft_specimen = base.model_copy(
        update={
            "claim_id": "clm_88888888",
            "claim_key": "ast.specimen.serum",
            "field_path": "category_content.test_item.specimens",
            "assertion": "血清を検体とする。",
            "status": RegistryStatus.DRAFT,
            "fact_payload": {
                "claim_id": "clm_88888888",
                "assertion": "血清を検体とする。",
            },
        }
    )
    registry = publication_source.registry.model_copy(
        update={"claims": [*publication_source.registry.claims, draft_specimen]}
    )
    source = publication_source.model_copy(update={"registry": registry})
    bundle = ClaimMappingResolver().resolve(_plan(template_registry, source), source)
    sample = next(
        item
        for item in bundle.blueprints[0].missing_concepts
        if item.concept_id == "concept.measurement.sample"
    )

    assert sample.origin == MissingConceptOrigin.KNOWLEDGE
    assert sample.reason == MissingConceptReason.NO_APPROVED_CLAIM
    assert sample.matching_unapproved_claims == 1


def test_missing_report_identifies_intent_mapping_shortage(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = _plan(template_registry, publication_source)
    measurement = plan.diagram_intent_bindings[0]
    strategy = measurement.claim_mapping_strategy.model_copy(
        update={
            "concept_rules": tuple(
                item
                for item in measurement.claim_mapping_strategy.concept_rules
                if item.concept_id != "concept.measurement.sample"
            )
        }
    )
    changed_measurement = measurement.model_copy(update={"claim_mapping_strategy": strategy})
    changed_plan = plan.model_copy(
        update={
            "diagram_intent_bindings": (
                changed_measurement,
                *plan.diagram_intent_bindings[1:],
            )
        }
    )

    bundle = ClaimMappingResolver().resolve(changed_plan, publication_source)
    sample = next(
        item
        for item in bundle.blueprints[0].missing_concepts
        if item.concept_id == "concept.measurement.sample"
    )

    assert sample.origin == MissingConceptOrigin.INTENT
    assert sample.reason == MissingConceptReason.MAPPING_RULE_MISSING


def test_semantic_relations_are_copied_from_intent_without_inference(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = _plan(template_registry, publication_source)
    bundle = ClaimMappingResolver().resolve(plan, publication_source)

    for planned_intent, blueprint in zip(
        plan.diagram_intent_bindings,
        bundle.blueprints,
        strict=True,
    ):
        expected = [
            step.relation_to_next
            for sequence in planned_intent.semantic_sequences
            for step in sorted(sequence.steps, key=lambda item: item.order)[:-1]
        ]
        assert [item.relation_type for item in blueprint.semantic_relations] == expected
    assert {
        SemanticRelation.CAUSES,
        SemanticRelation.MEASURES,
        SemanticRelation.CONTAINS,
        SemanticRelation.COMPARES,
        SemanticRelation.DERIVED_FROM,
        SemanticRelation.FLOWS_TO,
    }.issubset(set(SemanticRelation))


def test_semantic_blueprint_rejects_render_properties(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    blueprint = (
        ClaimMappingResolver()
        .resolve(
            _plan(template_registry, publication_source),
            publication_source,
        )
        .blueprints[0]
    )
    payload = blueprint.model_dump(mode="json")
    payload["color"] = "#00AACC"
    payload["x"] = 100
    payload["prompt"] = "図を生成する"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SemanticBlueprint.model_validate(payload)


def test_semantic_blueprint_is_deterministic(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = _plan(template_registry, publication_source)
    resolver = ClaimMappingResolver()

    first = resolver.resolve(plan, publication_source)
    second = resolver.resolve(plan, publication_source)

    assert first == second
    assert [item.revision_hash for item in first.blueprints] == [
        item.revision_hash for item in second.blueprints
    ]


def test_resolver_rejects_source_drift(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = _plan(template_registry, publication_source)
    changed_knowledge = publication_source.knowledge.model_copy(update={"content_revision": 2})
    changed_source = publication_source.model_copy(update={"knowledge": changed_knowledge})

    with pytest.raises(ClaimMappingError, match="Knowledge revision"):
        ClaimMappingResolver().resolve(plan, changed_source)
