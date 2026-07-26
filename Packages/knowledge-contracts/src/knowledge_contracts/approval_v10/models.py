"""Provider-neutral Approval Contract Version 1.0."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from knowledge_contracts.registry_v10 import (
    ApprovalState,
    KnowledgeRegistryEntry,
)
from knowledge_contracts.v10.models import KnowledgeId, ShortText, StrictModel


class ApprovalGateAction(StrEnum):
    PUBLISH = "publish"
    EXTERNAL_AI_SEND = "external_ai_send"


class ApprovalSnapshot(StrictModel):
    """The approval facts projected from the Registry without changing it."""

    approval_contract_version: Literal["1.0"] = "1.0"
    knowledge_id: KnowledgeId
    approval_state: ApprovalState
    approved_at: datetime | None = None
    approved_by: ShortText | None = None
    review_version: int = Field(ge=1)
    review_required: bool


class ApprovalGateDecision(StrictModel):
    """One auditable, provider-independent eligibility decision."""

    approval_contract_version: Literal["1.0"] = "1.0"
    knowledge_id: KnowledgeId
    action: ApprovalGateAction
    approval_state: ApprovalState
    allowed: bool
    reason_code: Literal[
        "approval_granted",
        "approval_required",
        "published_state_not_enabled",
        "knowledge_deprecated",
    ]
    reason: ShortText
    review_version: int = Field(ge=1)
    evaluated_at: datetime


class ApprovalContractDescriptor(StrictModel):
    """Machine-readable state and gate policy shared by every client."""

    approval_contract_version: Literal["1.0"] = "1.0"
    state_sequence: tuple[ApprovalState, ...]
    compatibility_states: tuple[ApprovalState, ...]
    allowed_transitions: dict[ApprovalState, tuple[ApprovalState, ...]]
    publishable_states: tuple[ApprovalState, ...]
    external_ai_sendable_states: tuple[ApprovalState, ...]


def approval_snapshot_from_registry(
    knowledge: KnowledgeRegistryEntry,
) -> ApprovalSnapshot:
    """Project the latest approval evidence from one Registry entry."""

    approved_decisions = [
        item for item in knowledge.approval if item.status == ApprovalState.APPROVED
    ]
    latest_approval = approved_decisions[-1] if approved_decisions else None
    return ApprovalSnapshot(
        knowledge_id=knowledge.knowledge_id,
        approval_state=knowledge.status,
        approved_at=(
            latest_approval.decided_at if latest_approval is not None else None
        ),
        approved_by=latest_approval.actor if latest_approval is not None else None,
        review_version=knowledge.knowledge_version,
        review_required=knowledge.status
        not in {ApprovalState.APPROVED, ApprovalState.PUBLISHED},
    )
