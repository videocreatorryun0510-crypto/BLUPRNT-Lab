"""Compatibility tests for the deprecated Phase 5.23 Authoring path."""

from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def test_legacy_authoring_preview_is_retained_but_rejected_without_registry_write() -> None:
    client = _client()
    before = client.get("/api/registry").json()

    response = client.post("/api/authoring/drafts/kad_missing000/promotion/preview")

    assert response.status_code == 410
    assert response.json()["status"] == "deprecated"
    assert response.json()["errors"][0]["code"] == (
        "authoring_promotion_path_deprecated"
    )
    assert response.json()["registry_mutated"] is False
    assert client.get("/api/registry").json() == before


def test_legacy_authoring_commit_is_retained_but_rejected_without_registry_write() -> None:
    client = _client()
    before = client.get("/api/registry").json()

    response = client.post(
        "/api/authoring/promotions",
        json={"preview_id": "ppv_legacy000", "draft_disposition": "keep"},
    )

    assert response.status_code == 410
    assert response.json()["status"] == "deprecated"
    assert response.json()["registry_mutated"] is False
    assert client.get("/api/registry").json() == before


def test_legacy_contracts_remain_visible_while_workbench_uses_v2() -> None:
    client = _client()
    page = client.get("/")
    status = client.get("/api/status").json()

    assert status["knowledge_promotion_version"] == "2.0"
    assert status["knowledge_promotion_input"] == "knowledge_draft_only"
    assert status["authoring_draft_promotion_path"] == "deprecated_rejected"
    assert 'id="previewKnowledgeDraftPromotionButton"' in page.text
    assert 'id="previewPromotionButton"' not in page.text
    assert client.get("/api/schema/knowledge-promotion-preview-1.0").status_code == 200
    assert client.get("/api/schema/knowledge-promotion-result-1.0").status_code == 200
    assert (
        client.get("/api/schema/knowledge-draft-promotion-preview-2.0").status_code
        == 200
    )
    assert (
        client.get("/api/schema/knowledge-draft-promotion-result-2.0").status_code
        == 200
    )
