"""Phase 5.30 acceptance tests for the Knowledge Draft-only Promotion route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_workbench.knowledge_draft_models import knowledge_draft_fingerprint
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def _knowledge_draft(
    client: TestClient,
    *,
    title: str,
    assertion: str,
) -> dict[str, object]:
    authoring = client.post(
        "/api/authoring/drafts",
        json={
            "category": "laboratory_test_item",
            "title": title,
            "aliases": [],
            "difficulty": "standard",
            "exam_importance": "high",
        },
    ).json()["draft"]
    authoring_id = authoring["draft_id"]
    claim = client.post(
        f"/api/authoring/drafts/{authoring_id}/claims",
        json={"assertion": assertion, "semantic_slot": "definition"},
    ).json()["draft"]["claims"][0]
    reference = client.post(
        f"/api/authoring/drafts/{authoring_id}/references",
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
    assembled = client.post(
        "/api/knowledge-assembler/drafts",
        json={"authoring_draft_id": authoring_id},
    )
    assert assembled.status_code == 200
    return assembled.json()["draft"]


def _preview(client: TestClient, draft: dict[str, object]) -> dict[str, object]:
    response = client.post(
        f"/api/knowledge-drafts/{draft['knowledge_draft_id']}/promotion/preview"
    )
    assert response.status_code == 200
    return response.json()["preview"]


def _commit(client: TestClient, preview: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/knowledge-draft-promotions",
        json={
            "preview_id": preview["preview_id"],
            "actor": "phase_5_30_test",
            "comment": "Knowledge Draft promotion acceptance",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_knowledge_draft_preview_is_read_only_and_commit_creates_draft() -> None:
    client = _client()
    draft = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )
    before = client.get("/api/registry").json()

    preview = _preview(client, draft)

    assert preview["preview_version"] == "2.0"
    assert preview["knowledge_draft_id"] == draft["knowledge_draft_id"]
    assert preview["operation"] == "create"
    assert preview["current_version"] == 0
    assert preview["target_version"] == 1
    assert preview["summary"] == draft["summary"]
    assert preview["claims"] == draft["claims"]
    assert preview["references"] == draft["references"]
    assert preview["registry_diff"]["is_new"] is True
    assert preview["validation"]["promotion_allowed"] is True
    assert client.get("/api/registry").json() == before

    result = _commit(client, preview)

    assert result["promotion_version"] == "2.0"
    assert result["approval_state"] == "draft"
    assert result["registry_saved"] is True
    assert result["knowledge_version"] == 1
    view = client.get(f"/api/registry/{result['knowledge_id']}").json()
    assert view["knowledge"]["status"] == "draft"


def test_summary_or_fingerprint_mismatch_blocks_promotion_and_storage() -> None:
    client = _client()
    draft = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )
    output = Path(client.get("/api/status").json()["knowledge_draft_output"])
    path = output / f"{draft['knowledge_draft_id']}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["summary"] = "元Claimに存在しない要約"
    raw["fingerprint"] = knowledge_draft_fingerprint(raw)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    before = client.get("/api/registry").json()

    preview = _preview(client, draft)

    assert preview["validation"]["summary_valid"] is False
    assert preview["validation"]["promotion_allowed"] is False
    commit = client.post(
        "/api/knowledge-draft-promotions",
        json={"preview_id": preview["preview_id"]},
    )
    assert commit.status_code == 409
    assert client.get("/api/registry").json() == before


def test_existing_knowledge_preview_shows_diff_and_next_version() -> None:
    client = _client()
    first = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )
    first_result = _commit(client, _preview(client, first))
    second = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは細胞内で鉄を貯蔵する蛋白質である。",
    )

    preview = _preview(client, second)

    assert preview["operation"] == "version_update"
    assert preview["target_knowledge_id"] == first_result["knowledge_id"]
    assert preview["current_version"] == 1
    assert preview["target_version"] == 2
    assert preview["registry_diff"]["summary_changed"] is True
    assert preview["registry_diff"]["updated_claim_keys"] == [
        "labtest.ferritin.definition"
    ]
    result = _commit(client, preview)
    assert result["knowledge_id"] == first_result["knowledge_id"]
    assert result["knowledge_version"] == 2
    assert result["approval_state"] == "draft"


def test_no_registry_diff_is_blocked() -> None:
    client = _client()
    first = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )
    _commit(client, _preview(client, first))
    duplicate = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )

    preview = _preview(client, duplicate)

    assert preview["registry_diff"]["has_changes"] is False
    assert preview["validation"]["registry_diff_valid"] is False
    assert preview["validation"]["promotion_allowed"] is False


def test_preview_is_stale_after_another_registry_promotion() -> None:
    client = _client()
    stale = _knowledge_draft(
        client,
        title="フェリチン",
        assertion="フェリチンは鉄を貯蔵する蛋白質である。",
    )
    stale_preview = _preview(client, stale)
    other = _knowledge_draft(
        client,
        title="血清鉄",
        assertion="血清鉄は血清中の鉄を示す検査項目である。",
    )
    _commit(client, _preview(client, other))

    response = client.post(
        "/api/knowledge-draft-promotions",
        json={"preview_id": stale_preview["preview_id"]},
    )

    assert response.status_code == 409
    assert "RegistryがPreview後に変更" in response.json()["errors"][0]["message"]


def test_workbench_requires_knowledge_draft_before_preview() -> None:
    page = _client().get("/").text

    assert "Knowledge Draftだけを入力" in page
    assert 'id="previewKnowledgeDraftPromotionButton"' in page
    assert 'id="commitKnowledgeDraftPromotionButton"' in page
    assert 'id="promotionRegistryDiff"' in page
    assert 'id="previewPromotionButton"' not in page
