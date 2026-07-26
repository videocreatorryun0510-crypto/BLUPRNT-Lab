"""Approval state transition and gate policy Version 1.0."""

from datetime import UTC, datetime
from typing import Literal

from knowledge_contracts.approval_v10.models import (
    ApprovalContractDescriptor,
    ApprovalGateAction,
    ApprovalGateDecision,
    ApprovalSnapshot,
)
from knowledge_contracts.registry_v10 import ApprovalState


_TRANSITIONS: dict[ApprovalState, frozenset[ApprovalState]] = {
    ApprovalState.DRAFT: frozenset(
        {ApprovalState.OWNER_REVIEW, ApprovalState.DEPRECATED}
    ),
    ApprovalState.OWNER_REVIEW: frozenset(
        {
            ApprovalState.DRAFT,
            ApprovalState.MEDICAL_REVIEW,
            ApprovalState.DEPRECATED,
        }
    ),
    ApprovalState.MEDICAL_REVIEW: frozenset(
        {
            ApprovalState.OWNER_REVIEW,
            ApprovalState.APPROVED,
            ApprovalState.DEPRECATED,
        }
    ),
    ApprovalState.APPROVED: frozenset(
        {
            ApprovalState.MEDICAL_REVIEW,
            ApprovalState.PUBLISHED,
            ApprovalState.DEPRECATED,
        }
    ),
    ApprovalState.PUBLISHED: frozenset(
        {ApprovalState.APPROVED, ApprovalState.DEPRECATED}
    ),
    ApprovalState.DEPRECATED: frozenset({ApprovalState.DRAFT}),
}


def approval_contract() -> ApprovalContractDescriptor:
    return ApprovalContractDescriptor(
        state_sequence=(
            ApprovalState.DRAFT,
            ApprovalState.OWNER_REVIEW,
            ApprovalState.MEDICAL_REVIEW,
            ApprovalState.APPROVED,
            ApprovalState.PUBLISHED,
        ),
        compatibility_states=(ApprovalState.DEPRECATED,),
        allowed_transitions={
            state: tuple(sorted(targets, key=lambda item: item.value))
            for state, targets in _TRANSITIONS.items()
        },
        publishable_states=(ApprovalState.APPROVED,),
        external_ai_sendable_states=(ApprovalState.APPROVED,),
    )


def approval_transition_is_allowed(
    current: ApprovalState,
    target: ApprovalState,
) -> bool:
    return target in _TRANSITIONS[current]


def evaluate_approval_gate(
    snapshot: ApprovalSnapshot,
    action: ApprovalGateAction,
    *,
    evaluated_at: datetime | None = None,
) -> ApprovalGateDecision:
    timestamp = evaluated_at or datetime.now(UTC)
    if snapshot.approval_state == ApprovalState.APPROVED:
        return ApprovalGateDecision(
            knowledge_id=snapshot.knowledge_id,
            action=action,
            approval_state=snapshot.approval_state,
            allowed=True,
            reason_code="approval_granted",
            reason="医学監修を含む承認が完了しています。",
            review_version=snapshot.review_version,
            evaluated_at=timestamp,
        )
    reason_code: Literal[
        "approval_required",
        "published_state_not_enabled",
        "knowledge_deprecated",
    ]
    if snapshot.approval_state == ApprovalState.DEPRECATED:
        reason_code = "knowledge_deprecated"
        reason = "廃止済みKnowledgeは公開・外部送信できません。"
    elif snapshot.approval_state == ApprovalState.PUBLISHED:
        reason_code = "published_state_not_enabled"
        reason = "published状態の再公開・再送信は将来の運用で定義します。"
    else:
        reason_code = "approval_required"
        reason = (
            f"現在の承認状態は{snapshot.approval_state.value}です。"
            "approvedになるまで公開・外部送信できません。"
        )
    return ApprovalGateDecision(
        knowledge_id=snapshot.knowledge_id,
        action=action,
        approval_state=snapshot.approval_state,
        allowed=False,
        reason_code=reason_code,
        reason=reason,
        review_version=snapshot.review_version,
        evaluated_at=timestamp,
    )
