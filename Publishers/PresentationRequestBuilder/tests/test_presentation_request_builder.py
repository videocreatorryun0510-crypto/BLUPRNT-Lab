import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.registry_v10 import RegistryEntityType, RegistryStatus
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from source_bundle_publisher import SourceBundle, SourceBundlePublisherAdapter

from presentation_request_builder import (
    PresentationRequestBuilder,
    PresentationRequestValidator,
    RequestMode,
)
from presentation_request_builder.profiles import PresentationProfileCatalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0"
SOURCE_PROFILES = REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
PRESENTATION_PROFILES = REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
NOW = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)


def _fixture(
    tmp_path: Path,
    *,
    example_name: str = "laboratory-test-item.example.json",
    status: RegistryStatus = RegistryStatus.DRAFT,
) -> tuple[
    SQLiteKnowledgeRegistry,
    object,
    SourceBundlePublisherAdapter,
    PresentationRequestBuilder,
    SourceBundle,
    str,
]:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    record = validate_knowledge_record(
        json.loads((EXAMPLES / example_name).read_text(encoding="utf-8"))
    )
    reconciled = registry.reconcile(
        record,
        actor="presentation_test",
        note="Presentation Contractテスト",
    )
    record = reconciled.record
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        SOURCE_PROFILES,
        tmp_path / "source_bundle",
        tmp_path / "logs" / "approval_gate.jsonl",
    )
    draft_publication = (
        source_publisher.publish(
            record,
            registry.view(record.knowledge_id),
            None,
            generated_at=NOW,
        )
        if status == RegistryStatus.DEPRECATED
        else None
    )
    if status != RegistryStatus.DRAFT:
        sequence = [
            RegistryStatus.OWNER_REVIEW,
            RegistryStatus.MEDICAL_REVIEW,
            RegistryStatus.APPROVED,
            RegistryStatus.PUBLISHED,
        ]
        if status == RegistryStatus.DEPRECATED:
            sequence = [RegistryStatus.DEPRECATED]
        for target in sequence:
            claim_ids = [item.claim_id for item in registry.view(record.knowledge_id).claims]
            registry.transition_claims_status(
                claim_ids,
                target,
                actor="medical_reviewer",
                note=f"{target.value}へ変更",
            )
            registry.transition_status(
                RegistryEntityType.KNOWLEDGE,
                record.knowledge_id,
                target,
                actor="medical_reviewer",
                note=f"{target.value}へ変更",
            )
            if target == status:
                break
    view = registry.view(record.knowledge_id)
    expected_fingerprint = source_publisher.source_fingerprint(record, view, None)
    if draft_publication is not None:
        publication_bundle = draft_publication.bundle.model_copy(
            update={
                "metadata": draft_publication.bundle.metadata.model_copy(
                    update={
                        "approval_state": RegistryStatus.DEPRECATED,
                        "source_fingerprint": expected_fingerprint,
                    }
                )
            }
        )
    else:
        publication_bundle = source_publisher.publish(
            record,
            view,
            None,
            generated_at=NOW,
        ).bundle
    builder = PresentationRequestBuilder.from_directories(
        PRESENTATION_PROFILES,
        tmp_path / "presentation_request",
        tmp_path / "logs" / "presentation_request.jsonl",
        source_publisher,
    )
    return (
        registry,
        record,
        source_publisher,
        builder,
        publication_bundle,
        expected_fingerprint,
    )


@pytest.mark.parametrize(
    "status",
    [
        RegistryStatus.DRAFT,
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ],
)
def test_preview_is_available_during_supported_review_states(
    tmp_path: Path,
    status: RegistryStatus,
) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(
        tmp_path,
        status=status,
    )

    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )

    assert result.status == "success"
    assert result.request is not None
    assert result.request.request_mode == RequestMode.PREVIEW
    assert result.output_path is not None
    assert Path(result.output_path).is_file()


@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        (RegistryStatus.DRAFT, False),
        (RegistryStatus.OWNER_REVIEW, False),
        (RegistryStatus.MEDICAL_REVIEW, False),
        (RegistryStatus.APPROVED, True),
        (RegistryStatus.PUBLISHED, False),
        (RegistryStatus.DEPRECATED, False),
    ],
)
def test_external_request_requires_current_approved_state(
    tmp_path: Path,
    status: RegistryStatus,
    allowed: bool,
) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(
        tmp_path,
        status=status,
    )

    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        request_mode=RequestMode.EXTERNAL,
        created_at=NOW,
    )

    assert (result.status == "success") is allowed
    assert (result.request is not None) is allowed
    if not allowed:
        assert result.output_path is None


def test_deprecated_preview_is_blocked(tmp_path: Path) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(
        tmp_path,
        status=RegistryStatus.DEPRECATED,
    )

    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )

    assert result.status == "blocked"
    assert result.decision.reason_code == "knowledge_deprecated"


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ("knowledge_version", "knowledge_version_mismatch"),
        ("fingerprint", "fingerprint_mismatch"),
        ("approval_state", "approval_state_changed"),
        ("review_version", "review_version_mismatch"),
    ],
)
def test_stale_source_is_blocked_with_specific_reason(
    tmp_path: Path,
    change: str,
    expected_code: str,
) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(tmp_path)
    changed_bundle = bundle
    current_view = registry.view(record.knowledge_id)
    expected = fingerprint
    if change == "knowledge_version":
        changed_bundle = bundle.model_copy(
            update={"metadata": bundle.metadata.model_copy(update={"version": 2})}
        )
    elif change == "fingerprint":
        expected = "f" * 64
    elif change == "approval_state":
        changed_bundle = bundle.model_copy(
            update={
                "metadata": bundle.metadata.model_copy(
                    update={"approval_state": RegistryStatus.OWNER_REVIEW}
                )
            }
        )
    else:
        changed_bundle = bundle.model_copy(
            update={"metadata": bundle.metadata.model_copy(update={"review_version": 2})}
        )

    result = builder.build(
        changed_bundle,
        current_view,
        expected_source_fingerprint=expected,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )

    assert result.status == "blocked"
    assert result.decision.reason_code == expected_code
    assert "source_bundle_stale" in result.decision.freshness.failure_codes
    assert expected_code in result.decision.freshness.failure_codes


@pytest.mark.parametrize(
    "example_name",
    [
        "laboratory-test-item.example.json",
        "disease.example.json",
    ],
)
def test_contract_preserves_traceability_without_copying_medical_assertions(
    tmp_path: Path,
    example_name: str,
) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(
        tmp_path,
        example_name=example_name,
    )
    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )

    assert result.request is not None
    request = result.request
    source_claim_ids = {item.claim_id for item in bundle.claims}
    assert set(request.content_policy.selected_claim_ids) == source_claim_ids
    assert set(request.content_policy.key_message_claim_ids).issubset(source_claim_ids)
    assert set(request.content_policy.diagram_request_ids) == {
        item.request_id for item in bundle.diagram_requests
    }
    assert set(request.content_policy.reference_ids) == {
        item.source_id for item in bundle.references
    }
    assert request.source.source_fingerprint == bundle.metadata.source_fingerprint
    assert request.content_policy.allow_medical_rephrasing is False
    assert request.content_policy.allow_medical_fact_addition is False
    request_json = json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
    assert all(item.assertion not in request_json for item in bundle.claims)


def test_validator_rejects_unknown_traceability_and_medical_changes(
    tmp_path: Path,
) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(tmp_path)
    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        created_at=NOW,
    )
    assert result.request is not None
    request = result.request.model_copy(
        update={
            "presentation": result.request.presentation.model_copy(
                update={
                    "presentation_type": "pdf_material",
                    "output_format": "pdf",
                }
            ),
            "content_policy": result.request.content_policy.model_copy(
                update={
                    "selected_claim_ids": ("clm_99999999",),
                    "key_message_claim_ids": ("clm_99999999",),
                    "diagram_request_ids": ("diagram.unknown.request",),
                    "allow_medical_rephrasing": True,
                    "allow_medical_fact_addition": True,
                }
            )
        }
    )
    profile = PresentationProfileCatalog.from_directory(PRESENTATION_PROFILES).resolve(
        "presentation_document_basic_v1", "1.0"
    )

    report = PresentationRequestValidator().validate(
        request,
        bundle,
        profile,
        fingerprint,
    )

    assert report.is_valid is False
    codes = {item.code for item in report.issues}
    assert {
        "selected_claim_unknown",
        "diagram_request_unknown",
        "presentation_type_not_enabled",
        "output_format_not_enabled",
        "medical_rephrasing_not_allowed",
        "medical_fact_addition_not_allowed",
    }.issubset(codes)


def test_audit_log_contains_no_claim_text_or_source_bundle(tmp_path: Path) -> None:
    registry, record, _, builder, bundle, fingerprint = _fixture(tmp_path)
    result = builder.build(
        bundle,
        registry.view(record.knowledge_id),
        expected_source_fingerprint=fingerprint,
        created_at=NOW,
    )

    audit_text = Path(result.audit_log_path).read_text(encoding="utf-8")
    assert "assertion" not in audit_text
    assert "claims" not in audit_text
    assert all(item.assertion not in audit_text for item in bundle.claims)
