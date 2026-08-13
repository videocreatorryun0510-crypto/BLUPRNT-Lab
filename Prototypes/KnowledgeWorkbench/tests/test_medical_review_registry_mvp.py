"""Phase 5.31 acceptance tests for immutable human medical review."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.medical_review_models import MedicalReviewRecord
from knowledge_workbench.medical_review_registry import SQLiteMedicalReviewRegistry
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def _saved_ferritin(client: TestClient) -> tuple[str, dict[str, object]]:
    starter = client.get(
        "/api/knowledge-templates/laboratory-test-item/ferritin"
    ).json()["data"]
    knowledge_id = starter["knowledge_id"]
    response = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter,
            "actor": "phase_5_31_fixture",
            "comment": "Medical Review隔離Fixture",
        },
    )
    assert response.status_code == 200
    return str(knowledge_id), starter


def _review_payload(
    client: TestClient,
    knowledge_id: str,
    *,
    decision: str = "approved",
    first_claim_decision: str = "approved",
    drop_first_evidence: bool = False,
    days: int = 30,
) -> dict[str, object]:
    context = client.get(f"/api/medical-review/knowledge/{knowledge_id}").json()
    claim_reviews = []
    for index, claim in enumerate(context["claims"]):
        assessments = [
            {
                "evidence_id": evidence["source_id"],
                "exists_confirmed": True,
                "current_confirmed": True,
                "directly_supports": True,
                "evidence_level": "A",
                "support": "supports",
                "locator": evidence.get("pages") or "該当箇所確認済み",
                "comment": "人が原資料を確認",
            }
            for evidence in claim["evidence"]
        ]
        if index == 0 and drop_first_evidence:
            assessments = []
        claim_reviews.append(
            {
                "claim_id": claim["claim_id"],
                "evidence_assessments": assessments,
                "decision": first_claim_decision if index == 0 else "approved",
                "comment": "Claimと根拠の対応を人が確認",
            }
        )
    checklist_results = [
        {"item_id": item["item_id"], "result": "pass", "reason": "確認済み"}
        for item in context["checklist"]
    ]
    return {
        "knowledge_id": knowledge_id,
        "reviewer_id": "reviewer_fixture_chemistry_001",
        "reviewer_role": "final_approver",
        "review_scope": "knowledge_and_claims",
        "claim_reviews": claim_reviews,
        "checklist_results": checklist_results,
        "decision": decision,
        "comments": "隔離FixtureでReview Criteriaをすべて確認",
        "valid_until": (datetime.now(UTC) + timedelta(days=days)).isoformat(),
    }


def _create_review(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/api/medical-review/reviews", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_review_record_is_append_only_and_review_version_is_independent() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    first = _create_review(client, _review_payload(client, knowledge_id))
    second_payload = _review_payload(
        client,
        knowledge_id,
        decision="revision_required",
        first_claim_decision="revision_required",
    )
    second = _create_review(client, second_payload)

    assert first["review"]["review_version"] == 1
    assert second["review"]["review_version"] == 2
    assert first["review"]["review_id"] != second["review"]["review_id"]
    records = client.get(f"/api/medical-review/knowledge/{knowledge_id}/reviews").json()
    assert [item["review_version"] for item in records["reviews"]] == [1, 2]
    assert records["reviews"][0] == first["review"]


def test_all_human_review_conditions_make_fixture_eligible_without_approval() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    before = client.get(f"/api/registry/{knowledge_id}").json()
    result = _create_review(client, _review_payload(client, knowledge_id))
    after = client.get(f"/api/registry/{knowledge_id}").json()

    assert result["eligibility"]["eligible_for_final_approval"] is True
    assert result["eligibility"]["validity"] == "current"
    assert result["knowledge_registry_changed"] is False
    assert result["approval_state_changed"] is False
    assert before == after
    assert after["knowledge"]["status"] == "draft"


def test_claim_revision_and_approved_with_conditions_are_not_eligible() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    revision = _create_review(
        client,
        _review_payload(
            client,
            knowledge_id,
            decision="revision_required",
            first_claim_decision="revision_required",
        ),
    )
    assert revision["eligibility"]["eligible_for_final_approval"] is False
    assert "claims_approved" in revision["eligibility"]["reasons"]

    conditional = _create_review(
        client,
        _review_payload(client, knowledge_id, decision="approved_with_conditions"),
    )
    assert conditional["eligibility"]["eligible_for_final_approval"] is False
    assert "final_decision" in conditional["eligibility"]["reasons"]


def test_missing_evidence_blocks_final_approval() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    result = _create_review(
        client,
        _review_payload(client, knowledge_id, drop_first_evidence=True),
    )
    assert result["eligibility"]["eligible_for_final_approval"] is False
    assert "evidence_assessed" in result["eligibility"]["reasons"]


def test_knowledge_or_claim_change_makes_old_review_stale() -> None:
    client = _client()
    knowledge_id, original = _saved_ferritin(client)
    review = _create_review(client, _review_payload(client, knowledge_id))["review"]
    parsed = MedicalReviewRecord.model_validate(review)
    fingerprint_mismatch = parsed.model_copy(
        update={"knowledge_fingerprint": "sha256:" + "0" * 64}
    )
    fingerprint_result = client.app.state.medical_review_service.evaluate_eligibility(
        knowledge_id, fingerprint_mismatch
    )
    assert fingerprint_result.validity.value == "stale"
    assert "knowledge_fingerprint" in fingerprint_result.reasons
    changed = deepcopy(original)
    changed["core_facts"]["definitions"][0]["assertion"] += "（改訂）"
    response = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": changed,
            "actor": "phase_5_31_fixture",
            "comment": "Review後のClaim変更",
        },
    )
    assert response.status_code == 200, response.text

    eligibility = client.get(
        f"/api/medical-review/knowledge/{knowledge_id}/eligibility"
    ).json()
    assert eligibility["eligible_for_final_approval"] is False
    assert eligibility["validity"] == "stale"
    assert {
        "knowledge_version",
        "knowledge_fingerprint",
        "claim_versions",
    } & set(eligibility["reasons"])
    history = client.get(f"/api/medical-review/knowledge/{knowledge_id}/reviews").json()
    assert history["reviews"][0] == review


def test_formal_registry_approval_route_requires_medical_review(
    tmp_path: Path,
) -> None:
    knowledge_registry = SQLiteKnowledgeRegistry(tmp_path / "knowledge.sqlite3")
    review_registry = SQLiteMedicalReviewRegistry(tmp_path / "medical-review.sqlite3")
    source_client = _client()
    source = source_client.get(
        "/api/knowledge-templates/laboratory-test-item/ferritin"
    ).json()["data"]
    from knowledge_contracts.v10 import validate_knowledge_record

    saved = knowledge_registry.reconcile(
        validate_knowledge_record(source), actor="isolated_test", note="gate fixture"
    ).record
    app = create_app(
        provider=FixtureKnowledgeProvider(),
        registry=knowledge_registry,
        medical_review_registry=review_registry,
    )
    client = TestClient(app)
    review_result = _create_review(client, _review_payload(client, saved.knowledge_id))
    assert review_result["eligibility"]["eligible_for_final_approval"] is False
    assert "reviewer_identity" in review_result["eligibility"]["reasons"]
    response = client.post(
        f"/api/registry/{saved.knowledge_id}/status",
        json={
            "target_status": "approved",
            "actor": "fixture_actor",
            "comment": "Reviewなしの承認を試行",
        },
    )
    assert response.status_code == 409
    assert response.json()["status"] == "medical_review_required"
    assert knowledge_registry.view(saved.knowledge_id).knowledge.status.value == "draft"


def test_review_deadline_expiry_is_derived_without_rewriting_record() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    payload = _review_payload(client, knowledge_id)
    payload["valid_until"] = (datetime.now(UTC) + timedelta(milliseconds=200)).isoformat()
    result = _create_review(client, payload)
    review = result["review"]
    parsed = client.app.state.medical_review_service.review_registry.get(
        review["review_id"]
    )
    assert parsed is not None
    eligibility = client.app.state.medical_review_service.evaluate_eligibility(
        knowledge_id,
        parsed,
        now=parsed.valid_until + timedelta(seconds=1),
    )
    assert eligibility.validity.value == "expired"
    assert eligibility.eligible_for_final_approval is False
    assert "review_deadline" in eligibility.reasons
    unchanged = client.app.state.medical_review_service.review_registry.get(
        review["review_id"]
    )
    assert unchanged == parsed


def test_reviewer_id_is_required_and_must_exist_in_registry() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    payload = _review_payload(client, knowledge_id)
    payload["reviewer_id"] = "free_text_person"
    response = client.post("/api/medical-review/reviews", json=payload)
    assert response.status_code == 422
    assert "Reviewer Registry" in response.json()["errors"][0]["message"]


def test_queue_and_workbench_expose_human_review_without_changing_real_state() -> None:
    client = _client()
    knowledge_id, _ = _saved_ferritin(client)
    queue = client.get("/api/medical-review/queue").json()["queue"]
    entry = next(item for item in queue if item["knowledge_id"] == knowledge_id)
    assert entry["review_version"] == 0
    assert entry["claim_count"] == 11
    assert entry["completeness"] == 100

    page = client.get("/").text
    assert "Medical Review Queue" in page
    assert 'id="medicalReviewQueue"' in page
    assert 'id="saveMedicalReviewButton"' in page


def test_medical_review_contract_schema_is_available() -> None:
    schema = _client().get("/api/schema/medical-review-record-1.0")
    assert schema.status_code == 200
    assert schema.json()["properties"]["review_version"]["minimum"] == 1
