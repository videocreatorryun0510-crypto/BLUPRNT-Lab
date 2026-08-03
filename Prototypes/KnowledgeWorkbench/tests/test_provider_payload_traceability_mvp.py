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
            "comment": "Provider Payloadテスト用に保存",
        },
    )
    assert response.status_code == 200


def _approve(client: TestClient) -> None:
    claim_ids = [
        item["claim_id"]
        for item in client.get(f"/api/registry/{KNOWLEDGE_ID}").json()["claims"]
    ]
    for status in ("owner_review", "medical_review", "approved"):
        assert client.post(
            f"/api/registry/{KNOWLEDGE_ID}/claims/status",
            json={
                "target_status": status,
                "claim_ids": claim_ids,
                "actor": "medical_reviewer",
                "comment": "Provider Payload用Claim承認",
            },
        ).status_code == 200
        assert client.post(
            f"/api/registry/{KNOWLEDGE_ID}/status",
            json={
                "target_status": status,
                "actor": "medical_reviewer",
                "comment": "Provider Payload用Knowledge承認",
            },
        ).status_code == 200


def _prepare_request(client: TestClient, mode: str) -> None:
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    result = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": mode},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "success"


def test_draft_payload_preview_is_blocked_without_medical_payload() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    _prepare_request(client, "preview")
    source_bundle = client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").json()["bundle"]

    response = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}",
        json={"request_mode": "preview", "adapter": "dummy"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert payload["payload"] is None
    assert payload["output_path"] is None
    assert payload["external_use_allowed"] is False
    assert payload["validation"]["approval_result"] is False
    assert payload["payload_context"]["approval_state"] == "draft"
    audit = Path(payload["audit_log_path"]).read_text(encoding="utf-8")
    for claim in source_bundle["claims"]:
        assert claim["assertion"] not in audit


def test_approved_external_payload_and_traceable_dummy_succeed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    _approve(client)
    _prepare_request(client, "external")
    knowledge_before = client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"]
    registry_before = client.get("/api/registry").json()

    resolved = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}",
        json={"request_mode": "external", "adapter": "dummy"},
    ).json()
    assert resolved["status"] == "success"
    assert resolved["payload"]["source"]["approval_state"] == "approved"
    assert resolved["validation"]["is_valid"] is True
    assert resolved["validation"]["egress_policy_result"] is True
    assert resolved["validation"]["secret_scan_result"] is True
    assert resolved["validation"]["stale_check_result"] is True
    assert resolved["payload_context"]["claim_count"] == 11
    assert resolved["payload_context"]["exam_point_count"] == 0
    assert resolved["external_ai_called"] is False

    executed = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}/execute-dummy",
        json={"request_mode": "external", "adapter": "dummy"},
    ).json()
    context = executed["response_context"]
    assert executed["status"] == "accepted"
    assert context["provider"] == "dummy"
    assert context["execution_status"] == "completed"
    assert context["payload_fingerprint_match"] is True
    assert context["used_claim_count"] == 11
    assert context["used_diagram_request_count"] == 1
    assert context["validation_result"] is True
    assert executed["external_ai_called"] is False
    assert client.get(f"/api/knowledge-records/{KNOWLEDGE_ID}").json()["data"] == (
        knowledge_before
    )
    assert client.get("/api/registry").json() == registry_before


def test_traceable_response_and_audits_do_not_copy_medical_body() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)
    _approve(client)
    source_bundle = client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").json()["bundle"]
    request = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).json()
    assert request["status"] == "success"
    resolved = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).json()
    executed = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}/execute-dummy",
        json={"request_mode": "external"},
    ).json()

    response_text = json.dumps(executed["response"], ensure_ascii=False)
    audits = Path(resolved["audit_log_path"]).read_text(encoding="utf-8") + Path(
        executed["audit_log_path"]
    ).read_text(encoding="utf-8")
    for claim in source_bundle["claims"]:
        assert claim["assertion"] not in response_text
        assert claim["assertion"] not in audits


def test_payload_and_dummy_require_saved_predecessor() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    _saved_ferritin(client)

    missing_payload_sources = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}",
        json={"request_mode": "preview"},
    )
    missing_payload = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}/execute-dummy",
        json={"request_mode": "preview"},
    )

    assert missing_payload_sources.status_code == 409
    assert missing_payload_sources.json()["errors"][0]["code"] == (
        "presentation_sources_required"
    )
    assert missing_payload.status_code == 409
    assert missing_payload.json()["errors"][0]["code"] == "provider_payload_required"


def test_contract_status_and_workbench_surface_are_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    payload_schema = client.get("/api/schema/provider-payload-1.0")
    response_schema = client.get("/api/schema/traceable-response-1.0")
    status = client.get("/api/status").json()
    page = client.get("/")

    assert payload_schema.status_code == 200
    assert response_schema.status_code == 200
    assert status["provider_payload_contract_version"] == "1.0"
    assert status["provider_payload_resolver_version"] == "1.0.0"
    assert status["provider_payload_preview_policy"] == "approved_only"
    assert status["traceable_response_contract_version"] == "1.0"
    assert "Provider Payload Preview" in page.text
    assert "Traceable Dummy実行" in page.text
