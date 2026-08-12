"""Provider-neutral contracts for human-facing source discovery only."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    StringConstraints,
    model_validator,
)

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
LongText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=6000),
]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class FrozenDiscoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiscoverySearchRequest(FrozenDiscoveryModel):
    discovery_request_version: Literal["1.0"] = "1.0"
    medical_term: ShortText


class DiscoveryCandidate(FrozenDiscoveryModel):
    """A human review lead. It is deliberately not medical Evidence."""

    discovery_candidate_version: Literal["1.0"] = "1.0"
    candidate_id: str = Field(pattern=r"^dsc_[a-f0-9]{20}$")
    provider: ShortText
    provider_version: ShortText
    search_query: ShortText
    title: ShortText
    url: HttpUrl
    publisher: ShortText
    domain: ShortText
    snippet: LongText | None = None
    retrieved_at: datetime
    provider_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    discovery_fingerprint: Fingerprint
    claim_eligible: Literal[False] = False
    evidence_bundle_eligible: Literal[False] = False
    promotion_allowed: Literal[False] = False
    registry_allowed: Literal[False] = False
    approval_allowed: Literal[False] = False


class DiscoveryCandidateSet(FrozenDiscoveryModel):
    """The only object exposed by a Discovery Provider."""

    discovery_candidate_set_version: Literal["1.0"] = "1.0"
    candidate_set_id: str = Field(pattern=r"^dcs_[a-f0-9]{20}$")
    provider: ShortText
    provider_version: ShortText
    input_term: ShortText
    generated_queries: tuple[ShortText, ...] = Field(min_length=1, max_length=4)
    executed_queries: tuple[ShortText, ...] = Field(default=(), max_length=20)
    candidates: tuple[DiscoveryCandidate, ...] = Field(max_length=100)
    raw_source_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    created_at: datetime
    discovery_fingerprint: Fingerprint
    warnings: tuple[ShortText, ...] = ()
    claim_eligible: Literal[False] = False
    evidence_bundle_eligible: Literal[False] = False
    promotion_allowed: Literal[False] = False
    registry_allowed: Literal[False] = False
    approval_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        if self.candidate_count != len(self.candidates):
            raise ValueError("candidate_count must match candidates length")
        if self.raw_source_count != self.candidate_count + self.duplicate_count:
            raise ValueError(
                "raw_source_count must equal candidate_count plus duplicate_count"
            )
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id must be unique within a candidate set")
        return self


class DiscoverySearchUsage(FrozenDiscoveryModel):
    request_count: int = Field(ge=0, le=2)
    attempt_count: int = Field(ge=0, le=2)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    search_grounding_used: bool
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class DiscoverySearchAuditEntry(FrozenDiscoveryModel):
    audit_version: Literal["1.1"] = "1.1"
    search_execution_id: str = Field(pattern=r"^gse_[a-f0-9]{32}$")
    candidate_set_id: str | None = None
    input_term: ShortText
    generated_queries: tuple[ShortText, ...] = Field(min_length=1, max_length=4)
    executed_queries: tuple[ShortText, ...] = Field(default=(), max_length=20)
    provider: ShortText
    model: ShortText
    search_started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    raw_source_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    usage: DiscoverySearchUsage
    status: Literal["success", "failed"]
    error_code: str | None = None
    response_body_stored: Literal[False] = False
    evidence_stored: Literal[False] = False


class GroundedDiscoveryPreview(FrozenDiscoveryModel):
    preview_version: Literal["1.1"] = "1.1"
    search_execution_id: str = Field(pattern=r"^gse_[a-f0-9]{32}$")
    input_term: ShortText
    provider: ShortText
    provider_version: ShortText
    model: ShortText
    discovery_candidate_set: DiscoveryCandidateSet
    search_audit: DiscoverySearchAuditEntry
    response_fingerprint: Fingerprint
    formal_evidence_provider_available: Literal[False] = False
    external_search_called: Literal[True] = True
    llm_claim_generation_called: Literal[False] = False
    evidence_bundle_generated: Literal[False] = False
    knowledge_draft_generated: Literal[False] = False
    registry_mutated: Literal[False] = False
    promotion_performed: Literal[False] = False
    approval_performed: Literal[False] = False
