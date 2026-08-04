import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from fastapi.testclient import TestClient
from presentation_engine_adapter import GeminiAdapterConfig
from presentation_engine_adapter.gemini_models import (
    GeminiHttpResponse,
    GeminiProviderRequest,
)

from knowledge_workbench.gemini_acceptance import GeminiAcceptanceService
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT
    / "Prototypes"
    / "KnowledgeWorkbench"
    / "fixtures"
    / "gemini_acceptance"
    / "knowledge.json"
)
PROFILES = ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"


@dataclass
class DynamicSuccessTransport:
    requests: list[GeminiProviderRequest] = field(default_factory=list)
    api_keys: list[str] = field(default_factory=list)

    def post(
        self,
        request: GeminiProviderRequest,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> GeminiHttpResponse:
        assert timeout_seconds == 30
        self.requests.append(request)
        self.api_keys.append(api_key)
        envelope = json.loads(request.prompt_text)
        prompt = envelope["presentation_prompt"]
        claims = prompt["claims"]
        references = prompt["references"]
        diagrams = prompt["diagram_requests"]
        summary = {
            "presentation_request_id": prompt["source"]["presentation_request_id"],
            "payload_id": prompt["source"]["payload_id"],
            "payload_fingerprint": prompt["source"]["payload_fingerprint"],
            "status": "completed",
            "pages": prompt["layout_policy"]["page_or_slide_count"],
            "title": prompt["title"],
            "sections": [
                {
                    "heading": "要点1",
                    "exact_claim_texts": [item["exact_text"] for item in claims],
                    "source_claim_ids": [item["claim_id"] for item in claims],
                }
            ],
            "source_claim_ids": [item["claim_id"] for item in claims],
            "source_reference_ids": [
                item["reference_id"] for item in references
            ],
            "omitted_claim_ids": [],
            "used_diagram_request_ids": [
                item["diagram_request_id"] for item in diagrams
            ],
            "warnings": [],
        }
        body = {
            "id": "int_acceptance_fixture_001",
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
                "totalInputTokens": 420,
                "totalOutputTokens": 120,
                "totalTokens": 540,
            },
        }
        return GeminiHttpResponse(200, json.dumps(body).encode())


def _fingerprint(registry: SQLiteKnowledgeRegistry) -> str:
    value = json.dumps(
        registry.snapshot().model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _client(
    tmp_path: Path,
    transport: DynamicSuccessTransport,
    *,
    api_key: str = "fixture-secret-not-real",
) -> tuple[TestClient, SQLiteKnowledgeRegistry, Path]:
    output_root = tmp_path / "acceptance_output"
    acceptance = GeminiAcceptanceService.from_config(
        GeminiAdapterConfig(api_key=api_key),
        output_root,
        FIXTURE,
        PROFILES,
        transport=transport,
    )
    registry = SQLiteKnowledgeRegistry(tmp_path / "production_registry.sqlite3")
    app = create_app(
        provider=FixtureKnowledgeProvider(),
        registry=registry,
        gemini_acceptance_service=acceptance,
    )
    return TestClient(app), registry, output_root


def test_preflight_is_isolated_and_does_not_call_provider(tmp_path: Path) -> None:
    transport = DynamicSuccessTransport()
    client, registry, _ = _client(tmp_path, transport)
    before = _fingerprint(registry)

    response = client.post("/api/gemini-acceptance/preflight")
    result = response.json()
    preflight = result["preflight"]

    assert response.status_code == 200
    assert result["status"] == "ready"
    assert preflight["knowledge_id"] == "knw_sandbox_fixture_001"
    assert preflight["fixture_mode"] is True
    assert preflight["approval_state"] == "approved"
    assert preflight["claim_count"] == 2
    assert preflight["reference_count"] == 1
    assert preflight["diagram_request_count"] == 0
    assert preflight["page_count"] == 3
    assert preflight["can_execute"] is True
    assert result["external_ai_called"] is False
    assert transport.requests == []
    assert _fingerprint(registry) == before
    assert "fixture-secret-not-real" not in json.dumps(result)


def test_explicit_acceptance_execution_is_traceable_and_one_shot(
    tmp_path: Path,
) -> None:
    transport = DynamicSuccessTransport()
    client, registry, output_root = _client(tmp_path, transport)
    before = _fingerprint(registry)
    preflight = client.post("/api/gemini-acceptance/preflight").json()["preflight"]

    response = client.post(
        "/api/gemini-acceptance/execute",
        json={
            "confirm_external_communication": True,
            "payload_fingerprint": preflight["payload_fingerprint"],
        },
    )
    payload = response.json()
    result = payload["result"]

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["external_ai_called"] is True
    assert result["fixture_mode"] is True
    assert result["transport_result"] == "success"
    assert result["validation_result"] == "passed"
    assert result["http_status"] == 200
    assert result["provider_request_id"] == "int_acceptance_fixture_001"
    assert result["claim_traceability_result"] is True
    assert result["reference_traceability_result"] is True
    assert result["production_registry_unchanged"] is True
    assert result["audit_saved"] is True
    assert result["response_metadata_saved"] is True
    assert result["token_usage"]["total_tokens"] == 540
    assert len(transport.requests) == 1
    assert transport.api_keys == ["fixture-secret-not-real"]
    assert _fingerprint(registry) == before

    audit_path = output_root / "audit" / "gemini_acceptance.jsonl"
    audit = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert set(audit) == {
        "execution_id",
        "request_id",
        "payload_id",
        "response_id",
        "provider",
        "model",
        "sandbox",
        "fixture_mode",
        "started_at",
        "completed_at",
        "duration",
        "token_usage",
        "retry_count",
        "transport_result",
        "validation_result",
        "final_result",
        "error_code",
    }
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    persisted = audit_path.read_text(encoding="utf-8")
    assert "fixture-secret-not-real" not in persisted
    statements = [
        fixture["core_facts"]["definitions"][0]["assertion"],
        fixture["category_content"]["laboratory_test_item"]["overview"][0][
            "assertion"
        ],
    ]
    for statement in statements:
        assert statement not in persisted

    repeated = client.post(
        "/api/gemini-acceptance/execute",
        json={
            "confirm_external_communication": True,
            "payload_fingerprint": preflight["payload_fingerprint"],
        },
    )
    assert repeated.status_code == 409
    assert len(transport.requests) == 1


def test_missing_key_blocks_before_external_communication(tmp_path: Path) -> None:
    transport = DynamicSuccessTransport()
    client, _, _ = _client(tmp_path, transport, api_key="")

    result = client.post("/api/gemini-acceptance/preflight").json()

    assert result["status"] == "blocked"
    assert result["preflight"]["api_key_configured"] is False
    assert result["preflight"]["can_execute"] is False
    assert transport.requests == []


def test_phase_5181_workbench_requires_explicit_button() -> None:
    page = (ROOT / "Prototypes" / "KnowledgeWorkbench" / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "Prototypes" / "KnowledgeWorkbench" / "web" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "PHASE 5.18.1" in page
    assert "Test FixtureをGeminiへ1回送信" in page
    assert 'id="executeGeminiAcceptanceButton"' in page
    assert 'fetch("/api/gemini-acceptance/execute"' in script
    assert "confirm_external_communication: true" in script
    assert 'fetch("/api/gemini-acceptance/preflight"' in script
