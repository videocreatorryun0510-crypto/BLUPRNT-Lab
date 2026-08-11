"""Gemini Interactions Google Search provider isolated from downstream Evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, NoReturn, Protocol
from uuid import uuid4

import httpx

from knowledge_workbench.authoring_models import AuthoringCategory
from knowledge_workbench.grounded_evidence_models import (
    GroundedProviderExecution,
    GroundedSearchErrorCode,
    GroundedSearchQuery,
    GroundedSearchQueryPlan,
    GroundedSearchUsage,
    SearchIntentType,
)
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceSearchRequest,
    EvidenceSubject,
    RawEvidenceRecord,
    RawEvidenceSearchResult,
)


@dataclass(frozen=True)
class GeminiGroundedSearchConfig:
    api_key: str
    model: str = "gemini-3.6-flash"
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    timeout_seconds: float = 30.0
    retry_limit: int = 1
    max_queries: int = 4
    max_sources: int = 50

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Gemini Search model is required")
        if self.timeout_seconds <= 0:
            raise ValueError("Gemini Search timeout must be positive")
        if self.retry_limit not in (0, 1):
            raise ValueError("Gemini Search retry_limit must be 0 or 1")
        if not 1 <= self.max_queries <= 4:
            raise ValueError("Gemini Search max_queries must be between 1 and 4")
        if not 1 <= self.max_sources <= 100:
            raise ValueError("Gemini Search max_sources must be between 1 and 100")


@dataclass(frozen=True)
class GroundedSearchHttpResponse:
    status_code: int
    content: bytes


class GroundedSearchTransportTimeout(RuntimeError):
    pass


class GroundedSearchTransportNetworkError(RuntimeError):
    pass


class GroundedSearchTransport(Protocol):
    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GroundedSearchHttpResponse: ...


class HttpxGroundedSearchTransport:
    """Send one stateless Interactions API request without logging secrets."""

    def post(
        self,
        *,
        endpoint: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: float,
    ) -> GroundedSearchHttpResponse:
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "x-goog-api-key": api_key,
                        "content-type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as error:
            raise GroundedSearchTransportTimeout from error
        except httpx.NetworkError as error:
            raise GroundedSearchTransportNetworkError from error
        return GroundedSearchHttpResponse(
            status_code=response.status_code,
            content=response.content,
        )


class GeminiGroundedSearchError(RuntimeError):
    def __init__(
        self,
        code: GroundedSearchErrorCode,
        message: str,
        *,
        search_execution_id: str,
        model: str,
        query_plan: GroundedSearchQueryPlan,
        started_at: datetime,
        completed_at: datetime,
        attempt_count: int,
        executed_queries: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.search_execution_id = search_execution_id
        self.model = model
        self.query_plan = query_plan
        self.started_at = started_at
        self.completed_at = completed_at
        self.attempt_count = attempt_count
        self.executed_queries = executed_queries


class MedicalSearchQueryBuilder:
    builder_version = "1.0"

    def build(self, term: str, *, max_queries: int = 4) -> GroundedSearchQueryPlan:
        normalized = " ".join(term.strip().split())
        if not normalized:
            raise ValueError("医療用語を入力してください。")
        if len(normalized) > 300:
            raise ValueError("医療用語は300文字以内で入力してください。")
        queries = (
            GroundedSearchQuery(
                intent=SearchIntentType.DEFINITION,
                query=f"{normalized} 医学 定義 基礎 信頼できる資料",
            ),
            GroundedSearchQuery(
                intent=SearchIntentType.OFFICIAL_GUIDELINE,
                query=f"{normalized} ガイドライン 厚生労働省 学会 公式",
            ),
            GroundedSearchQuery(
                intent=SearchIntentType.LABORATORY_METHOD,
                query=f"{normalized} 臨床検査 測定法 原理 検査医学",
            ),
            GroundedSearchQuery(
                intent=SearchIntentType.EXAM_RELEVANCE,
                query=f"{normalized} 臨床検査技師 国家試験 出題基準 学習要点",
            ),
        )
        return GroundedSearchQueryPlan(
            input_term=normalized,
            queries=queries[:max_queries],
        )


@dataclass(frozen=True)
class GeminiGroundedProviderResult:
    raw: RawEvidenceSearchResult
    execution: GroundedProviderExecution


class GeminiGroundedSearchProvider:
    provider_name = "gemini_google_search"
    provider_version = "1.0"

    def __init__(
        self,
        config: GeminiGroundedSearchConfig,
        *,
        query_builder: MedicalSearchQueryBuilder | None = None,
        transport: GroundedSearchTransport | None = None,
    ) -> None:
        self.config = config
        self.query_builder = query_builder or MedicalSearchQueryBuilder()
        self.transport = transport or HttpxGroundedSearchTransport()

    def search(self, request: EvidenceSearchRequest) -> RawEvidenceSearchResult:
        """Satisfy the common Search Provider interface."""

        return self.search_with_report(request).raw

    def search_with_report(
        self,
        request: EvidenceSearchRequest,
    ) -> GeminiGroundedProviderResult:
        execution_id = f"gse_{uuid4().hex}"
        started_at = datetime.now(UTC)
        clock_started = monotonic()
        query_plan = self.query_builder.build(
            request.theme,
            max_queries=self.config.max_queries,
        )
        if not self.config.api_key.strip():
            self._raise(
                GroundedSearchErrorCode.MISSING_API_KEY,
                "Gemini Search APIキーが設定されていません。",
                execution_id=execution_id,
                query_plan=query_plan,
                started_at=started_at,
                attempt_count=0,
            )

        body: dict[str, object] = {
            "model": self.config.model,
            "store": False,
            "input": _grounded_search_prompt(query_plan),
            "tools": [{"type": "google_search"}],
        }
        response_data: dict[str, Any] | None = None
        attempts = 0
        final_error: tuple[GroundedSearchErrorCode, str] | None = None
        for attempt in range(self.config.retry_limit + 1):
            attempts = attempt + 1
            try:
                response = self.transport.post(
                    endpoint=self.config.endpoint,
                    api_key=self.config.api_key,
                    body=body,
                    timeout_seconds=self.config.timeout_seconds,
                )
            except GroundedSearchTransportTimeout:
                final_error = (
                    GroundedSearchErrorCode.TIMEOUT,
                    "Gemini Grounded Searchが制限時間内に応答しませんでした。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            except GroundedSearchTransportNetworkError:
                final_error = (
                    GroundedSearchErrorCode.NETWORK,
                    "Gemini Grounded Searchへ接続できませんでした。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break

            if response.status_code in (401, 403):
                final_error = (
                    GroundedSearchErrorCode.AUTHENTICATION,
                    "Gemini Grounded Searchの認証に失敗しました。",
                )
                break
            if response.status_code == 429:
                final_error = (
                    GroundedSearchErrorCode.RATE_LIMIT,
                    "Gemini Grounded Searchの利用上限に達しました。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            if response.status_code >= 500:
                final_error = (
                    GroundedSearchErrorCode.PROVIDER_SERVER,
                    "Gemini Grounded Searchで一時的なサーバーエラーが発生しました。",
                )
                if attempt < self.config.retry_limit:
                    continue
                break
            if response.status_code >= 400:
                final_error = (
                    GroundedSearchErrorCode.REQUEST,
                    "Gemini Grounded Searchが検索Requestを受け付けませんでした。",
                )
                break
            try:
                parsed = json.loads(response.content)
                if not isinstance(parsed, dict):
                    raise ValueError("response must be an object")
                response_data = parsed
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                final_error = (
                    GroundedSearchErrorCode.INVALID_RESPONSE,
                    "Gemini Grounded Searchの応答形式を確認できませんでした。",
                )
            break

        if response_data is None:
            code, message = final_error or (
                GroundedSearchErrorCode.INVALID_RESPONSE,
                "Gemini Grounded Searchの応答を取得できませんでした。",
            )
            self._raise(
                code,
                message,
                execution_id=execution_id,
                query_plan=query_plan,
                started_at=started_at,
                attempt_count=attempts,
            )

        executed_queries = _extract_executed_queries(response_data)
        records = _extract_grounding_sources(
            response_data,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            query_plan=query_plan,
            retrieved_at=datetime.now(UTC),
            max_sources=self.config.max_sources,
        )
        if not records:
            self._raise(
                GroundedSearchErrorCode.NO_GROUNDING_SOURCE,
                "Google Search Groundingから外部Sourceを取得できませんでした。",
                execution_id=execution_id,
                query_plan=query_plan,
                started_at=started_at,
                attempt_count=attempts,
                executed_queries=executed_queries,
            )

        completed_at = datetime.now(UTC)
        duration_ms = max(0, int((monotonic() - clock_started) * 1000))
        usage = _extract_usage(response_data, attempts=attempts)
        raw = RawEvidenceSearchResult(
            search_provider_name=self.provider_name,
            search_provider_version=self.provider_version,
            searched_at=started_at,
            duration_ms=duration_ms,
            query=request,
            subject=EvidenceSubject(
                canonical_name=query_plan.input_term,
                aliases=[],
                category=AuthoringCategory.TEST_ITEM,
            ),
            records=records,
            external_search_performed=True,
            warnings=[
                "Gemini生成回答本文は破棄し、Grounding Citationだけを候補にしています。",
                "Categoryは自動分類せず、Evidence検索用の汎用test_itemとして扱います。",
                "国家試験Web検索は出題実績の証明ではありません。",
            ],
        )
        response_id = response_data.get("id")
        execution = GroundedProviderExecution(
            search_execution_id=execution_id,
            provider_result_id=response_id if isinstance(response_id, str) else None,
            model=self.config.model,
            query_plan=query_plan,
            executed_queries=executed_queries,
            search_started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            usage=usage,
            retry_count=max(0, attempts - 1),
        )
        return GeminiGroundedProviderResult(raw=raw, execution=execution)

    def _raise(
        self,
        code: GroundedSearchErrorCode,
        message: str,
        *,
        execution_id: str,
        query_plan: GroundedSearchQueryPlan,
        started_at: datetime,
        attempt_count: int,
        executed_queries: tuple[str, ...] = (),
    ) -> NoReturn:
        raise GeminiGroundedSearchError(
            code,
            message,
            search_execution_id=execution_id,
            model=self.config.model,
            query_plan=query_plan,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            attempt_count=attempt_count,
            executed_queries=executed_queries,
        )


def _grounded_search_prompt(plan: GroundedSearchQueryPlan) -> str:
    lines = [
        "Use Google Search to discover external medical evidence sources for the term below.",
        f"Medical term: {plan.input_term}",
        "Search intents:",
        *[
            f"- {item.intent.value}: {item.query}"
            for item in plan.queries
        ],
        (
            "Prefer official Japanese sources, professional societies, official "
            "international sources, and academic literature."
        ),
        "Do not claim national examination appearance history from web results.",
        (
            "Provide a short grounded response with citations. The response prose "
            "will be discarded; only citation metadata will be used."
        ),
    ]
    return "\n".join(lines)


def _extract_executed_queries(response: dict[str, Any]) -> tuple[str, ...]:
    queries: list[str] = []
    for step in _steps(response):
        if step.get("type") != "google_search_call":
            continue
        arguments = step.get("arguments")
        if not isinstance(arguments, dict):
            continue
        raw_queries = arguments.get("queries")
        if not isinstance(raw_queries, list):
            continue
        for query in raw_queries:
            if isinstance(query, str) and query.strip() and query not in queries:
                queries.append(query.strip())
    return tuple(queries[:20])


def _extract_grounding_sources(
    response: dict[str, Any],
    *,
    provider_name: str,
    provider_version: str,
    query_plan: GroundedSearchQueryPlan,
    retrieved_at: datetime,
    max_sources: int,
) -> list[RawEvidenceRecord]:
    records: list[RawEvidenceRecord] = []
    source_index = 0
    for step in _steps(response):
        if step.get("type") != "model_output":
            continue
        content = step.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            annotations = block.get("annotations")
            if not isinstance(annotations, list):
                continue
            for annotation in annotations:
                if len(records) >= max_sources:
                    return records
                if not isinstance(annotation, dict):
                    continue
                if annotation.get("type") != "url_citation":
                    continue
                source_url = annotation.get("url")
                if not isinstance(source_url, str) or not source_url.startswith(
                    ("https://", "http://")
                ):
                    continue
                title_value = annotation.get("title")
                title = (
                    title_value.strip()
                    if isinstance(title_value, str) and title_value.strip()
                    else source_url
                )
                source_index += 1
                raw_snippet = annotation.get("snippet")
                snippet = (
                    raw_snippet.strip()
                    if isinstance(raw_snippet, str) and raw_snippet.strip()
                    else None
                )
                digest = hashlib.sha256(
                    f"{source_url}|{title}|{source_index}".encode()
                ).hexdigest()[:20]
                records.append(
                    RawEvidenceRecord(
                        provider_name=provider_name,
                        provider_version=provider_version,
                        provider_record_id=f"gemini-grounding:{digest}",
                        retrieved_at=retrieved_at,
                        payload={
                            "source_url": source_url,
                            "title": title,
                            "publisher": _domain(source_url),
                            "domain": _domain(source_url),
                            "snippet": snippet,
                            "published_date": None,
                            "search_queries": [item.query for item in query_plan.queries],
                            "grounding_metadata": {
                                "annotation_type": "url_citation",
                                "start_index": annotation.get(
                                    "start_index",
                                    annotation.get("startIndex"),
                                ),
                                "end_index": annotation.get(
                                    "end_index",
                                    annotation.get("endIndex"),
                                ),
                            },
                            "content_acquisition": (
                                "grounding_snippet"
                                if snippet
                                else "citation_metadata_only"
                            ),
                        },
                    )
                )
    return records


def _steps(response: dict[str, Any]) -> list[dict[str, Any]]:
    value = response.get("steps")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_usage(
    response: dict[str, Any],
    *,
    attempts: int,
) -> GroundedSearchUsage:
    raw_usage = response.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    prompt_tokens = _int_value(usage, "totalInputTokens", "total_input_tokens")
    completion_tokens = _int_value(
        usage,
        "totalOutputTokens",
        "total_output_tokens",
    )
    total_tokens = _int_value(usage, "totalTokens", "total_tokens")
    return GroundedSearchUsage(
        request_count=attempts,
        attempt_count=attempts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        search_grounding_used=(
            bool(_extract_executed_queries(response))
            or _contains_grounding_citation(response)
        ),
        estimated_cost_usd=None,
    )


def _int_value(mapping: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _contains_grounding_citation(response: dict[str, Any]) -> bool:
    for step in _steps(response):
        content = step.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            annotations = block.get("annotations")
            if isinstance(annotations, list) and any(
                isinstance(item, dict) and item.get("type") == "url_citation"
                for item in annotations
            ):
                return True
    return False


def _domain(url: str) -> str:
    try:
        return httpx.URL(url).host or "unknown"
    except httpx.InvalidURL:
        return "unknown"
