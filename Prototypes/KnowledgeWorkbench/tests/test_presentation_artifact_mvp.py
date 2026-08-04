from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


@pytest.mark.parametrize(
    ("starter_endpoint", "knowledge_id"),
    [
        ("/api/knowledge-templates/laboratory-test-item/ferritin", "knw_10000013"),
        ("/api/knowledge-templates/disease/iron-deficiency-anemia", "knw_10000012"),
    ],
)
def test_workbench_builds_valid_provider_neutral_artifact_without_mutation(
    starter_endpoint: str,
    knowledge_id: str,
) -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(starter_endpoint).json()["data"]
    assert (
        client.put(
            f"/api/knowledge-records/{knowledge_id}",
            json={
                "record": starter,
                "actor": "product_owner",
                "comment": "Presentation Artifactテスト",
            },
        ).status_code
        == 200
    )
    assert client.post(f"/api/source-bundles/{knowledge_id}").status_code == 200
    assert (
        client.post(
            f"/api/presentation-requests/{knowledge_id}",
            json={"request_mode": "preview"},
        ).status_code
        == 200
    )
    knowledge_before = client.get(f"/api/knowledge-records/{knowledge_id}").json()[
        "data"
    ]
    registry_before = client.get("/api/registry").json()

    response = client.post(
        f"/api/presentation-artifacts/{knowledge_id}",
        json={"request_mode": "preview"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["validation"]["is_valid"] is True
    assert payload["knowledge_mutated"] is False
    assert payload["registry_mutated"] is False
    assert payload["external_ai_called"] is False
    assert payload["renderer_called"] is False
    artifact = payload["artifact"]
    assert artifact["identity"]["contract_version"] == "1.0"
    assert artifact["identity"]["artifact_version"] == 1
    assert artifact["source"]["knowledge_id"] == knowledge_id
    assert len(artifact["pages"]) == 5
    assert payload["artifact_context"]["page_count"] == 5
    assert payload["artifact_context"]["validation"] == "passed"
    assert Path(payload["output_path"]).is_file()
    assert Path(payload["audit_log_path"]).is_file()
    assert client.get(f"/api/knowledge-records/{knowledge_id}").json()["data"] == (
        knowledge_before
    )
    assert client.get("/api/registry").json() == registry_before
    assert not _has_provider_key(artifact)
    claim_texts = {
        item["claim_id"]: item["exact_text"] for item in artifact["claim_catalog"]
    }
    assert all(
        block["exact_text"] == claim_texts[block["claim_id"]]
        for page in artifact["pages"]
        for block in page["body_blocks"]
    )


def test_artifact_requires_source_bundle_and_presentation_request() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(
        "/api/knowledge-templates/laboratory-test-item/ferritin"
    ).json()["data"]
    assert (
        client.put(
            "/api/knowledge-records/knw_10000013",
            json={
                "record": starter,
                "actor": "product_owner",
                "comment": "Artifact前提条件テスト",
            },
        ).status_code
        == 200
    )

    response = client.post(
        "/api/presentation-artifacts/knw_10000013",
        json={"request_mode": "preview"},
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "presentation_sources_required"


def test_phase_519_schema_status_and_workbench_surface_are_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    schema = client.get("/api/schema/presentation-artifact-1.0")
    status = client.get("/api/status").json()
    page = client.get("/").text

    assert schema.status_code == 200
    assert schema.json()["properties"]["identity"]["$ref"]
    assert status["presentation_artifact_contract_version"] == "1.0"
    assert status["presentation_artifact_builder_version"] == "1.0.0"
    assert status["presentation_artifact_provider_neutral"] is True
    assert status["presentation_artifact_renderer_neutral"] is True
    assert "Presentation Artifact生成・保存" in page
    assert "Presentation Artifact Preview" in page
    assert "媒体に依存しない教材構成の正本" in page


def _has_provider_key(value: object) -> bool:
    forbidden = {"provider", "gemini", "api", "api_key", "model", "endpoint"}
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _has_provider_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_provider_key(item) for item in value)
    return False
