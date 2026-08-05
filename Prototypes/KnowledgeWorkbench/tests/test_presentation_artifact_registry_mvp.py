import pytest
from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

KNOWLEDGE_ID = "knw_10000013"


def _prepared_client(knowledge_state: str = "draft") -> TestClient:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get("/api/knowledge-templates/laboratory-test-item/ferritin").json()["data"]
    saved = client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "Artifact Registry APIテスト",
        },
    )
    assert saved.status_code == 200
    if knowledge_state != "draft":
        registry = client.get(f"/api/registry/{KNOWLEDGE_ID}").json()
        claim_ids = [item["claim_id"] for item in registry["claims"]]
        sequence = ["owner_review", "medical_review", "approved"]
        for target in sequence:
            claim_response = client.post(
                f"/api/registry/{KNOWLEDGE_ID}/claims/status",
                json={
                    "claim_ids": claim_ids,
                    "target_status": target,
                    "actor": "isolated_test_reviewer",
                    "comment": f"隔離Fixtureを{target}へ変更",
                },
            )
            assert claim_response.status_code == 200
            knowledge_response = client.post(
                f"/api/registry/{KNOWLEDGE_ID}/status",
                json={
                    "target_status": target,
                    "actor": "isolated_test_reviewer",
                    "comment": f"隔離Fixtureを{target}へ変更",
                },
            )
            assert knowledge_response.status_code == 200
            if target == knowledge_state:
                break
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    request = client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "preview"},
    )
    assert request.status_code == 200
    return client


def _register(client: TestClient) -> dict[str, object]:
    response = client.post(
        f"/api/presentation-artifacts/{KNOWLEDGE_ID}",
        json={
            "request_mode": "preview",
            "owner": "product_owner",
            "actor": "product_owner",
            "review_comment": "教材構成を登録",
        },
    )
    assert response.status_code == 200
    return response.json()


def _transition(
    client: TestClient,
    artifact_id: str,
    version: int,
    target_state: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/artifact-registry/{artifact_id}/versions/{version}/approval",
        json={
            "target_state": target_state,
            "actor": "education_reviewer",
            "review_comment": f"{target_state}へ変更",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_generation_registers_stable_artifact_series_and_completeness() -> None:
    client = _prepared_client()
    knowledge_registry_before = client.get("/api/registry").json()

    first = _register(client)
    second = _register(client)

    assert first["artifact_registry_mutated"] is True
    assert first["registry_mutated"] is False
    assert first["registry_entry"]["approval_state"] == "draft"
    assert first["artifact_completeness"]["score"] == 100
    assert second["registry_entry"]["artifact_id"] == first["registry_entry"]["artifact_id"]
    assert second["registry_entry"]["artifact_version"] == 2
    assert client.get("/api/registry").json() == knowledge_registry_before

    snapshot = client.get("/api/artifact-registry").json()
    assert snapshot["validation"]["is_valid"] is True
    assert snapshot["renderer_source_policy"] == "knowledge_and_artifact_dual_approval"
    assert len(snapshot["registry"]["artifacts"]) == 1


def test_independent_approval_history_and_renderer_gate() -> None:
    client = _prepared_client("approved")
    created = _register(client)
    artifact_id = created["registry_entry"]["artifact_id"]

    blocked = client.get(f"/api/artifact-registry/{artifact_id}/render-source?artifact_version=1")
    assert blocked.status_code == 403
    assert blocked.json()["status"] == "render_blocked"

    skipped = client.post(
        f"/api/artifact-registry/{artifact_id}/versions/1/approval",
        json={
            "target_state": "approved",
            "actor": "reviewer",
            "review_comment": "途中を省略",
        },
    )
    assert skipped.status_code == 422

    _transition(client, artifact_id, 1, "owner_review")
    _transition(client, artifact_id, 1, "education_review")
    approved = _transition(client, artifact_id, 1, "approved")
    assert approved["version"]["entry"]["immutable"] is True
    assert approved["knowledge_registry_mutated"] is False

    render_source = client.get(
        f"/api/artifact-registry/{artifact_id}/render-source?artifact_version=1"
    )
    assert render_source.status_code == 200
    assert render_source.json()["artifact"]["identity"]["artifact_version"] == 1

    view = client.get(f"/api/artifact-registry/{artifact_id}").json()
    assert len(view["registry"]["history"]) == 4
    assert view["registry"]["current"]["approval_state"] == "approved"


def test_latest_approved_version_is_used_when_newer_draft_exists() -> None:
    client = _prepared_client("approved")
    first = _register(client)
    artifact_id = first["registry_entry"]["artifact_id"]
    _transition(client, artifact_id, 1, "owner_review")
    _transition(client, artifact_id, 1, "education_review")
    _transition(client, artifact_id, 1, "approved")
    second = _register(client)
    assert second["registry_entry"]["artifact_version"] == 2

    latest_approved = client.get(f"/api/artifact-registry/{artifact_id}/render-source")
    assert latest_approved.status_code == 200
    assert latest_approved.json()["artifact"]["identity"]["artifact_version"] == 1

    draft = client.get(f"/api/artifact-registry/{artifact_id}/render-source?artifact_version=2")
    assert draft.status_code == 403

    diff = client.get(f"/api/artifact-registry/{artifact_id}/diff?from_version=1&to_version=2")
    assert diff.status_code == 200
    assert diff.json()["diff"]["from_version"] == 1
    assert diff.json()["diff"]["to_version"] == 2


def test_phase_520_schema_status_and_workbench_surface_are_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    schema = client.get("/api/schema/presentation-artifact-registry-1.0")
    status = client.get("/api/status").json()
    page = client.get("/").text

    assert schema.status_code == 200
    assert schema.json()["properties"]["registry_version"]["const"] == "1.0"
    assert status["presentation_artifact_registry_version"] == "1.0.1"
    assert status["presentation_artifact_registry_storage"] == "sqlite"
    assert status["renderer_artifact_source_policy"] == ("knowledge_and_artifact_dual_approval")
    assert "Artifact Registry" in page
    assert "Version差分" in page
    assert "Renderer利用可否" in page


@pytest.mark.parametrize(
    "knowledge_state",
    ["draft", "owner_review", "medical_review"],
)
def test_workbench_rejects_artifact_approval_until_knowledge_is_approved(
    knowledge_state: str,
) -> None:
    client = _prepared_client(knowledge_state)
    created = _register(client)
    artifact_id = created["registry_entry"]["artifact_id"]
    _transition(client, artifact_id, 1, "owner_review")
    _transition(client, artifact_id, 1, "education_review")

    response = client.post(
        f"/api/artifact-registry/{artifact_id}/versions/1/approval",
        json={
            "target_state": "approved",
            "actor": "education_reviewer",
            "review_comment": "Knowledge承認を確認",
        },
    )

    assert response.status_code == 422
    assert "knowledge_not_approved" in response.json()["reason_codes"]
    view = client.get(f"/api/artifact-registry/{artifact_id}").json()
    assert view["registry"]["current"]["approval_state"] == "education_review"
    assert view["registry"]["gate_audit"][0]["outcome"] == "blocked"


def test_workbench_displays_dual_gate_results_separately() -> None:
    client = _prepared_client()
    created = _register(client)
    artifact_id = created["registry_entry"]["artifact_id"]

    view = client.get(f"/api/artifact-registry/{artifact_id}").json()
    eligibility = view["renderer_eligibility"]
    page = client.get("/").text

    assert eligibility["artifact_approval_state"] == "draft"
    assert eligibility["source_knowledge_approval_state"] == "draft"
    assert eligibility["renderer_eligibility"] == "ineligible"
    assert "artifact_not_approved" in eligibility["reasons"]
    assert "knowledge_not_approved" in eligibility["reasons"]
    assert "Artifact Review" in page
    assert "Knowledge Approval" in page
    assert "Renderer停止理由" in page
