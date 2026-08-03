import json
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

FERRITIN_ENDPOINT = "/api/knowledge-templates/laboratory-test-item/ferritin"
KNOWLEDGE_ID = "knw_10000013"


def _saved_ferritin(client: TestClient) -> None:
    starter = client.get(FERRITIN_ENDPOINT).json()
    response = client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "Presentation Engine Adapterテスト用に保存",
        },
    )
    assert response.status_code == 200


def _approve(client: TestClient) -> None:
    claim_ids = [
        item["claim_id"]
        for item in client.get(f"/api/registry/{KNOWLEDGE_ID}").json()["claims"]
    ]
    for status in ("owner_review", "medical_review", "approved"):
        assert (
            client.post(
                f"/api/registry/{KNOWLEDGE_ID}/claims/status",
                json={
                    "target_status": status,
                    "claim_ids": claim_ids,
                    "actor": "medical_reviewer",
                    "comment": "Presentation Engine用Claim確認",
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
                    "comment": "Presentation Engine用Knowledge確認",
                },
            ).status_code
            == 200
        )


def _prepare_request(client: TestClient, mode: str = "preview") -> dict[str, object]:
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    response = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": mode},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    return response.json()


def test_draft_preview_executes_dummy_without_mutating_ssot() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    request_payload = _prepare_request(client)
    knowledge_before = client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"]
    registry_before = client.get("/api/registry").json()

    response = client.post(
        f"/api/presentation-engine/{KNOWLEDGE_ID}/execute",
        json={"request_mode": "preview", "adapter": "dummy"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["adapter"] == {
        "provider_name": "dummy",
        "provider_version": "1.0.0",
        "supports_preview": True,
        "supports_external": True,
    }
    assert payload["external_ai_called"] is False
    assert payload["registry_mutated"] is False
    assert payload["knowledge_mutated"] is False
    assert payload["result"]["validation_result"]["is_valid"] is True
    assert payload["result"]["validation_result"]["approval_gate_checked"] is True
    assert payload["result"]["validation_result"]["approval_gate_required"] is False
    assert payload["engine_context"]["mode"] == "preview"
    assert payload["engine_context"]["pages"] == 5
    assert payload["engine_context"]["claims_used"] == 11
    assert payload["engine_context"]["diagram_requests"] == 1
    assert payload["request_fingerprint"] != request_payload["request_context"][
        "source_fingerprint"
    ]
    assert client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"] == (
        knowledge_before
    )
    assert client.get("/api/registry").json() == registry_before


def test_approved_external_executes_dummy_after_approval_gate() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    _approve(client)
    _prepare_request(client, "external")

    payload = client.post(
        f"/api/presentation-engine/{KNOWLEDGE_ID}/execute",
        json={"request_mode": "external", "adapter": "dummy"},
    ).json()

    assert payload["status"] == "success"
    assert payload["approval_gate"]["allowed"] is True
    assert payload["approval_gate"]["reason_code"] == "approval_granted"
    assert payload["result"]["validation_result"]["approval_gate_required"] is True
    assert payload["result"]["validation_result"]["approval_gate_allowed"] is True
    assert payload["external_ai_called"] is False


def test_engine_requires_saved_presentation_request() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)

    response = client.post(
        f"/api/presentation-engine/{KNOWLEDGE_ID}/execute",
        json={"request_mode": "preview", "adapter": "dummy"},
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "presentation_request_required"


def test_engine_audit_and_result_store_no_medical_body() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    source_bundle = client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").json()["bundle"]
    assert (
        client.post(
            f"/api/presentation-requests/{KNOWLEDGE_ID}",
            json={"request_mode": "preview"},
        ).json()["status"]
        == "success"
    )

    payload = client.post(
        f"/api/presentation-engine/{KNOWLEDGE_ID}/execute",
        json={"request_mode": "preview", "adapter": "dummy"},
    ).json()

    result_text = json.dumps(payload["result"], ensure_ascii=False)
    audit_text = Path(payload["audit_log_path"]).read_text(encoding="utf-8")
    for claim in source_bundle["claims"]:
        assert claim["assertion"] not in result_text
        assert claim["assertion"] not in audit_text
    assert "source_bundle" not in audit_text
    assert "claims" not in audit_text


def test_contract_schema_status_and_workbench_surface_are_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    schema = client.get("/api/schema/presentation-result-1.0")
    status = client.get("/api/status").json()
    page = client.get("/")

    assert schema.status_code == 200
    assert schema.json()["properties"]["result_contract_version"]["const"] == "1.0"
    assert status["presentation_engine_adapter_contract_version"] == "1.0"
    assert status["presentation_result_contract_version"] == "1.0"
    assert status["presentation_engine_adapters"] == ["dummy"]
    assert status["presentation_engine_external_api_enabled"] is False
    assert "Dummy Adapter実行" in page.text
