"""Gemini execution contracts; discovery content lives in discovery_models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchIntentType(StrEnum):
    DEFINITION = "definition"
    OFFICIAL_GUIDELINE = "official_guideline"
    LABORATORY_METHOD = "laboratory_method"
    EXAM_RELEVANCE = "exam_relevance"


class GroundedSearchErrorCode(StrEnum):
    MISSING_API_KEY = "missing_api_key"
    AUTHENTICATION = "authentication_error"
    TIMEOUT = "timeout_error"
    RATE_LIMIT = "rate_limit_error"
    PROVIDER_SERVER = "provider_server_error"
    NETWORK = "network_error"
    INVALID_RESPONSE = "invalid_response"
    NO_GROUNDING_SOURCE = "no_grounding_source"
    REQUEST = "request_error"


class GroundedSearchQuery(FrozenModel):
    intent: SearchIntentType
    query: ShortText


class GroundedSearchQueryPlan(FrozenModel):
    query_plan_version: Literal["1.0"] = "1.0"
    input_term: ShortText
    queries: tuple[GroundedSearchQuery, ...] = Field(min_length=1, max_length=4)


class GroundedSearchUsage(FrozenModel):
    request_count: int = Field(ge=0, le=2)
    attempt_count: int = Field(ge=0, le=2)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    search_grounding_used: bool
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class GroundedProviderExecution(FrozenModel):
    search_execution_id: str = Field(pattern=r"^gse_[a-f0-9]{32}$")
    provider_result_id: str | None = None
    provider: Literal["gemini_google_search"] = "gemini_google_search"
    provider_version: Literal["1.0"] = "1.0"
    model: ShortText
    query_plan: GroundedSearchQueryPlan
    executed_queries: tuple[ShortText, ...] = Field(default=(), max_length=20)
    search_started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    usage: GroundedSearchUsage
    retry_count: int = Field(ge=0, le=1)
    store_enabled: Literal[False] = False
