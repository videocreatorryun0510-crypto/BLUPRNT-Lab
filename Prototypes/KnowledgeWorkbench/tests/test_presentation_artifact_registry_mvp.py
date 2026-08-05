from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

KNOWLEDGE_ID = "knw_10000013"


def _prepared_client() -> TestClient:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(
        "/api/knowledge-templates/laboratory-test-item/ferritin"
    ).json()["data"]
    saved = client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "Artifact Registry APIテスト",
        },
    )
    assert saved.status_code == 200
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
    assert second["registry_entry"]["artifact_id"] == first["registry_entry"][
        "artifact_id"
    ]
    assert second["registry_entry"]["artifact_version"] == 2
    assert client.get("/api/registry").json() == knowledge_registry_before

    snapshot = client.get("/api/artifact-registry").json()
    assert snapshot["validation"]["is_valid"] is True
    assert snapshot["renderer_source_policy"] == "registry_approved_only"
    assert len(snapshot["registry"]["artifacts"]) == 1


def test_independent_approval_history_and_renderer_gate() -> None:
    client = _prepared_client()
    created = _register(client)
    artifact_id = created["registry_entry"]["artifact_id"]

    blocked = client.get(
        f"/api/artifact-registry/{artifact_id}/render-source?artifact_version=1"
    )
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
    client = _prepared_client()
    first = _register(client)
    artifact_id = first["registry_entry"]["artifact_id"]
    _transition(client, artifact_id, 1, "owner_review")
    _transition(client, artifact_id, 1, "education_review")
    _transition(client, artifact_id, 1, "approved")
    second = _register(client)
    assert second["registry_entry"]["artifact_version"] == 2

    latest_approved = client.get(
        f"/api/artifact-registry/{artifact_id}/render-source"
    )
    assert latest_approved.status_code == 200
    assert latest_approved.json()["artifact"]["identity"]["artifact_version"] == 1

    draft = client.get(
        f"/api/artifact-registry/{artifact_id}/render-source?artifact_version=2"
    )
    assert draft.status_code == 403

    diff = client.get(
        f"/api/artifact-registry/{artifact_id}/diff?from_version=1&to_version=2"
    )
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
    assert status["presentation_artifact_registry_version"] == "1.0"
    assert status["presentation_artifact_registry_storage"] == "sqlite"
    assert status["renderer_artifact_source_policy"] == "registry_approved_only"
    assert "Artifact Registry" in page
    assert "Version差分" in page
    assert "Renderer利用可否" in page
