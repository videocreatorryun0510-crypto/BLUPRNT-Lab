"""Exchangeable boundaries for Evidence Intelligence and Knowledge creation."""

from typing import Protocol, runtime_checkable

from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    EvidenceBundle,
    EvidenceDeduplicationResult,
    EvidenceNormalizationResult,
    EvidenceRankingResult,
    EvidenceSearchRequest,
    RawEvidenceSearchResult,
)


@runtime_checkable
class EvidenceSearchProvider(Protocol):
    provider_name: str
    provider_version: str

    def search(self, request: EvidenceSearchRequest) -> RawEvidenceSearchResult:
        """Return Provider-owned Raw Evidence without exposing it downstream."""


@runtime_checkable
class EvidenceNormalizer(Protocol):
    normalizer_name: str
    normalizer_version: str

    def normalize(self, result: RawEvidenceSearchResult) -> EvidenceNormalizationResult:
        """Convert Provider payloads into the common Evidence Contract."""


@runtime_checkable
class EvidenceDeduplicator(Protocol):
    deduplicator_version: str

    def deduplicate(
        self,
        result: EvidenceNormalizationResult,
    ) -> EvidenceDeduplicationResult:
        """Merge matching DOI, PMID, URL, or highly similar title records."""


@runtime_checkable
class EvidenceRanker(Protocol):
    ranking_version: str

    def rank(self, result: EvidenceDeduplicationResult) -> EvidenceRankingResult:
        """Rank by Evidence Level before independent Information Priority."""


@runtime_checkable
class ClaimBuilder(Protocol):
    builder_name: str
    builder_version: str

    def build(
        self,
        subject_key: str,
        evidence: EvidenceBundle,
    ) -> ClaimBuildResult:
        """Build Claim candidates from the only allowed downstream Evidence object."""
