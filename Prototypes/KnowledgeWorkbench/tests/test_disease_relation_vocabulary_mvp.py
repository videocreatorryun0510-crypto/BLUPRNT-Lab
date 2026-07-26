from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def test_disease_vocabulary_is_visible_without_registry_or_growth_writes() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    knowledge_id = "knw_10000012"
    registry_before = client.get("/api/registry").json()
    relations_before = client.get(f"/api/knowledge-relations/{knowledge_id}").json()
    reports_before = client.get(
        f"/api/relation-resolution-reports/{knowledge_id}"
    ).json()

    response = client.get("/api/relation-vocabulary/disease")
    schema = client.get("/api/schema/relation-vocabulary-disease-1.0")

    assert response.status_code == 200
    assert schema.status_code == 200
    assert schema.json()["$id"].endswith("/relation-vocabulary/disease/1.0")
    assert response.json()["schema_version"] == "1.0"
    assert len(response.json()["entries"]) == 7
    assert {item["relation_type"] for item in response.json()["entries"]} == {
        "has_high_test_item",
        "has_low_test_item",
        "diagnosed_by",
        "caused_by",
        "related_disease",
        "affects_structure",
        "has_pathophysiology",
    }

    assert client.get("/api/registry").json() == registry_before
    assert client.get(f"/api/knowledge-relations/{knowledge_id}").json() == relations_before
    assert (
        client.get(f"/api/relation-resolution-reports/{knowledge_id}").json()
        == reports_before
    )


def test_workbench_page_exposes_disease_vocabulary_panel() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    response = client.get("/")

    assert response.status_code == 200
    assert "PHASE 5.12" in response.text
    assert "疾患を安全につなぐ共通Vocabulary" in response.text
    assert 'id="diseaseVocabularyList"' in response.text
