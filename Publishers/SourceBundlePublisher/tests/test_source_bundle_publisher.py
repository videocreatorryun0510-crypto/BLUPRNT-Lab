import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.registry_v10 import RegistryEntityType, RegistryStatus
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry

from source_bundle_publisher import (
    SourceBundlePublisherAdapter,
    SourceBundlePublisherError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0"
PROFILES = (
    REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
)
GENERATED_AT = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("example_name", "expected_title", "expected_claim_count", "diagram_title"),
    [
        (
            "laboratory-test-item.example.json",
            "フェリチン",
            11,
            "鉄代謝の概略図",
        ),
        (
            "disease.example.json",
            "鉄欠乏性貧血",
            17,
            "鉄欠乏による赤血球形成低下",
        ),
    ],
)
def test_publish_source_bundle_without_mutating_ssot(
    tmp_path: Path,
    example_name: str,
    expected_title: str,
    expected_claim_count: int,
    diagram_title: str,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    source = validate_knowledge_record(
        json.loads((EXAMPLES / example_name).read_text(encoding="utf-8"))
    )
    reconciled = registry.reconcile(
        source,
        actor="source_bundle_test",
        note="Source Bundle用の読取元を登録",
    )
    record = reconciled.record
    view = reconciled.view
    knowledge_before = record.model_dump(mode="json")
    registry_before = registry.snapshot().model_dump(mode="json")
    publisher = SourceBundlePublisherAdapter.from_directories(
        PROFILES,
        tmp_path / "source_bundle",
    )

    publication = publisher.publish(
        record,
        view,
        None,
        generated_at=GENERATED_AT,
    )

    bundle = publication.bundle
    assert bundle.title == expected_title
    assert len(bundle.claims) == expected_claim_count
    assert bundle.exam_points == ()
    assert bundle.diagram_requests[0].title == diagram_title
    assert {item.claim_id for item in bundle.key_messages}.issubset(
        {item.claim_id for item in bundle.claims}
    )
    assert all(
        item.assertion
        in {claim.assertion for claim in view.claims}
        for item in (*bundle.claims, *bundle.key_messages)
    )
    assert bundle.metadata.status.value == "draft"
    assert bundle.metadata.approval_state.value == "draft"
    assert bundle.metadata.approved_at is None
    assert bundle.metadata.approved_by is None
    assert bundle.metadata.review_version == 1
    assert bundle.metadata.review_required is True
    assert bundle.metadata.publisher_version == "1.1.0"
    assert publication.output_path.is_file()
    stored = json.loads(publication.output_path.read_text(encoding="utf-8"))
    assert stored == bundle.model_dump(mode="json")
    assert record.model_dump(mode="json") == knowledge_before
    assert registry.snapshot().model_dump(mode="json") == registry_before


def test_unsupported_knowledge_is_rejected_without_output(tmp_path: Path) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    gram = validate_knowledge_record(
        json.loads(
            (EXAMPLES / "staining-method.example.json").read_text(encoding="utf-8")
        )
    )
    reconciled = registry.reconcile(
        gram,
        actor="source_bundle_test",
        note="非対応Knowledgeの確認",
    )
    publisher = SourceBundlePublisherAdapter.from_directories(
        PROFILES,
        tmp_path / "source_bundle",
    )

    with pytest.raises(SourceBundlePublisherError, match="フェリチン"):
        publisher.publish(reconciled.record, reconciled.view, None)

    assert not (tmp_path / "source_bundle").exists()


def test_approval_gate_is_audited_and_allows_only_approved_registry(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    source = validate_knowledge_record(
        json.loads(
            (EXAMPLES / "laboratory-test-item.example.json").read_text(
                encoding="utf-8"
            )
        )
    )
    reconciled = registry.reconcile(
        source,
        actor="source_bundle_test",
        note="Approval Gateテスト",
    )
    publisher = SourceBundlePublisherAdapter.from_directories(
        PROFILES,
        tmp_path / "source_bundle",
        tmp_path / "publisher_logs" / "approval_gate.jsonl",
    )

    draft_publish = publisher.can_publish(
        reconciled.view,
        evaluated_at=GENERATED_AT,
    )
    draft_send = publisher.can_send_to_external_ai(
        reconciled.view,
        evaluated_at=GENERATED_AT,
    )
    assert draft_publish.allowed is False
    assert draft_send.allowed is False

    claim_ids = [item.claim_id for item in reconciled.view.claims]
    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        registry.transition_claims_status(
            claim_ids,
            status,
            actor="medical_reviewer",
            note="全Claim確認",
        )
        registry.transition_status(
            RegistryEntityType.KNOWLEDGE,
            source.knowledge_id,
            status,
            actor="medical_reviewer",
            note="Knowledge確認",
        )

    approved_view = registry.view(source.knowledge_id)
    approved_send = publisher.can_send_to_external_ai(
        approved_view,
        evaluated_at=GENERATED_AT,
    )
    assert approved_send.allowed is True
    assert approved_send.reason_code == "approval_granted"

    publication = publisher.publish(
        reconciled.record,
        approved_view,
        None,
        generated_at=GENERATED_AT,
    )
    assert publication.bundle.metadata.approval_state == RegistryStatus.APPROVED
    assert publication.bundle.metadata.approved_by == "medical_reviewer"
    assert publication.bundle.metadata.review_required is False

    audit_records = [
        json.loads(line)
        for line in publisher.audit_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [item["action"] for item in audit_records] == [
        "publish",
        "external_ai_send",
        "external_ai_send",
    ]
    assert [item["allowed"] for item in audit_records] == [False, False, True]
