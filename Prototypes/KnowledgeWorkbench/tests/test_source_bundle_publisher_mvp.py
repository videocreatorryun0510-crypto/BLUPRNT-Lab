import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


@pytest.mark.parametrize(
    (
        "starter_endpoint",
        "knowledge_id",
        "expected_title",
        "expected_category",
        "claim_count",
        "diagram_title",
    ),
    [
        (
            "/api/knowledge-templates/laboratory-test-item/ferritin",
            "knw_10000013",
            "フェリチン",
            "laboratory_test_item",
            11,
            "鉄代謝の概略図",
        ),
        (
            "/api/knowledge-templates/disease/iron-deficiency-anemia",
            "knw_10000012",
            "鉄欠乏性貧血",
            "disease",
            17,
            "鉄欠乏による赤血球形成低下",
        ),
    ],
)
def test_workbench_generates_source_bundle_without_mutating_registry(
    starter_endpoint: str,
    knowledge_id: str,
    expected_title: str,
    expected_category: str,
    claim_count: int,
    diagram_title: str,
) -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(starter_endpoint).json()
    saved_response = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "Source Bundle生成テスト用に正式保存",
        },
    )
    assert saved_response.status_code == 200
    knowledge_before = client.get(f"/api/knowledge-records/{knowledge_id}").json()[
        "data"
    ]
    registry_before = client.get("/api/registry").json()

    response = client.post(f"/api/source-bundles/{knowledge_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["knowledge_mutated"] is False
    assert payload["registry_mutated"] is False
    bundle = payload["bundle"]
    assert bundle["schema_version"] == "1.0"
    assert bundle["title"] == expected_title
    assert bundle["metadata"]["knowledge_id"] == knowledge_id
    assert bundle["metadata"]["category"] == expected_category
    assert bundle["metadata"]["publisher_version"] == "1.1.0"
    assert bundle["metadata"]["approval_state"] == "draft"
    assert bundle["metadata"]["approved_at"] is None
    assert bundle["metadata"]["approved_by"] is None
    assert bundle["metadata"]["review_version"] == 1
    assert bundle["metadata"]["review_required"] is True
    assert payload["approval_gate"]["can_publish"]["allowed"] is False
    assert payload["approval_gate"]["can_send_to_external_ai"]["allowed"] is False
    assert len(bundle["claims"]) == claim_count
    assert bundle["exam_points"] == []
    assert bundle["diagram_requests"][0]["title"] == diagram_title
    assert {item["claim_id"] for item in bundle["key_messages"]}.issubset(
        {item["claim_id"] for item in bundle["claims"]}
    )
    output_path = Path(payload["output_path"])
    assert output_path.is_file()
    assert output_path.name == f"{knowledge_id}_v1.source-bundle.json"
    assert client.get(f"/api/knowledge-records/{knowledge_id}").json()[
        "data"
    ] == knowledge_before
    assert client.get("/api/registry").json() == registry_before
    audit_records = [
        json.loads(line)
        for line in Path(payload["audit_log_path"]).read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [item["action"] for item in audit_records] == [
        "publish",
        "external_ai_send",
    ]
    assert all(item["knowledge_id"] == knowledge_id for item in audit_records)


def test_source_bundle_requires_persisted_supported_knowledge() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    missing = client.post("/api/source-bundles/knw_10000013")
    assert missing.status_code == 404
    assert missing.json()["errors"][0]["code"] == "knowledge_record_not_found"

    gram = client.get("/api/knowledge-templates/staining-method/gram-stain").json()
    assert client.put(
        "/api/knowledge-records/knw_10000004",
        json={
            "record": gram["data"],
            "actor": "product_owner",
            "comment": "非対応Knowledgeを保存",
        },
    ).status_code == 200
    unsupported = client.post("/api/source-bundles/knw_10000004")
    assert unsupported.status_code == 422
    assert unsupported.json()["errors"][0]["code"] == (
        "source_bundle_generation_failed"
    )


def test_approved_knowledge_passes_both_publisher_gates() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    knowledge_id = "knw_10000013"
    starter = client.get(
        "/api/knowledge-templates/laboratory-test-item/ferritin"
    ).json()
    assert client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "承認テスト用に保存",
        },
    ).status_code == 200
    claim_ids = [
        item["claim_id"]
        for item in client.get(f"/api/registry/{knowledge_id}").json()["claims"]
    ]
    for status in ("owner_review", "medical_review", "approved"):
        claims = client.post(
            f"/api/registry/{knowledge_id}/claims/status",
            json={
                "target_status": status,
                "claim_ids": claim_ids,
                "actor": "medical_reviewer",
                "comment": "Claimを確認",
            },
        )
        assert claims.status_code == 200
        knowledge = client.post(
            f"/api/registry/{knowledge_id}/status",
            json={
                "target_status": status,
                "actor": "medical_reviewer",
                "comment": "Knowledgeを確認",
            },
        )
        assert knowledge.status_code == 200

    response = client.post(f"/api/source-bundles/{knowledge_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["bundle"]["metadata"]["approval_state"] == "approved"
    assert payload["bundle"]["metadata"]["approved_by"] == "medical_reviewer"
    assert payload["bundle"]["metadata"]["review_required"] is False
    assert payload["approval_gate"]["can_publish"]["allowed"] is True
    assert payload["approval_gate"]["can_send_to_external_ai"]["allowed"] is True


def test_source_bundle_schema_and_status_are_exposed() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    schema = client.get("/api/schema/source-bundle-1.0")
    status = client.get("/api/status")

    assert schema.status_code == 200
    assert schema.json()["properties"]["schema_version"]["const"] == "1.0"
    assert status.json()["source_bundle_schema_version"] == "1.0"
    assert status.json()["approval_contract_version"] == "1.0"
    assert status.json()["approval_gate_policy"] == "approved_only"
    assert status.json()["source_bundle_supported_knowledge_ids"] == [
        "knw_10000012",
        "knw_10000013",
    ]

    contract = client.get("/api/approval-contract")
    assert contract.status_code == 200
    assert contract.json()["state_sequence"] == [
        "draft",
        "owner_review",
        "medical_review",
        "approved",
        "published",
    ]
