import json
from pathlib import Path

from fastapi.testclient import TestClient
from knowledge_contracts.relation_v11 import RelationResolutionStatus, RelationType
from knowledge_contracts.v10 import validate_knowledge_record

from knowledge_workbench.knowledge_relation_service import KnowledgeRelationService
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from knowledge_workbench.sqlite_knowledge_relation_repository import (
    SQLiteKnowledgeRelationRepository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0"


def _record(relative_path: str):  # type: ignore[no-untyped-def]
    path = EXAMPLES / relative_path
    return validate_knowledge_record(json.loads(path.read_text(encoding="utf-8")))


def test_workbench_can_open_save_and_reopen_bacterial_cell_wall() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    starter_response = client.get(
        "/api/knowledge-templates/biological-structure/bacterial-cell-wall"
    )
    starter = starter_response.json()

    assert starter_response.status_code == 200
    assert starter["persisted"] is False
    assert starter["schema_valid"] is True
    assert starter["data"]["knowledge_id"] == "knw_10000011"
    assert starter["data"]["classification"]["term_type"] == "biological_structure"
    assert starter["data"]["category_content"]["template_id"] == (
        "biological_structure_v1.0"
    )
    assert starter["knowledge_completeness"]["score"] == 100

    saved_response = client.put(
        "/api/knowledge-records/knw_10000011",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "細菌細胞壁を正式Categoryへ登録",
        },
    )
    saved = saved_response.json()

    assert saved_response.status_code == 200
    assert saved["schema_valid"] is True
    assert saved["registry"]["knowledge"]["registry_key"] == (
        "structure.bacterial_cell_wall"
    )
    assert saved["registry"]["knowledge"]["knowledge_version"] == 1
    assert {item["claim_key"] for item in saved["registry"]["claims"]} == {
        "structure.bacterial_cell_wall.definition",
        "structure.bacterial_cell_wall.overview.gram_differentiation",
        "structure.bacterial_cell_wall.function.shape_and_protection",
        "structure.bacterial_cell_wall.component.peptidoglycan",
        "structure.bacterial_cell_wall.organism.distribution",
    }
    assert saved["resolution_report"]["evaluated_count"] == 0
    assert client.get(
        "/api/knowledge-templates/biological-structure/bacterial-cell-wall"
    ).json()["persisted"] is True


def test_bacterial_cell_wall_completes_gram_network_using_only_the_index(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    repository = SQLiteKnowledgeRelationRepository(database_path)
    service = KnowledgeRelationService(registry, repository)

    gram = registry.reconcile(
        _record("staining-method.example.json"),
        actor="phase_5_8_test",
        note="Gram染色を登録",
    ).record
    service.synchronize(
        gram,
        actor="phase_5_8_test",
        note="Gram染色Relationを登録",
    )
    specimen = registry.reconcile(
        _record("specimen.example.json"),
        actor="phase_5_8_test",
        note="塗抹標本を登録",
    ).record
    service.resolve_for_target(specimen, actor="phase_5_8_test", note="Specimen再解決")
    reagent_paths = sorted((EXAMPLES / "reagents").glob("*.example.json"))
    for path in reagent_paths:
        reagent = registry.reconcile(
            validate_knowledge_record(json.loads(path.read_text(encoding="utf-8"))),
            actor="phase_5_8_test",
            note="Reagentを登録",
        ).record
        service.resolve_for_target(reagent, actor="phase_5_8_test", note="Reagent再解決")
    acid_fast = registry.reconcile(
        _record("acid-fast-staining-method.example.json"),
        actor="phase_5_8_test",
        note="抗酸菌染色を登録",
    ).record
    service.resolve_for_target(
        acid_fast,
        actor="phase_5_8_test",
        note="関連染色法を再解決",
    )

    before_summary = repository.network_summary(gram.knowledge_id)
    gram_before = registry.record(gram.knowledge_id)
    assert gram_before is not None
    gram_before_json = gram_before.model_dump(mode="json")
    assert before_summary.resolved_count == 6
    assert before_summary.unresolved_count == 1
    assert before_summary.network_completeness == 85.7

    structure = registry.reconcile(
        _record("biological-structure.example.json"),
        actor="phase_5_8_test",
        note="細菌細胞壁を正式登録",
    ).record
    indexed = repository.find_unresolved_for_target(
        "biological_structure",
        [structure.term.canonical_name, *structure.term.aliases],
    )
    assert len(indexed) == 1
    assert indexed[0].relation_type == RelationType.TARGETS_STRUCTURE

    def fail_on_registry_scan(*_args):  # type: ignore[no-untyped-def]
        raise AssertionError("Relation再解決でKnowledge全件走査は禁止")

    with monkeypatch.context() as scoped:
        scoped.setattr(registry, "record", fail_on_registry_scan)
        scoped.setattr(registry, "snapshot", fail_on_registry_scan)
        report = service.resolve_for_target(
            structure,
            actor="phase_5_8_test",
            note="細菌細胞壁保存イベントによる索引候補の再評価",
        )

    assert (report.evaluated_count, report.resolved_count, report.unresolved_count) == (
        1,
        1,
        0,
    )
    gram_after = registry.record(gram.knowledge_id)
    assert gram_after is not None
    assert gram_after.model_dump(mode="json") == gram_before_json
    view = repository.view(gram.knowledge_id)
    relation = next(
        item
        for item in view.relations
        if item.relation_type == RelationType.TARGETS_STRUCTURE
    )
    assert relation.relation_id == indexed[0].relation_id
    assert relation.target_knowledge_id == structure.knowledge_id
    assert relation.target_label == "細菌細胞壁"
    assert relation.resolution_status == RelationResolutionStatus.RESOLVED
    assert relation.version == 2
    assert repository.network_summary(gram.knowledge_id).model_dump(mode="json") == {
        "schema_version": "1.0",
        "knowledge_id": gram.knowledge_id,
        "relation_count": 7,
        "resolved_count": 7,
        "unresolved_count": 0,
        "network_completeness": 100.0,
    }
    assert repository.resolution_reports(structure.knowledge_id) == [report]
