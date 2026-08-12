"""Phase 5.28 Evidence-grounded Claim Builder MVP tests."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pytest import mark, raises

from knowledge_workbench.claim_candidate_models import (
    ClaimAdapterResult,
    ClaimAdapterUsage,
    ClaimCandidate,
    ClaimCandidateType,
    ClaimDuplicateAssessment,
    ClaimDuplicateClassification,
    ClaimGenerationErrorCode,
    ClaimGenerationRequest,
    ClaimSourceLocator,
    ClaimSupportAssessment,
    ClaimSupportLevel,
    ClaimSupportScope,
    ClaimSupportScopeType,
    FormalEvidenceClaimInput,
    FormalEvidenceSelectionSet,
    GeneratedClaimDraft,
    SourceLocatorType,
    StructuredClaimCandidateResponse,
    candidate_fingerprint,
    formal_selection_set_id,
)
from knowledge_workbench.claim_candidate_service import ClaimCandidateValidator
from knowledge_workbench.claim_generation_interfaces import (
    ClaimGenerationAdapterError,
)
from knowledge_workbench.claim_prompt_builder import (
    EvidenceGroundedClaimPromptBuilder,
)
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.providers.gemini_claim_adapter import (
    GeminiClaimAdapterConfig,
    GeminiClaimGenerationAdapter,
    GeminiClaimHttpResponse,
    GeminiClaimTransportNetworkError,
    GeminiClaimTransportTimeout,
)
from knowledge_workbench.providers.pubmed_provider import (
    PubMedEvidenceProvider,
    PubMedEvidenceProviderConfig,
    PubMedHttpResponse,
)
from knowledge_workbench.pubmed_models import PubMedRateLimitMode


class NoWaitLimiter:
    mode = PubMedRateLimitMode.PUBLIC

    def wait(self) -> None:
        return None


class PubMedQueueTransport:
    def __init__(self, outcomes: Sequence[PubMedHttpResponse]) -> None:
        self.outcomes = list(outcomes)

    def get(
        self,
        *,
        url: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> PubMedHttpResponse:
        del url, params, timeout_seconds
        return self.outcomes.pop(0)


class StubClaimAdapter:
    provider_name = "stub_llm"
    provider_version = "1.0"
    model = "stub-model"

    def __init__(self, *, support_level: ClaimSupportLevel = ClaimSupportLevel.DIRECT) -> None:
        self.support_level = support_level
        self.requests: list[ClaimGenerationRequest] = []

    def generate(self, request: ClaimGenerationRequest) -> ClaimAdapterResult:
        self.requests.append(request)
        evidence = request.evidence_selection.evidence[0]
        generated = _generated_claim(evidence, support_level=self.support_level)
        return ClaimAdapterResult(
            provider=self.provider_name,
            model=self.model,
            generator_id="evidence_grounded_claim_builder",
            generator_version="1.0",
            response=StructuredClaimCandidateResponse(candidates=(generated,)),
            usage=ClaimAdapterUsage(
                prompt_tokens=100,
                completion_tokens=40,
                total_tokens=140,
            ),
            duration_ms=20,
            retry_count=0,
        )


class DuplicateClaimAdapter(StubClaimAdapter):
    def generate(self, request: ClaimGenerationRequest) -> ClaimAdapterResult:
        result = super().generate(request)
        generated = result.response.candidates[0]
        return result.model_copy(
            update={
                "response": StructuredClaimCandidateResponse(
                    candidates=(generated, generated)
                )
            }
        )


class GeminiQueueTransport:
    def __init__(
        self,
        outcomes: Sequence[
            GeminiClaimHttpResponse
            | GeminiClaimTransportTimeout
            | GeminiClaimTransportNetworkError
        ],
    ) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GeminiClaimHttpResponse:
        del endpoint, api_key, timeout_seconds
        self.calls.append(body)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _pubmed_response(value: str) -> PubMedHttpResponse:
    return PubMedHttpResponse(status_code=200, content=value.encode())


def _pubmed_provider() -> PubMedEvidenceProvider:
    esearch = _pubmed_response('{"esearchresult":{"idlist":["12345678"]}}')
    efetch = _pubmed_response(
        """
        <PubmedArticleSet><PubmedArticle><MedlineCitation>
          <PMID>12345678</PMID><Article>
            <ArticleTitle>Ferritin and iron stores</ArticleTitle>
            <Abstract><AbstractText Label="BACKGROUND">
              Ferritin is associated with iron stores.
            </AbstractText></Abstract>
            <AuthorList><Author><LastName>Smith</LastName>
              <ForeName>Jane</ForeName></Author></AuthorList>
            <Journal><Title>Clinical Laboratory</Title><JournalIssue>
              <PubDate><Year>2025</Year></PubDate>
            </JournalIssue></Journal>
            <PublicationTypeList>
              <PublicationType>Journal Article</PublicationType>
            </PublicationTypeList>
            <Language>eng</Language>
          </Article></MedlineCitation><PubmedData><ArticleIdList>
            <ArticleId IdType="pubmed">12345678</ArticleId>
            <ArticleId IdType="doi">10.1000/ferritin</ArticleId>
          </ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>
        """
    )
    return PubMedEvidenceProvider(
        PubMedEvidenceProviderConfig(
            tool="bluprnt_test",
            email="owner@example.test",
            timeout_seconds=2,
            retry_limit=0,
            max_records=1,
        ),
        transport=PubMedQueueTransport([esearch, efetch]),
        limiter=NoWaitLimiter(),
    )


def _client(adapter: StubClaimAdapter) -> TestClient:
    return TestClient(
        create_app(
            provider=FixtureKnowledgeProvider(),
            pubmed_evidence_provider=_pubmed_provider(),
            claim_generation_adapter=adapter,
        )
    )


def _select_formal_evidence(client: TestClient) -> tuple[str, str]:
    preview_response = client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "フェリチン", "max_records": 1},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["preview"]
    bundle = preview["evidence_bundle"]
    evidence_id = bundle["evidence"][0]["evidence"]["evidence_id"]
    selection = client.post(
        "/api/formal-evidence/pubmed/selections",
        json={
            "bundle_id": bundle["bundle_id"],
            "evidence_id": evidence_id,
            "decision": "include",
            "operator": "product_owner",
        },
    )
    assert selection.status_code == 200
    return bundle["bundle_id"], evidence_id


def _formal_evidence() -> FormalEvidenceClaimInput:
    return FormalEvidenceClaimInput(
        evidence_id="evd_pubmed_12345678",
        title="Ferritin and iron stores",
        abstract_or_snippet="Ferritin is associated with iron stores.",
        citation="Smith J. Ferritin and iron stores. 2025.",
        pmid="12345678",
        doi="10.1000/ferritin",
        provider_names=("pubmed",),
    )


def _selection() -> FormalEvidenceSelectionSet:
    evidence = _formal_evidence()
    bundle_fingerprint = "a" * 64
    bundle_id = "evb_pubmed_ferritin"
    return FormalEvidenceSelectionSet(
        selection_set_id=formal_selection_set_id(
            "フェリチン",
            bundle_id,
            bundle_fingerprint,
            [evidence.evidence_id],
        ),
        knowledge_term="フェリチン",
        evidence_bundle_id=bundle_id,
        evidence_bundle_fingerprint=bundle_fingerprint,
        evidence=(evidence,),
    )


def _support_parts(
    level: ClaimSupportLevel,
) -> tuple[ClaimSupportScope, ClaimSupportAssessment]:
    scope_type = {
        ClaimSupportLevel.DIRECT: ClaimSupportScopeType.FULL_CLAIM,
        ClaimSupportLevel.PARTIAL: ClaimSupportScopeType.CLAIM_PART,
        ClaimSupportLevel.INDIRECT: ClaimSupportScopeType.CONTEXT_ONLY,
        ClaimSupportLevel.UNSUPPORTED: ClaimSupportScopeType.NO_SUPPORT,
        ClaimSupportLevel.CONFLICTING: ClaimSupportScopeType.CONFLICTING_EVIDENCE,
    }[level]
    return (
        ClaimSupportScope(
            scope_type=scope_type,
            explanation="EvidenceとClaimの支持範囲を保守的に評価した。",
        ),
        ClaimSupportAssessment(
            support_level=level,
            assessed_evidence_ids=("evd_pubmed_12345678",),
            rationale="Abstractの短い抜粋に基づく評価。",
        ),
    )


def _generated_claim(
    evidence: FormalEvidenceClaimInput,
    *,
    support_level: ClaimSupportLevel = ClaimSupportLevel.DIRECT,
) -> GeneratedClaimDraft:
    scope, assessment = _support_parts(support_level)
    assessment = assessment.model_copy(
        update={"assessed_evidence_ids": (evidence.evidence_id,)}
    )
    return GeneratedClaimDraft(
        claim_text="フェリチンは鉄貯蔵と関連する。",
        claim_type=ClaimCandidateType.FACT,
        supporting_evidence_ids=(evidence.evidence_id,),
        source_locators=(
            ClaimSourceLocator(
                evidence_id=evidence.evidence_id,
                locator_type=SourceLocatorType.ABSTRACT_SECTION,
                locator_value="Abstract: BACKGROUND",
                quote_excerpt="Ferritin is associated with iron stores.",
                pmid=evidence.pmid,
                doi=evidence.doi,
            ),
        ),
        support_level=support_level,
        support_scope=scope,
        support_assessment=assessment,
        confidence=0.91,
    )


def _candidate(
    *,
    evidence_id: str = "evd_pubmed_12345678",
    quote: str = "Ferritin is associated with iron stores.",
) -> ClaimCandidate:
    evidence = _formal_evidence().model_copy(update={"evidence_id": evidence_id})
    generated = _generated_claim(evidence).model_copy(
        update={
            "source_locators": (
                ClaimSourceLocator(
                    evidence_id=evidence_id,
                    locator_type=SourceLocatorType.ABSTRACT,
                    locator_value="Abstract",
                    quote_excerpt=quote,
                    pmid="12345678",
                    doi="10.1000/ferritin",
                ),
            )
        }
    )
    provisional = ClaimCandidate.model_construct(
        candidate_claim_id="ccl_1234567890abcdef1234",
        knowledge_term="フェリチン",
        claim_text=generated.claim_text,
        claim_type=generated.claim_type,
        supporting_evidence_ids=generated.supporting_evidence_ids,
        source_locators=generated.source_locators,
        support_level=generated.support_level,
        support_scope=generated.support_scope,
        support_assessment=generated.support_assessment,
        confidence=generated.confidence,
        generator_id="evidence_grounded_claim_builder",
        generator_version="1.0",
        generated_at=datetime.now(UTC),
        candidate_fingerprint="0" * 64,
        duplicate_assessment=ClaimDuplicateAssessment(
            classification=ClaimDuplicateClassification.DISTINCT
        ),
        candidate_contract_version="1.0",
        ai_generated_candidate=True,
        formal_claim_id_issued=False,
    )
    return ClaimCandidate.model_validate(
        provisional.model_copy(
            update={"candidate_fingerprint": candidate_fingerprint(provisional)}
        )
    )


def test_prompt_builder_is_provider_neutral_and_uses_formal_evidence_only() -> None:
    request = ClaimGenerationRequest(evidence_selection=_selection(), max_candidates=5)

    prompt = EvidenceGroundedClaimPromptBuilder().build(request)

    assert prompt.selected_evidence_ids == ("evd_pubmed_12345678",)
    assert "Do not use memory" in prompt.prompt_text
    assert "structured JSON only" in prompt.prompt_text
    assert "Gemini" not in prompt.prompt_text
    assert "OpenAI" not in prompt.prompt_text
    assert "Claude" not in prompt.prompt_text


def test_candidate_contract_does_not_issue_formal_claim_id() -> None:
    candidate = _candidate()

    assert candidate.formal_claim_id_issued is False
    assert not hasattr(candidate, "claim_id")
    assert candidate.support_assessment.ai_confidence_is_separate is True
    assert candidate.support_assessment.medical_review_performed is False


def test_validator_rejects_hallucinated_evidence_id() -> None:
    candidate = _candidate(evidence_id="evd_pubmed_99999999")

    report = ClaimCandidateValidator().validate(
        (candidate,),
        accepted_evidence={
            "evd_pubmed_12345678": "Ferritin is associated with iron stores."
        },
        evidence_metadata={
            "evd_pubmed_12345678": ("12345678", "10.1000/ferritin")
        },
    )

    assert report.validation_passed is False
    assert any(item.code == "evidence_id_hallucination" for item in report.issues)


def test_validator_rejects_locator_mismatch() -> None:
    candidate = _candidate(quote="This text is not present in the abstract.")

    report = ClaimCandidateValidator().validate(
        (candidate,),
        accepted_evidence={
            "evd_pubmed_12345678": "Ferritin is associated with iron stores."
        },
        evidence_metadata={
            "evd_pubmed_12345678": ("12345678", "10.1000/ferritin")
        },
    )

    assert report.validation_passed is False
    assert report.locators_valid is False
    assert any(item.code == "locator_mismatch" for item in report.issues)


def test_claim_generation_requires_human_accepted_formal_evidence() -> None:
    client = _client(StubClaimAdapter())
    preview = client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "フェリチン", "max_records": 1},
    ).json()["preview"]

    response = client.post(
        "/api/claim-candidates/previews",
        json={
            "knowledge_term": "フェリチン",
            "evidence_bundle_id": preview["evidence_bundle"]["bundle_id"],
        },
    )

    assert response.status_code == 422
    assert "採用されたFormal Evidenceがありません" in response.text
    assert response.json()["registry_changed"] is False


def test_api_generates_traceable_candidate_without_registry_mutation() -> None:
    adapter = StubClaimAdapter()
    client = _client(adapter)
    registry_before = client.get("/api/registry").json()
    bundle_id, evidence_id = _select_formal_evidence(client)

    response = client.post(
        "/api/claim-candidates/previews",
        json={"knowledge_term": "フェリチン", "evidence_bundle_id": bundle_id},
    )

    assert response.status_code == 200
    payload = response.json()
    candidate_set = payload["candidate_set"]
    candidate = candidate_set["candidates"][0]
    assert candidate["supporting_evidence_ids"] == [evidence_id]
    assert candidate["source_locators"][0]["pmid"] == "12345678"
    assert candidate["source_locators"][0]["doi"] == "10.1000/ferritin"
    assert candidate["support_level"] == "direct"
    assert candidate_set["validation"]["validation_passed"] is True
    assert candidate_set["validation"]["direct_count"] == 1
    assert payload["medical_approval"] is False
    assert client.get("/api/registry").json() == registry_before
    assert adapter.requests[0].outside_knowledge_allowed is False
    assert adapter.requests[0].discovery_input_allowed is False


def test_only_human_accepted_direct_candidate_enters_authoring_draft() -> None:
    client = _client(StubClaimAdapter())
    bundle_id, _ = _select_formal_evidence(client)
    candidate_set = client.post(
        "/api/claim-candidates/previews",
        json={"knowledge_term": "フェリチン", "evidence_bundle_id": bundle_id},
    ).json()["candidate_set"]
    candidate_id = candidate_set["candidates"][0]["candidate_claim_id"]

    review = client.post(
        "/api/claim-candidates/reviews",
        json={
            "candidate_set_id": candidate_set["candidate_set_id"],
            "candidate_claim_id": candidate_id,
            "decision": "accepted",
            "operator": "product_owner",
            "review_duration_ms": 1200,
        },
    )
    result = client.post(
        "/api/claim-candidates/authoring-drafts",
        json={
            "candidate_set_id": candidate_set["candidate_set_id"],
            "category": "laboratory_test_item",
            "operator": "product_owner",
        },
    )

    assert review.status_code == 200
    assert review.json()["review"]["original_claim_text"]
    assert review.json()["kpi"]["human_revision_rate"] == 0
    assert review.json()["kpi"]["human_exclusion_rate"] == 0
    assert review.json()["kpi"]["claim_review_duration_ms"] == 1200
    assert result.status_code == 200
    draft = result.json()["result"]["draft"]
    assert len(draft["claims"]) == 1
    assert len(draft["references"]) == 1
    assert draft["references"][0]["pmid"] == "12345678"
    assert result.json()["promotion_performed"] is False
    assert result.json()["registry_changed"] is False


def test_unsupported_candidate_is_visible_but_cannot_enter_draft() -> None:
    client = _client(StubClaimAdapter(support_level=ClaimSupportLevel.UNSUPPORTED))
    bundle_id, _ = _select_formal_evidence(client)
    candidate_set = client.post(
        "/api/claim-candidates/previews",
        json={"knowledge_term": "フェリチン", "evidence_bundle_id": bundle_id},
    ).json()["candidate_set"]
    candidate_id = candidate_set["candidates"][0]["candidate_claim_id"]
    client.post(
        "/api/claim-candidates/reviews",
        json={
            "candidate_set_id": candidate_set["candidate_set_id"],
            "candidate_claim_id": candidate_id,
            "decision": "accepted",
            "operator": "product_owner",
        },
    )

    result = client.post(
        "/api/claim-candidates/authoring-drafts",
        json={
            "candidate_set_id": candidate_set["candidate_set_id"],
            "category": "laboratory_test_item",
            "operator": "product_owner",
        },
    )

    assert candidate_set["validation"]["unsupported_count"] == 1
    assert candidate_set["validation"]["validation_passed"] is True
    assert result.status_code == 422
    assert "Direct" in result.text


def test_generation_audit_is_metadata_only_and_secret_free() -> None:
    client = _client(StubClaimAdapter())
    bundle_id, _ = _select_formal_evidence(client)
    client.post(
        "/api/claim-candidates/previews",
        json={"knowledge_term": "フェリチン", "evidence_bundle_id": bundle_id},
    )

    audit = client.get("/api/claim-candidates/audit").json()

    assert audit["medical_body_stored"] is False
    assert audit["api_key_stored"] is False
    assert audit["events"][0]["candidate_count"] == 1
    assert "フェリチンは鉄貯蔵と関連する" not in str(audit)
    assert "Ferritin is associated with iron stores" not in str(audit)


def test_duplicate_candidates_are_reported_without_automatic_merge() -> None:
    client = _client(DuplicateClaimAdapter())
    bundle_id, _ = _select_formal_evidence(client)

    candidate_set = client.post(
        "/api/claim-candidates/previews",
        json={"knowledge_term": "フェリチン", "evidence_bundle_id": bundle_id},
    ).json()["candidate_set"]

    assert len(candidate_set["candidates"]) == 2
    assert all(
        item["duplicate_assessment"]["classification"] == "exact_duplicate"
        for item in candidate_set["candidates"]
    )
    assert all(
        item["duplicate_assessment"]["automatic_merge_performed"] is False
        for item in candidate_set["candidates"]
    )


def test_gemini_payload_is_adapter_local_and_store_false() -> None:
    adapter = GeminiClaimGenerationAdapter(
        GeminiClaimAdapterConfig(api_key="secret", model="gemini-test"),
        transport=GeminiQueueTransport([]),
    )

    prompt, body = adapter.build_provider_payload(
        ClaimGenerationRequest(evidence_selection=_selection())
    )

    assert body["store"] is False
    assert body["model"] == "gemini-test"
    assert body["response_format"]
    assert "Gemini" not in prompt.prompt_text
    assert "secret" not in json.dumps(body)


def test_gemini_structured_response_maps_to_provider_neutral_result() -> None:
    generated = _generated_claim(_formal_evidence())
    provider_response = {
        "id": "interaction_test_001",
        "output_text": StructuredClaimCandidateResponse(
            candidates=(generated,)
        ).model_dump_json(),
        "usage": {
            "total_input_tokens": 120,
            "total_output_tokens": 50,
            "total_tokens": 170,
        },
    }
    transport = GeminiQueueTransport(
        [
            GeminiClaimHttpResponse(
                status_code=200,
                content=json.dumps(provider_response).encode(),
            )
        ]
    )
    adapter = GeminiClaimGenerationAdapter(
        GeminiClaimAdapterConfig(api_key="secret", model="gemini-test"),
        transport=transport,
    )

    result = adapter.generate(ClaimGenerationRequest(evidence_selection=_selection()))

    assert result.provider == "gemini"
    assert result.provider_request_id == "interaction_test_001"
    assert result.response.candidates[0].support_level is ClaimSupportLevel.DIRECT
    assert result.usage.total_tokens == 170
    assert result.provider_body_persisted is False
    assert transport.calls[0]["store"] is False


@mark.parametrize(
    ("outcomes", "expected"),
    [
        (
            [GeminiClaimTransportTimeout(), GeminiClaimTransportTimeout()],
            ClaimGenerationErrorCode.TIMEOUT,
        ),
        (
            [
                GeminiClaimTransportNetworkError(),
                GeminiClaimTransportNetworkError(),
            ],
            ClaimGenerationErrorCode.NETWORK,
        ),
        (
            [
                GeminiClaimHttpResponse(status_code=429, content=b"{}"),
                GeminiClaimHttpResponse(status_code=429, content=b"{}"),
            ],
            ClaimGenerationErrorCode.RATE_LIMIT,
        ),
        (
            [
                GeminiClaimHttpResponse(status_code=500, content=b"{}"),
                GeminiClaimHttpResponse(status_code=500, content=b"{}"),
            ],
            ClaimGenerationErrorCode.PROVIDER_SERVER,
        ),
        (
            [GeminiClaimHttpResponse(status_code=401, content=b"{}")],
            ClaimGenerationErrorCode.AUTHENTICATION,
        ),
        (
            [GeminiClaimHttpResponse(status_code=200, content=b"not-json")],
            ClaimGenerationErrorCode.INVALID_RESPONSE,
        ),
    ],
)
def test_gemini_error_mapping_is_provider_local(
    outcomes: list[
        GeminiClaimHttpResponse
        | GeminiClaimTransportTimeout
        | GeminiClaimTransportNetworkError
    ],
    expected: ClaimGenerationErrorCode,
) -> None:
    adapter = GeminiClaimGenerationAdapter(
        GeminiClaimAdapterConfig(api_key="secret", retry_limit=1),
        transport=GeminiQueueTransport(outcomes),
    )

    with raises(ClaimGenerationAdapterError) as captured:
        adapter.generate(ClaimGenerationRequest(evidence_selection=_selection()))

    assert captured.value.code is expected


def test_workbench_exposes_claim_support_and_human_review_without_approval() -> None:
    client = _client(StubClaimAdapter())

    page = client.get("/").text
    script = client.get("/static/app.js").text
    status = client.get("/api/claim-candidates").json()

    assert "Claim Candidate &amp; Support Assessment" in page
    assert "AI Generated Candidate：Yes" in page
    assert "Medical Approval：No" in page
    assert "選択EvidenceからClaim候補生成" in page
    assert "accepted" in script
    assert "revised" in script
    assert "excluded" in script
    assert "hold" in script
    assert status["formal_evidence_only"] is True
    assert status["discovery_input_allowed"] is False
    assert status["medical_approval"] is False
