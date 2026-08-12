"""Provider-neutral boundaries between discovery and formal Evidence acquisition."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from knowledge_workbench.discovery_models import (
    DiscoveryCandidateSet,
    DiscoverySearchRequest,
)
from knowledge_workbench.knowledge_pipeline_models import RawEvidenceSearchResult


@runtime_checkable
class DiscoveryProvider(Protocol):
    provider_name: str
    provider_version: str

    def discover(self, request: DiscoverySearchRequest) -> DiscoveryCandidateSet:
        """Return human-facing leads that cannot be used as Evidence."""


class FormalEvidenceProviderType(StrEnum):
    PUBMED = "pubmed"
    PMC = "pmc"
    PMDA = "pmda"
    MHLW = "mhlw"
    J_STAGE = "j_stage"


class FormalEvidenceAcquisitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_version: Literal["1.0"] = "1.0"
    candidate_id: str = Field(pattern=r"^dsc_[a-f0-9]{20}$")
    source_url: HttpUrl
    selected_provider: FormalEvidenceProviderType
    candidate_title: str | None = Field(default=None, max_length=2000)
    candidate_doi: str | None = Field(default=None, max_length=500)
    candidate_pmid: str | None = Field(default=None, pattern=r"^[0-9]{1,12}$")
    search_term: str | None = Field(default=None, max_length=500)


@runtime_checkable
class FormalEvidenceProvider(Protocol):
    """Future dedicated Provider with explicit acquisition conditions."""

    provider_name: str
    provider_version: str

    def acquire(
        self,
        request: FormalEvidenceAcquisitionRequest,
    ) -> RawEvidenceSearchResult:
        """Acquire Provider-owned data for the formal Evidence pipeline."""
