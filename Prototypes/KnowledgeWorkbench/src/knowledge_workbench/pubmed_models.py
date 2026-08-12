"""Contracts for PubMed formal Evidence acquisition and human selection."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from knowledge_workbench.knowledge_pipeline_models import EvidenceBundle

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
LongText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
]


class FrozenPubMedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PubMedSearchMode(StrEnum):
    DIRECT = "direct"
    DISCOVERY_HANDOFF = "discovery_handoff"


class PubMedRateLimitMode(StrEnum):
    PUBLIC = "public_below_3_requests_per_second"
    API_KEY = "api_key_below_10_requests_per_second"


class PubMedSearchStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PubMedErrorCode(StrEnum):
    TIMEOUT = "timeout_error"
    RATE_LIMIT = "rate_limit_error"
    PROVIDER_SERVER = "provider_server_error"
    NETWORK = "network_error"
    INVALID_JSON = "invalid_json"
    INVALID_XML = "invalid_xml"
    PMID_NOT_FOUND = "pmid_not_found"
    EMPTY_RESULT = "empty_result"
    INVALID_RECORD = "invalid_record"
    API_KEY = "api_key_error"
    REQUEST = "request_error"


class PubMedDirectSearchRequest(FrozenPubMedModel):
    request_version: Literal["1.0"] = "1.0"
    medical_term: ShortText
    aliases: tuple[ShortText, ...] = Field(default=(), max_length=20)
    max_records: int = Field(default=20, ge=1, le=30)


class PubMedSearchQuery(FrozenPubMedModel):
    query_version: Literal["1.0"] = "1.0"
    input_term: ShortText
    aliases: tuple[ShortText, ...] = Field(default=(), max_length=20)
    query: LongText
    strategy: Literal[
        "literal_term",
        "known_aliases",
        "pmid_lookup",
        "doi_lookup",
        "title_lookup",
    ]


class PubMedRecord(FrozenPubMedModel):
    """Parsed EFetch record. Raw XML stays inside the Provider."""

    record_version: Literal["1.0"] = "1.0"
    pmid: str = Field(pattern=r"^[0-9]{1,12}$")
    title: LongText
    authors: tuple[ShortText, ...] = Field(default=(), max_length=500)
    journal: ShortText
    publication_date: date | None = None
    abstract: LongText | None = None
    doi: ShortText | None = None
    publication_types: tuple[ShortText, ...] = Field(default=(), max_length=100)
    language: ShortText
    mesh_terms: tuple[ShortText, ...] = Field(default=(), max_length=500)
    url: HttpUrl
    retrieved_at: datetime


class PubMedProviderExecution(FrozenPubMedModel):
    execution_version: Literal["1.0"] = "1.0"
    execution_id: str = Field(pattern=r"^pme_[a-f0-9]{32}$")
    mode: PubMedSearchMode
    input_term: ShortText
    query: LongText
    requested_pmids: tuple[str, ...] = Field(default=(), max_length=30)
    returned_pmids: tuple[str, ...] = Field(default=(), max_length=30)
    invalid_record_pmids: tuple[str, ...] = Field(default=(), max_length=30)
    missing_pmids: tuple[str, ...] = Field(default=(), max_length=30)
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    request_count: int = Field(ge=0, le=4)
    retry_count: int = Field(ge=0, le=2)
    api_key_used: bool
    rate_limit_mode: PubMedRateLimitMode
    status: PubMedSearchStatus


class PubMedFormalEvidenceMetadata(FrozenPubMedModel):
    """Workbench-safe PubMed metadata indexed by the unchanged Evidence ID."""

    metadata_version: Literal["1.0"] = "1.0"
    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    pmid: str = Field(pattern=r"^[0-9]{1,12}$")
    title: LongText
    authors: tuple[ShortText, ...] = Field(default=(), max_length=500)
    journal: ShortText
    publication_date: date | None = None
    publication_types: tuple[ShortText, ...] = Field(default=(), max_length=100)
    doi: ShortText | None = None
    language: ShortText
    mesh_terms: tuple[ShortText, ...] = Field(default=(), max_length=500)
    abstract_available: bool
    evidence_level: Literal["A", "B", "C"]
    retrieved_at: datetime


class PubMedSearchAuditEntry(FrozenPubMedModel):
    audit_version: Literal["1.0"] = "1.0"
    execution_id: str = Field(pattern=r"^pme_[a-f0-9]{32}$")
    bundle_id: str | None = None
    input_term: ShortText
    provider: Literal["pubmed"] = "pubmed"
    query: LongText
    retrieved_pmids: tuple[str, ...] = Field(default=(), max_length=30)
    returned_record_count: int = Field(ge=0, le=30)
    accepted_count: int = Field(ge=0, le=30)
    excluded_count: int = Field(ge=0, le=30)
    deduplicated_count: int = Field(ge=0, le=30)
    duration_ms: int = Field(ge=0)
    request_count: int = Field(ge=0, le=4)
    retry_count: int = Field(ge=0, le=2)
    api_key_used: bool
    rate_limit_mode: PubMedRateLimitMode
    status: PubMedSearchStatus
    error_code: PubMedErrorCode | None = None
    retrieved_at: datetime
    medical_body_stored: Literal[False] = False
    secret_stored: Literal[False] = False


class PubMedFormalEvidencePreview(FrozenPubMedModel):
    preview_version: Literal["1.0"] = "1.0"
    preview_id: str = Field(pattern=r"^pfp_[a-f0-9]{20}$")
    mode: PubMedSearchMode
    input_term: ShortText
    query: LongText
    evidence_bundle: EvidenceBundle
    formal_evidence_metadata: tuple[PubMedFormalEvidenceMetadata, ...]
    search_audit: PubMedSearchAuditEntry
    formal_evidence: Literal[True] = True
    claim_generated: Literal[False] = False
    knowledge_draft_generated: Literal[False] = False
    registry_changed: Literal[False] = False
    promotion_performed: Literal[False] = False
    approval_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_metadata_matches_bundle(self) -> Self:
        evidence_ids = {
            item.evidence.evidence_id for item in self.evidence_bundle.evidence
        }
        metadata_ids = {item.evidence_id for item in self.formal_evidence_metadata}
        if evidence_ids != metadata_ids:
            raise ValueError("PubMed metadata must match Evidence Bundle IDs")
        return self


class EvidenceSelectionDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    HOLD = "hold"


class PubMedEvidenceSelectionRequest(FrozenPubMedModel):
    selection_version: Literal["1.0"] = "1.0"
    bundle_id: str = Field(pattern=r"^evb_[a-z0-9][a-z0-9_-]{7,63}$")
    evidence_id: str = Field(pattern=r"^evd_[a-z0-9][a-z0-9_-]{7,63}$")
    decision: EvidenceSelectionDecision
    operator: ShortText
    comment: ShortText | None = None


class PubMedEvidenceSelectionEntry(FrozenPubMedModel):
    selection_version: Literal["1.0"] = "1.0"
    selection_id: str = Field(pattern=r"^pes_[a-f0-9]{20}$")
    bundle_id: str
    evidence_id: str
    decision: EvidenceSelectionDecision
    operator: ShortText
    timestamp: datetime
    comment: ShortText | None = None
    medical_review_performed: Literal[False] = False
    claim_generated: Literal[False] = False
