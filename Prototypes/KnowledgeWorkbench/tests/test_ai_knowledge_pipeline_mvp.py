"""Phase 5.24 acceptance tests for the provider-neutral Knowledge Pipeline."""

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import mark

from knowledge_workbench.fixture_knowledge_pipeline import (
    FixtureClaimBuilder,
    FixtureEvidenceSearchProvider,
    FixturePipelineCatalog,
)
from knowledge_workbench.knowledge_pipeline_builders import DefaultEvidenceRanker
from knowledge_workbench.knowledge_pipeline_interfaces import (
    ClaimBuilder,
    EvidenceRanker,
    EvidenceSearchProvider,
)
from knowledge_workbench.knowledge_pipeline_models import EvidenceSearchRequest
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


@mark.parametrize(
    ("theme", "category", "minimum_claims"),
    [
        ("フェリチン", "laboratory_test_item", 2),
        ("鉄欠乏性貧血", "disease", 2),
        ("Gram染色", "staining_method", 1),
    ],
)
def test_theme_builds_traceable_preview_without_external_calls_or_writes(
    theme: str,
    category: str,
    minimum_claims: int,
) -> None:
    client = _client()
    registry_before = client.get("/api/registry").json()
    drafts_before = client.get("/api/authoring/drafts").json()

    response = client.post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": theme},
    )

    assert response.status_code == 200
    payload = response.json()
    preview = payload["preview"]
    evidence = preview["evidence_search"]["evidence"]
    claims = preview["claim_build"]["claims"]
    references = preview["references"]
    evidence_ids = {item["evidence_id"] for item in evidence}
    claim_ids = {item["claim_id"] for item in claims}
    assert preview["evidence_search"]["subject"]["category"] == category
    assert len(evidence) >= 1
    assert len(claims) >= minimum_claims
    assert len(references) >= 1
    assert all(set(item["evidence_ids"]) <= evidence_ids for item in claims)
    assert all(set(item["supported_claim_ids"]) <= claim_ids for item in references)
    assert preview["authoring_draft"]["review"]["state"] == "draft"
    assert preview["authoring_draft_saved"] is False
    assert preview["registry_mutated"] is False
    assert preview["external_ai_called"] is False
    assert preview["external_search_called"] is False
    assert payload["promotion_performed"] is False
    assert client.get("/api/registry").json() == registry_before
    assert client.get("/api/authoring/drafts").json() == drafts_before


def test_preview_can_be_saved_once_as_authoring_draft_only() -> None:
    client = _client()
    registry_before = client.get("/api/registry").json()
    preview = client.post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": "フェリチン"},
    ).json()["preview"]

    saved = client.post(f"/api/ai-knowledge-pipeline/previews/{preview['pipeline_id']}/save")

    assert saved.status_code == 200
    result = saved.json()["result"]
    assert result["draft"]["metadata"]["title"] == "フェリチン"
    assert result["draft"]["review"]["state"] == "draft"
    assert result["registry_mutated"] is False
    assert result["promotion_performed"] is False
    drafts = client.get("/api/authoring/drafts").json()["drafts"]
    assert any(item["draft_id"] == result["draft"]["draft_id"] for item in drafts)
    assert client.get("/api/registry").json() == registry_before

    repeated = client.post(f"/api/ai-knowledge-pipeline/previews/{preview['pipeline_id']}/save")
    assert repeated.status_code == 422


def test_unknown_theme_stops_without_inventing_evidence_or_draft() -> None:
    client = _client()
    drafts_before = client.get("/api/authoring/drafts").json()

    response = client.post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": "Howell-Jolly小体"},
    )

    assert response.status_code == 422
    assert "実Provider接続後" in response.json()["errors"][0]["message"]
    assert client.get("/api/authoring/drafts").json() == drafts_before


def test_fixture_components_satisfy_provider_neutral_protocols_and_rank_deterministically() -> None:
    catalog = FixturePipelineCatalog(REPOSITORY_ROOT)
    provider = FixtureEvidenceSearchProvider(catalog)
    ranker = DefaultEvidenceRanker()
    builder = FixtureClaimBuilder(catalog)
    assert isinstance(provider, EvidenceSearchProvider)
    assert isinstance(ranker, EvidenceRanker)
    assert isinstance(builder, ClaimBuilder)

    search = provider.search(EvidenceSearchRequest(theme="フェリチン"))
    first = ranker.rank(search)
    second = ranker.rank(search)
    assert first == second
    assert [item.rank for item in first.ranked_evidence] == list(
        range(1, len(first.ranked_evidence) + 1)
    )


def test_workbench_and_contracts_expose_pipeline_boundaries() -> None:
    client = _client()
    page = client.get("/")
    status = client.get("/api/status").json()
    pipeline = client.get("/api/ai-knowledge-pipeline").json()
    evidence_schema = client.get("/api/schema/evidence-search-1.0")
    preview_schema = client.get("/api/schema/knowledge-pipeline-preview-1.0")

    assert page.status_code == 200
    assert "AI Knowledge Wizard" in page.text
    assert "Evidence Preview" in page.text
    assert "Claim Preview" in page.text
    assert "Reference Preview" in page.text
    assert "Authoring Draftへ保存" in page.text
    assert status["ai_knowledge_pipeline_version"] == "1.0"
    assert status["ai_knowledge_pipeline_external_search_enabled"] is False
    assert status["ai_knowledge_pipeline_llm_enabled"] is False
    assert status["ai_knowledge_pipeline_registry_write_enabled"] is False
    assert pipeline["mode"] == "local_fixture_sandbox"
    assert pipeline["external_search_enabled"] is False
    assert pipeline["llm_enabled"] is False
    assert evidence_schema.status_code == 200
    assert evidence_schema.json()["title"] == "EvidenceSearchResult"
    assert preview_schema.status_code == 200
    assert preview_schema.json()["title"] == "KnowledgePipelinePreview"
