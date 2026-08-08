"""Phase 5.22 acceptance tests for pre-Registry Knowledge authoring."""

from fastapi.testclient import TestClient
from knowledge_contracts.v10 import KnowledgeRecord
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from pytest import mark


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


@mark.parametrize(
    "category",
    [
        "test_item",
        "staining_method",
        "specimen",
        "reagent",
        "biological_structure",
        "disease",
        "laboratory_test_item",
    ],
)
def test_wizard_builds_contract_valid_empty_skeleton_for_every_category(
    category: str,
) -> None:
    client = _client()
    registry_before = client.get("/api/registry").json()

    response = client.post(
        "/api/authoring/drafts",
        json={
            "category": category,
            "title": f"作成テスト {category}",
            "aliases": [f"alias {category}"],
            "difficulty": "standard",
            "exam_importance": "high",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    draft = payload["draft"]
    KnowledgeRecord.model_validate(draft["knowledge"])
    assert draft["knowledge"]["classification"]["term_type"] == category
    assert draft["claims"] == []
    assert draft["references"] == []
    assert draft["relations"] == []
    assert draft["review"] == {
        "state": "draft",
        "review_version": None,
        "medical_review_performed": False,
    }
    assert payload["validation"]["schema_valid"] is True
    assert payload["validation"]["completeness_score"] == 40
    assert payload["registry_mutated"] is False
    assert client.get("/api/registry").json() == registry_before


def test_claims_can_be_added_edited_reordered_and_deleted_with_stable_ids() -> None:
    client = _client()
    draft_id = _create_draft(client)

    first = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={"assertion": "フェリチンは鉄貯蔵状態を反映する。"},
    ).json()["draft"]["claims"][0]
    second_response = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={"assertion": "鉄欠乏ではフェリチンが低値となる。"},
    )
    second = second_response.json()["draft"]["claims"][1]
    assert first["claim_id"].startswith("clm_")
    assert second["claim_id"] != first["claim_id"]

    reordered = client.post(
        f"/api/authoring/drafts/{draft_id}/claims/reorder",
        json={"claim_ids": [second["claim_id"], first["claim_id"]]},
    ).json()["draft"]["claims"]
    assert [item["claim_id"] for item in reordered] == [
        second["claim_id"],
        first["claim_id"],
    ]
    assert [item["position"] for item in reordered] == [1, 2]

    updated = client.put(
        f"/api/authoring/drafts/{draft_id}/claims/{first['claim_id']}",
        json={"assertion": "フェリチンは体内の貯蔵鉄を反映する。"},
    ).json()["draft"]["claims"]
    assert (
        next(item for item in updated if item["claim_id"] == first["claim_id"])["assertion"]
        == "フェリチンは体内の貯蔵鉄を反映する。"
    )

    deleted = client.delete(f"/api/authoring/drafts/{draft_id}/claims/{second['claim_id']}").json()[
        "draft"
    ]["claims"]
    assert [item["claim_id"] for item in deleted] == [first["claim_id"]]
    assert deleted[0]["position"] == 1


def test_reference_editor_validates_claim_links_and_detaches_deleted_claim() -> None:
    client = _client()
    draft_id = _create_draft(client)
    claim = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={"assertion": "鉄欠乏ではフェリチンが低値となる。"},
    ).json()["draft"]["claims"][0]

    response = client.post(
        f"/api/authoring/drafts/{draft_id}/references",
        json={
            "evidence_level": "A",
            "evidence_role": "primary",
            "title": "臨床検査ガイドライン",
            "issuing_organization": "日本臨床検査医学会",
            "publication_year": 2025,
            "url": "https://example.test/guideline",
            "doi": "10.1234/example.1",
            "pages": "12-14",
            "supported_claim_ids": [claim["claim_id"]],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["references"][0]["source_id"].startswith("src_")
    assert payload["validation"]["reference_integrity_valid"] is True
    assert payload["validation"]["completeness_score"] == 70

    after_delete = client.delete(
        f"/api/authoring/drafts/{draft_id}/claims/{claim['claim_id']}"
    ).json()
    assert after_delete["draft"]["references"][0]["supported_claim_ids"] == []
    assert after_delete["validation"]["reference_integrity_valid"] is True


def test_json_import_export_and_markdown_export_keep_registry_unchanged() -> None:
    client = _client()
    registry_before = client.get("/api/registry").json()
    draft_id = _create_draft(client)
    exported = client.get(f"/api/authoring/drafts/{draft_id}/export?format=json")
    markdown = client.get(f"/api/authoring/drafts/{draft_id}/export?format=markdown")

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert markdown.status_code == 200
    assert "# フェリチン" in markdown.text
    assert "## Claims" in markdown.text

    imported = client.post(
        "/api/authoring/import",
        json={"draft": exported.json()},
    )
    assert imported.status_code == 200
    assert imported.json()["draft"]["draft_id"] != draft_id
    assert (
        imported.json()["draft"]["knowledge"]["knowledge_id"]
        == exported.json()["knowledge"]["knowledge_id"]
    )
    assert client.get("/api/registry").json() == registry_before


def test_workbench_exposes_authoring_controls_and_status_contract() -> None:
    client = _client()
    page = client.get("/")
    status = client.get("/api/status").json()
    schema = client.get("/api/schema/knowledge-authoring-1.0")

    assert page.status_code == 200
    assert "Knowledge Wizard" in page.text
    assert "Claim Authoring" in page.text
    assert "Reference Authoring" in page.text
    assert "JSON Export" in page.text
    assert "Markdown Export" in page.text
    assert status["knowledge_authoring_version"] == "1.0"
    assert status["knowledge_authoring_registry_write_enabled"] is False
    assert status["knowledge_authoring_ai_generation_enabled"] is False
    assert schema.status_code == 200
    assert schema.json()["title"] == "KnowledgeAuthoringDraft"


def _create_draft(client: TestClient) -> str:
    response = client.post(
        "/api/authoring/drafts",
        json={
            "category": "laboratory_test_item",
            "title": "フェリチン",
            "aliases": ["Ferritin"],
            "difficulty": "standard",
            "exam_importance": "high",
        },
    )
    assert response.status_code == 200
    return response.json()["draft"]["draft_id"]
