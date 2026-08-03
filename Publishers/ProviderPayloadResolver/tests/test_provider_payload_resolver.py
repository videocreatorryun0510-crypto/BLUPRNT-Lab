import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.registry_v10 import (
    ClaimMergeRedirect,
    RegistryEntityType,
    RegistryKnowledgeView,
    RegistryStatus,
)
from knowledge_contracts.v10 import KnowledgeRecord, validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_request_builder import (
    PresentationRequest,
    PresentationRequestBuilder,
    RequestMode,
)
from source_bundle_publisher import SourceBundle, SourceBundlePublisherAdapter

from provider_payload_resolver import (
    DataEgressPolicyValidator,
    ProviderPayloadResolver,
    TraceableResponseService,
    TraceableResponseValidator,
    build_dummy_traceable_response,
    presentation_payload_fingerprint,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = (
    REPOSITORY_ROOT
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "laboratory-test-item.example.json"
)
SOURCE_PROFILES = REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
REQUEST_PROFILES = (
    REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
)
NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class ApprovedFixture:
    record: KnowledgeRecord
    registry: RegistryKnowledgeView
    source_publisher: SourceBundlePublisherAdapter
    bundle: SourceBundle
    request: PresentationRequest
    resolver: ProviderPayloadResolver


def _approved_fixture(tmp_path: Path) -> ApprovedFixture:
    registry_store = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    record = validate_knowledge_record(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    record = registry_store.reconcile(
        record,
        actor="payload_test",
        note="Provider Payloadテスト",
    ).record
    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        claim_ids = [item.claim_id for item in registry_store.view(record.knowledge_id).claims]
        registry_store.transition_claims_status(
            claim_ids,
            status,
            actor="medical_reviewer",
            note="承認済みFixture",
        )
        registry_store.transition_status(
            RegistryEntityType.KNOWLEDGE,
            record.knowledge_id,
            status,
            actor="medical_reviewer",
            note="承認済みFixture",
        )
    view = registry_store.view(record.knowledge_id)
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        SOURCE_PROFILES,
        tmp_path / "source_bundle",
        tmp_path / "logs" / "approval_gate.jsonl",
    )
    publication = source_publisher.publish(record, view, None, generated_at=NOW)
    builder = PresentationRequestBuilder.from_directories(
        REQUEST_PROFILES,
        tmp_path / "presentation_request",
        tmp_path / "logs" / "presentation_request.jsonl",
        source_publisher,
    )
    build = builder.build(
        publication.bundle,
        view,
        expected_source_fingerprint=publication.bundle.metadata.source_fingerprint,
        request_mode=RequestMode.EXTERNAL,
        created_at=NOW,
    )
    assert build.request is not None
    resolver = ProviderPayloadResolver.from_directories(
        source_publisher,
        tmp_path / "provider_payload",
        tmp_path / "logs" / "provider_payload.jsonl",
    )
    return ApprovedFixture(
        record,
        view,
        source_publisher,
        publication.bundle,
        build.request,
        resolver,
    )


def _resolve(fixture: ApprovedFixture, **kwargs: object):
    return fixture.resolver.resolve(
        fixture.request,
        fixture.bundle,
        fixture.registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
        **kwargs,
    )


def test_resolves_exact_approved_claims_in_deterministic_order(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    result = _resolve(fixture)

    assert result.status == "success"
    assert result.payload is not None
    payload = result.payload
    expected_ids = fixture.request.content_policy.selected_claim_ids
    assert tuple(item.claim_id for item in payload.medical_content.selected_claims) == (
        expected_ids
    )
    registry_claims = {item.claim_id: item for item in fixture.registry.claims}
    for item in payload.medical_content.selected_claims:
        assert item.exact_text == registry_claims[item.claim_id].assertion
        assert item.claim_key == registry_claims[item.claim_id].claim_key
        assert item.approval_state == "approved"
    assert result.external_use_allowed is True
    assert result.validation.is_valid is True
    assert Path(result.output_path or "").is_file()


def test_resolves_key_messages_diagrams_references_and_trace_maps(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    result = _resolve(fixture)
    assert result.payload is not None
    payload = result.payload

    assert tuple(item.claim_id for item in payload.medical_content.key_messages) == (
        fixture.request.content_policy.key_message_claim_ids
    )
    selected = {item.claim_id for item in payload.medical_content.selected_claims}
    assert {item.claim_id for item in payload.medical_content.key_messages}.issubset(selected)
    assert all(
        set(item.source_claim_ids).issubset(selected)
        for item in payload.visual_content.diagram_requests
    )
    assert all(
        set(item.supported_claim_ids).issubset(selected)
        for item in payload.medical_content.references
    )
    assert len(payload.traceability.claim_trace_map) == len(selected)
    assert len(payload.traceability.diagram_trace_map) == len(
        payload.visual_content.diagram_requests
    )
    assert len(payload.traceability.reference_trace_map) == len(
        payload.medical_content.references
    )


def test_payload_contains_no_unselected_claim(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    first = fixture.request.content_policy.selected_claim_ids[0]
    request = fixture.request.model_copy(
        update={
            "content_policy": fixture.request.content_policy.model_copy(
                update={
                    "use_all_claims": False,
                    "selected_claim_ids": (first,),
                    "key_message_claim_ids": (),
                    "diagram_request_ids": (),
                    "reference_ids": (),
                    "include_references": False,
                    "include_exam_points": False,
                }
            )
        }
    )
    result = fixture.resolver.resolve(
        request,
        fixture.bundle,
        fixture.registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )

    assert result.payload is not None
    assert tuple(item.claim_id for item in result.payload.medical_content.selected_claims) == (
        first,
    )
    payload_text = result.payload.model_dump_json()
    for claim_id in fixture.request.content_policy.selected_claim_ids[1:]:
        assert claim_id not in payload_text


@pytest.mark.parametrize(
    "status",
    [
        RegistryStatus.DRAFT,
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.PUBLISHED,
        RegistryStatus.DEPRECATED,
    ],
)
def test_only_approved_state_can_build_payload(
    tmp_path: Path,
    status: RegistryStatus,
) -> None:
    fixture = _approved_fixture(tmp_path)
    registry = fixture.registry.model_copy(
        update={
            "knowledge": fixture.registry.knowledge.model_copy(update={"status": status}),
            "claims": [
                item.model_copy(update={"status": status})
                for item in fixture.registry.claims
            ],
        }
    )
    bundle = fixture.bundle.model_copy(
        update={"metadata": fixture.bundle.metadata.model_copy(update={"approval_state": status})}
    )
    request = fixture.request.model_copy(
        update={"source": fixture.request.source.model_copy(update={"approval_state": status})}
    )
    result = fixture.resolver.resolve(
        request,
        bundle,
        registry,
        None,
        expected_source_fingerprint=bundle.metadata.source_fingerprint,
        created_at=NOW,
    )

    assert result.status == "blocked"
    assert result.payload is None
    assert result.external_use_allowed is False


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("knowledge_version", 99, "knowledge_version_mismatch"),
        ("source_fingerprint", "f" * 64, "source_fingerprint_mismatch"),
        ("review_version", 99, "review_version_mismatch"),
    ],
)
def test_stale_source_blocks_payload(
    tmp_path: Path,
    field: str,
    value: object,
    expected_code: str,
) -> None:
    fixture = _approved_fixture(tmp_path)
    request = fixture.request.model_copy(
        update={"source": fixture.request.source.model_copy(update={field: value})}
    )
    result = fixture.resolver.resolve(
        request,
        fixture.bundle,
        fixture.registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )

    assert result.status == "blocked"
    assert expected_code in {item.code for item in result.validation.issues}
    assert result.validation.stale_check_result is False


@pytest.mark.parametrize(
    ("unsafe_text", "expected_code"),
    [
        ("API_KEY=secret-value", "secret_detected"),
        ("設定は .env に保存", "secret_detected"),
        ("/Users/example/private.txt", "local_absolute_path_detected"),
        ("registry.sqlite3", "database_file_reference_detected"),
        ("owner@example.com", "personal_data_detected"),
    ],
)
def test_data_egress_policy_blocks_unsafe_claim_text(
    tmp_path: Path,
    unsafe_text: str,
    expected_code: str,
) -> None:
    fixture = _approved_fixture(tmp_path)
    changed = fixture.registry.claims[0].model_copy(update={"assertion": unsafe_text})
    registry = fixture.registry.model_copy(
        update={"claims": [changed, *fixture.registry.claims[1:]]}
    )
    result = fixture.resolver.resolve(
        fixture.request,
        fixture.bundle,
        registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )

    assert result.status == "blocked"
    assert expected_code in {item.code for item in result.validation.issues}


def test_payload_fingerprint_is_deterministic_and_changes_with_content(
    tmp_path: Path,
) -> None:
    fixture = _approved_fixture(tmp_path)
    first = _resolve(fixture)
    second = _resolve(fixture)
    assert first.payload is not None and second.payload is not None
    assert first.payload.metadata.payload_fingerprint == (
        second.payload.metadata.payload_fingerprint
    )

    changed_claim = fixture.registry.claims[0].model_copy(
        update={
            "assertion": fixture.registry.claims[0].assertion + "（監修済み改訂）",
            "claim_version": fixture.registry.claims[0].claim_version + 1,
        }
    )
    changed_registry = fixture.registry.model_copy(
        update={"claims": [changed_claim, *fixture.registry.claims[1:]]}
    )
    changed = fixture.resolver.resolve(
        fixture.request,
        fixture.bundle,
        changed_registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )
    assert changed.payload is not None
    assert changed.payload.metadata.payload_fingerprint != (
        first.payload.metadata.payload_fingerprint
    )


def test_deprecated_selected_claim_uses_current_redirect_target(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    target = fixture.registry.claims[0]
    source_id = "clm_deprecated_source"
    source = target.model_copy(
        update={
            "claim_id": source_id,
            "claim_key": "ferritin.deprecated_source",
            "status": RegistryStatus.DEPRECATED,
            "fact_payload": {**target.fact_payload, "claim_id": source_id},
        }
    )
    redirect = ClaimMergeRedirect(
        source_claim_id=source.claim_id,
        source_claim_key=source.claim_key,
        target_claim_id=target.claim_id,
        target_claim_key=target.claim_key,
        merged_at=NOW,
        actor="medical_reviewer",
        comment="同義Claim統合",
    )
    registry = fixture.registry.model_copy(
        update={
            "claims": [source, *fixture.registry.claims],
            "merge_redirects": [redirect, *fixture.registry.merge_redirects],
        }
    )
    source_bundle_claim = fixture.bundle.claims[0].model_copy(
        update={
            "claim_id": source.claim_id,
            "claim_key": source.claim_key,
            "assertion": source.assertion,
        }
    )
    bundle = fixture.bundle.model_copy(
        update={"claims": (source_bundle_claim, *fixture.bundle.claims)}
    )
    request = fixture.request.model_copy(
        update={
            "content_policy": fixture.request.content_policy.model_copy(
                update={
                    "use_all_claims": False,
                    "selected_claim_ids": (source.claim_id,),
                    "key_message_claim_ids": (),
                    "diagram_request_ids": (),
                    "reference_ids": (),
                    "include_references": False,
                    "include_exam_points": False,
                }
            )
        }
    )
    result = fixture.resolver.resolve(
        request,
        bundle,
        registry,
        None,
        expected_source_fingerprint=bundle.metadata.source_fingerprint,
        created_at=NOW,
    )

    assert result.payload is not None
    resolved = result.payload.medical_content.selected_claims[0]
    assert resolved.claim_id == target.claim_id
    assert resolved.claim_key == target.claim_key
    assert resolved.exact_text == target.assertion


def test_request_change_changes_payload_fingerprint(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    original = _resolve(fixture)
    request = fixture.request.model_copy(
        update={
            "presentation": fixture.request.presentation.model_copy(
                update={"title": fixture.request.presentation.title + " 学習版"}
            )
        }
    )
    changed = fixture.resolver.resolve(
        request,
        fixture.bundle,
        fixture.registry,
        None,
        expected_source_fingerprint=fixture.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )
    assert original.payload is not None and changed.payload is not None
    assert original.payload.metadata.payload_fingerprint != (
        changed.payload.metadata.payload_fingerprint
    )


def test_dummy_response_is_traceable_and_contains_no_medical_body(tmp_path: Path) -> None:
    result = _resolve(_approved_fixture(tmp_path))
    assert result.payload is not None
    response = build_dummy_traceable_response(result.payload, executed_at=NOW)
    service = TraceableResponseService.from_directories(
        tmp_path / "presentation_response",
        tmp_path / "logs" / "presentation_response.jsonl",
    )
    accepted = service.accept(result.payload, response, validated_at=NOW)

    assert accepted.status == "accepted"
    assert accepted.response.execution.status.value == "completed"
    assert accepted.response.validation.is_valid is True
    assert set(accepted.response.traceability.used_claim_ids) == {
        item.claim_id for item in result.payload.medical_content.selected_claims
    }
    response_text = accepted.response.model_dump_json()
    for claim in result.payload.medical_content.selected_claims:
        assert claim.exact_text not in response_text
    assert Path(accepted.output_path).is_file()


def test_response_validator_rejects_unknown_claim_and_fingerprint(tmp_path: Path) -> None:
    result = _resolve(_approved_fixture(tmp_path))
    assert result.payload is not None
    response = build_dummy_traceable_response(result.payload, executed_at=NOW)
    bad_trace = response.traceability.model_copy(
        update={"used_claim_ids": (*response.traceability.used_claim_ids, "clm_unknown_claim")}
    )
    bad_response = response.model_copy(
        update={
            "request": response.request.model_copy(
                update={"payload_fingerprint": "f" * 64}
            ),
            "traceability": bad_trace,
        }
    )
    validation = TraceableResponseValidator().validate(result.payload, bad_response)

    assert validation.is_valid is False
    assert validation.fingerprint_result is False
    assert validation.claim_traceability_result is False


def test_response_validator_rejects_unknown_reference(tmp_path: Path) -> None:
    result = _resolve(_approved_fixture(tmp_path))
    assert result.payload is not None
    response = build_dummy_traceable_response(result.payload, executed_at=NOW)
    bad_response = response.model_copy(
        update={
            "traceability": response.traceability.model_copy(
                update={
                    "used_reference_ids": (
                        *response.traceability.used_reference_ids,
                        "src_unknown_reference",
                    )
                }
            )
        }
    )

    validation = TraceableResponseValidator().validate(result.payload, bad_response)
    assert validation.is_valid is False
    assert validation.reference_traceability_result is False


def test_audit_logs_store_no_medical_or_reference_body(tmp_path: Path) -> None:
    fixture = _approved_fixture(tmp_path)
    result = _resolve(fixture)
    assert result.payload is not None
    response = build_dummy_traceable_response(result.payload, executed_at=NOW)
    service = TraceableResponseService.from_directories(
        tmp_path / "presentation_response",
        tmp_path / "logs" / "presentation_response.jsonl",
    )
    accepted = service.accept(result.payload, response, validated_at=NOW)
    logs = Path(result.audit_log_path).read_text(encoding="utf-8") + Path(
        accepted.audit_log_path
    ).read_text(encoding="utf-8")

    assert "exact_text" not in logs
    assert "references" not in logs
    for claim in result.payload.medical_content.selected_claims:
        assert claim.exact_text not in logs


def test_payload_fingerprint_validator_detects_mutation(tmp_path: Path) -> None:
    result = _resolve(_approved_fixture(tmp_path))
    assert result.payload is not None
    mutated = result.payload.model_copy(
        update={
            "presentation": result.payload.presentation.model_copy(
                update={"title": "改変されたタイトル"}
            )
        }
    )
    scan = DataEgressPolicyValidator().validate(mutated)

    assert scan.fingerprint_result is False
    assert presentation_payload_fingerprint(mutated) != (
        result.payload.metadata.payload_fingerprint
    )
