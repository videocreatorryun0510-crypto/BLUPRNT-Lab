"""Phase 5.26.1 tests for the Discovery Candidate boundary."""

import json
from collections.abc import Sequence

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pytest import mark, raises

from knowledge_workbench.discovery_boundary import (
    DiscoveryBoundaryTarget,
    DiscoveryBoundaryValidationError,
    reject_discovery_asset,
)
from knowledge_workbench.discovery_interfaces import (
    DiscoveryProvider,
    FormalEvidenceProviderType,
)
from knowledge_workbench.discovery_models import (
    DiscoveryCandidate,
    DiscoverySearchRequest,
)
from knowledge_workbench.gemini_grounded_search import (
    GeminiGroundedSearchConfig,
    GeminiGroundedSearchError,
    GeminiGroundedSearchProvider,
    GroundedSearchHttpResponse,
    GroundedSearchTransportNetworkError,
    GroundedSearchTransportTimeout,
    MedicalSearchQueryBuilder,
)
from knowledge_workbench.grounded_evidence_models import GroundedSearchErrorCode
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceBundle,
    EvidenceSearchRequest,
)
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

GENERATED_ANSWER = "GEMINI_GENERATED_MEDICAL_ANSWER_MUST_NEVER_BE_STORED"


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
) -> GroundedSearchHttpResponse:
    payload = {
        "id": "int_discovery_test",
        "steps": [
            {
                "type": "google_search_call",
                "arguments": {
                    "queries": ["フェリチン 医学", "フェリチン ガイドライン"]
                },
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
                        "text": GENERATED_ANSWER,
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


def _citation(
    url: str,
    title: str,
    *,
    snippet: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "type": "url_citation",
        "url": url,
        "title": title,
        "start_index": 0,
        "end_index": 10,
    }
    if snippet is not None:
        value["snippet"] = snippet
    return value


def _provider(
    transport: QueueTransport,
    *,
    api_key: str = "test-secret-key",
    max_sources: int = 50,
) -> GeminiGroundedSearchProvider:
    return GeminiGroundedSearchProvider(
        GeminiGroundedSearchConfig(
            api_key=api_key,
            model="gemini-search-test",
            endpoint="https://example.invalid/interactions",
            timeout_seconds=2,
            retry_limit=1,
            max_queries=4,
            max_sources=max_sources,
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


def test_provider_returns_discovery_candidate_set_and_discards_answer() -> None:
    transport = QueueTransport(
        [
            _response(
                [
                    _citation(
                        "https://www.mhlw.go.jp/stf/ferritin.html",
                        "厚生労働省 フェリチン検査資料",
                        snippet="Citation metadata snippet",
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

    result = provider.discover_with_report(
        DiscoverySearchRequest(medical_term="フェリチン")
    )

    assert isinstance(provider, DiscoveryProvider)
    assert len(transport.calls) == 1
    body = transport.calls[0]["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["tools"] == [{"type": "google_search"}]
    assert body["model"] == "gemini-search-test"
    assert "test-secret-key" not in json.dumps(body)
    candidate_set = result.candidate_set
    assert candidate_set.candidate_count == 2
    assert candidate_set.claim_eligible is False
    assert candidate_set.evidence_bundle_eligible is False
    assert candidate_set.registry_allowed is False
    assert all(item.claim_eligible is False for item in candidate_set.candidates)
    assert all(item.evidence_bundle_eligible is False for item in candidate_set.candidates)
    serialized = candidate_set.model_dump_json()
    assert GENERATED_ANSWER not in serialized
    assert "search_suggestions" not in serialized
    assert "evidence_level" not in serialized
    assert '"evidence_bundle":' not in serialized


def test_phase_526_search_method_migrates_to_discovery_type() -> None:
    provider = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    )

    candidate_set = provider.search(EvidenceSearchRequest(theme="フェリチン"))

    assert candidate_set.discovery_candidate_set_version == "1.0"
    assert candidate_set.evidence_bundle_eligible is False


@mark.parametrize(
    "target",
    [
        DiscoveryBoundaryTarget.EVIDENCE_BUNDLE,
        DiscoveryBoundaryTarget.CLAIM_BUILDER,
        DiscoveryBoundaryTarget.PROMOTION,
        DiscoveryBoundaryTarget.REGISTRY,
        DiscoveryBoundaryTarget.APPROVAL,
    ],
)
def test_discovery_candidate_is_rejected_at_every_formal_boundary(
    target: DiscoveryBoundaryTarget,
) -> None:
    provider = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    )
    candidate = provider.discover(
        DiscoverySearchRequest(medical_term="フェリチン")
    ).candidates[0]

    with raises(DiscoveryBoundaryValidationError) as captured:
        reject_discovery_asset(candidate, target=target)

    assert captured.value.target == target
    assert captured.value.code == f"discovery_not_allowed_for_{target.value}"


def test_discovery_candidate_cannot_validate_as_evidence_bundle() -> None:
    candidate = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    ).discover(DiscoverySearchRequest(medical_term="フェリチン")).candidates[0]

    with raises(ValidationError):
        EvidenceBundle.model_validate(candidate.model_dump(mode="json"))


def test_discovery_flags_cannot_be_changed_to_true() -> None:
    candidate = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    ).discover(DiscoverySearchRequest(medical_term="フェリチン")).candidates[0]
    payload = candidate.model_dump(mode="json")
    payload["claim_eligible"] = True

    with raises(ValidationError):
        DiscoveryCandidate.model_validate(payload)


def test_duplicate_grounding_citation_is_only_one_discovery_candidate() -> None:
    citation = _citation("https://example.org/source", "Same source")
    candidate_set = _provider(
        QueueTransport([_response([citation, citation])])
    ).discover(DiscoverySearchRequest(medical_term="フェリチン"))

    assert candidate_set.raw_source_count == 2
    assert candidate_set.candidate_count == 1
    assert candidate_set.duplicate_count == 1


def test_source_count_is_bounded() -> None:
    candidate_set = _provider(
        QueueTransport(
            [
                _response(
                    [
                        _citation("https://example.org/one", "One"),
                        _citation("https://example.org/two", "Two"),
                    ]
                )
            ]
        ),
        max_sources=1,
    ).discover(DiscoverySearchRequest(medical_term="フェリチン"))

    assert candidate_set.raw_source_count == 1
    assert candidate_set.candidate_count == 1


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
        ([_response([])], GroundedSearchErrorCode.NO_GROUNDING_SOURCE, 1),
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
        _provider(transport).discover(
            DiscoverySearchRequest(medical_term="フェリチン")
        )

    assert captured.value.code == expected_code
    assert len(transport.calls) == expected_calls
    assert captured.value.attempt_count == expected_calls


def test_missing_api_key_fails_before_transport() -> None:
    transport = QueueTransport([])

    with raises(GeminiGroundedSearchError) as captured:
        _provider(transport, api_key="").discover(
            DiscoverySearchRequest(medical_term="フェリチン")
        )

    assert captured.value.code == GroundedSearchErrorCode.MISSING_API_KEY
    assert transport.calls == []


def test_discovery_api_does_not_create_evidence_draft_or_registry_data() -> None:
    provider = _provider(
        QueueTransport(
            [
                _response(
                    [
                        _citation(
                            "https://www.jamt.or.jp/ferritin",
                            "フェリチン探索候補",
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
        "/api/discovery/gemini/previews",
        json={"theme": "フェリチン"},
    )

    assert response.status_code == 200
    payload = response.json()
    preview = payload["preview"]
    assert "discovery_candidate_set" in preview
    assert "evidence_bundle" not in preview
    assert "policy_decisions" not in preview
    assert payload["formal_evidence_acquired"] is False
    assert payload["evidence_bundle_generated"] is False
    assert payload["knowledge_draft_generated"] is False
    assert payload["registry_mutated"] is False
    assert payload["promotion_performed"] is False
    assert payload["approval_performed"] is False
    assert GENERATED_ANSWER not in response.text
    assert client.get("/api/registry").json() == registry_before
    assert client.get("/api/authoring/drafts").json() == drafts_before


def test_phase_526_http_routes_remain_as_discovery_compatibility_aliases() -> None:
    provider = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    )
    client = _client(provider)

    status = client.get("/api/evidence-search/gemini")
    preview = client.post(
        "/api/evidence-search/gemini/previews",
        json={"theme": "フェリチン"},
    )

    assert status.status_code == 200
    assert status.json()["legacy_route"] is True
    assert status.json()["migrated_to"] == "/api/discovery/gemini"
    assert preview.status_code == 200
    assert preview.headers["x-bluprnt-migration"] == "discovery-candidate-set-1.0"
    assert preview.headers["deprecation"] == "true"
    assert '"evidence_bundle":' not in preview.text


def test_audit_contains_metadata_only_and_no_secret_or_answer() -> None:
    provider = _provider(
        QueueTransport(
            [_response([_citation("https://example.org/source", "Source")])]
        )
    )
    client = _client(provider)

    client.post("/api/discovery/gemini/previews", json={"theme": "フェリチン"})
    audit = client.get("/api/discovery/gemini/audit").json()

    assert audit["formal_evidence_stored"] is False
    assert audit["medical_body_stored"] is False
    assert audit["http_headers_stored"] is False
    assert audit["events"][0]["evidence_stored"] is False
    assert GENERATED_ANSWER not in str(audit)
    assert "test-secret-key" not in str(audit)


def test_workbench_uses_discovery_words_and_hides_formal_evidence_fields() -> None:
    client = _client(_provider(QueueTransport([])))

    page = client.get("/").text
    script = client.get("/static/app.js").text
    status = client.get("/api/discovery/gemini").json()

    assert "Discovery Results" in page
    assert "正式Evidenceではありません" in page
    assert "探索候補を検索（Gemini）" in page
    assert "正式Evidence取得" in script
    assert "Evidence A / B / C" not in page
    assert "Grounding Citations Only" not in page
    assert status["output_contract"] == "discovery_candidate_set_1.0"
    assert status["evidence_bundle_generation_enabled"] is False
    assert status["claim_generation_enabled"] is False
    assert status["formal_evidence_provider_available"] is True
    assert status["formal_evidence_providers"] == [
        provider.value for provider in FormalEvidenceProviderType
    ]
