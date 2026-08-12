"""NCBI E-utilities adapter for PubMed formal Evidence acquisition."""

from __future__ import annotations

import json
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import monotonic, sleep
from typing import Literal, NoReturn, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import HttpUrl

from knowledge_workbench.authoring_models import AuthoringCategory
from knowledge_workbench.discovery_interfaces import (
    FormalEvidenceAcquisitionRequest,
    FormalEvidenceProviderType,
)
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceLanguage,
    EvidenceSearchRequest,
    EvidenceSubject,
    RawEvidenceRecord,
    RawEvidenceSearchResult,
)
from knowledge_workbench.pubmed_models import (
    PubMedErrorCode,
    PubMedProviderExecution,
    PubMedRateLimitMode,
    PubMedRecord,
    PubMedSearchMode,
    PubMedSearchQuery,
    PubMedSearchStatus,
)


@dataclass(frozen=True)
class PubMedEvidenceProviderConfig:
    api_key: str = ""
    tool: str = "bluprnt_lab_medical_os"
    email: str = ""
    base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    timeout_seconds: float = 20.0
    retry_limit: int = 1
    max_records: int = 20

    def __post_init__(self) -> None:
        if not self.tool.strip():
            raise ValueError("NCBI_TOOL is required")
        if self.timeout_seconds <= 0:
            raise ValueError("NCBI timeout must be positive")
        if self.retry_limit not in (0, 1):
            raise ValueError("PubMed retry_limit must be 0 or 1")
        if not 1 <= self.max_records <= 30:
            raise ValueError("PubMed max_records must be between 1 and 30")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" or parsed.netloc != "eutils.ncbi.nlm.nih.gov":
            raise ValueError("PubMed base_url must use the official NCBI HTTPS host")


@dataclass(frozen=True)
class PubMedHttpResponse:
    status_code: int
    content: bytes


class PubMedTransportTimeout(RuntimeError):
    pass


class PubMedTransportNetworkError(RuntimeError):
    pass


class PubMedTransport(Protocol):
    def get(
        self,
        *,
        url: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> PubMedHttpResponse: ...


class HttpxPubMedTransport:
    def get(
        self,
        *,
        url: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> PubMedHttpResponse:
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as error:
            raise PubMedTransportTimeout from error
        except httpx.NetworkError as error:
            raise PubMedTransportNetworkError from error
        return PubMedHttpResponse(
            status_code=response.status_code,
            content=response.content,
        )


class PubMedRequestLimiter(Protocol):
    mode: PubMedRateLimitMode

    def wait(self) -> None: ...


class NcbiRateLimiter:
    """Process-local safety limiter below NCBI's public and API-key ceilings."""

    def __init__(
        self,
        *,
        api_key_configured: bool,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.mode = (
            PubMedRateLimitMode.API_KEY
            if api_key_configured
            else PubMedRateLimitMode.PUBLIC
        )
        self.minimum_interval_seconds = 0.11 if api_key_configured else 0.34
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request_at is not None:
                remaining = self.minimum_interval_seconds - (
                    now - self._last_request_at
                )
                if remaining > 0:
                    self._sleeper(remaining)
            self._last_request_at = self._clock()


class PubMedRecordCache(Protocol):
    """Replaceable derived cache; never an Evidence system of record."""

    def get_many(self, pmids: tuple[str, ...]) -> dict[str, PubMedRecord]: ...

    def put_many(self, records: tuple[PubMedRecord, ...]) -> None: ...


class NullPubMedRecordCache:
    def get_many(self, pmids: tuple[str, ...]) -> dict[str, PubMedRecord]:
        del pmids
        return {}

    def put_many(self, records: tuple[PubMedRecord, ...]) -> None:
        del records


class PubMedQueryBuilder:
    builder_version = "1.0"

    def direct(
        self,
        term: str,
        *,
        aliases: tuple[str, ...] = (),
    ) -> PubMedSearchQuery:
        normalized = _required_text(term, "medical term")
        safe_aliases = tuple(
            dict.fromkeys(
                _required_text(item, "alias")
                for item in aliases
                if item.strip() and item.strip() != normalized
            )
        )
        terms = (normalized, *safe_aliases)
        if len(terms) == 1:
            query = f'"{_escape_query(normalized)}"[Title/Abstract]'
            strategy: Literal["literal_term", "known_aliases"] = "literal_term"
        else:
            query = " OR ".join(
                f'"{_escape_query(item)}"[Title/Abstract]' for item in terms
            )
            strategy = "known_aliases"
        return PubMedSearchQuery(
            input_term=normalized,
            aliases=safe_aliases,
            query=query,
            strategy=strategy,
        )

    def handoff(
        self,
        request: FormalEvidenceAcquisitionRequest,
    ) -> PubMedSearchQuery:
        if request.selected_provider is not FormalEvidenceProviderType.PUBMED:
            raise ValueError("PubMed Providerへ渡せるのはpubmed選択だけです。")
        pmid = request.candidate_pmid or _pmid_from_url(str(request.source_url))
        if pmid:
            return PubMedSearchQuery(
                input_term=request.search_term or request.candidate_title or pmid,
                query=f"{pmid}[PMID]",
                strategy="pmid_lookup",
            )
        doi = request.candidate_doi or _doi_from_url(str(request.source_url))
        if doi:
            return PubMedSearchQuery(
                input_term=request.search_term or request.candidate_title or doi,
                query=f'"{_escape_query(doi)}"[AID]',
                strategy="doi_lookup",
            )
        if request.candidate_title:
            title = _required_text(request.candidate_title, "candidate title")
            return PubMedSearchQuery(
                input_term=request.search_term or title,
                query=f'"{_escape_query(title)}"[Title]',
                strategy="title_lookup",
            )
        return self.direct(request.search_term or str(request.source_url))


@dataclass(frozen=True)
class PubMedEvidenceProviderResult:
    raw: RawEvidenceSearchResult
    records: tuple[PubMedRecord, ...]
    execution: PubMedProviderExecution


class PubMedEvidenceError(RuntimeError):
    def __init__(
        self,
        code: PubMedErrorCode,
        message: str,
        *,
        execution_id: str,
        mode: PubMedSearchMode,
        input_term: str,
        query: str,
        started_at: datetime,
        request_count: int,
        retry_count: int,
        api_key_used: bool,
        rate_limit_mode: PubMedRateLimitMode,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.execution_id = execution_id
        self.mode = mode
        self.input_term = input_term
        self.query = query
        self.started_at = started_at
        self.completed_at = datetime.now(UTC)
        self.request_count = request_count
        self.retry_count = retry_count
        self.api_key_used = api_key_used
        self.rate_limit_mode = rate_limit_mode


class PubMedEvidenceProvider:
    provider_name = "pubmed"
    provider_version = "1.0"

    def __init__(
        self,
        config: PubMedEvidenceProviderConfig,
        *,
        query_builder: PubMedQueryBuilder | None = None,
        transport: PubMedTransport | None = None,
        limiter: PubMedRequestLimiter | None = None,
        cache: PubMedRecordCache | None = None,
    ) -> None:
        self.config = config
        self.query_builder = query_builder or PubMedQueryBuilder()
        self.transport = transport or HttpxPubMedTransport()
        self.limiter = limiter or NcbiRateLimiter(
            api_key_configured=bool(config.api_key.strip())
        )
        self.cache = cache or NullPubMedRecordCache()

    def search(self, request: EvidenceSearchRequest) -> RawEvidenceSearchResult:
        return self.search_with_report(request).raw

    def search_with_report(
        self,
        request: EvidenceSearchRequest,
        *,
        aliases: tuple[str, ...] = (),
        max_records: int | None = None,
    ) -> PubMedEvidenceProviderResult:
        query = self.query_builder.direct(request.theme, aliases=aliases)
        return self._run(
            request=request,
            query=query,
            mode=PubMedSearchMode.DIRECT,
            max_records=max_records,
        )

    def acquire(
        self,
        request: FormalEvidenceAcquisitionRequest,
    ) -> RawEvidenceSearchResult:
        return self.acquire_with_report(request).raw

    def acquire_with_report(
        self,
        request: FormalEvidenceAcquisitionRequest,
    ) -> PubMedEvidenceProviderResult:
        query = self.query_builder.handoff(request)
        return self._run(
            request=EvidenceSearchRequest(
                theme=query.input_term,
                preferred_languages=[EvidenceLanguage.EN],
            ),
            query=query,
            mode=PubMedSearchMode.DISCOVERY_HANDOFF,
            max_records=1 if query.strategy in {"pmid_lookup", "doi_lookup"} else 5,
        )

    def _run(
        self,
        *,
        request: EvidenceSearchRequest,
        query: PubMedSearchQuery,
        mode: PubMedSearchMode,
        max_records: int | None,
    ) -> PubMedEvidenceProviderResult:
        execution_id = f"pme_{uuid4().hex}"
        started_at = datetime.now(UTC)
        timer = monotonic()
        request_count = 0
        retry_count = 0
        limit = min(max_records or self.config.max_records, self.config.max_records)
        search_response, attempts = self._request(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query.query,
                "retmode": "json",
                "retmax": str(limit),
                "sort": "relevance",
            },
            execution_id=execution_id,
            mode=mode,
            input_term=query.input_term,
            query=query.query,
            started_at=started_at,
            request_count=request_count,
            retry_count=retry_count,
        )
        request_count += attempts
        retry_count += max(0, attempts - 1)
        try:
            pmids = _parse_esearch(search_response.content)
        except PubMedPayloadError:
            self._raise(
                PubMedErrorCode.INVALID_JSON,
                "PubMed ESearchの応答形式を確認できませんでした。",
                execution_id=execution_id,
                mode=mode,
                input_term=query.input_term,
                query=query.query,
                started_at=started_at,
                request_count=request_count,
                retry_count=retry_count,
            )
        pmids = tuple(dict.fromkeys(pmids))[:limit]
        if not pmids:
            self._raise(
                PubMedErrorCode.EMPTY_RESULT,
                "PubMedで該当文献を確認できませんでした。",
                execution_id=execution_id,
                mode=mode,
                input_term=query.input_term,
                query=query.query,
                started_at=started_at,
                request_count=request_count,
                retry_count=retry_count,
            )

        cached = self.cache.get_many(pmids)
        fetch_pmids = tuple(pmid for pmid in pmids if pmid not in cached)
        parsed_records: tuple[PubMedRecord, ...] = ()
        invalid_pmids: tuple[str, ...] = ()
        if fetch_pmids:
            fetch_response, attempts = self._request(
                "efetch.fcgi",
                {
                    "db": "pubmed",
                    "id": ",".join(fetch_pmids),
                    "retmode": "xml",
                },
                execution_id=execution_id,
                mode=mode,
                input_term=query.input_term,
                query=query.query,
                started_at=started_at,
                request_count=request_count,
                retry_count=retry_count,
            )
            request_count += attempts
            retry_count += max(0, attempts - 1)
            try:
                parsed_records, invalid_pmids = _parse_efetch(
                    fetch_response.content,
                    retrieved_at=datetime.now(UTC),
                )
            except PubMedPayloadError:
                self._raise(
                    PubMedErrorCode.INVALID_XML,
                    "PubMed EFetchの応答形式を確認できませんでした。",
                    execution_id=execution_id,
                    mode=mode,
                    input_term=query.input_term,
                    query=query.query,
                    started_at=started_at,
                    request_count=request_count,
                    retry_count=retry_count,
                )
            self.cache.put_many(parsed_records)

        record_by_pmid = {**cached, **{item.pmid: item for item in parsed_records}}
        records = tuple(record_by_pmid[pmid] for pmid in pmids if pmid in record_by_pmid)
        returned_pmids = tuple(item.pmid for item in records)
        missing_pmids = tuple(pmid for pmid in pmids if pmid not in record_by_pmid)
        if not records:
            code = (
                PubMedErrorCode.PMID_NOT_FOUND
                if mode is PubMedSearchMode.DISCOVERY_HANDOFF
                else PubMedErrorCode.INVALID_RECORD
            )
            self._raise(
                code,
                "PubMed Recordを正式Evidenceとして取得できませんでした。",
                execution_id=execution_id,
                mode=mode,
                input_term=query.input_term,
                query=query.query,
                started_at=started_at,
                request_count=request_count,
                retry_count=retry_count,
            )

        completed_at = datetime.now(UTC)
        status = (
            PubMedSearchStatus.PARTIAL_SUCCESS
            if invalid_pmids or missing_pmids
            else PubMedSearchStatus.SUCCESS
        )
        duration_ms = max(0, round((monotonic() - timer) * 1000))
        warnings = [
            "PubMed EFetchの正式Metadataだけを取得し、全文は取得していません。",
            "Publication Typeに基づくEvidence Level評価はNormalizer側で行います。",
            "Claim生成・Knowledge Draft・Registry・Promotion・Approvalは実行しません。",
        ]
        if invalid_pmids or missing_pmids:
            warnings.append(
                "一部Recordを除外しました"
                f"（invalid={len(invalid_pmids)}, missing={len(missing_pmids)}）。"
            )
        raw = RawEvidenceSearchResult(
            search_provider_name=self.provider_name,
            search_provider_version=self.provider_version,
            searched_at=started_at,
            duration_ms=duration_ms,
            query=request,
            subject=EvidenceSubject(
                canonical_name=query.input_term,
                aliases=list(query.aliases),
                category=AuthoringCategory.TEST_ITEM,
            ),
            records=[
                RawEvidenceRecord(
                    provider_name=self.provider_name,
                    provider_version=self.provider_version,
                    provider_record_id=item.pmid,
                    retrieved_at=item.retrieved_at,
                    payload=item.model_dump(mode="json"),
                )
                for item in records
            ],
            external_search_performed=True,
            warnings=warnings,
        )
        execution = PubMedProviderExecution(
            execution_id=execution_id,
            mode=mode,
            input_term=query.input_term,
            query=query.query,
            requested_pmids=pmids,
            returned_pmids=returned_pmids,
            invalid_record_pmids=invalid_pmids,
            missing_pmids=missing_pmids,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            request_count=request_count,
            retry_count=retry_count,
            api_key_used=bool(self.config.api_key.strip()),
            rate_limit_mode=self.limiter.mode,
            status=status,
        )
        return PubMedEvidenceProviderResult(
            raw=raw,
            records=records,
            execution=execution,
        )

    def _request(
        self,
        path: str,
        params: dict[str, str],
        *,
        execution_id: str,
        mode: PubMedSearchMode,
        input_term: str,
        query: str,
        started_at: datetime,
        request_count: int,
        retry_count: int,
    ) -> tuple[PubMedHttpResponse, int]:
        common = {"tool": self.config.tool}
        if self.config.email.strip():
            common["email"] = self.config.email
        if self.config.api_key.strip():
            common["api_key"] = self.config.api_key
        final_params = {**params, **common}
        attempts = 0
        for attempt in range(self.config.retry_limit + 1):
            attempts = attempt + 1
            self.limiter.wait()
            try:
                response = self.transport.get(
                    url=f"{self.config.base_url.rstrip('/')}/{path}",
                    params=final_params,
                    timeout_seconds=self.config.timeout_seconds,
                )
            except PubMedTransportTimeout:
                if attempt < self.config.retry_limit:
                    continue
                self._raise_request_error(
                    PubMedErrorCode.TIMEOUT,
                    "PubMedが制限時間内に応答しませんでした。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            except PubMedTransportNetworkError:
                if attempt < self.config.retry_limit:
                    continue
                self._raise_request_error(
                    PubMedErrorCode.NETWORK,
                    "PubMedへ接続できませんでした。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            if response.status_code == 429:
                if attempt < self.config.retry_limit:
                    continue
                self._raise_request_error(
                    PubMedErrorCode.RATE_LIMIT,
                    "PubMedの利用上限に達しました。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            if response.status_code >= 500:
                if attempt < self.config.retry_limit:
                    continue
                self._raise_request_error(
                    PubMedErrorCode.PROVIDER_SERVER,
                    "PubMedで一時的なサーバーエラーが発生しました。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            if response.status_code in (401, 403) or (
                response.status_code >= 400
                and self.config.api_key.strip()
                and b"api key" in response.content.lower()
            ):
                self._raise_request_error(
                    PubMedErrorCode.API_KEY,
                    "NCBI API Keyを確認してください。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            if response.status_code >= 400:
                self._raise_request_error(
                    PubMedErrorCode.REQUEST,
                    "PubMedが検索Requestを受け付けませんでした。",
                    execution_id,
                    mode,
                    input_term,
                    query,
                    started_at,
                    request_count + attempts,
                    retry_count + max(0, attempts - 1),
                )
            return response, attempts
        raise AssertionError("unreachable")

    def _raise_request_error(
        self,
        code: PubMedErrorCode,
        message: str,
        execution_id: str,
        mode: PubMedSearchMode,
        input_term: str,
        query: str,
        started_at: datetime,
        request_count: int,
        retry_count: int,
    ) -> NoReturn:
        self._raise(
            code,
            message,
            execution_id=execution_id,
            mode=mode,
            input_term=input_term,
            query=query,
            started_at=started_at,
            request_count=request_count,
            retry_count=retry_count,
        )

    def _raise(
        self,
        code: PubMedErrorCode,
        message: str,
        *,
        execution_id: str,
        mode: PubMedSearchMode,
        input_term: str,
        query: str,
        started_at: datetime,
        request_count: int,
        retry_count: int,
    ) -> NoReturn:
        raise PubMedEvidenceError(
            code,
            message,
            execution_id=execution_id,
            mode=mode,
            input_term=input_term,
            query=query,
            started_at=started_at,
            request_count=request_count,
            retry_count=retry_count,
            api_key_used=bool(self.config.api_key.strip()),
            rate_limit_mode=self.limiter.mode,
        )


def _parse_esearch(content: bytes) -> tuple[str, ...]:
    try:
        parsed = json.loads(content)
        result = parsed["esearchresult"]
        values = result["idlist"]
        if not isinstance(values, list):
            raise TypeError("idlist must be a list")
        return tuple(
            value for value in values if isinstance(value, str) and value.isdigit()
        )
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise PubMedPayloadError(PubMedErrorCode.INVALID_JSON) from error


class PubMedPayloadError(ValueError):
    def __init__(self, code: PubMedErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _parse_efetch(
    content: bytes,
    *,
    retrieved_at: datetime,
) -> tuple[tuple[PubMedRecord, ...], tuple[str, ...]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise PubMedPayloadError(PubMedErrorCode.INVALID_XML) from error
    records: list[PubMedRecord] = []
    invalid: list[str] = []
    for index, article in enumerate(root.findall(".//PubmedArticle"), start=1):
        pmid = _node_text(article.find("./MedlineCitation/PMID"))
        try:
            records.append(_parse_article(article, retrieved_at=retrieved_at))
        except (TypeError, ValueError):
            invalid.append(pmid or f"unknown-{index}")
    return tuple(records), tuple(invalid)


def _parse_article(article: ET.Element, *, retrieved_at: datetime) -> PubMedRecord:
    citation = article.find("./MedlineCitation")
    article_node = article.find("./MedlineCitation/Article")
    if citation is None or article_node is None:
        raise ValueError("missing citation or article")
    pmid = _required_text(_node_text(citation.find("./PMID")), "PMID")
    title = _required_text(_node_text(article_node.find("./ArticleTitle")), "title")
    journal = _required_text(
        _node_text(article_node.find("./Journal/Title"))
        or _node_text(article_node.find("./Journal/ISOAbbreviation"))
        or "Journal未収載",
        "journal",
    )
    authors = tuple(
        value
        for value in (_author_name(item) for item in article_node.findall("./AuthorList/Author"))
        if value
    )
    abstract_parts: list[str] = []
    for abstract_node in article_node.findall("./Abstract/AbstractText"):
        text = _node_text(abstract_node)
        if not text:
            continue
        label = abstract_node.attrib.get("Label", "").strip()
        abstract_parts.append(f"{label}: {text}" if label else text)
    publication_types = tuple(
        dict.fromkeys(
            value
            for value in (
                _node_text(item)
                for item in article_node.findall("./PublicationTypeList/PublicationType")
            )
            if value
        )
    )
    mesh_terms = tuple(
        dict.fromkeys(
            value
            for value in (
                _mesh_heading(item)
                for item in citation.findall("./MeshHeadingList/MeshHeading")
            )
            if value
        )
    )
    doi = next(
        (
            _node_text(item)
            for item in article.findall("./PubmedData/ArticleIdList/ArticleId")
            if item.attrib.get("IdType", "").lower() == "doi" and _node_text(item)
        ),
        None,
    )
    language = _node_text(article_node.find("./Language")) or "und"
    return PubMedRecord(
        pmid=pmid,
        title=title,
        authors=authors,
        journal=journal,
        publication_date=_article_date(article_node),
        abstract="\n".join(abstract_parts) or None,
        doi=doi,
        publication_types=publication_types,
        language=language,
        mesh_terms=mesh_terms,
        url=HttpUrl(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
        retrieved_at=retrieved_at,
    )


def _article_date(article: ET.Element) -> date | None:
    for node in (
        article.find("./ArticleDate"),
        article.find("./Journal/JournalIssue/PubDate"),
    ):
        if node is None:
            continue
        year = _node_text(node.find("./Year"))
        medline_date = _node_text(node.find("./MedlineDate"))
        if not year and medline_date:
            match = re.search(r"(?:18|19|20)\d{2}", medline_date)
            year = match.group(0) if match else None
        if not year or not year.isdigit():
            continue
        month = _month_number(_node_text(node.find("./Month")))
        day_text = _node_text(node.find("./Day"))
        day = int(day_text) if day_text and day_text.isdigit() else 1
        try:
            return date(int(year), month, day)
        except ValueError:
            return date(int(year), month, 1)
    return None


def _month_number(value: str | None) -> int:
    if not value:
        return 1
    if value.isdigit() and 1 <= int(value) <= 12:
        return int(value)
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return months.get(value[:3].lower(), 1)


def _author_name(author: ET.Element) -> str | None:
    collective = _node_text(author.find("./CollectiveName"))
    if collective:
        return collective
    last = _node_text(author.find("./LastName"))
    fore = _node_text(author.find("./ForeName"))
    initials = _node_text(author.find("./Initials"))
    parts = [item for item in (last, fore or initials) if item]
    return " ".join(parts) or None


def _mesh_heading(node: ET.Element) -> str | None:
    descriptor = _node_text(node.find("./DescriptorName"))
    if not descriptor:
        return None
    qualifiers = [
        value
        for value in (_node_text(item) for item in node.findall("./QualifierName"))
        if value
    ]
    return f"{descriptor} / {' / '.join(qualifiers)}" if qualifiers else descriptor


def _node_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return " ".join(value.split()) if value else None


def _pmid_from_url(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.netloc.lower() not in {
        "pubmed.ncbi.nlm.nih.gov",
        "www.pubmed.ncbi.nlm.nih.gov",
    }:
        return None
    match = re.search(r"/(\d{1,12})(?:/|$)", parsed.path)
    return match.group(1) if match else None


def _doi_from_url(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.netloc.lower() not in {"doi.org", "www.doi.org", "dx.doi.org"}:
        return None
    return parsed.path.lstrip("/") or None


def _required_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{label} is required")
    return " ".join(value.strip().split())


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
