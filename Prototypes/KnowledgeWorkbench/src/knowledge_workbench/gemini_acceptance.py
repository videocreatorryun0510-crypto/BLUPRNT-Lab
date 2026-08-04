"""Isolated Phase 5.18.1 Gemini real-API acceptance flow."""

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from knowledge_contracts.registry_v10 import RegistryEntityType, RegistryStatus
from knowledge_contracts.v10 import validate_knowledge_record
from presentation_engine_adapter import GeminiAdapterConfig, GeminiSandboxAdapter
from presentation_engine_adapter.gemini_models import (
    GeminiSandboxExecutionReport,
    GeminiTokenUsage,
)
from presentation_engine_adapter.gemini_transport import GeminiTransport
from presentation_prompt_builder import PresentationPrompt, PresentationPromptBuilder
from presentation_request_builder import PresentationRequestBuilder, RequestMode
from provider_payload_resolver import (
    PayloadValidationReport,
    PresentationPayload,
    ProviderPayloadResolver,
)
from pydantic import BaseModel, ConfigDict, Field
from source_bundle_publisher import SourceBundlePublisherAdapter

from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry


class GeminiAcceptanceError(RuntimeError):
    pass


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GeminiAcceptancePreflight(FrozenModel):
    provider: Literal["gemini"] = "gemini"
    mode: Literal["sandbox"] = "sandbox"
    model: str
    execution_environment: Literal["sandbox"] = "sandbox"
    fixture_mode: Literal[True] = True
    knowledge_id: str
    approval_state: Literal["approved"] = "approved"
    claim_count: int = Field(ge=1, le=3)
    reference_count: int = Field(ge=0, le=3)
    diagram_request_count: int = Field(ge=0, le=1)
    page_count: int = Field(ge=1, le=3)
    payload_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_egress_policy_result: bool
    secret_scan_result: bool
    stale_check_result: bool
    approval_result: bool
    fingerprint_result: bool
    api_key_configured: bool
    send_character_count: int = Field(ge=1)
    max_output_tokens: int = Field(ge=64, le=4096)
    retry_limit: int = Field(ge=0, le=1)
    timeout_seconds: float = Field(gt=0)
    external_communication: Literal[True] = True
    execution_limit: Literal[1] = 1
    already_executed: bool
    can_execute: bool
    stop_reasons: tuple[str, ...] = ()


class GeminiAcceptanceResult(FrozenModel):
    status: Literal["success", "validation_failed", "failed"]
    execution_id: str
    response_id: str
    provider_request_id: str | None
    provider: Literal["gemini"] = "gemini"
    model: str
    execution_environment: Literal["sandbox"] = "sandbox"
    fixture_mode: Literal[True] = True
    transport_result: Literal["success", "failed", "not_called"]
    validation_result: Literal["passed", "failed", "not_run"]
    http_status: int | None
    token_usage: GeminiTokenUsage
    duration_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0, le=1)
    claim_traceability_result: bool
    reference_traceability_result: bool
    fingerprint_result: bool
    policy_result: bool
    production_registry_unchanged: bool
    audit_saved: bool
    response_metadata_saved: bool
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class _AcceptanceContext:
    payload: PresentationPayload
    prompt: PresentationPrompt
    payload_validation: PayloadValidationReport
    stale_check_result: bool
    production_registry_fingerprint: str


class GeminiAcceptanceService:
    """Build an approved fixture without reading or mutating the real Registry."""

    fixture_knowledge_id = "knw_sandbox_fixture_001"

    def __init__(
        self,
        adapter: GeminiSandboxAdapter,
        output_root: Path,
        fixture_path: Path,
        presentation_profile_directory: Path,
    ) -> None:
        self._adapter = adapter
        self._output_root = output_root
        self._fixture_path = fixture_path
        self._presentation_profile_directory = presentation_profile_directory
        self._temporary_directory = TemporaryDirectory(
            prefix="bluprnt-gemini-acceptance-"
        )
        self._context: _AcceptanceContext | None = None
        self._execution_started = False

    @classmethod
    def from_config(
        cls,
        config: GeminiAdapterConfig,
        output_root: Path,
        fixture_path: Path,
        presentation_profile_directory: Path,
        *,
        transport: GeminiTransport | None = None,
    ) -> "GeminiAcceptanceService":
        adapter = GeminiSandboxAdapter.from_directories(
            config,
            output_root / "response",
            output_root / "audit" / "gemini_acceptance.jsonl",
            transport=transport,
        )
        return cls(
            adapter,
            output_root,
            fixture_path,
            presentation_profile_directory,
        )

    def prepare(self, production_registry_fingerprint: str) -> GeminiAcceptancePreflight:
        if self._context is None:
            self._context = self._build_context(production_registry_fingerprint)
        context = self._context
        payload = context.payload
        prompt = context.prompt
        provider_request = self._adapter.build_provider_request(prompt)
        validation = context.payload_validation
        api_key_configured = bool(self._adapter.config.api_key.strip())
        checks = (
            validation.egress_policy_result,
            validation.secret_scan_result,
            context.stale_check_result,
            validation.approval_result,
            validation.fingerprint_result,
        )
        reasons: list[str] = []
        if not all(checks):
            reasons.append("送信前Validationが成功していません。")
        if not api_key_configured:
            reasons.append("GEMINI_API_KEYが.envへ設定されていません。")
        if self._execution_started:
            reasons.append("この起動中の実API受入テストはすでに実行済みです。")
        return GeminiAcceptancePreflight(
            model=self._adapter.config.model,
            knowledge_id=payload.source.knowledge_id,
            claim_count=len(payload.medical_content.selected_claims),
            reference_count=len(payload.medical_content.references),
            diagram_request_count=len(payload.visual_content.diagram_requests),
            page_count=payload.presentation.page_or_slide_count,
            payload_fingerprint=payload.metadata.payload_fingerprint,
            data_egress_policy_result=validation.egress_policy_result,
            secret_scan_result=validation.secret_scan_result,
            stale_check_result=context.stale_check_result,
            approval_result=validation.approval_result,
            fingerprint_result=validation.fingerprint_result,
            api_key_configured=api_key_configured,
            send_character_count=len(provider_request.prompt_text),
            max_output_tokens=self._adapter.config.max_output_tokens,
            retry_limit=self._adapter.config.retry_limit,
            timeout_seconds=self._adapter.config.timeout_seconds,
            already_executed=self._execution_started,
            can_execute=not reasons,
            stop_reasons=tuple(reasons),
        )

    def execute(
        self,
        *,
        expected_payload_fingerprint: str,
        production_registry_fingerprint: str,
    ) -> GeminiAcceptanceResult:
        preflight = self.prepare(production_registry_fingerprint)
        if self._execution_started:
            raise GeminiAcceptanceError(
                "実API受入テストは1回だけ実行できます。再実行にはWorkbenchの再起動が必要です。"
            )
        if not preflight.can_execute:
            raise GeminiAcceptanceError(" ".join(preflight.stop_reasons))
        if expected_payload_fingerprint != preflight.payload_fingerprint:
            raise GeminiAcceptanceError(
                "画面確認後にPayload Fingerprintが変わりました。再確認してください。"
            )
        assert self._context is not None
        if (
            production_registry_fingerprint
            != self._context.production_registry_fingerprint
        ):
            raise GeminiAcceptanceError(
                "送信前確認後に実Registryが変化しました。受入テストを停止します。"
            )
        self._execution_started = True
        run = self._adapter.execute(
            self._context.payload,
            self._context.prompt,
            fixture_mode=True,
        )
        return self._result(
            run.report,
            run.response.identity.response_id,
            run.response.validation.claim_traceability_result,
            run.response.validation.reference_traceability_result,
            run.response.validation.fingerprint_result,
            run.response.validation.policy_result,
            production_registry_unchanged=(
                self._context.production_registry_fingerprint
                == production_registry_fingerprint
            ),
        )

    def _build_context(
        self,
        production_registry_fingerprint: str,
    ) -> _AcceptanceContext:
        temporary_root = Path(self._temporary_directory.name)
        record = validate_knowledge_record(
            json.loads(self._fixture_path.read_text(encoding="utf-8"))
        )
        fixture_registry = SQLiteKnowledgeRegistry(
            temporary_root / "fixture_registry.sqlite3"
        )
        record = fixture_registry.reconcile(
            record,
            actor="sandbox_fixture_builder",
            note="Phase 5.18.1 isolated fixture",
        ).record
        for status in (
            RegistryStatus.OWNER_REVIEW,
            RegistryStatus.MEDICAL_REVIEW,
            RegistryStatus.APPROVED,
        ):
            view = fixture_registry.view(record.knowledge_id)
            fixture_registry.transition_claims_status(
                [item.claim_id for item in view.claims],
                status,
                actor="sandbox_fixture_reviewer",
                note="Isolated acceptance fixture only",
            )
            fixture_registry.transition_status(
                RegistryEntityType.KNOWLEDGE,
                record.knowledge_id,
                status,
                actor="sandbox_fixture_reviewer",
                note="Isolated acceptance fixture only",
            )
        view = fixture_registry.view(record.knowledge_id)
        record = fixture_registry.record(record.knowledge_id) or record
        claim_by_path = {item.field_path: item for item in view.claims}
        summary = claim_by_path["category_content.laboratory_test_item.overview"]
        ordered_claims = sorted(view.claims, key=lambda item: item.field_path)

        source_profile_directory = temporary_root / "source_profiles"
        source_profile_directory.mkdir(parents=True, exist_ok=True)
        source_profile = {
            "profile_id": "source_bundle.gemini_acceptance_fixture.v1",
            "profile_version": "1.0",
            "knowledge_id": record.knowledge_id,
            "summary_claim_key": summary.claim_key,
            "learning_objective": (
                "承認済みIDと無変更本文を短い構造化応答で追跡できることを確認する。"
            ),
            "target_audience": "BLUPRNT Lab接続確認担当者",
            "key_claim_keys": [item.claim_key for item in ordered_claims],
            "diagram_requests": [],
        }
        (source_profile_directory / "acceptance_fixture.json").write_text(
            json.dumps(source_profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        source_publisher = SourceBundlePublisherAdapter.from_directories(
            source_profile_directory,
            self._output_root / "source_bundle",
            self._output_root / "audit" / "approval_gate.jsonl",
        )
        publication = source_publisher.publish(record, view, None)

        presentation_profile_directory = temporary_root / "presentation_profiles"
        presentation_profile_directory.mkdir(parents=True, exist_ok=True)
        presentation_profile = json.loads(
            (
                self._presentation_profile_directory
                / "presentation_document_basic_v1.json"
            ).read_text(encoding="utf-8")
        )
        presentation_profile.update(
            {
                "profile_id": "presentation_document_sandbox_acceptance_v1",
                "page_or_slide_count": 3,
                "information_density": "low",
                "visual_priority": "low",
                "text_amount": "short",
                "notes": "接続確認用の固定見出しと無変更Claim本文だけを許可する。",
            }
        )
        (presentation_profile_directory / "acceptance_fixture.json").write_text(
            json.dumps(presentation_profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        request_builder = PresentationRequestBuilder.from_directories(
            presentation_profile_directory,
            self._output_root / "presentation_request",
            self._output_root / "audit" / "presentation_request.jsonl",
            source_publisher,
        )
        request_result = request_builder.build(
            publication.bundle,
            view,
            expected_source_fingerprint=(
                publication.bundle.metadata.source_fingerprint
            ),
            profile_id="presentation_document_sandbox_acceptance_v1",
            request_mode=RequestMode.EXTERNAL,
        )
        if request_result.request is None or request_result.validation is None:
            raise GeminiAcceptanceError("Fixture Presentation Requestを生成できません。")

        resolver = ProviderPayloadResolver.from_directories(
            source_publisher,
            self._output_root / "provider_payload",
            self._output_root / "audit" / "provider_payload.jsonl",
        )
        payload_result = resolver.resolve(
            request_result.request,
            publication.bundle,
            view,
            None,
            expected_source_fingerprint=(
                publication.bundle.metadata.source_fingerprint
            ),
        )
        if payload_result.payload is None:
            raise GeminiAcceptanceError("Fixture Provider Payloadを生成できません。")

        prompt_builder = PresentationPromptBuilder.from_directories(
            self._output_root / "presentation_prompt",
            self._output_root / "audit" / "presentation_prompt.jsonl",
        )
        prompt_result = prompt_builder.build(payload_result.payload)
        if prompt_result.prompt is None:
            raise GeminiAcceptanceError("Fixture Presentation Promptを生成できません。")
        return _AcceptanceContext(
            payload=payload_result.payload,
            prompt=prompt_result.prompt,
            payload_validation=payload_result.validation,
            stale_check_result=request_result.decision.freshness.is_current,
            production_registry_fingerprint=production_registry_fingerprint,
        )

    @staticmethod
    def _result(
        report: GeminiSandboxExecutionReport,
        response_id: str,
        claim_traceability_result: bool,
        reference_traceability_result: bool,
        fingerprint_result: bool,
        policy_result: bool,
        *,
        production_registry_unchanged: bool,
    ) -> GeminiAcceptanceResult:
        return GeminiAcceptanceResult(
            status=report.final_result,
            execution_id=report.execution_id,
            response_id=response_id,
            provider_request_id=report.provider_request_id,
            model=report.model,
            transport_result=report.transport_result,
            validation_result=report.validation_result,
            http_status=report.http_status,
            token_usage=report.usage,
            duration_ms=report.duration_ms,
            retry_count=report.retry_count,
            claim_traceability_result=claim_traceability_result,
            reference_traceability_result=reference_traceability_result,
            fingerprint_result=fingerprint_result,
            policy_result=policy_result,
            production_registry_unchanged=production_registry_unchanged,
            audit_saved=Path(report.audit_log_path).is_file(),
            response_metadata_saved=Path(report.response_output_path).is_file(),
            error_code=report.error_code.value if report.error_code else None,
            error_message=report.error_message,
        )
