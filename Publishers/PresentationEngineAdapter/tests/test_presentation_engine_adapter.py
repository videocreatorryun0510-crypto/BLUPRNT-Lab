import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.approval_v10 import ApprovalGateDecision
from knowledge_contracts.registry_v10 import (
    RegistryEntityType,
    RegistryKnowledgeView,
    RegistryStatus,
)
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_request_builder import (
    PresentationRequest,
    PresentationRequestBuilder,
    RequestMode,
)
from provider_payload_resolver import ProviderPayloadResolver
from source_bundle_publisher import SourceBundlePublisherAdapter

from presentation_engine_adapter import (
    DummyPresentationEngineAdapter,
    EngineExecutionStatus,
    PresentationEngineAdapter,
    PresentationEngineResponseValidator,
    PresentationEngineRunner,
    presentation_request_fingerprint,
    presentation_result_json_schema,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0"
SOURCE_PROFILES = REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
PRESENTATION_PROFILES = REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def _fixture(
    tmp_path: Path,
    *,
    status: RegistryStatus = RegistryStatus.DRAFT,
    mode: RequestMode = RequestMode.PREVIEW,
) -> tuple[
    SQLiteKnowledgeRegistry,
    RegistryKnowledgeView,
    SourceBundlePublisherAdapter,
    PresentationRequest,
    tuple[str, ...],
]:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    record = validate_knowledge_record(
        json.loads((EXAMPLES / "laboratory-test-item.example.json").read_text(encoding="utf-8"))
    )
    reconciled = registry.reconcile(
        record,
        actor="presentation_engine_test",
        note="Presentation Engine Adapterテスト",
    )
    record = reconciled.record
    if status != RegistryStatus.DRAFT:
        for target in (
            RegistryStatus.OWNER_REVIEW,
            RegistryStatus.MEDICAL_REVIEW,
            RegistryStatus.APPROVED,
        ):
            claim_ids = [item.claim_id for item in registry.view(record.knowledge_id).claims]
            registry.transition_claims_status(
                claim_ids,
                target,
                actor="medical_reviewer",
                note="Presentation Engine実行確認",
            )
            registry.transition_status(
                RegistryEntityType.KNOWLEDGE,
                record.knowledge_id,
                target,
                actor="medical_reviewer",
                note="Presentation Engine実行確認",
            )
            if target == status:
                break
    view = registry.view(record.knowledge_id)
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        SOURCE_PROFILES,
        tmp_path / "source_bundle",
        tmp_path / "logs" / "approval_gate.jsonl",
    )
    publication = source_publisher.publish(record, view, None, generated_at=NOW)
    builder = PresentationRequestBuilder.from_directories(
        PRESENTATION_PROFILES,
        tmp_path / "presentation_request",
        tmp_path / "logs" / "presentation_request.jsonl",
        source_publisher,
    )
    build = builder.build(
        publication.bundle,
        view,
        expected_source_fingerprint=publication.bundle.metadata.source_fingerprint,
        request_mode=mode,
        created_at=NOW,
    )
    assert build.request is not None
    assertions = tuple(item.assertion for item in publication.bundle.claims)
    return registry, view, source_publisher, build.request, assertions


def _runner(
    tmp_path: Path,
    gate: SourceBundlePublisherAdapter,
) -> PresentationEngineRunner:
    return PresentationEngineRunner.from_audit_path(
        gate,
        tmp_path / "logs" / "presentation_engine.jsonl",
    )


def test_dummy_implements_provider_neutral_interface() -> None:
    adapter = DummyPresentationEngineAdapter()

    assert isinstance(adapter, PresentationEngineAdapter)
    assert adapter.provider_name == "dummy"
    assert adapter.provider_version == "1.0.0"
    assert adapter.supports_preview is True
    assert adapter.supports_external is True


def test_draft_preview_runs_without_network_or_medical_body(tmp_path: Path) -> None:
    _, view, gate, request, assertions = _fixture(tmp_path)
    outcome = _runner(tmp_path, gate).run(
        request,
        view,
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.SUCCESS
    assert outcome.external_ai_called is False
    assert outcome.result.validation_result.is_valid is True
    assert outcome.result.validation_result.approval_gate_checked is True
    assert outcome.result.validation_result.approval_gate_required is False
    assert outcome.result.validation_result.approval_gate_allowed is False
    artifact = outcome.result.generated_artifacts[0]
    assert artifact.pages == 5
    assert artifact.claims_used == 11
    assert artifact.diagram_requests == 1
    assert artifact.references == len(request.content_policy.reference_ids)
    assert artifact.output_type.value == "presentation_document"
    result_json = json.dumps(outcome.result.model_dump(mode="json"), ensure_ascii=False)
    assert all(assertion not in result_json for assertion in assertions)


def test_draft_external_is_blocked_before_execute(tmp_path: Path) -> None:
    _, view, gate, preview_request, _ = _fixture(tmp_path)
    external_request = preview_request.model_copy(update={"request_mode": RequestMode.EXTERNAL})

    outcome = _runner(tmp_path, gate).run(
        external_request,
        view,
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.BLOCKED
    assert outcome.result.generated_artifacts == ()
    assert outcome.result.validation_result.approval_gate_checked is True
    assert outcome.result.validation_result.approval_gate_required is True
    assert outcome.approval_gate.reason_code == "approval_required"


def test_approved_external_runs_through_same_contract(tmp_path: Path) -> None:
    _, view, gate, request, _ = _fixture(
        tmp_path,
        status=RegistryStatus.APPROVED,
        mode=RequestMode.EXTERNAL,
    )

    outcome = _runner(tmp_path, gate).run(
        request,
        view,
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.SUCCESS
    assert outcome.result.validation_result.approval_gate_required is True
    assert outcome.result.validation_result.approval_gate_allowed is True
    assert outcome.approval_gate.reason_code == "approval_granted"


class AlternateProviderDummy(DummyPresentationEngineAdapter):
    provider_name = "openai_simulated"
    provider_version = "9.9.9"


def test_provider_can_be_replaced_without_changing_result_contract(tmp_path: Path) -> None:
    _, view, gate, request, _ = _fixture(tmp_path)

    outcome = _runner(tmp_path, gate).run(
        request,
        view,
        AlternateProviderDummy(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.SUCCESS
    assert outcome.result.result_contract_version == "1.0"
    assert outcome.result.provider == "openai_simulated"
    assert outcome.result.provider_version == "9.9.9"


def test_dummy_accepts_phase_517_traceable_payload_without_network(tmp_path: Path) -> None:
    registry, view, gate, request, assertions = _fixture(
        tmp_path,
        status=RegistryStatus.APPROVED,
        mode=RequestMode.EXTERNAL,
    )
    record = registry.record(request.source.knowledge_id)
    assert record is not None
    publication = gate.publish(record, view, None, generated_at=NOW)
    resolver = ProviderPayloadResolver.from_directories(
        gate,
        tmp_path / "provider_payload",
        tmp_path / "logs" / "provider_payload.jsonl",
    )
    payload_result = resolver.resolve(
        request,
        publication.bundle,
        view,
        None,
        expected_source_fingerprint=publication.bundle.metadata.source_fingerprint,
        created_at=NOW,
    )
    assert payload_result.payload is not None

    adapter = DummyPresentationEngineAdapter()
    response = adapter.execute_traceable_payload(payload_result.payload, executed_at=NOW)
    validation = adapter.validate_traceable_response(payload_result.payload, response)

    assert response.execution.status.value == "completed"
    assert validation.is_valid is True
    response_json = response.model_dump_json()
    assert all(assertion not in response_json for assertion in assertions)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("request_fingerprint", "f" * 64, "request_fingerprint_mismatch"),
        ("provider_version", "2.0.0", "provider_version_mismatch"),
        ("claims_used", 10, "claim_count_mismatch"),
        ("diagram_requests", 0, "diagram_request_count_mismatch"),
        ("references", 0, "reference_count_mismatch"),
        ("pages", 4, "page_count_mismatch"),
    ],
)
def test_response_validator_detects_contract_mismatch(
    tmp_path: Path,
    field: str,
    value: object,
    expected_code: str,
) -> None:
    _, _, _, request, _ = _fixture(tmp_path)
    adapter = DummyPresentationEngineAdapter()
    payload = adapter.build_payload(request)
    response = adapter.execute(payload).model_copy(update={field: value})

    report = PresentationEngineResponseValidator().validate(
        request,
        payload,
        response,
    )

    assert report.is_valid is False
    assert expected_code in {item.code for item in report.issues}


def test_registry_change_blocks_stale_request(tmp_path: Path) -> None:
    registry, _, gate, request, _ = _fixture(tmp_path)
    claim_ids = [item.claim_id for item in registry.view(request.source.knowledge_id).claims]
    registry.transition_claims_status(
        claim_ids,
        RegistryStatus.OWNER_REVIEW,
        actor="product_owner",
        note="Request生成後の状態変更",
    )
    registry.transition_status(
        RegistryEntityType.KNOWLEDGE,
        request.source.knowledge_id,
        RegistryStatus.OWNER_REVIEW,
        actor="product_owner",
        note="Request生成後の状態変更",
    )

    outcome = _runner(tmp_path, gate).run(
        request,
        registry.view(request.source.knowledge_id),
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.BLOCKED
    codes = {item.code for item in outcome.result.validation_result.request_validation.issues}
    assert "approval_state_changed" in codes


class CountingGate:
    def __init__(self, delegate: SourceBundlePublisherAdapter) -> None:
        self.delegate = delegate
        self.call_count = 0

    def can_send_to_external_ai(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision:
        self.call_count += 1
        return self.delegate.can_send_to_external_ai(
            registry,
            evaluated_at=evaluated_at,
        )


def test_approval_gate_is_checked_for_preview_too(tmp_path: Path) -> None:
    _, view, source_gate, request, _ = _fixture(tmp_path)
    counting_gate = CountingGate(source_gate)
    runner = PresentationEngineRunner.from_audit_path(
        counting_gate,
        tmp_path / "logs" / "presentation_engine.jsonl",
    )

    outcome = runner.run(
        request,
        view,
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    assert outcome.result.status == EngineExecutionStatus.SUCCESS
    assert counting_gate.call_count == 1


def test_audit_contains_only_execution_metadata(tmp_path: Path) -> None:
    _, view, gate, request, assertions = _fixture(tmp_path)
    outcome = _runner(tmp_path, gate).run(
        request,
        view,
        DummyPresentationEngineAdapter(),
        executed_at=NOW,
    )

    audit = Path(outcome.audit_log_path).read_text(encoding="utf-8")
    record = json.loads(audit)
    assert set(record) == {
        "audit_contract_version",
        "request_id",
        "provider",
        "provider_version",
        "mode",
        "status",
        "validation_result",
        "gate_result",
        "timestamp",
    }
    assert "claims" not in audit
    assert "source_bundle" not in audit
    assert all(assertion not in audit for assertion in assertions)


def test_result_schema_and_request_fingerprint_are_stable(tmp_path: Path) -> None:
    _, _, _, request, _ = _fixture(tmp_path)
    schema = presentation_result_json_schema()

    assert schema["properties"]["result_contract_version"]["const"] == "1.0"
    assert presentation_request_fingerprint(request) == presentation_request_fingerprint(
        PresentationRequest.model_validate(request.model_dump(mode="json"))
    )
