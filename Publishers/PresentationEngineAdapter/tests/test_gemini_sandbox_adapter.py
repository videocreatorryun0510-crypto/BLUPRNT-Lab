import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge_contracts.approval_v10 import ApprovalState
from knowledge_contracts.registry_v10 import RegistryEntityType, RegistryStatus
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_prompt_builder import PresentationPromptBuilder
from presentation_request_builder import PresentationRequestBuilder, RequestMode
from provider_payload_resolver import (
    ProviderPayloadResolver,
    presentation_payload_fingerprint,
)
from source_bundle_publisher import SourceBundlePublisherAdapter

from presentation_engine_adapter import GeminiAdapterConfig, GeminiSandboxAdapter
from presentation_engine_adapter.gemini_models import (
    GeminiHttpResponse,
    GeminiProviderRequest,
)
from presentation_engine_adapter.gemini_transport import (
    GeminiTransportNetworkError,
    GeminiTransportTimeout,
)

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = (
    ROOT
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "laboratory-test-item.example.json"
)
NOW = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def _approved_payload_and_prompt(tmp_path: Path) -> tuple[Any, Any]:
    store = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    record = validate_knowledge_record(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    record = store.reconcile(record, actor="test", note="gemini fixture").record
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
    prompt_builder = PresentationPromptBuilder.from_directories(
        tmp_path / "prompt",
        tmp_path / "logs" / "prompt.jsonl",
    )
    prompt_result = prompt_builder.build(payload_result.payload, built_at=NOW)
    assert prompt_result.prompt is not None
    return payload_result.payload, prompt_result.prompt


@dataclass
class FakeTransport:
    outcomes: list[GeminiHttpResponse | Exception]
    requests: list[GeminiProviderRequest] = field(default_factory=list)
    api_keys: list[str] = field(default_factory=list)

    def post(
        self,
        request: GeminiProviderRequest,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> GeminiHttpResponse:
        assert timeout_seconds > 0
        self.requests.append(request)
        self.api_keys.append(api_key)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _success(payload: Any, prompt: Any, *, fingerprint: str | None = None):
    summary = {
        "presentation_request_id": payload.request.presentation_request_id,
        "payload_id": payload.identity.payload_id,
        "payload_fingerprint": fingerprint or payload.metadata.payload_fingerprint,
        "status": "completed",
        "pages": payload.presentation.page_or_slide_count,
        "used_claim_ids": [
            item.claim_id for item in payload.medical_content.selected_claims
        ],
        "omitted_claim_ids": [],
        "used_diagram_request_ids": [
            item.diagram_request_id
            for item in payload.visual_content.diagram_requests
        ],
        "used_reference_ids": [
            item.reference_id for item in payload.medical_content.references
        ],
        "warnings": [],
    }
    body = {
        "id": "int_sandbox_123",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(summary, ensure_ascii=False),
                    }
                ],
            }
        ],
        "usage": {
            "totalInputTokens": 1000,
            "totalOutputTokens": 200,
            "totalThoughtTokens": 20,
            "totalTokens": 1220,
        },
    }
    return GeminiHttpResponse(200, json.dumps(body).encode())


def _adapter(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    api_key: str = "test-key-not-real",
    debug: bool = False,
    input_rate: float | None = None,
    output_rate: float | None = None,
) -> GeminiSandboxAdapter:
    return GeminiSandboxAdapter.from_directories(
        GeminiAdapterConfig(
            api_key=api_key,
            debug_prompt=debug,
            input_cost_per_million_tokens=input_rate,
            output_cost_per_million_tokens=output_rate,
        ),
        tmp_path / "response",
        tmp_path / "logs" / "gemini.jsonl",
        transport=transport,
    )


def test_gemini_sandbox_success_maps_metadata_only(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([_success(payload, prompt)])
    result = _adapter(
        tmp_path,
        transport,
        input_rate=1.0,
        output_rate=2.0,
    ).execute(payload, prompt, started_at=NOW)

    assert result.response.execution.status == "completed"
    assert result.response.provider.provider_name == "gemini"
    assert result.response.request.payload_fingerprint == (
        payload.metadata.payload_fingerprint
    )
    assert result.report.external_ai_called is True
    assert result.report.attempt_count == 1
    assert result.report.usage.prompt_tokens == 1000
    assert result.report.usage.completion_tokens == 200
    assert result.report.usage.total_tokens == 1220
    assert result.report.usage.estimated_cost_usd == 0.0014
    assert result.gemini_prompt_debug is None
    assert transport.requests[0].body["store"] is False
    assert transport.api_keys == ["test-key-not-real"]
    assert "test-key-not-real" not in json.dumps(transport.requests[0].body)

    persisted = Path(result.report.response_output_path).read_text(encoding="utf-8")
    audit = Path(result.report.audit_log_path).read_text(encoding="utf-8")
    for claim in payload.medical_content.selected_claims:
        assert claim.exact_text not in persisted
        assert claim.exact_text not in audit
    assert "test-key-not-real" not in audit


def test_gemini_prompt_is_only_visible_in_debug_mode(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([_success(payload, prompt)])
    result = _adapter(tmp_path, transport, debug=True).execute(payload, prompt)

    assert result.gemini_prompt_debug is not None
    assert prompt.claims[0].exact_text in result.gemini_prompt_debug
    assert result.gemini_prompt_debug not in Path(
        result.report.audit_log_path
    ).read_text(encoding="utf-8")


def test_timeout_retries_once_then_fails(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport(
        [GeminiTransportTimeout(), GeminiTransportTimeout()]
    )
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.response.execution.status == "failed"
    assert result.report.error_code == "timeout_error"
    assert result.report.attempt_count == 2


def test_429_retries_once_and_can_succeed(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport(
        [GeminiHttpResponse(429, b"{}"), _success(payload, prompt)]
    )
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.response.execution.status == "completed"
    assert result.report.attempt_count == 2
    assert result.report.error_code is None


def test_500_retries_once_then_fails(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport(
        [GeminiHttpResponse(500, b"{}"), GeminiHttpResponse(503, b"{}")]
    )
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.response.execution.status == "failed"
    assert result.report.error_code == "provider_server_error"
    assert result.report.attempt_count == 2


def test_network_error_retries_once_then_fails(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport(
        [GeminiTransportNetworkError(), GeminiTransportNetworkError()]
    )
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.report.error_code == "network_error"
    assert result.report.attempt_count == 2


def test_authentication_http_error_does_not_retry(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([GeminiHttpResponse(401, b"secret provider body")])
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.report.error_code == "authentication_error"
    assert result.report.attempt_count == 1
    assert "secret provider body" not in Path(
        result.report.audit_log_path
    ).read_text(encoding="utf-8")


def test_missing_key_returns_traceable_failure_without_call(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([])
    result = _adapter(tmp_path, transport, api_key="").execute(payload, prompt)

    assert result.response.execution.status == "failed"
    assert result.report.error_code == "authentication_error"
    assert result.report.external_ai_called is False
    assert result.report.attempt_count == 0
    assert transport.requests == []


def test_invalid_json_returns_traceable_json_error(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([GeminiHttpResponse(200, b"not-json")])
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.report.error_code == "json_error"
    assert result.response.execution.status == "failed"


def test_approval_error_stops_before_transport(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
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
    transport = FakeTransport([])
    result = _adapter(tmp_path, transport).execute(draft, prompt)

    assert result.report.error_code == "approval_error"
    assert result.report.external_ai_called is False
    assert transport.requests == []


def test_prompt_fingerprint_error_stops_before_transport(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    tampered = prompt.model_copy(update={"title": "tampered"})
    transport = FakeTransport([])
    result = _adapter(tmp_path, transport).execute(payload, tampered)

    assert result.report.error_code == "fingerprint_error"
    assert result.report.external_ai_called is False


def test_response_fingerprint_error_is_traceable(tmp_path: Path) -> None:
    payload, prompt = _approved_payload_and_prompt(tmp_path)
    transport = FakeTransport([_success(payload, prompt, fingerprint="0" * 64)])
    result = _adapter(tmp_path, transport).execute(payload, prompt)

    assert result.report.error_code == "fingerprint_error"
    assert result.response.execution.status == "failed"
    assert result.report.external_ai_called is True
