import json
from pathlib import Path

from fastapi.testclient import TestClient
from knowledge_contracts.v10 import validate_knowledge_record

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from knowledge_workbench.sqlite_knowledge_relation_repository import (
    SQLiteKnowledgeRelationRepository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_PATH = (
    REPOSITORY_ROOT
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "disease.example.json"
)


def _record():  # type: ignore[no-untyped-def]
    return validate_knowledge_record(
        json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    )


def test_workbench_can_open_save_and_reopen_iron_deficiency_anemia() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    starter_response = client.get(
        "/api/knowledge-templates/disease/iron-deficiency-anemia"
    )
    starter = starter_response.json()

    assert starter_response.status_code == 200
    assert starter["persisted"] is False
    assert starter["schema_valid"] is True
    assert starter["data"]["knowledge_id"] == "knw_10000012"
    assert starter["data"]["classification"]["term_type"] == "disease"
    assert starter["data"]["category_content"]["template_id"] == "disease_v1.0"
    assert starter["knowledge_completeness"]["score"] == 100

    saved_response = client.put(
        "/api/knowledge-records/knw_10000012",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "鉄欠乏性貧血を正式Categoryへ登録",
        },
    )
    saved = saved_response.json()

    assert saved_response.status_code == 200
    assert saved["schema_valid"] is True
    assert saved["registry"]["knowledge"]["registry_key"] == (
        "disease.iron_deficiency_anemia"
    )
    assert saved["registry"]["knowledge"]["knowledge_version"] == 1
    assert len(saved["registry"]["claims"]) == 17
    assert saved["relations"]["relations"] == []
    assert saved["resolution_report"]["evaluated_count"] == 0
    reopened = client.get(
        "/api/knowledge-templates/disease/iron-deficiency-anemia"
    ).json()
    assert reopened["persisted"] is True

    saved_again = client.put(
        "/api/knowledge-records/knw_10000012",
        json={
            "record": reopened["data"],
            "actor": "product_owner",
            "comment": "内容を変えずに安定IDを確認",
        },
    ).json()
    assert saved_again["registry"]["knowledge"]["knowledge_version"] == 1
    assert {item["claim_id"] for item in saved_again["registry"]["claims"]} == {
        item["claim_id"] for item in saved["registry"]["claims"]
    }
    assert {item["claim_key"] for item in saved_again["registry"]["claims"]} == {
        item["claim_key"] for item in saved["registry"]["claims"]
    }


def test_disease_save_does_not_scan_or_modify_existing_knowledge(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    repository = SQLiteKnowledgeRelationRepository(database_path)
    existing_path = (
        REPOSITORY_ROOT
        / "Docs"
        / "examples"
        / "knowledge-json-v1.0"
        / "staining-method.example.json"
    )
    existing = registry.reconcile(
        validate_knowledge_record(json.loads(existing_path.read_text(encoding="utf-8"))),
        actor="phase_5_10_test",
        note="回帰用Knowledgeを登録",
    ).record
    before = existing.model_dump(mode="json")

    disease = registry.reconcile(
        _record(),
        actor="phase_5_10_test",
        note="Diseaseを登録",
    ).record

    assert repository.view(disease.knowledge_id).relations == []
    after = registry.record(existing.knowledge_id)
    assert after is not None
    assert after.model_dump(mode="json") == before
