import json
from dataclasses import dataclass, field
from pathlib import Path

from fastapi.testclient import TestClient
from presentation_engine_adapter import GeminiAdapterConfig, GeminiSandboxAdapter
from presentation_engine_adapter.gemini_models import (
    GeminiHttpResponse,
    GeminiProviderRequest,
)

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

FERRITIN_ENDPOINT = "/api/knowledge-templates/laboratory-test-item/ferritin"
KNOWLEDGE_ID = "knw_10000013"


@dataclass
class FakeTransport:
    outcomes: list[GeminiHttpResponse]
    requests: list[GeminiProviderRequest] = field(default_factory=list)

    def post(
        self,
        request: GeminiProviderRequest,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> GeminiHttpResponse:
        assert api_key == "fixture"
        assert timeout_seconds > 0
        self.requests.append(request)
        return self.outcomes.pop(0)


def _client(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    api_key: str = "fixture",
) -> TestClient:
    adapter = GeminiSandboxAdapter.from_directories(
        GeminiAdapterConfig(api_key=api_key),
        tmp_path / "gemini_response",
        tmp_path / "logs" / "gemini.jsonl",
        transport=transport,
    )
    return TestClient(
        create_app(
            provider=FixtureKnowledgeProvider(),
            gemini_adapter=adapter,
        )
    )


def _save_and_approve(client: TestClient) -> None:
    starter = client.get(FERRITIN_ENDPOINT).json()["data"]
    assert client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "Prompt Builderテスト用に保存",
        },
    ).status_code == 200
    claim_ids = [
        item["claim_id"]
        for item in client.get(f"/api/registry/{KNOWLEDGE_ID}").json()["claims"]
    ]
    for status in ("owner_review", "medical_review", "approved"):
        assert client.post(
            f"/api/registry/{KNOWLEDGE_ID}/claims/status",
            json={
                "target_status": status,
                "claim_ids": claim_ids,
                "actor": "medical_reviewer",
                "comment": "Sandbox Fixture承認",
            },
        ).status_code == 200
        assert client.post(
            f"/api/registry/{KNOWLEDGE_ID}/status",
            json={
                "target_status": status,
                "actor": "medical_reviewer",
                "comment": "Sandbox Fixture承認",
            },
        ).status_code == 200


def _prepare_payload(client: TestClient) -> dict[str, object]:
    assert client.post(f"/api/source-bundles/{KNOWLEDGE_ID}").status_code == 200
    assert client.post(
        f"/api/presentation-requests/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).status_code == 200
    response = client.post(
        f"/api/provider-payloads/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    return payload["payload"]


def _success_response(payload: dict[str, object]) -> GeminiHttpResponse:
    medical = payload["medical_content"]
    visual = payload["visual_content"]
    assert isinstance(medical, dict)
    assert isinstance(visual, dict)
    selected = medical["selected_claims"]
    diagrams = visual["diagram_requests"]
    references = medical["references"]
    assert isinstance(selected, list)
    assert isinstance(diagrams, list)
    assert isinstance(references, list)
    summary = {
        "presentation_request_id": payload["request"]["presentation_request_id"],
        "payload_id": payload["identity"]["payload_id"],
        "payload_fingerprint": payload["metadata"]["payload_fingerprint"],
        "status": "completed",
        "pages": payload["presentation"]["page_or_slide_count"],
        "used_claim_ids": [item["claim_id"] for item in selected],
        "omitted_claim_ids": [],
        "used_diagram_request_ids": [
            item["diagram_request_id"] for item in diagrams
        ],
        "used_reference_ids": [item["reference_id"] for item in references],
        "warnings": [],
    }
    provider_response = {
        "id": "int_workbench_sandbox",
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
            "totalInputTokens": 700,
            "totalOutputTokens": 100,
            "totalTokens": 800,
        },
    }
    return GeminiHttpResponse(200, json.dumps(provider_response).encode())


def test_workbench_prompt_and_gemini_sandbox_flow(tmp_path: Path) -> None:
    transport = FakeTransport([])
    client = _client(tmp_path, transport)
    _save_and_approve(client)
    payload = _prepare_payload(client)
    transport.outcomes.append(_success_response(payload))

    prompt_response = client.post(
        f"/api/presentation-prompts/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    )
    assert prompt_response.status_code == 200
    prompt_result = prompt_response.json()
    assert prompt_result["status"] == "success"
    assert prompt_result["validation"]["is_valid"] is True
    assert prompt_result["prompt_context"]["provider_neutral"] is True
    serialized_prompt = json.dumps(prompt_result["prompt"], ensure_ascii=False).lower()
    assert "gemini" not in serialized_prompt
    assert "openai" not in serialized_prompt

    sandbox_response = client.post(
        f"/api/presentation-prompts/{KNOWLEDGE_ID}/execute-gemini",
        json={"request_mode": "external"},
    )
    assert sandbox_response.status_code == 200
    sandbox = sandbox_response.json()
    assert sandbox["status"] == "completed"
    assert sandbox["sandbox_report"]["provider"] == "gemini"
    assert sandbox["sandbox_report"]["external_ai_called"] is True
    assert sandbox["sandbox_report"]["usage"]["total_tokens"] == 800
    assert sandbox["response"]["validation"]["is_valid"] is True
    assert sandbox["gemini_prompt_debug"] is None
    assert transport.requests[0].body["store"] is False


def test_missing_key_is_traceable_and_never_calls_transport(tmp_path: Path) -> None:
    transport = FakeTransport([])
    client = _client(tmp_path, transport, api_key="")
    _save_and_approve(client)
    _prepare_payload(client)
    assert client.post(
        f"/api/presentation-prompts/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    ).status_code == 200

    response = client.post(
        f"/api/presentation-prompts/{KNOWLEDGE_ID}/execute-gemini",
        json={"request_mode": "external"},
    )
    result = response.json()

    assert response.status_code == 200
    assert result["status"] == "failed"
    assert result["sandbox_report"]["error_code"] == "authentication_error"
    assert result["sandbox_report"]["external_ai_called"] is False
    assert transport.requests == []


def test_prompt_requires_approved_saved_payload(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeTransport([]))
    starter = client.get(FERRITIN_ENDPOINT).json()["data"]
    assert client.put(
        f"/api/knowledge-records/{KNOWLEDGE_ID}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "draft",
        },
    ).status_code == 200

    response = client.post(
        f"/api/presentation-prompts/{KNOWLEDGE_ID}",
        json={"request_mode": "external"},
    )
    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "provider_payload_required"


def test_phase_518_status_schema_and_ui_are_exposed(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeTransport([]))
    status = client.get("/api/status").json()
    schema = client.get("/api/schema/presentation-prompt-1.0")
    page = client.get("/")

    assert schema.status_code == 200
    assert status["presentation_prompt_contract_version"] == "1.0"
    assert status["presentation_prompt_builder_version"] == "1.0.0"
    assert status["presentation_prompt_provider_neutral"] is True
    assert status["gemini_sandbox_adapter_version"] == "1.0.0"
    assert status["gemini_sandbox_store_provider_data"] is False
    assert status["gemini_sandbox_retry_limit"] == 1
    assert "PHASE 5.18" in page.text
    assert "Presentation Prompt Preview" in page.text
    assert "Gemini Sandbox実行" in page.text
