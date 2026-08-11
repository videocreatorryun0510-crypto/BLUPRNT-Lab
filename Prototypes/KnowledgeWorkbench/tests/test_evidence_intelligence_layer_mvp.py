"""Phase 5.25 acceptance tests for the Evidence Intelligence Layer."""

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import mark

from knowledge_workbench.evidence_intelligence import (
    DefaultEvidenceDeduplicator,
    DefaultEvidenceRanker,
    EvidenceBundleBuilder,
)
from knowledge_workbench.fixture_knowledge_pipeline import (
    FixtureEvidenceNormalizer,
    FixtureEvidenceSearchProvider,
    FixturePipelineCatalog,
)
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceCitation,
    EvidenceLanguage,
    EvidenceNormalizationResult,
    EvidenceProviderReference,
    EvidenceSearchRequest,
    EvidenceSubject,
    EvidenceType,
    NormalizedEvidence,
    PipelineEvidenceLevel,
)
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def _evidence(
    suffix: str,
    *,
    title: str,
    level: PipelineEvidenceLevel = PipelineEvidenceLevel.B,
    information_priority: int = 5,
    doi: str | None = None,
    pmid: str | None = None,
    url: str | None = None,
    provider: str = "provider_a",
) -> NormalizedEvidence:
    return NormalizedEvidence(
        evidence_id=f"evd_{suffix:0<12}",
        title=title,
        publisher="テスト発行団体",
        evidence_type=EvidenceType.GUIDELINE,
        evidence_level=level,
        publication_date=date(2025, 1, 1),
        url=url,
        doi=doi,
        pmid=pmid,
        language=EvidenceLanguage.JA,
        abstract_or_snippet=f"{title}の検証用要約",
        retrieved_at=NOW,
        provider=EvidenceProviderReference(
            provider_name=provider,
            provider_version="1.0",
            provider_record_id=f"{provider}:{suffix}",
            retrieved_at=NOW,
        ),
        information_priority_rank=information_priority,
        citation=EvidenceCitation(formatted=f"{title}、2025"),
    )


def _normalization(*evidence: NormalizedEvidence) -> EvidenceNormalizationResult:
    return EvidenceNormalizationResult(
        normalized_at=NOW,
        query=EvidenceSearchRequest(theme="テストテーマ"),
        subject=EvidenceSubject(
            canonical_name="テストテーマ",
            category="laboratory_test_item",
        ),
        evidence=list(evidence),
        rejected_provider_record_ids=[],
        external_search_performed=False,
        search_duration_ms=12,
    )


def test_pipeline_exposes_bundle_only_and_never_raw_provider_payload() -> None:
    response = _client().post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": "フェリチン"},
    )

    assert response.status_code == 200
    preview = response.json()["preview"]
    serialized = response.text
    assert preview["pipeline_version"] == "1.1"
    assert preview["evidence_bundle"]["evidence_bundle_version"] == "1.0"
    assert "evidence_search" not in preview
    assert "evidence_ranking" not in preview
    assert '"raw_contract_version"' not in serialized
    assert '"records"' not in serialized
    assert '"payload"' not in serialized
    assert preview["search_audit_recorded"] is True


def test_fixture_normalizer_creates_the_common_evidence_contract() -> None:
    catalog = FixturePipelineCatalog(REPOSITORY_ROOT)
    raw = FixtureEvidenceSearchProvider(catalog).search(
        EvidenceSearchRequest(theme="Gram染色")
    )

    normalized = FixtureEvidenceNormalizer().normalize(raw)

    assert normalized.evidence
    item = normalized.evidence[0]
    assert item.evidence_contract_version == "1.0"
    assert item.title
    assert item.publisher
    assert item.evidence_type
    assert item.evidence_level == PipelineEvidenceLevel.C
    assert item.language == EvidenceLanguage.JA
    assert item.abstract_or_snippet
    assert item.retrieved_at == raw.searched_at
    assert item.provider.provider_name == "local_fixture_evidence"


@mark.parametrize(
    ("left", "right", "expected_reason"),
    [
        (
            {"doi": "10.1000/TEST", "title": "DOIによる重複確認資料"},
            {"doi": "https://doi.org/10.1000/test", "title": "別タイトル資料"},
            "doi",
        ),
        (
            {"pmid": "12345678", "title": "PMIDによる重複確認資料"},
            {"pmid": "PMID: 12345678", "title": "別タイトル資料"},
            "pmid",
        ),
        (
            {"url": "https://example.org/evidence/?ref=a", "title": "URL重複確認資料"},
            {"url": "https://example.org/evidence", "title": "別タイトル資料"},
            "url",
        ),
        (
            {"title": "臨床検査技師国家試験の標準化された根拠資料"},
            {"title": "臨床検査技師国家試験の標準化された根拠資料"},
            "title_similarity",
        ),
    ],
)
def test_deduplicator_merges_common_identity_and_retains_provenance(
    left: dict[str, str],
    right: dict[str, str],
    expected_reason: str,
) -> None:
    first = _evidence("first", provider="pubmed", **left)
    second = _evidence("second", provider="jstage", **right)

    result = DefaultEvidenceDeduplicator().deduplicate(
        _normalization(first, second)
    )

    assert result.input_count == 2
    assert result.unique_count == 1
    assert result.excluded_count == 1
    assert expected_reason in result.decisions[0].reasons
    assert {item.provider_name for item in result.evidence[0].providers} == {
        "pubmed",
        "jstage",
    }


def test_ranker_uses_evidence_level_before_independent_information_priority() -> None:
    level_c_priority_1 = _evidence(
        "levelc",
        title="Level C資料",
        level=PipelineEvidenceLevel.C,
        information_priority=1,
    )
    level_a_priority_99 = _evidence(
        "levela",
        title="Level A資料",
        level=PipelineEvidenceLevel.A,
        information_priority=99,
    )
    level_b = _evidence(
        "levelb",
        title="Level B資料",
        level=PipelineEvidenceLevel.B,
        information_priority=50,
    )
    unique = DefaultEvidenceDeduplicator().deduplicate(
        _normalization(level_c_priority_1, level_a_priority_99, level_b)
    )

    ranked = DefaultEvidenceRanker().rank(unique)

    assert [item.evidence.evidence_level for item in ranked.ranked_evidence] == [
        PipelineEvidenceLevel.A,
        PipelineEvidenceLevel.B,
        PipelineEvidenceLevel.C,
    ]
    assert all("補助基準" in item.ranking_reasons[1] for item in ranked.ranked_evidence)


def test_bundle_counts_deduplication_and_semantic_fingerprint_are_stable() -> None:
    first = _evidence(
        "first",
        title="同一根拠の一次資料",
        doi="10.1000/bundle",
        provider="pubmed",
    )
    duplicate = _evidence(
        "second",
        title="別経路で取得した同一資料",
        doi="10.1000/bundle",
        provider="jstage",
    )
    normalization = _normalization(first, duplicate)
    deduplication = DefaultEvidenceDeduplicator().deduplicate(normalization)
    ranking = DefaultEvidenceRanker().rank(deduplication)

    first_bundle = EvidenceBundleBuilder().build(
        normalization, deduplication, ranking
    )
    second_bundle = EvidenceBundleBuilder().build(
        normalization, deduplication, ranking
    )

    assert first_bundle.input_record_count == 2
    assert first_bundle.accepted_evidence_count == 1
    assert first_bundle.excluded_evidence_count == 1
    assert first_bundle.fingerprint == second_bundle.fingerprint
    assert first_bundle.bundle_id == second_bundle.bundle_id


def test_search_audit_is_metadata_only_for_success_and_failure() -> None:
    client = _client()
    client.post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": "フェリチン"},
    )
    failed = client.post(
        "/api/ai-knowledge-pipeline/previews",
        json={"theme": "未対応テーマ"},
    )
    audit = client.get("/api/evidence-intelligence/audit").json()

    assert failed.status_code == 422
    assert audit["medical_body_stored"] is False
    assert {event["status"] for event in audit["events"]} == {"success", "failed"}
    serialized = str(audit["events"])
    assert "abstract_or_snippet" not in serialized
    assert "citation" not in serialized
    assert "claim" not in serialized.lower()
    assert all("duration_ms" in event for event in audit["events"])
    assert all("search_query" in event for event in audit["events"])


def test_workbench_and_schema_endpoints_publish_only_stable_contracts() -> None:
    client = _client()
    page = client.get("/").text
    status = client.get("/api/evidence-intelligence").json()
    evidence_schema = client.get("/api/schema/evidence-contract-1.0").json()
    bundle_schema = client.get("/api/schema/evidence-bundle-1.0").json()

    assert "Evidence Preview" in page
    assert "Evidence Ranking" in page
    assert "Evidence Bundle" in page
    assert "Raw Evidence 非公開" in page
    assert status["raw_evidence_exposed_to_workbench"] is False
    assert status["information_priority_is_independent"] is True
    assert evidence_schema["title"] == "NormalizedEvidence"
    assert bundle_schema["title"] == "EvidenceBundle"
