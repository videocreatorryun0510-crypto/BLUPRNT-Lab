"""Phase 5.27 PubMed E-utilities Formal Evidence Provider MVP tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import HttpUrl
from pytest import mark, raises

from knowledge_workbench.discovery_boundary import (
    DiscoveryBoundaryTarget,
    DiscoveryBoundaryValidationError,
    reject_discovery_asset,
)
from knowledge_workbench.discovery_interfaces import (
    FormalEvidenceAcquisitionRequest,
    FormalEvidenceProvider,
    FormalEvidenceProviderType,
)
from knowledge_workbench.discovery_models import DiscoveryCandidate
from knowledge_workbench.evidence_intelligence import stable_evidence_id
from knowledge_workbench.knowledge_pipeline_models import EvidenceSearchRequest
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.providers.pubmed_provider import (
    NcbiRateLimiter,
    PubMedEvidenceError,
    PubMedEvidenceProvider,
    PubMedEvidenceProviderConfig,
    PubMedHttpResponse,
    PubMedTransportNetworkError,
    PubMedTransportTimeout,
)
from knowledge_workbench.pubmed_models import (
    PubMedErrorCode,
    PubMedRateLimitMode,
)


class NoWaitLimiter:
    def __init__(self, mode: PubMedRateLimitMode) -> None:
        self.mode = mode
        self.calls = 0

    def wait(self) -> None:
        self.calls += 1


class QueueTransport:
    def __init__(
        self,
        outcomes: Sequence[
            PubMedHttpResponse
            | PubMedTransportTimeout
            | PubMedTransportNetworkError
        ],
    ) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(
        self,
        *,
        url: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> PubMedHttpResponse:
        del timeout_seconds
        self.calls.append((url, dict(params)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _json_response(value: str, status_code: int = 200) -> PubMedHttpResponse:
    return PubMedHttpResponse(status_code=status_code, content=value.encode())


def _esearch(*pmids: str) -> PubMedHttpResponse:
    values = ",".join(f'"{item}"' for item in pmids)
    return _json_response(f'{{"esearchresult":{{"idlist":[{values}]}}}}')


def _article(
    pmid: str,
    *,
    title: str = "Ferritin in iron deficiency anemia",
    journal: str = "Clinical laboratory medicine",
    abstract: str | None = "Ferritin is associated with iron stores.",
    doi: str | None = "10.1000/ferritin",
    publication_types: tuple[str, ...] = ("Journal Article",),
    mesh: str | None = "Ferritins",
) -> str:
    abstract_xml = (
        f"<Abstract><AbstractText Label=\"BACKGROUND\">{abstract}</AbstractText></Abstract>"
        if abstract is not None
        else ""
    )
    doi_xml = (
        f'<ArticleId IdType="doi">{doi}</ArticleId>' if doi is not None else ""
    )
    types_xml = "".join(
        f"<PublicationType>{item}</PublicationType>" for item in publication_types
    )
    mesh_xml = (
        f"<MeshHeadingList><MeshHeading><DescriptorName>{mesh}</DescriptorName>"
        "<QualifierName>analysis</QualifierName></MeshHeading></MeshHeadingList>"
        if mesh is not None
        else ""
    )
    return f"""
    <PubmedArticle>
      <MedlineCitation>
        <PMID>{pmid}</PMID>
        <Article>
          <ArticleTitle>{title}</ArticleTitle>
          <AbstractText>This field is ignored.</AbstractText>
          {abstract_xml}
          <AuthorList>
            <Author><LastName>Smith</LastName><ForeName>Jane</ForeName></Author>
            <Author><CollectiveName>Ferritin Study Group</CollectiveName></Author>
          </AuthorList>
          <Journal>
            <Title>{journal}</Title>
            <JournalIssue><PubDate><Year>2025</Year><Month>Aug</Month><Day>12</Day></PubDate></JournalIssue>
          </Journal>
          <PublicationTypeList>{types_xml}</PublicationTypeList>
          <Language>eng</Language>
        </Article>
        {mesh_xml}
      </MedlineCitation>
      <PubmedData><ArticleIdList>
        <ArticleId IdType="pubmed">{pmid}</ArticleId>{doi_xml}
      </ArticleIdList></PubmedData>
    </PubmedArticle>
    """


def _efetch(*articles: str) -> PubMedHttpResponse:
    return PubMedHttpResponse(
        status_code=200,
        content=("<PubmedArticleSet>" + "".join(articles) + "</PubmedArticleSet>").encode(),
    )


def _provider(
    transport: QueueTransport,
    *,
    api_key: str = "",
    retry_limit: int = 1,
    max_records: int = 20,
) -> PubMedEvidenceProvider:
    mode = (
        PubMedRateLimitMode.API_KEY
        if api_key
        else PubMedRateLimitMode.PUBLIC
    )
    return PubMedEvidenceProvider(
        PubMedEvidenceProviderConfig(
            api_key=api_key,
            tool="bluprnt_test",
            email="owner@example.test",
            timeout_seconds=2,
            retry_limit=retry_limit,
            max_records=max_records,
        ),
        transport=transport,
        limiter=NoWaitLimiter(mode),
    )


def _client(provider: PubMedEvidenceProvider) -> TestClient:
    return TestClient(
        create_app(
            provider=FixtureKnowledgeProvider(),
            pubmed_evidence_provider=provider,
        )
    )


def _candidate(
    *,
    url: str = "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    title: str = "Ferritin paper",
) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        candidate_id="dsc_1234567890abcdef1234",
        provider="gemini_google_search",
        provider_version="1.0",
        search_query="フェリチン",
        title=title,
        url=HttpUrl(url),
        publisher="pubmed.ncbi.nlm.nih.gov",
        domain="pubmed.ncbi.nlm.nih.gov",
        retrieved_at=datetime.now(UTC),
        discovery_fingerprint="a" * 64,
    )


def test_direct_search_uses_official_esearch_then_efetch_and_maps_record() -> None:
    transport = QueueTransport([_esearch("12345678"), _efetch(_article("12345678"))])
    provider = _provider(transport)

    result = provider.search_with_report(
        EvidenceSearchRequest(theme="Ferritin"),
        aliases=("Iron storage protein",),
    )

    assert isinstance(provider, FormalEvidenceProvider)
    assert len(transport.calls) == 2
    assert transport.calls[0][0].endswith("/esearch.fcgi")
    assert transport.calls[1][0].endswith("/efetch.fcgi")
    assert transport.calls[0][1]["db"] == "pubmed"
    assert transport.calls[0][1]["retmax"] == "20"
    assert transport.calls[0][1]["tool"] == "bluprnt_test"
    assert transport.calls[0][1]["email"] == "owner@example.test"
    assert "api_key" not in transport.calls[0][1]
    record = result.records[0]
    assert record.pmid == "12345678"
    assert record.authors == ("Smith Jane", "Ferritin Study Group")
    assert record.publication_date is not None
    assert record.publication_date.isoformat() == "2025-08-12"
    assert record.abstract == "BACKGROUND: Ferritin is associated with iron stores."
    assert record.doi == "10.1000/ferritin"
    assert record.publication_types == ("Journal Article",)
    assert record.mesh_terms == ("Ferritins / analysis",)
    assert result.execution.request_count == 2
    assert result.execution.rate_limit_mode is PubMedRateLimitMode.PUBLIC


def test_api_key_is_optional_and_only_sent_to_ncbi() -> None:
    transport = QueueTransport([_esearch("1"), _efetch(_article("1"))])
    provider = _provider(transport, api_key="private-ncbi-key")

    result = provider.search_with_report(EvidenceSearchRequest(theme="Ferritin"))

    assert result.execution.api_key_used is True
    assert result.execution.rate_limit_mode is PubMedRateLimitMode.API_KEY
    assert all(params["api_key"] == "private-ncbi-key" for _, params in transport.calls)
    assert "private-ncbi-key" not in result.raw.model_dump_json()
    assert "private-ncbi-key" not in result.execution.model_dump_json()


def test_public_and_api_key_rate_limit_intervals_are_safe() -> None:
    public = NcbiRateLimiter(api_key_configured=False)
    keyed = NcbiRateLimiter(api_key_configured=True)

    assert public.mode is PubMedRateLimitMode.PUBLIC
    assert public.minimum_interval_seconds >= 1 / 3
    assert keyed.mode is PubMedRateLimitMode.API_KEY
    assert keyed.minimum_interval_seconds >= 0.1


def test_duplicate_pmids_are_removed_before_efetch() -> None:
    transport = QueueTransport(
        [
            _esearch("1", "1", "2"),
            _efetch(_article("1"), _article("2", doi="10.2/two")),
        ]
    )
    provider = _provider(transport)

    result = provider.search_with_report(EvidenceSearchRequest(theme="Ferritin"))

    assert result.execution.requested_pmids == ("1", "2")
    assert transport.calls[1][1]["id"] == "1,2"


def test_duplicate_doi_records_are_merged_in_evidence_bundle() -> None:
    shared_doi = "10.1000/shared-ferritin"
    transport = QueueTransport(
        [
            _esearch("11", "12"),
            _efetch(
                _article("11", doi=shared_doi),
                _article("12", title="Ferritin duplicate record", doi=shared_doi),
            ),
        ]
    )
    client = _client(_provider(transport))

    response = client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "Ferritin", "max_records": 2},
    )

    assert response.status_code == 200
    bundle = response.json()["preview"]["evidence_bundle"]
    assert bundle["input_record_count"] == 2
    assert bundle["accepted_evidence_count"] == 1
    assert bundle["excluded_evidence_count"] == 1
    assert "doi" in bundle["deduplication_decisions"][0]["reasons"]


@mark.parametrize(
    ("abstract", "doi"),
    [(None, "10.1/no-abstract"), ("Available", None)],
)
def test_abstract_and_doi_are_optional(
    abstract: str | None,
    doi: str | None,
) -> None:
    provider = _provider(
        QueueTransport([_esearch("3"), _efetch(_article("3", abstract=abstract, doi=doi))])
    )

    record = provider.search_with_report(EvidenceSearchRequest(theme="Test")).records[0]

    assert record.abstract == (f"BACKGROUND: {abstract}" if abstract else None)
    assert record.doi == doi


def test_multiple_publication_types_are_preserved() -> None:
    provider = _provider(
        QueueTransport(
            [
                _esearch("4"),
                _efetch(
                    _article(
                        "4",
                        publication_types=("Systematic Review", "Meta-Analysis"),
                    )
                ),
            ]
        )
    )

    record = provider.search_with_report(EvidenceSearchRequest(theme="Test")).records[0]

    assert record.publication_types == ("Systematic Review", "Meta-Analysis")


def test_partial_invalid_record_keeps_valid_record_and_reports_partial_success() -> None:
    invalid = "<PubmedArticle><MedlineCitation><PMID>9</PMID></MedlineCitation></PubmedArticle>"
    provider = _provider(
        QueueTransport([_esearch("8", "9"), _efetch(_article("8"), invalid)])
    )

    result = provider.search_with_report(EvidenceSearchRequest(theme="Test"))

    assert [item.pmid for item in result.records] == ["8"]
    assert result.execution.status.value == "partial_success"
    assert result.execution.invalid_record_pmids == ("9",)


@mark.parametrize(
    ("outcomes", "code"),
    [
        ([PubMedTransportTimeout(), PubMedTransportTimeout()], PubMedErrorCode.TIMEOUT),
        ([PubMedTransportNetworkError(), PubMedTransportNetworkError()], PubMedErrorCode.NETWORK),
        ([_json_response("{}", 429), _json_response("{}", 429)], PubMedErrorCode.RATE_LIMIT),
        ([_json_response("{}", 500), _json_response("{}", 500)], PubMedErrorCode.PROVIDER_SERVER),
        ([_json_response("not-json")], PubMedErrorCode.INVALID_JSON),
        ([_esearch("1"), _json_response("not-xml")], PubMedErrorCode.INVALID_XML),
        ([_esearch()], PubMedErrorCode.EMPTY_RESULT),
    ],
)
def test_error_handling(
    outcomes: list[PubMedHttpResponse | PubMedTransportTimeout | PubMedTransportNetworkError],
    code: PubMedErrorCode,
) -> None:
    provider = _provider(QueueTransport(outcomes))

    with raises(PubMedEvidenceError) as captured:
        provider.search_with_report(EvidenceSearchRequest(theme="Test"))

    assert captured.value.code is code


def test_api_key_error_is_distinct_and_not_retried() -> None:
    transport = QueueTransport([_json_response("invalid api key", 403)])
    provider = _provider(transport, api_key="private-ncbi-key")

    with raises(PubMedEvidenceError) as captured:
        provider.search_with_report(EvidenceSearchRequest(theme="Test"))

    assert captured.value.code is PubMedErrorCode.API_KEY
    assert len(transport.calls) == 1


def test_discovery_handoff_requeries_pubmed_by_pmid() -> None:
    transport = QueueTransport([_esearch("12345678"), _efetch(_article("12345678"))])
    provider = _provider(transport)
    candidate = _candidate()

    result = provider.acquire_with_report(
        FormalEvidenceAcquisitionRequest(
            candidate_id=candidate.candidate_id,
            source_url=candidate.url,
            selected_provider=FormalEvidenceProviderType.PUBMED,
            candidate_title=candidate.title,
            search_term=candidate.search_query,
        )
    )

    assert transport.calls[0][1]["term"] == "12345678[PMID]"
    assert result.records[0].pmid == "12345678"
    assert result.execution.mode.value == "discovery_handoff"


def test_discovery_handoff_not_found_does_not_promote_candidate() -> None:
    provider = _provider(QueueTransport([_esearch()]))

    with raises(PubMedEvidenceError) as captured:
        provider.acquire_with_report(
            FormalEvidenceAcquisitionRequest(
                candidate_id="dsc_1234567890abcdef1234",
                source_url="https://example.org/not-pubmed",
                selected_provider=FormalEvidenceProviderType.PUBMED,
                candidate_title="Not indexed in PubMed",
                search_term="ferritin",
            )
        )

    assert captured.value.code is PubMedErrorCode.EMPTY_RESULT


def test_discovery_candidate_still_cannot_be_converted_directly() -> None:
    candidate = _candidate()

    with raises(DiscoveryBoundaryValidationError):
        reject_discovery_asset(
            candidate,
            target=DiscoveryBoundaryTarget.EVIDENCE_BUNDLE,
        )


def test_normalized_evidence_id_prefers_pmid_and_bundle_generates_no_claim() -> None:
    transport = QueueTransport(
        [
            _esearch("5"),
            _efetch(_article("5", publication_types=("Guideline",))),
        ]
    )
    client = _client(_provider(transport))

    response = client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "Ferritin", "max_records": 20},
    )

    assert response.status_code == 200
    payload = response.json()
    preview = payload["preview"]
    evidence = preview["evidence_bundle"]["evidence"][0]["evidence"]
    assert evidence["evidence_id"] == stable_evidence_id(
        doi=None,
        pmid="5",
        url="https://pubmed.ncbi.nlm.nih.gov/5/",
        title="Ferritin in iron deficiency anemia",
        publisher="Clinical laboratory medicine",
        publication_date="2025-08-12",
    )
    assert evidence["evidence_level"] == "B"
    assert preview["formal_evidence"] is True
    assert payload["claim_generated"] is False
    assert payload["knowledge_draft_generated"] is False
    assert payload["registry_changed"] is False
    assert payload["promotion_performed"] is False
    assert payload["approval_performed"] is False
    assert "claim_build" not in response.text


def test_human_selection_is_saved_without_medical_review(tmp_path: Path) -> None:
    del tmp_path
    transport = QueueTransport([_esearch("6"), _efetch(_article("6"))])
    client = _client(_provider(transport))
    registry_before = client.get("/api/registry").json()
    preview = client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "Ferritin", "max_records": 1},
    ).json()["preview"]
    evidence_id = preview["evidence_bundle"]["evidence"][0]["evidence"]["evidence_id"]

    response = client.post(
        "/api/formal-evidence/pubmed/selections",
        json={
            "bundle_id": preview["evidence_bundle"]["bundle_id"],
            "evidence_id": evidence_id,
            "decision": "include",
            "operator": "product_owner",
            "comment": "Claim候補作成に使用予定",
        },
    )

    assert response.status_code == 200
    assert response.json()["selection"]["decision"] == "include"
    assert response.json()["medical_review_performed"] is False
    assert response.json()["claim_generated"] is False
    assert client.get("/api/registry").json() == registry_before
    audit = client.get("/api/formal-evidence/pubmed/selections").json()
    assert audit["selections"][0]["operator"] == "product_owner"


def test_search_audit_is_metadata_only_and_does_not_expose_secret() -> None:
    transport = QueueTransport(
        [
            _esearch("7"),
            _efetch(_article("7", abstract="SENSITIVE ABSTRACT")),
        ]
    )
    client = _client(_provider(transport, api_key="private-ncbi-key"))

    client.post(
        "/api/formal-evidence/pubmed/previews",
        json={"theme": "Ferritin", "max_records": 1},
    )
    audit = client.get("/api/formal-evidence/pubmed/audit").json()

    assert audit["medical_body_stored"] is False
    assert audit["secret_stored"] is False
    assert audit["events"][0]["api_key_used"] is True
    assert "private-ncbi-key" not in str(audit)
    assert "SENSITIVE ABSTRACT" not in str(audit)


def test_workbench_separates_discovery_from_formal_pubmed_evidence() -> None:
    client = _client(_provider(QueueTransport([])))

    page = client.get("/").text
    script = client.get("/static/app.js").text
    status = client.get("/api/formal-evidence/pubmed").json()

    assert "Gemini Discovery Search" in page
    assert "正式Evidenceではありません" in page
    assert "PubMed正式Evidence検索" in page
    assert "Formal Evidence：Yes" in page
    assert "Claim Generated：No" in page
    assert "PubMedで正式Evidence取得" in script
    assert status["official_api"] == "NCBI E-utilities"
    assert status["discovery_direct_conversion_allowed"] is False
    assert status["claim_generation_enabled"] is False
    assert status["registry_write_enabled"] is False
