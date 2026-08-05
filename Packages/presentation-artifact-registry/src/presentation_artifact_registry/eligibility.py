"""Knowledge–Artifact dual approval eligibility contract and evaluator."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from presentation_artifact import PresentationArtifact, artifact_fingerprint
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from presentation_artifact_registry.models import (
    ArtifactApprovalState,
    ArtifactRegistryEntry,
    ArtifactRegistryStatus,
)

Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RendererBlockReason(StrEnum):
    ARTIFACT_STATUS_NOT_ACTIVE = "artifact_status_not_active"
    ARTIFACT_NOT_APPROVED = "artifact_not_approved"
    KNOWLEDGE_NOT_APPROVED = "knowledge_not_approved"
    KNOWLEDGE_VERSION_MISMATCH = "knowledge_version_mismatch"
    REVIEW_VERSION_MISMATCH = "review_version_mismatch"
    SOURCE_FINGERPRINT_MISMATCH = "source_fingerprint_mismatch"
    ARTIFACT_FINGERPRINT_MISMATCH = "artifact_fingerprint_mismatch"
    CLAIM_NOT_APPROVED = "claim_not_approved"
    DEPRECATED_CLAIM_REDIRECT_UNRESOLVED = "deprecated_claim_redirect_unresolved"
    KNOWLEDGE_APPROVAL_CHANGED_AFTER_ARTIFACT_APPROVAL = (
        "knowledge_approval_changed_after_artifact_approval"
    )
    ARTIFACT_STALE = "artifact_stale"


class SourceClaimSnapshot(FrozenModel):
    """Current Registry facts needed to validate one Artifact claim reference."""

    claim_id: str
    claim_version: int = Field(ge=1)
    approval_state: str
    is_deleted: bool
    updated_at: datetime
    canonical_claim_id: str | None
    redirect_resolved: bool


class KnowledgeArtifactSourceSnapshot(FrozenModel):
    """Read-only current Knowledge state supplied to the Artifact boundary."""

    knowledge_id: str
    knowledge_version: int = Field(ge=1)
    approval_state: str
    review_version: int = Field(ge=1)
    source_fingerprint: Fingerprint
    knowledge_updated_at: datetime
    source_changed_at: datetime
    claims: tuple[SourceClaimSnapshot, ...]


class ClaimApprovalResult(FrozenModel):
    referenced_claim_id: str
    canonical_claim_id: str | None
    approval_state: str | None
    approved_and_current: bool
    redirect_required: bool
    redirect_resolved: bool


class RendererEligibility(FrozenModel):
    """Derived renderer eligibility; it never mutates either Registry."""

    eligible: bool
    primary_reason: str | None
    reasons: tuple[str, ...]
    evaluated_at: datetime
    artifact_approval_state: ArtifactApprovalState
    source_knowledge_approval_state: str
    artifact_review_result: Literal["passed", "blocked"]
    renderer_eligibility: Literal["eligible", "ineligible"]
    artifact_status_active: bool
    artifact_approval_valid: bool
    knowledge_approval_valid: bool
    knowledge_version_matches: bool
    review_version_matches: bool
    source_fingerprint_matches: bool
    artifact_fingerprint_valid: bool
    claim_approval_valid: bool
    deprecated_claim_redirects_resolved: bool
    knowledge_unchanged_after_artifact_approval: bool
    artifact_stale: bool
    claim_results: tuple[ClaimApprovalResult, ...]


def evaluate_renderer_eligibility(
    entry: ArtifactRegistryEntry,
    artifact: PresentationArtifact,
    source: KnowledgeArtifactSourceSnapshot,
    *,
    artifact_approved_at: datetime | None,
    evaluated_at: datetime | None = None,
    approval_state_override: ArtifactApprovalState | None = None,
) -> RendererEligibility:
    """Apply every Knowledge and Artifact gate as one explicit AND decision."""

    timestamp = evaluated_at or datetime.now(UTC)
    artifact_approval_state = approval_state_override or entry.approval_state
    artifact_status_active = entry.status == ArtifactRegistryStatus.ACTIVE
    artifact_approval_valid = artifact_approval_state == ArtifactApprovalState.APPROVED
    knowledge_approval_valid = source.approval_state == "approved"
    knowledge_version_matches = (
        entry.knowledge_version == source.knowledge_version
        and artifact.source.knowledge_version == source.knowledge_version
    )
    review_version_matches = entry.source_review_version == source.review_version
    source_fingerprint_matches = artifact.source.source_fingerprint == source.source_fingerprint
    artifact_fingerprint_valid = (
        artifact.metadata.fingerprint == entry.fingerprint
        and artifact_fingerprint(artifact) == entry.fingerprint
    )

    claims_by_id = {item.claim_id: item for item in source.claims}
    claim_results: list[ClaimApprovalResult] = []
    for referenced in artifact.claim_catalog:
        current = claims_by_id.get(referenced.claim_id)
        if current is None:
            claim_results.append(
                ClaimApprovalResult(
                    referenced_claim_id=referenced.claim_id,
                    canonical_claim_id=None,
                    approval_state=None,
                    approved_and_current=False,
                    redirect_required=False,
                    redirect_resolved=False,
                )
            )
            continue
        redirect_required = current.approval_state == "deprecated" or current.is_deleted
        expected_claim_version = entry.source_claim_versions.get(referenced.claim_id)
        approved_and_current = (
            current.approval_state == "approved"
            and not current.is_deleted
            and current.canonical_claim_id == current.claim_id
            and expected_claim_version == current.claim_version
        )
        claim_results.append(
            ClaimApprovalResult(
                referenced_claim_id=referenced.claim_id,
                canonical_claim_id=current.canonical_claim_id,
                approval_state=current.approval_state,
                approved_and_current=approved_and_current,
                redirect_required=redirect_required,
                redirect_resolved=(current.redirect_resolved if redirect_required else True),
            )
        )
    claim_approval_valid = bool(claim_results) and all(
        item.approved_and_current for item in claim_results
    )
    deprecated_claim_redirects_resolved = all(
        not item.redirect_required or item.redirect_resolved for item in claim_results
    )
    knowledge_unchanged = (
        artifact_approved_at is None or source.source_changed_at <= artifact_approved_at
    )

    reasons: list[str] = []
    if not artifact_status_active:
        reasons.append(RendererBlockReason.ARTIFACT_STATUS_NOT_ACTIVE.value)
    if not artifact_approval_valid:
        reasons.append(RendererBlockReason.ARTIFACT_NOT_APPROVED.value)
    if not knowledge_approval_valid:
        reasons.append(RendererBlockReason.KNOWLEDGE_NOT_APPROVED.value)
    if not knowledge_version_matches:
        reasons.append(RendererBlockReason.KNOWLEDGE_VERSION_MISMATCH.value)
    if not review_version_matches:
        reasons.append(RendererBlockReason.REVIEW_VERSION_MISMATCH.value)
    if not source_fingerprint_matches:
        reasons.append(RendererBlockReason.SOURCE_FINGERPRINT_MISMATCH.value)
    if not artifact_fingerprint_valid:
        reasons.append(RendererBlockReason.ARTIFACT_FINGERPRINT_MISMATCH.value)
    if not claim_approval_valid:
        reasons.append(RendererBlockReason.CLAIM_NOT_APPROVED.value)
    if not deprecated_claim_redirects_resolved:
        reasons.append(RendererBlockReason.DEPRECATED_CLAIM_REDIRECT_UNRESOLVED.value)
    if not knowledge_unchanged:
        reasons.append(RendererBlockReason.KNOWLEDGE_APPROVAL_CHANGED_AFTER_ARTIFACT_APPROVAL.value)

    stale = not all(
        (
            knowledge_version_matches,
            review_version_matches,
            source_fingerprint_matches,
            artifact_fingerprint_valid,
            claim_approval_valid,
            deprecated_claim_redirects_resolved,
            knowledge_unchanged,
        )
    )
    if stale:
        reasons.append(RendererBlockReason.ARTIFACT_STALE.value)
    unique_reasons = tuple(dict.fromkeys(reasons))
    eligible = not unique_reasons
    artifact_review_passed = (
        artifact_status_active
        and artifact_approval_valid
        and artifact_fingerprint_valid
    )
    return RendererEligibility(
        eligible=eligible,
        primary_reason=unique_reasons[0] if unique_reasons else None,
        reasons=unique_reasons,
        evaluated_at=timestamp,
        artifact_approval_state=artifact_approval_state,
        source_knowledge_approval_state=source.approval_state,
        artifact_review_result=(
            "passed" if artifact_review_passed else "blocked"
        ),
        renderer_eligibility="eligible" if eligible else "ineligible",
        artifact_status_active=artifact_status_active,
        artifact_approval_valid=artifact_approval_valid,
        knowledge_approval_valid=knowledge_approval_valid,
        knowledge_version_matches=knowledge_version_matches,
        review_version_matches=review_version_matches,
        source_fingerprint_matches=source_fingerprint_matches,
        artifact_fingerprint_valid=artifact_fingerprint_valid,
        claim_approval_valid=claim_approval_valid,
        deprecated_claim_redirects_resolved=deprecated_claim_redirects_resolved,
        knowledge_unchanged_after_artifact_approval=knowledge_unchanged,
        artifact_stale=stale,
        claim_results=tuple(claim_results),
    )
