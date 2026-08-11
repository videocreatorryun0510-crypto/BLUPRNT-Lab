"""Phase 5.23 acceptance tests for Preview-gated Registry promotion."""

from fastapi.testclient import TestClient
from knowledge_contracts.registry_v10 import RegistryStatus
from knowledge_contracts.v10 import KnowledgeRecord

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def test_preview_is_read_only_and_commit_creates_draft_registry_knowledge() -> None:
    client = _client()
    draft_id = _ready_draft(client, title="血清鉄", disposition_slot="overview")
    before = client.get("/api/registry").json()

    preview_response = client.post(
        f"/api/authoring/drafts/{draft_id}/promotion/preview"
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()["preview"]
    assert preview_response.json()["registry_mutated"] is False
    assert preview["operation"] == "create"
    assert preview["validation"]["promotion_allowed"] is True
    assert preview["claim_count"] == 1
    assert preview["reference_count"] == 1
    assert preview["target_version"] == 1
    assert client.get("/api/registry").json() == before

    committed = client.post(
        "/api/authoring/promotions",
        json={
            "preview_id": preview["preview_id"],
            "draft_disposition": "keep",
            "actor": "phase_5_23_test",
            "comment": "Promotion acceptance",
        },
    )
    assert committed.status_code == 200
    result = committed.json()["result"]
    assert result["registry_saved"] is True
    assert result["approval_state"] == "draft"
    assert result["draft_lifecycle_state"] == "active"
    view = client.get(f"/api/registry/{result['knowledge_id']}").json()
    assert view["knowledge"]["status"] == RegistryStatus.DRAFT.value
    record = client.get(f"/api/knowledge-records/{result['knowledge_id']}").json()["data"]
    KnowledgeRecord.model_validate(record)
    assert record["category_content"]["laboratory_test_item"]["overview"][0][
        "assertion"
    ] == "血清鉄は血清中の鉄を測定する検査項目である。"
    assert record["evidence"][0]["supported_claim_ids"]


def test_blocked_preview_never_mutates_registry() -> None:
    client = _client()
    created = client.post(
        "/api/authoring/drafts",
        json={
            "category": "laboratory_test_item",
            "title": "未完成検査",
            "aliases": [],
            "difficulty": "basic",
            "exam_importance": "low",
        },
    ).json()["draft"]
    draft_id = created["draft_id"]
    client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={"assertion": "保存先と出典が未指定である。"},
    )
    before = client.get("/api/registry").json()

    preview = client.post(
        f"/api/authoring/drafts/{draft_id}/promotion/preview"
    ).json()["preview"]

    assert preview["validation"]["promotion_allowed"] is False
    failed_codes = {
        item["code"] for item in preview["validation"]["checks"] if not item["passed"]
    }
    assert {"category", "claims", "references"}.issubset(failed_codes)
    assert client.get("/api/registry").json() == before
    commit = client.post(
        "/api/authoring/promotions",
        json={"preview_id": preview["preview_id"]},
    )
    assert commit.status_code == 409
    assert client.get("/api/registry").json() == before


def test_preview_becomes_stale_after_draft_change() -> None:
    client = _client()
    draft_id = _ready_draft(client, title="不飽和鉄結合能", disposition_slot="overview")
    preview = client.post(
        f"/api/authoring/drafts/{draft_id}/promotion/preview"
    ).json()["preview"]
    claim = client.get(f"/api/authoring/drafts/{draft_id}").json()["draft"]["claims"][0]
    client.put(
        f"/api/authoring/drafts/{draft_id}/claims/{claim['claim_id']}",
        json={
            "assertion": "UIBCは不飽和トランスフェリンの鉄結合能を表す。",
            "semantic_slot": "overview",
        },
    )

    response = client.post(
        "/api/authoring/promotions",
        json={"preview_id": preview["preview_id"]},
    )
    assert response.status_code == 409
    assert client.get("/api/registry").json()["knowledge"] == []


def test_existing_registry_key_is_promoted_as_new_draft_version() -> None:
    client = _client()
    first_draft = _ready_draft(client, title="フェリチン", disposition_slot="definition")
    first_preview = client.post(
        f"/api/authoring/drafts/{first_draft}/promotion/preview"
    ).json()["preview"]
    first_result = client.post(
        "/api/authoring/promotions",
        json={"preview_id": first_preview["preview_id"]},
    ).json()["result"]

    second_draft = _ready_draft(
        client,
        title="フェリチン",
        disposition_slot="overview",
        assertion="フェリチンは体内の貯蔵鉄を反映する。",
    )
    second_preview = client.post(
        f"/api/authoring/drafts/{second_draft}/promotion/preview"
    ).json()["preview"]
    assert second_preview["operation"] == "version_update"
    assert second_preview["target_knowledge_id"] == first_result["knowledge_id"]
    assert second_preview["target_version"] == 2

    second_result = client.post(
        "/api/authoring/promotions",
        json={
            "preview_id": second_preview["preview_id"],
            "draft_disposition": "archive",
        },
    ).json()["result"]
    assert second_result["knowledge_id"] == first_result["knowledge_id"]
    assert second_result["knowledge_version"] == 2
    assert second_result["approval_state"] == "draft"
    assert second_result["draft_lifecycle_state"] == "archived"
    archived = client.get(f"/api/authoring/drafts/{second_draft}").json()["draft"]
    assert archived["lifecycle_state"] == "archived"


def test_workbench_exposes_preview_log_and_result_contracts() -> None:
    client = _client()
    page = client.get("/")
    status = client.get("/api/status").json()
    slots = client.get("/api/authoring/promotion/semantic-slots").json()

    assert "Promotion Preview" in page.text
    assert "Promotion Log" in page.text
    assert "正式RegistryへPromotion" in page.text
    assert status["knowledge_promotion_version"] == "1.0"
    assert status["knowledge_promotion_preview_mutates_registry"] is False
    assert status["knowledge_promotion_registry_write_enabled"] is True
    assert status["knowledge_promotion_approval_state"] == "draft"
    assert "overview" in slots["semantic_slots"]["laboratory_test_item"]
    assert client.get("/api/schema/knowledge-promotion-preview-1.0").status_code == 200
    assert client.get("/api/schema/knowledge-promotion-result-1.0").status_code == 200


def _ready_draft(
    client: TestClient,
    *,
    title: str,
    disposition_slot: str,
    assertion: str | None = None,
) -> str:
    draft = client.post(
        "/api/authoring/drafts",
        json={
            "category": "laboratory_test_item",
            "title": title,
            "aliases": [],
            "difficulty": "standard",
            "exam_importance": "high",
        },
    ).json()["draft"]
    draft_id = draft["draft_id"]
    claim = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={
            "assertion": assertion or f"{title}は血清中の鉄を測定する検査項目である。",
            "semantic_slot": disposition_slot,
        },
    ).json()["draft"]["claims"][0]
    reference = client.post(
        f"/api/authoring/drafts/{draft_id}/references",
        json={
            "evidence_level": "A",
            "evidence_role": "primary",
            "source_priority_rank": 3,
            "title": "臨床検査標準資料",
            "issuing_organization": "公的検査機関",
            "publication_year": 2026,
            "url": "https://example.test/standard",
            "supported_claim_ids": [claim["claim_id"]],
        },
    )
    assert reference.status_code == 200
    return draft_id
