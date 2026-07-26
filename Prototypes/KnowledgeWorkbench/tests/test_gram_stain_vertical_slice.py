import json
from pathlib import Path

from knowledge_contracts.registry_v10 import (
    RegistryEntityType,
    RegistryStatus,
)
from knowledge_contracts.v10 import (
    KnowledgeRecord,
    evaluate_staining_method_completeness,
    validate_knowledge_record,
)
from publisher_core import (
    ClaimMappingResolver,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    TemplateRegistry,
)

from knowledge_workbench.exam_metadata_provider import DummyExamMetadataProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = REPOSITORY_ROOT / "Packages" / "publisher-core" / "profiles"
DESIGN_SAMPLE_PATH = (
    REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0" / "staining-method.example.json"
)


def _raw_staining_method() -> dict[str, object]:
    return json.loads(DESIGN_SAMPLE_PATH.read_text(encoding="utf-8"))


def _approve(
    registry: SQLiteKnowledgeRegistry,
    record: KnowledgeRecord,
) -> PublicationSourceBundle:
    reconciled = registry.reconcile(record, actor="phase_4_1_vertical_slice")
    exam_metadata = DummyExamMetadataProvider().build("Gram染色", reconciled.record)
    claim_ids = [item.claim_id for item in reconciled.view.claims]
    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        registry.transition_claims_status(
            claim_ids,
            status,
            actor="phase_4_1_reviewer",
            note="互換性検証用データをVertical Sliceで承認",
        )
        registry.transition_status(
            RegistryEntityType.KNOWLEDGE,
            reconciled.record.knowledge_id,
            status,
            actor="phase_4_1_reviewer",
            note="互換性検証用データをVertical Sliceで承認",
        )
    return PublicationSourceBundle(
        knowledge=reconciled.record,
        exam_metadata=exam_metadata,
        registry=registry.view(reconciled.record.knowledge_id),
    )


def test_staining_method_is_a_formal_category_with_full_completeness() -> None:
    raw = json.loads(DESIGN_SAMPLE_PATH.read_text(encoding="utf-8"))
    record = validate_knowledge_record(raw)
    completeness = evaluate_staining_method_completeness(record)

    assert record.classification.term_type == "staining_method"
    assert record.category_content.template_id == "staining_method_v1.0"
    assert completeness.profile_id == "knowledge_completeness.staining_method"
    assert completeness.score == 100
    assert completeness.is_complete_for_review is True


def test_gram_stain_claim_dictionary_is_stable_when_steps_are_reordered(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    first = registry.reconcile(validate_knowledge_record(_raw_staining_method()))
    first_ids = {item.claim_key: item.claim_id for item in first.view.claims}
    reordered = _raw_staining_method()
    category = reordered["category_content"]
    assert isinstance(category, dict)
    staining_method = category["staining_method"]
    assert isinstance(staining_method, dict)
    steps = staining_method["procedure_steps"]
    assert isinstance(steps, list)
    steps.reverse()

    second = registry.reconcile(validate_knowledge_record(reordered))
    second_ids = {item.claim_key: item.claim_id for item in second.view.claims}

    assert first_ids == second_ids
    assert set(first_ids) >= {
        "gram.stain.definition.differential_stain",
        "gram.stain.procedure.step1_primary_stain",
        "gram.stain.procedure.step2_mordant",
        "gram.stain.procedure.step3_decolorization",
        "gram.stain.procedure.step4_counterstain",
        "gram.stain.principle.differential_retention",
        "gram.stain.result.gram_positive_purple",
        "gram.stain.result.gram_negative_red",
        "gram.stain.reagent.primary_stain",
        "gram.stain.reagent.mordant",
        "gram.stain.reagent.decolorizer",
        "gram.stain.reagent.counterstain",
    }
    assert first.view.knowledge.knowledge_version == 1
    assert second.view.knowledge.knowledge_version == 1


def test_gram_stain_reaches_complete_semantic_blueprint_and_publication_plan(
    tmp_path: Path,
) -> None:
    record = validate_knowledge_record(_raw_staining_method())
    completeness = evaluate_staining_method_completeness(record)
    source = _approve(
        SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3"),
        record,
    )
    registry = TemplateRegistry.from_directory(PROFILE_ROOT)
    before = source.model_dump(mode="json")

    plan = PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id="request.gram_stain_vertical_slice",
            template_ref=ProfileReference(
                profile_id="template.gram_stain_national_exam_pdf",
                version="1.0.0",
            ),
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )
    blueprints = ClaimMappingResolver().resolve(plan, source)

    assert source.model_dump(mode="json") == before
    assert plan.plan_schema_version == "1.4"
    assert [item.content_role for item in plan.content_sections] == [
        "role.definition",
        "role.staining_workflow",
        "role.staining_principle",
        "role.comparison",
        "role.cautions",
    ]
    assert [item.visual_type for item in plan.visuals] == [
        "diagram.laboratory_workflow",
        "table.gram_reaction_comparison",
    ]
    assert plan.diagram_taxonomy_bindings[0].taxonomy_path == (
        "taxonomy.workflow",
        "taxonomy.workflow.staining",
        "taxonomy.workflow.staining.gram",
    )
    workflow, comparison = blueprints.blueprints
    assert workflow.is_complete is True
    assert workflow.missing_concepts == ()
    assert comparison.is_complete is True
    assert comparison.missing_concepts == ()
    assert completeness.profile_id == "knowledge_completeness.staining_method"
    assert completeness.missing_items == []
    assert completeness.score == 100


def test_gram_stain_record_persists_and_semantic_edit_bumps_version(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    first = registry.reconcile(
        validate_knowledge_record(_raw_staining_method()),
        actor="product_owner",
        note="正式Category登録",
    )
    stored = registry.record(first.record.knowledge_id)
    assert stored is not None
    first_ids = {item.claim_key: item.claim_id for item in first.view.claims}

    raw = stored.model_dump(mode="json")
    raw["category_content"]["staining_method"]["limitations"][0]["assertion"] += (
        "（医学監修前の改訂）"
    )
    second = registry.reconcile(
        validate_knowledge_record(raw),
        actor="product_owner",
        note="限界の表現を改訂",
    )

    second_ids = {item.claim_key: item.claim_id for item in second.view.claims}
    assert second.view.knowledge.knowledge_version == 2
    assert first_ids == second_ids
    assert registry.record(first.record.knowledge_id).content_revision == 2
