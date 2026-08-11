"""Exchangeable provider and builder boundaries for Knowledge creation."""

from typing import Protocol, runtime_checkable

from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    EvidenceRankingResult,
    EvidenceSearchRequest,
    EvidenceSearchResult,
)


@runtime_checkable
class EvidenceSearchProvider(Protocol):
    provider_name: str
    provider_version: str

    def search(self, request: EvidenceSearchRequest) -> EvidenceSearchResult:
        """Return evidence without creating Claims or writing Knowledge."""


@runtime_checkable
class EvidenceRanker(Protocol):
    ranking_version: str

    def rank(self, result: EvidenceSearchResult) -> EvidenceRankingResult:
        """Rank evidence independently from search and Claim generation."""


@runtime_checkable
class ClaimBuilder(Protocol):
    builder_name: str
    builder_version: str

    def build(
        self,
        subject_key: str,
        evidence: EvidenceRankingResult,
    ) -> ClaimBuildResult:
        """Build traceable Claim candidates; an LLM adapter can implement this later."""
