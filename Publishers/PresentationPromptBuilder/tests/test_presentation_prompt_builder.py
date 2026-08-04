import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator
from knowledge_contracts.approval_v10 import ApprovalState
from knowledge_contracts.registry_v10 import RegistryEntityType, RegistryStatus
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_request_builder import PresentationRequestBuilder, RequestMode
from provider_payload_resolver import (
    ProviderPayloadResolver,
    presentation_payload_fingerprint,
)
from source_bundle_publisher import SourceBundlePublisherAdapter

from presentation_prompt_builder import (
    PresentationPromptBuilder,
    presentation_prompt_fingerprint,
    presentation_prompt_json_schema,
)

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = (
    ROOT
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "laboratory-test-item.example.json"
)
NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


def _approved_payload(tmp_path: Path):
    store = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    record = validate_knowledge_record(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    record = store.reconcile(record, actor="test", note="prompt fixture").record
    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        claim_ids = [item.claim_id for item in store.view(record.knowledge_id).claims]
        store.transition_claims_status(
            claim_ids,
            status,
            actor="reviewer",
            note="approved fixture",
        )
        store.transition_status(
            RegistryEntityType.KNOWLEDGE,
            record.knowledge_id,
            status,
            actor="reviewer",
            note="approved fixture",
        )
    view = store.view(record.knowledge_id)
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        ROOT / "Publishers" / "SourceBundlePublisher" / "profiles",
        tmp_path / "source",
        tmp_path / "logs" / "approval.jsonl",
    )
    source = source_publisher.publish(record, view, None, generated_at=NOW).bundle
    request_builder = PresentationRequestBuilder.from_directories(
        ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles",
        tmp_path / "request",
        tmp_path / "logs" / "request.jsonl",
        source_publisher,
    )
    request_result = request_builder.build(
        source,
        view,
        expected_source_fingerprint=source.metadata.source_fingerprint,
        request_mode=RequestMode.EXTERNAL,
        created_at=NOW,
    )
    assert request_result.request is not None
    resolver = ProviderPayloadResolver.from_directories(
        source_publisher,
        tmp_path / "payload",
        tmp_path / "logs" / "payload.jsonl",
    )
    payload_result = resolver.resolve(
        request_result.request,
        source,
        view,
        None,
        expected_source_fingerprint=source.metadata.source_fingerprint,
        created_at=NOW,
    )
    assert payload_result.payload is not None
    return payload_result.payload


def _builder(tmp_path: Path) -> PresentationPromptBuilder:
    return PresentationPromptBuilder.from_directories(
        tmp_path / "prompt",
        tmp_path / "logs" / "prompt.jsonl",
    )


def test_builds_provider_neutral_prompt_with_exact_claim_text(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    result = _builder(tmp_path).build(payload, built_at=NOW)

    assert result.status == "success"
    assert result.prompt is not None
    prompt = result.prompt
    assert tuple(item.exact_text for item in prompt.claims) == tuple(
        item.exact_text for item in payload.medical_content.selected_claims
    )
    assert tuple(item.exact_text for item in prompt.key_messages) == tuple(
        item.exact_text for item in payload.medical_content.key_messages
    )
    assert prompt.source.payload_id == payload.identity.payload_id
    assert prompt.source.approval_state == "approved"
    assert Path(result.output_path or "").is_file()


def test_prompt_contains_no_provider_specific_contract(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    result = _builder(tmp_path).build(payload, built_at=NOW)
    assert result.prompt is not None
    serialized = result.prompt.model_dump_json().lower()

    for provider_term in (
        "gemini",
        "claude",
        "openai",
        "canva",
        "notebooklm",
        "generativelanguage.googleapis.com",
        "api_key",
    ):
        assert provider_term not in serialized


def test_prompt_fingerprint_is_deterministic_and_sensitive(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    builder = _builder(tmp_path)
    first = builder.build(payload, built_at=NOW)
    second = builder.build(payload, built_at=NOW + timedelta(minutes=5))
    assert first.prompt is not None
    assert second.prompt is not None
    assert first.prompt.identity.prompt_id != second.prompt.identity.prompt_id
    assert first.prompt.metadata.prompt_fingerprint == (
        second.prompt.metadata.prompt_fingerprint
    )
    changed = first.prompt.model_copy(
        update={"learning_objective": "Changed educational goal"}
    )
    assert presentation_prompt_fingerprint(changed) != (
        first.prompt.metadata.prompt_fingerprint
    )


def test_tampered_payload_fingerprint_is_blocked(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    tampered = payload.model_copy(
        update={
            "presentation": payload.presentation.model_copy(
                update={"title": "Tampered"}
            )
        }
    )
    result = _builder(tmp_path).build(tampered, built_at=NOW)

    assert result.status == "blocked"
    assert result.prompt is None
    assert result.validation.payload_fingerprint_result is False
    assert any(
        item.code == "payload_fingerprint_mismatch"
        for item in result.validation.issues
    )


def test_non_approved_payload_is_blocked(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    draft = payload.model_copy(
        update={
            "source": payload.source.model_copy(
                update={"approval_state": ApprovalState.DRAFT}
            )
        }
    )
    draft = draft.model_copy(
        update={
            "metadata": draft.metadata.model_copy(
                update={"payload_fingerprint": presentation_payload_fingerprint(draft)}
            )
        }
    )
    result = _builder(tmp_path).build(draft, built_at=NOW)

    assert result.status == "blocked"
    assert result.validation.approval_result is False
    assert result.output_path is None


def test_prompt_audit_contains_no_medical_body(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    result = _builder(tmp_path).build(payload, built_at=NOW)
    audit = Path(result.audit_log_path).read_text(encoding="utf-8")

    for claim in payload.medical_content.selected_claims:
        assert claim.exact_text not in audit
    assert payload.presentation.learning_objective not in audit


def test_prompt_schema_is_valid_draft_2020_12(tmp_path: Path) -> None:
    payload = _approved_payload(tmp_path)
    result = _builder(tmp_path).build(payload, built_at=NOW)
    assert result.prompt is not None
    schema = presentation_prompt_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        result.prompt.model_dump(mode="json")
    )
