import json
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

FERRITIN_ENDPOINT = "/api/knowledge-templates/laboratory-test-item/ferritin"
KNOWLEDGE_ID = "knw_10000013"


def _saved_ferritin(client: TestClient) -> dict[str, object]:
    starter = client.get(FERRITIN_ENDPOINT).json()
    response = client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "Presentation Contractテスト用に保存",
        },
    )
    assert response.status_code == 200
    return response.json()


def _approve(client: TestClient) -> None:
    claim_ids = [
        item["claim_id"] for item in client.get(f"/api/registry/{KNOWLEDGE_ID}").json()["claims"]
    ]
    for status in ("owner_review", "medical_review", "approved"):
        assert (
            client.post(
                f"/api/registry/{KNOWLEDGE_ID}/claims/status",
                json={
                    "target_status": status,
                    "claim_ids": claim_ids,
                    "actor": "medical_reviewer",
                    "comment": "Presentation Request用Claim確認",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/registry/{KNOWLEDGE_ID}/status",
                json={
                    "target_status": status,
                    "actor": "medical_reviewer",
                    "comment": "Presentation Request用Knowledge確認",
                },
            ).status_code
            == 200
        )


def test_draft_preview_request_is_generated_without_mutating_ssot() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    knowledge_before = client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"]
    registry_before = client.get("/api/registry").json()

    response = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "preview"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["external_ai_called"] is False
    assert payload["knowledge_mutated"] is False
    assert payload["registry_mutated"] is False
    request = payload["request"]
    assert request["identity"]["contract_version"] == "1.0"
    assert request["request_mode"] == "preview"
    assert request["presentation"]["presentation_type"] == "presentation_document"
    assert request["presentation"]["output_format"] == "structured_json"
    assert request["metadata"]["profile_id"] == "presentation_document_basic_v1"
    assert request["content_policy"]["allow_medical_rephrasing"] is False
    assert request["content_policy"]["allow_medical_fact_addition"] is False
    assert request["validation_policy"]["require_claim_traceability"] is True
    assert payload["validation"]["is_valid"] is True
    assert payload["request_context"]["claim_count"] == 11
    assert payload["request_context"]["key_message_count"] == 3
    assert payload["request_context"]["diagram_request_count"] == 1
    assert Path(payload["output_path"]).is_file()
    assert Path(payload["output_path"]).name == (
        f"{KNOWLEDGE_ID}_v1.preview.presentation-request.json"
    )
    assert client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"] == (knowledge_before)
    assert client.get("/api/registry").json() == registry_before
    request_text = json.dumps(request, ensure_ascii=False)
    source_bundle = client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").json()["bundle"]
    assert all(item["assertion"] not in request_text for item in source_bundle["claims"])
    audit_text = Path(payload["audit_log_path"]).read_text(encoding="utf-8")
    assert "assertion" not in audit_text
    assert "claims" not in audit_text


def test_draft_external_request_is_blocked_without_output() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200

    payload = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).json()

    assert payload["status"] == "blocked"
    assert payload["request"] is None
    assert payload["output_path"] is None
    assert payload["decision"]["reason_code"] == "approval_required"
    assert payload["decision"]["external_use_allowed"] is False


def test_approved_external_request_is_generated_from_test_registry() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    _approve(client)
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200

    payload = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).json()

    assert payload["status"] == "success"
    assert payload["request"]["request_mode"] == "external"
    assert payload["request"]["source"]["approval_state"] == "approved"
    assert payload["decision"]["external_use_allowed"] is True
    assert Path(payload["output_path"]).name.endswith(".external.presentation-request.json")


def test_stale_approval_state_blocks_preview_until_bundle_is_regenerated() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    claim_ids = [
        item["claim_id"] for item in client.get(f"/api/registry/{KNOWLEDGE_ID}").json()["claims"]
    ]
    assert (
        client.post(
            f"/api/registry/{KNOWLEDGE_ID}/claims/status",
            json={
                "target_status": "owner_review",
                "claim_ids": claim_ids,
                "actor": "product_owner",
                "comment": "承認状態変更",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/registry/{KNOWLEDGE_ID}/status",
            json={
                "target_status": "owner_review",
                "actor": "product_owner",
                "comment": "承認状態変更",
            },
        ).status_code
        == 200
    )

    payload = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "preview"},
    ).json()

    assert payload["status"] == "blocked"
    assert "source_bundle_stale" in payload["decision"]["freshness"]["failure_codes"]
    assert "approval_state_changed" in payload["decision"]["freshness"]["failure_codes"]


def test_request_requires_source_bundle_and_contract_is_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)

    missing = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "preview"},
    )
    schema = client.get("/api/schema/presentation-request-1.0")
    status = client.get("/api/status").json()
    page = client.get("/")

    assert missing.status_code == 409
    assert missing.json()["errors"][0]["code"] == "source_bundle_required"
    assert schema.status_code == 200
    assert schema.json()["properties"]["identity"]["$ref"]
    assert status["presentation_contract_version"] == "1.0"
    assert status["presentation_enabled_types"] == ["presentation_document"]
    assert status["presentation_enabled_output_formats"] == ["structured_json"]
    assert status["presentation_profile_ids"] == ["presentation_document_basic_v1"]
    assert "Presentation Request生成" in page.text
