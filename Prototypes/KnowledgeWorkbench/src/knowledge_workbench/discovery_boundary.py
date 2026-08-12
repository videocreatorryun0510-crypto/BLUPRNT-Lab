"""Fail-closed validation preventing Discovery assets from entering formal flows."""

from __future__ import annotations

from enum import StrEnum

from knowledge_workbench.discovery_models import (
    DiscoveryCandidate,
    DiscoveryCandidateSet,
)


class DiscoveryBoundaryTarget(StrEnum):
    EVIDENCE_BUNDLE = "evidence_bundle"
    CLAIM_BUILDER = "claim_builder"
    PROMOTION = "promotion"
    REGISTRY = "registry"
    APPROVAL = "approval"


class DiscoveryBoundaryValidationError(ValueError):
    def __init__(self, target: DiscoveryBoundaryTarget) -> None:
        self.code = f"discovery_not_allowed_for_{target.value}"
        self.target = target
        super().__init__(
            "Discovery Candidateは正式Evidenceではないため、"
            f"{target.value}へ渡せません。専用Evidence Providerで正式取得してください。"
        )


DiscoveryAsset = DiscoveryCandidate | DiscoveryCandidateSet


def reject_discovery_asset(
    value: object,
    *,
    target: DiscoveryBoundaryTarget,
) -> None:
    """Reject both a candidate and a candidate set at every prohibited boundary."""

    if isinstance(value, (DiscoveryCandidate, DiscoveryCandidateSet)):
        raise DiscoveryBoundaryValidationError(target)


def validate_discovery_candidate(candidate: DiscoveryCandidate) -> None:
    """Defense in depth for data created outside Pydantic construction."""

    flags = (
        candidate.claim_eligible,
        candidate.evidence_bundle_eligible,
        candidate.promotion_allowed,
        candidate.registry_allowed,
        candidate.approval_allowed,
    )
    if any(flags):
        raise ValueError("Discovery Candidateの禁止フラグがfalseではありません。")
