"""Phase 5.26 acceptance tests for Gemini Grounded Evidence Search."""

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import HttpUrl
from pytest import mark, raises

from knowledge_workbench.evidence_intelligence import DefaultEvidenceDeduplicator
from knowledge_workbench.gemini_grounded_search import (
    GeminiGroundedSearchConfig,
    GeminiGroundedSearchError,
    GeminiGroundedSearchProvider,
    GroundedSearchHttpResponse,
    GroundedSearchTransportNetworkError,
    GroundedSearchTransportTimeout,
    MedicalSearchQueryBuilder,
)
from knowledge_workbench.grounded_evidence_models import (
    EvidenceDomainClass,
    GroundedSearchErrorCode,
)
from knowledge_workbench.grounded_evidence_service import (
    GeminiGroundedEvidenceNormalizer,
    classify_evidence_domain,
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
GENERATED_ANSWER = "GEMINI_GENERATED_MEDICAL_ANSWER_MUST_NEVER_BECOME_EVIDENCE"


class QueueTransport:
    def __init__(
        self,
        outcomes: Sequence[
            GroundedSearchHttpResponse
            | GroundedSearchTransportTimeout
            | GroundedSearchTransportNetworkError
        ],
    ) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []
        self.api_keys: list[str] = []

    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GroundedSearchHttpResponse:
        self.calls.append(
            {
                "endpoint": endpoint,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        self.api_keys.append(api_key)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _response(
    citations: list[dict[str, object]],
    *,
    status_code: int = 200,
    body_text: str = GENERATED_ANSWER,
) -> GroundedSearchHttpResponse:
    payload = {
        "id": "int_grounded_test",
        "steps": [
            {
                "type": "google_search_call",
                "arguments": {"queries": ["フェリチン 医学", "フェリチン ガイドライン"]},
            },
            {
                "type": "google_search_result",
                "result": [{"search_suggestions": "discarded html"}],
            },
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": body_text,
                        "annotations": citations,
                    }
                ],
            },
        ],
        "usage": {
            "totalInputTokens": 120,
            "totalOutputTokens": 40,
            "totalTokens": 160,
        },
    }
    return GroundedSearchHttpResponse(
        status_code=status_code,
        content=json.dumps(payload).encode(),
    )


def _citation(url: str, title: str) -> dict[str, object]:
    return {
        "type": "url_citation",
        "url": url,
        "title": title,
        "start_index": 0,
        "end_index": 10,
    }


def _provider(
    transport: QueueTransport,
    *,
    api_key: str = "test-secret-key",
) -> GeminiGroundedSearchProvider:
    return GeminiGroundedSearchProvider(
        GeminiGroundedSearchConfig(
            api_key=api_key,
            model="gemini-search-test",
            endpoint="https://example.invalid/interactions",
            timeout_seconds=2,
            retry_limit=1,
            max_queries=4,
        ),
        transport=transport,
    )


def _client(provider: GeminiGroundedSearchProvider) -> TestClient:
    return TestClient(
        create_app(
            provider=FixtureKnowledgeProvider(),
            grounded_search_provider=provider,
        )
    )


def test_query_builder_creates_four_bounded_intents() -> None:
    plan = MedicalSearchQueryBuilder().build("フェリチン")

    assert len(plan.queries) == 4
    assert {item.intent.value for item in plan.queries} == {
        "definition",
        "official_guideline",
        "laboratory_method",
        "exam_relevance",
    }
    assert all("フェリチン" in item.query for item in plan.queries)


def test_provider_uses_one_stateless_grounded_request_and_extracts_citations_only() -> None:
    transport = QueueTransport(
        [
            _response(
                [
                    _citation(
                        "https://www.mhlw.go.jp/stf/ferritin.html",
                        "厚生労働省 フェリチン検査指針",
                    ),
                    _citation(
                        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                        "Ferritin review",
                    ),
                ]
            )
        ]
    )
    provider = _provider(transport)

    result = provider.search_with_report(EvidenceSearchRequest(theme="フェリチン"))

    assert len(transport.calls) == 1
    body = transport.calls[0]["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["tools"] == [{"type": "google_search"}]
    assert body["model"] == "gemini-search-test"
    assert "test-secret-key" not in json.dumps(body)
    assert len(result.raw.records) == 2
    assert result.raw.external_search_performed is True
    assert result.execution.usage.request_count == 1
    assert result.execution.usage.search_grounding_used is True
    assert result.execution.usage.total_tokens == 160
    serialized = result.raw.model_dump_json()
    assert GENERATED_ANSWER not in serialized
    assert "search_suggestions" not in serialized
    assert "https://www.mhlw.go.jp/stf/ferritin.html" in serialized


def test_normalizer_assigns_levels_from_policy_not_gemini_opinion() -> None:
    transport = QueueTransport(
        [
            _response(
                [
                    _citation(
                        "https://www.mhlw.go.jp/stf/guideline.html",
                        "フェリチン検査ガイドライン",
                    ),
                    _citation(
                        "https://www.pmda.go.jp/safety/info.html",
                        "フェリチン関連情報",
                    ),
                    _citation(
                        "https://unknown.example/medical/ferritin",
                        "Ferritin page",
                    ),
                ]
            )
        ]
    )
    raw = _provider(transport).search(EvidenceSearchRequest(theme="フェリチン"))

    result = GeminiGroundedEvidenceNormalizer().normalize_with_policy(raw)

    assert [item.evidence_level for item in result.normalization.evidence] == [
        PipelineEvidenceLevel.A,
        PipelineEvidenceLevel.B,
        PipelineEvidenceLevel.C,
    ]
    assert [item.domain_class for item in result.policy_decisions] == [
        EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL,
        EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL,
        EvidenceDomainClass.OTHER,
    ]
    assert all(
        "Gemini評価不使用" in item.classification_reasons[-1]
        for item in result.policy_decisions
    )


@mark.parametrize(
    ("outcomes", "expected_code", "expected_calls"),
    [
        (
            [GroundedSearchHttpResponse(status_code=401, content=b"{}")],
            GroundedSearchErrorCode.AUTHENTICATION,
            1,
        ),
        (
            [
                GroundedSearchHttpResponse(status_code=429, content=b"{}"),
                GroundedSearchHttpResponse(status_code=429, content=b"{}"),
            ],
            GroundedSearchErrorCode.RATE_LIMIT,
            2,
        ),
        (
            [
                GroundedSearchHttpResponse(status_code=500, content=b"{}"),
                GroundedSearchHttpResponse(status_code=500, content=b"{}"),
            ],
            GroundedSearchErrorCode.PROVIDER_SERVER,
            2,
        ),
        (
            [GroundedSearchTransportTimeout(), GroundedSearchTransportTimeout()],
            GroundedSearchErrorCode.TIMEOUT,
            2,
        ),
        (
            [
                GroundedSearchTransportNetworkError(),
                GroundedSearchTransportNetworkError(),
            ],
            GroundedSearchErrorCode.NETWORK,
            2,
        ),
        (
            [GroundedSearchHttpResponse(status_code=200, content=b"not-json")],
            GroundedSearchErrorCode.INVALID_RESPONSE,
            1,
        ),
        (
            [_response([])],
            GroundedSearchErrorCode.NO_GROUNDING_SOURCE,
            1,
        ),
    ],
)
def test_provider_errors_are_bounded_and_traceable(
    outcomes: list[
        GroundedSearchHttpResponse
        | GroundedSearchTransportTimeout
        | GroundedSearchTransportNetworkError
    ],
    expected_code: GroundedSearchErrorCode,
    expected_calls: int,
) -> None:
    transport = QueueTransport(outcomes)

    with raises(GeminiGroundedSearchError) as captured:
        _provider(transport).search(EvidenceSearchRequest(theme="フェリチン"))

    assert captured.value.code == expected_code
    assert len(transport.calls) == expected_calls
    assert captured.value.attempt_count == expected_calls


def test_missing_api_key_fails_before_transport() -> None:
    transport = QueueTransport([])

    with raises(GeminiGroundedSearchError) as captured:
        _provider(transport, api_key="").search(
            EvidenceSearchRequest(theme="フェリチン")
        )

    assert captured.value.code == GroundedSearchErrorCode.MISSING_API_KEY
    assert transport.calls == []


@mark.parametrize(
    ("citations", "expected_reason"),
    [
        (
            [
                _citation("https://example.org/ferritin", "Ferritin source A"),
                _citation("https://example.org/ferritin?ref=google", "Ferritin source B"),
            ],
            "url",
        ),
        (
            [
                _citation("https://doi.org/10.1000/ferritin", "Ferritin study A"),
                _citation(
                    "https://doi.org/10.1000/ferritin?source=google",
                    "Ferritin study B",
                ),
            ],
            "doi",
        ),
        (
            [
                _citation(
                    "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    "Ferritin paper A",
                ),
                _citation(
                    "https://www.ncbi.nlm.nih.gov/pubmed/12345678",
                    "Ferritin paper B",
                ),
            ],
            "pmid",
        ),
        (
            [
                _citation("https://example.org/a", "Standardized ferritin evidence"),
                _citation("https://example.org/b", "Standardized ferritin evidence"),
            ],
            "title_similarity",
        ),
    ],
)
def test_existing_deduplication_merges_multi_query_sources(
    citations: list[dict[str, object]],
    expected_reason: str,
) -> None:
    provider = _provider(QueueTransport([_response(citations)]))
    client = _client(provider)

    response = client.post(
        "/api/evidence-search/gemini/previews",
        json={"theme": "フェリチン"},
    )

    assert response.status_code == 200
    preview = response.json()["preview"]
    assert preview["search_audit"]["raw_source_count"] == 2
    assert preview["search_audit"]["accepted_count"] == 1
    assert preview["search_audit"]["deduplicated_count"] == 1
    reasons = preview["evidence_bundle"]["deduplication_decisions"][0]["reasons"]
    assert expected_reason in reasons


def test_same_title_different_dated_editions_are_not_merged() -> None:
    first = _normalized_evidence("one", date(2024, 1, 1), "第1版")
    second = _normalized_evidence("two", date(2025, 1, 1), "第2版")
    normalization = EvidenceNormalizationResult(
        normalized_at=datetime.now(UTC),
        query=EvidenceSearchRequest(theme="版管理"),
        subject=EvidenceSubject(canonical_name="版管理", category="test_item"),
        evidence=[first, second],
        rejected_provider_record_ids=[],
        external_search_performed=True,
        search_duration_ms=1,
    )

    deduplicated = DefaultEvidenceDeduplicator().deduplicate(normalization)

    assert deduplicated.unique_count == 2
    assert deduplicated.excluded_count == 0


def test_api_preview_is_bundle_only_and_does_not_create_draft_or_registry_data() -> None:
    provider = _provider(
        QueueTransport(
            [
                _response(
                    [
                        _citation(
                            "https://www.jamt.or.jp/ferritin",
                            "フェリチン検査情報",
                        )
                    ]
                )
            ]
        )
    )
    client = _client(provider)
    registry_before = client.get("/api/registry").json()
    drafts_before = client.get("/api/authoring/drafts").json()

    response = client.post(
        "/api/evidence-search/gemini/previews",
        json={"theme": "フェリチン"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_draft_generated"] is False
    assert payload["registry_mutated"] is False
    assert payload["promotion_performed"] is False
    assert payload["approval_performed"] is False
    assert payload["preview"]["external_search_called"] is True
    assert payload["preview"]["llm_claim_generation_called"] is False
    assert GENERATED_ANSWER not in response.text
    assert "raw_contract_version" not in response.text
    assert client.get("/api/registry").json() == registry_before
    assert client.get("/api/authoring/drafts").json() == drafts_before
    audit = client.get("/api/evidence-search/gemini/audit").json()
    assert audit["generated_answer_stored"] is False
    assert audit["medical_body_stored"] is False
    assert audit["http_headers_stored"] is False
    assert GENERATED_ANSWER not in str(audit)
    assert "test-secret-key" not in str(audit)


def test_workbench_requires_explicit_search_action_and_shows_safety_boundaries() -> None:
    client = _client(_provider(QueueTransport([])))

    page = client.get("/").text
    status = client.get("/api/evidence-search/gemini").json()

    assert "実Evidence検索（Gemini）" in page
    assert "このボタンを押した時だけ" in page
    assert "Gemini回答本文 非保存" in page
    assert status["external_search_requires_explicit_action"] is True
    assert status["request_limit_per_term"] == 1
    assert status["max_search_intents"] == 4
    assert status["max_sources"] == 50
    assert status["store"] is False
    assert status["claim_generation_enabled"] is False
    assert status["registry_write_enabled"] is False


def test_domain_classification_is_allowlist_based_and_unknown_stays_other() -> None:
    assert (
        classify_evidence_domain("www.mhlw.go.jp")
        == EvidenceDomainClass.JAPAN_OFFICIAL_PROFESSIONAL
    )
    assert (
        classify_evidence_domain("www.cdc.gov")
        == EvidenceDomainClass.INTERNATIONAL_OFFICIAL
    )
    assert (
        classify_evidence_domain("www.nature.com")
        == EvidenceDomainClass.ACADEMIC
    )
    assert (
        classify_evidence_domain("pubmed.ncbi.nlm.nih.gov")
        == EvidenceDomainClass.ACADEMIC
    )
    assert (
        classify_evidence_domain("www.ncbi.nlm.nih.gov")
        == EvidenceDomainClass.INTERNATIONAL_OFFICIAL
    )
    assert classify_evidence_domain("medical-blog.example") == EvidenceDomainClass.OTHER


def _normalized_evidence(
    suffix: str,
    publication_date: date,
    edition: str,
) -> NormalizedEvidence:
    now = datetime.now(UTC)
    return NormalizedEvidence(
        evidence_id=f"evd_{suffix:0<12}",
        title="同一タイトルの医学資料",
        publisher="医学出版",
        evidence_type=EvidenceType.TEXTBOOK,
        evidence_level=PipelineEvidenceLevel.B,
        publication_date=publication_date,
        url=HttpUrl(f"https://example.org/{suffix}"),
        language=EvidenceLanguage.JA,
        abstract_or_snippet="版の異なる資料",
        retrieved_at=now,
        provider=EvidenceProviderReference(
            provider_name="test",
            provider_version="1.0",
            provider_record_id=f"record:{suffix}",
            retrieved_at=now,
        ),
        information_priority_rank=5,
        citation=EvidenceCitation(
            formatted=f"同一タイトルの医学資料 {edition}",
            edition=edition,
        ),
    )
