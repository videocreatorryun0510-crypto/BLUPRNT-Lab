from datetime import UTC, datetime

from knowledge_contracts.approval_v10 import (
    ApprovalGateAction,
    ApprovalState,
    approval_contract,
    approval_contract_json_schema,
    approval_snapshot_from_registry,
    approval_transition_is_allowed,
    evaluate_approval_gate,
)
from knowledge_contracts.registry_v10 import ApprovalDecision, KnowledgeRegistryEntry


def _knowledge(state: ApprovalState) -> KnowledgeRegistryEntry:
    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    approval = (
        [
            ApprovalDecision(
                status=ApprovalState.APPROVED,
                actor="medical_reviewer",
                decided_at=now,
                note="医学監修完了",
            )
        ]
        if state in {ApprovalState.APPROVED, ApprovalState.PUBLISHED}
        else []
    )
    return KnowledgeRegistryEntry(
        knowledge_id="knw_approval_test1",
        registry_key="approval-test",
        canonical_name="承認テスト",
        knowledge_version=3,
        status=state,
        created_at=now,
        updated_at=now,
        aliases=[],
        approval=approval,
    )


def test_approval_contract_fixes_state_order_and_reversible_adjacent_steps() -> None:
    contract = approval_contract()

    assert [item.value for item in contract.state_sequence] == [
        "draft",
        "owner_review",
        "medical_review",
        "approved",
        "published",
    ]
    assert approval_transition_is_allowed(
        ApprovalState.APPROVED, ApprovalState.MEDICAL_REVIEW
    )
    assert approval_transition_is_allowed(
        ApprovalState.APPROVED, ApprovalState.PUBLISHED
    )
    assert not approval_transition_is_allowed(
        ApprovalState.DRAFT, ApprovalState.APPROVED
    )
    assert approval_contract_json_schema()["$id"].endswith("/1.0")


def test_approval_snapshot_keeps_review_evidence() -> None:
    snapshot = approval_snapshot_from_registry(_knowledge(ApprovalState.APPROVED))

    assert snapshot.approval_state == ApprovalState.APPROVED
    assert snapshot.approved_by == "medical_reviewer"
    assert snapshot.approved_at == datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    assert snapshot.review_version == 3
    assert snapshot.review_required is False


def test_gate_allows_only_approved_state() -> None:
    approved = approval_snapshot_from_registry(_knowledge(ApprovalState.APPROVED))
    draft = approval_snapshot_from_registry(_knowledge(ApprovalState.DRAFT))
    published = approval_snapshot_from_registry(_knowledge(ApprovalState.PUBLISHED))

    assert evaluate_approval_gate(
        approved, ApprovalGateAction.EXTERNAL_AI_SEND
    ).allowed
    assert not evaluate_approval_gate(draft, ApprovalGateAction.PUBLISH).allowed
    published_decision = evaluate_approval_gate(
        published, ApprovalGateAction.EXTERNAL_AI_SEND
    )
    assert published_decision.allowed is False
    assert published_decision.reason_code == "published_state_not_enabled"
