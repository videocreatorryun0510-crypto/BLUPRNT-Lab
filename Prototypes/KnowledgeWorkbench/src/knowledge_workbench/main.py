"""FastAPI entry point for the Prototype Phase 1 Knowledge Workbench."""

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, Self
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from knowledge_contracts.approval_v10 import (
    approval_contract,
    approval_contract_json_schema,
    approval_snapshot_from_registry,
)
from knowledge_contracts.exam_import_v10 import CsvImportPreview, CsvImportReport
from knowledge_contracts.exam_v10 import (
    ExamMetadataRecord,
    evaluate_exam_completeness,
    exam_metadata_json_schema,
)
from knowledge_contracts.registry_v10 import (
    RegistryEntityType,
    RegistrySnapshot,
    RegistryStatus,
    registry_snapshot_json_schema,
)
from knowledge_contracts.relation_v10 import (
    knowledge_relation_json_schema as knowledge_relation_v10_json_schema,
)
from knowledge_contracts.relation_v11 import (
    knowledge_relation_json_schema as knowledge_relation_v11_json_schema,
)
from knowledge_contracts.relation_v12 import (
    disease_relation_vocabulary,
    disease_relation_vocabulary_json_schema,
)
from knowledge_contracts.relation_v12 import (
    knowledge_relation_json_schema as knowledge_relation_v12_json_schema,
)
from knowledge_contracts.v03 import (
    knowledge_record_json_schema as knowledge_record_v03_json_schema,
)
from knowledge_contracts.v10 import (
    KnowledgeSchemaError,
    evaluate_knowledge_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)
from presentation_artifact import (
    PresentationArtifactBuilder,
    presentation_artifact_json_schema,
)
from presentation_artifact_registry import (
    ArtifactApprovalState,
    ArtifactNotFoundError,
    ArtifactRegistryError,
    SQLitePresentationArtifactRegistry,
    artifact_registry_json_schema,
    evaluate_artifact_completeness,
)
from presentation_engine_adapter import (
    DummyPresentationEngineAdapter,
    GeminiAdapterConfig,
    GeminiSandboxAdapter,
    PresentationEngineRunner,
    presentation_result_json_schema,
)
from presentation_prompt_builder import (
    PresentationPrompt,
    PresentationPromptBuilder,
    presentation_prompt_json_schema,
)
from presentation_request_builder import (
    PresentationRequest,
    PresentationRequestBuilder,
    PresentationRequestBuilderError,
    RequestMode,
    presentation_request_json_schema,
)
from provider_payload_resolver import (
    PresentationPayload,
    ProviderPayloadResolver,
    TraceableResponseService,
    presentation_payload_json_schema,
    traceable_response_json_schema,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from source_bundle_publisher import (
    SourceBundle,
    SourceBundlePublisherAdapter,
    SourceBundlePublisherError,
    source_bundle_json_schema,
)

from knowledge_workbench.application import GenerateKnowledge
from knowledge_workbench.errors import RegistryOperationError, WorkbenchError
from knowledge_workbench.exam_import_mapping import load_exam_csv_mapping
from knowledge_workbench.exam_import_service import (
    SAMPLE_CSV_PATH,
    ExamImportExecutionResult,
    import_exam_csv,
)
from knowledge_workbench.exam_metadata_provider import DummyExamMetadataProvider
from knowledge_workbench.gemini_acceptance import (
    GeminiAcceptanceError,
    GeminiAcceptanceService,
)
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.knowledge_relation_repository import (
    KnowledgeRelationRepository,
)
from knowledge_workbench.knowledge_relation_service import KnowledgeRelationService
from knowledge_workbench.providers.base import KnowledgeProvider
from knowledge_workbench.registry_backup import SQLiteRegistryBackupManager
from knowledge_workbench.settings import Settings, build_provider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from knowledge_workbench.sqlite_knowledge_relation_repository import (
    SQLiteKnowledgeRelationRepository,
)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
GRAM_STAIN_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "staining-method.example.json"
)
ACID_FAST_STAIN_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "acid-fast-staining-method.example.json"
)
SPECIMEN_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "specimen.example.json"
)
REAGENT_STARTER_DIRECTORY = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "reagents"
)
REAGENT_STARTER_PATHS = {
    "crystal-violet": REAGENT_STARTER_DIRECTORY / "crystal-violet.example.json",
    "gram-iodine": REAGENT_STARTER_DIRECTORY / "gram-iodine.example.json",
    "gram-decolorizer": REAGENT_STARTER_DIRECTORY / "gram-decolorizer.example.json",
    "gram-safranin": REAGENT_STARTER_DIRECTORY / "gram-safranin.example.json",
}
BIOLOGICAL_STRUCTURE_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "biological-structure.example.json"
)
DISEASE_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "disease.example.json"
)
LABORATORY_TEST_ITEM_STARTER_PATH = (
    Path(__file__).resolve().parents[4]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "laboratory-test-item.example.json"
)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=80)


class CsvImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str = Field(
        min_length=5,
        max_length=180,
        pattern=r"^[^/\\]+\.[cC][sS][vV]$",
    )
    csv_base64: str = Field(min_length=1, max_length=7_000_000)
    import_mode: Literal["append", "replace"] = "replace"

    @model_validator(mode="after")
    def require_valid_base64(self) -> Self:
        try:
            base64.b64decode(self.csv_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("csv_base64 must contain valid Base64 data") from error
        return self


class ImportCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(pattern=r"^prv_[a-z0-9][a-z0-9_-]{7,63}$")


class RegistryStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_status: RegistryStatus
    actor: str = Field(min_length=1, max_length=120)
    comment: str = Field(min_length=1, max_length=1000)


class ClaimStatusRequest(RegistryStatusRequest):
    claim_ids: list[str] = Field(min_length=1, max_length=200)


class ClaimMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_claim_id: str = Field(min_length=8, max_length=80)
    source_claim_ids: list[str] = Field(min_length=1, max_length=100)
    actor: str = Field(min_length=1, max_length=120)
    comment: str = Field(min_length=1, max_length=1000)


class RegistryRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=20, max_length=40)


class KnowledgeRecordSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: dict[str, Any]
    actor: str = Field(min_length=1, max_length=120)
    comment: str = Field(min_length=1, max_length=1000)


class PresentationRequestGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: RequestMode = RequestMode.PREVIEW
    profile_id: str = Field(
        default="presentation_document_basic_v1",
        min_length=3,
        max_length=180,
    )
    profile_version: Literal["1.0"] = "1.0"


class PresentationEngineExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: RequestMode = RequestMode.PREVIEW
    adapter: Literal["dummy"] = "dummy"


class PresentationArtifactGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: RequestMode = RequestMode.PREVIEW
    owner: str = Field(default="product_owner", min_length=1, max_length=120)
    actor: str = Field(default="product_owner", min_length=1, max_length=120)
    review_comment: str = Field(
        default="Presentation Artifact初版登録",
        min_length=1,
        max_length=1000,
    )


class ArtifactApprovalTransitionApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: ArtifactApprovalState
    actor: str = Field(min_length=1, max_length=120)
    review_comment: str = Field(min_length=1, max_length=1000)


class ProviderPayloadExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: RequestMode = RequestMode.PREVIEW
    adapter: Literal["dummy"] = "dummy"


class PresentationPromptExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: RequestMode = RequestMode.EXTERNAL


class GeminiSandboxExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: Literal[RequestMode.EXTERNAL] = RequestMode.EXTERNAL


class GeminiAcceptanceExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_external_communication: Literal[True]
    payload_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class _PendingCsvPreview:
    csv_text: str
    source_file: str
    import_mode: Literal["append", "replace"]
    registry_fingerprint: str
    preview: CsvImportPreview


def _import_response(
    result: ExamImportExecutionResult,
    *,
    phase: Literal["preview", "imported"],
    preview: CsvImportPreview | None = None,
) -> JSONResponse:
    outcome = result.outcome
    can_import = outcome.report.validation.can_import
    return JSONResponse(
        status_code=200,
        content={
            "status": "success" if can_import else "validation_error",
            "phase": phase,
            "preview": preview.model_dump(mode="json") if preview is not None else None,
            "report": _serialize_import_report(outcome.report),
            "normalized_records": [
                item.model_dump(mode="json") for item in outcome.normalized_records
            ],
            "mapped_records": [item.model_dump(mode="json") for item in outcome.mapped_records],
            "exam_metadata": _serialize_exam_metadata(outcome.exam_metadata),
            "exam_completeness": [
                item.model_dump(mode="json") for item in result.exam_completeness
            ],
            "errors": [
                issue.model_dump(mode="json")
                for issue in outcome.report.validation.issues
                if issue.severity == "error"
            ],
        },
    )


def _serialize_import_report(report: CsvImportReport) -> dict[str, object]:
    return report.model_dump(mode="json")


def _serialize_exam_metadata(
    records: list[ExamMetadataRecord],
) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in records]


def _registry_fingerprint(snapshot: RegistrySnapshot) -> str:
    serialized = json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_import_preview(
    result: ExamImportExecutionResult,
    before: RegistrySnapshot,
    after: RegistrySnapshot,
    registry_fingerprint: str,
) -> CsvImportPreview:
    outcome = result.outcome
    before_ids = {item.knowledge_id for item in before.knowledge}
    after_ids = {item.knowledge_id for item in after.knowledge}
    mapped_ids = {item.knowledge_id for item in outcome.mapped_records}
    issues = outcome.report.validation.issues
    unknown_rows = {
        item.source_row_number
        for item in issues
        if item.code == "knowledge_mapping_failed" and item.source_row_number is not None
    }
    unknown_terms = list(
        dict.fromkeys(
            item.theme
            for item in outcome.normalized_records
            if item.source_row_number in unknown_rows
        )
    )
    mapping_codes = {
        "ambiguous_mapping",
        "knowledge_mapping_failed",
        "required_column_missing",
        "duplicate_column",
        "invalid_row",
    }
    claim_codes = {"claim_mapping_missing", "claim_not_available"}
    return CsvImportPreview(
        preview_id=f"prv_{uuid4().hex[:16]}",
        can_commit=outcome.report.validation.can_import,
        registry_fingerprint=registry_fingerprint,
        new_knowledge_ids=sorted(after_ids - before_ids),
        updated_knowledge_ids=sorted(mapped_ids & before_ids),
        unknown_terms=unknown_terms,
        mapping_failures=[item.message for item in issues if item.code in mapping_codes],
        missing_images=[item.message for item in issues if item.code == "image_missing"],
        unsupported_claims=[item.message for item in issues if item.code in claim_codes],
    )


def _registry_error_response(error: RegistryOperationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "errors": [{"code": error.code, "message": error.message}],
        },
    )


def create_app(
    provider: KnowledgeProvider | None = None,
    settings: Settings | None = None,
    registry: KnowledgeRegistry | None = None,
    relation_repository: KnowledgeRelationRepository | None = None,
    gemini_adapter: GeminiSandboxAdapter | None = None,
    gemini_acceptance_service: GeminiAcceptanceService | None = None,
    artifact_registry: SQLitePresentationArtifactRegistry | None = None,
) -> FastAPI:
    app = FastAPI(
        title="BLUPRNT Lab Knowledge Workbench",
        version="5.20.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    resolved_settings = settings or Settings.from_environment()
    temporary_registry_directory: TemporaryDirectory[str] | None = None
    if registry is not None:
        resolved_registry = registry
    elif provider is not None:
        temporary_registry_directory = TemporaryDirectory(prefix="bluprnt-registry-api-test-")
        resolved_registry = SQLiteKnowledgeRegistry(
            Path(temporary_registry_directory.name) / "knowledge_registry.sqlite3"
        )
    else:
        resolved_registry = SQLiteKnowledgeRegistry(resolved_settings.registry_path)
    resolved_relation_repository = relation_repository
    if resolved_relation_repository is None and isinstance(
        resolved_registry, SQLiteKnowledgeRegistry
    ):
        resolved_relation_repository = SQLiteKnowledgeRelationRepository(
            resolved_registry.database_path
        )
    relation_service = (
        KnowledgeRelationService(resolved_registry, resolved_relation_repository)
        if resolved_relation_repository is not None
        else None
    )
    app.state.registry_tempdir = temporary_registry_directory
    backup_directory = (
        Path(temporary_registry_directory.name) / "backups"
        if temporary_registry_directory is not None
        else resolved_settings.registry_backup_dir
    )
    backup_manager = (
        SQLiteRegistryBackupManager(resolved_registry, backup_directory)
        if isinstance(resolved_registry, SQLiteKnowledgeRegistry)
        else None
    )
    source_bundle_output_directory = (
        Path(temporary_registry_directory.name) / "source_bundle"
        if temporary_registry_directory is not None
        else resolved_settings.source_bundle_output_dir
    )
    source_bundle_audit_log_path = (
        Path(temporary_registry_directory.name) / "publisher_logs" / "approval_gate.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.source_bundle_audit_log_path
    )
    source_bundle_publisher = SourceBundlePublisherAdapter.from_directories(
        resolved_settings.source_bundle_profile_dir,
        source_bundle_output_directory,
        source_bundle_audit_log_path,
    )
    presentation_request_output_directory = (
        Path(temporary_registry_directory.name) / "presentation_request"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_request_output_dir
    )
    presentation_request_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "presentation_request.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_request_audit_log_path
    )
    presentation_request_builder = PresentationRequestBuilder.from_directories(
        resolved_settings.presentation_profile_dir,
        presentation_request_output_directory,
        presentation_request_audit_log_path,
        source_bundle_publisher,
    )
    presentation_engine_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "presentation_engine.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_engine_audit_log_path
    )
    dummy_presentation_engine_adapter = DummyPresentationEngineAdapter()
    presentation_engine_runner = PresentationEngineRunner.from_audit_path(
        source_bundle_publisher,
        presentation_engine_audit_log_path,
    )
    provider_payload_output_directory = (
        Path(temporary_registry_directory.name) / "provider_payload"
        if temporary_registry_directory is not None
        else resolved_settings.provider_payload_output_dir
    )
    presentation_response_output_directory = (
        Path(temporary_registry_directory.name) / "presentation_response"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_response_output_dir
    )
    provider_payload_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "provider_payload.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.provider_payload_audit_log_path
    )
    presentation_response_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "presentation_response.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_response_audit_log_path
    )
    provider_payload_resolver = ProviderPayloadResolver.from_directories(
        source_bundle_publisher,
        provider_payload_output_directory,
        provider_payload_audit_log_path,
    )
    traceable_response_service = TraceableResponseService.from_directories(
        presentation_response_output_directory,
        presentation_response_audit_log_path,
    )
    presentation_prompt_output_directory = (
        Path(temporary_registry_directory.name) / "presentation_prompt"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_prompt_output_dir
    )
    presentation_prompt_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "presentation_prompt.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_prompt_audit_log_path
    )
    presentation_prompt_builder = PresentationPromptBuilder.from_directories(
        presentation_prompt_output_directory,
        presentation_prompt_audit_log_path,
    )
    presentation_artifact_output_directory = (
        Path(temporary_registry_directory.name) / "presentation_artifact"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_artifact_output_dir
    )
    presentation_artifact_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "presentation_artifact.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.presentation_artifact_audit_log_path
    )
    presentation_artifact_builder = PresentationArtifactBuilder.from_directories(
        presentation_artifact_output_directory,
        presentation_artifact_audit_log_path,
    )
    presentation_artifact_registry = artifact_registry or (
        SQLitePresentationArtifactRegistry(
            Path(temporary_registry_directory.name)
            / "presentation_artifact_registry.sqlite3"
        )
        if temporary_registry_directory is not None
        else SQLitePresentationArtifactRegistry(
            resolved_settings.presentation_artifact_registry_path
        )
    )
    gemini_response_output_directory = (
        Path(temporary_registry_directory.name) / "gemini_sandbox_response"
        if temporary_registry_directory is not None
        else resolved_settings.gemini_sandbox_response_output_dir
    )
    gemini_sandbox_audit_log_path = (
        Path(temporary_registry_directory.name)
        / "publisher_logs"
        / "gemini_sandbox.jsonl"
        if temporary_registry_directory is not None
        else resolved_settings.gemini_sandbox_audit_log_path
    )
    gemini_config = GeminiAdapterConfig(
        api_key=resolved_settings.gemini_api_key,
        model=resolved_settings.gemini_model,
        endpoint=resolved_settings.gemini_endpoint,
        timeout_seconds=resolved_settings.gemini_timeout_seconds,
        retry_limit=1,
        debug_prompt=resolved_settings.gemini_debug_prompt,
        input_cost_per_million_tokens=(
            resolved_settings.gemini_input_cost_per_million_tokens
        ),
        output_cost_per_million_tokens=(
            resolved_settings.gemini_output_cost_per_million_tokens
        ),
    )
    gemini_sandbox_adapter = gemini_adapter or GeminiSandboxAdapter.from_directories(
        gemini_config,
        gemini_response_output_directory,
        gemini_sandbox_audit_log_path,
    )
    gemini_acceptance_output_root = (
        Path(temporary_registry_directory.name) / "gemini_acceptance"
        if temporary_registry_directory is not None
        else resolved_settings.gemini_sandbox_response_output_dir.parent
        / "gemini_acceptance"
    )
    resolved_gemini_acceptance_service = (
        gemini_acceptance_service
        or GeminiAcceptanceService.from_config(
            gemini_config,
            gemini_acceptance_output_root,
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "gemini_acceptance"
            / "knowledge.json",
            resolved_settings.presentation_profile_dir,
        )
    )
    service = (
        GenerateKnowledge(provider, registry=resolved_registry) if provider is not None else None
    )
    latest_import_metadata: list[ExamMetadataRecord] = []
    pending_previews: dict[str, _PendingCsvPreview] = {}

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/status")
    def status() -> dict[str, object]:
        return {
            "prototype": "Knowledge Workbench Phase 1",
            "schema_version": "1.0",
            "supported_schema_versions": ["0.3", "1.0"],
            "exam_metadata_version": "1.0",
            "exam_metadata_source": "manual_dummy",
            "exam_import_version": "1.0",
            "exam_metadata_providers": ["dummy", "csv"],
            "exam_image_storage": "external_reference",
            "knowledge_registry_version": "1.0",
            "knowledge_registry_storage": "sqlite",
            "knowledge_registry_workflow": "approval_and_merge_mvp",
            "approval_contract_version": "1.0",
            "approval_gate_policy": "approved_only",
            "approval_state_sequence": [
                item.value for item in approval_contract().state_sequence
            ],
            "knowledge_relation_version": "1.1",
            "supported_knowledge_relation_versions": ["1.0", "1.1", "1.2"],
            "knowledge_relation_storage": "independent_sqlite_tables",
            "relation_growth_version": "1.0",
            "relation_resolution_strategy": "indexed_unresolved_only",
            "relation_resolution_report_storage": "sqlite",
            "knowledge_relation_vocabulary": [
                "uses_specimen",
                "uses_reagent",
                "targets_structure",
                "related_method",
            ],
            "disease_relation_vocabulary_version": "1.0",
            "supported_categories": [
                "test_item",
                "staining_method",
                "specimen",
                "reagent",
                "biological_structure",
                "disease",
                "laboratory_test_item",
            ],
            "production_categories": [
                "staining_method",
                "specimen",
                "reagent",
                "biological_structure",
                "disease",
                "laboratory_test_item",
            ],
            "csv_import_flow": ["validation", "preview", "import"],
            "provider": (
                resolved_settings.provider if provider is None else "injected_test_provider"
            ),
            "openai_key_configured": bool(resolved_settings.openai_api_key),
            "medical_review_required": True,
            "source_bundle_schema_version": "1.0",
            "source_bundle_publisher_version": "1.1.0",
            "source_bundle_supported_knowledge_ids": list(
                source_bundle_publisher.supported_knowledge_ids
            ),
            "source_bundle_output": str(source_bundle_output_directory),
            "publisher_approval_audit_log": str(source_bundle_audit_log_path),
            "presentation_contract_version": "1.0",
            "presentation_request_builder_version": "1.0.0",
            "presentation_types": [
                "presentation_document",
                "pdf_material",
                "instagram_slides",
                "training_material",
                "diagram",
                "notebook_material",
            ],
            "presentation_enabled_types": ["presentation_document"],
            "presentation_output_formats": [
                "structured_json",
                "pdf",
                "pptx",
                "png_sequence",
                "html",
                "markdown",
            ],
            "presentation_enabled_output_formats": ["structured_json"],
            "presentation_profile_ids": list(
                presentation_request_builder.supported_profile_ids
            ),
            "presentation_request_output": str(
                presentation_request_output_directory
            ),
            "presentation_request_audit_log": str(
                presentation_request_audit_log_path
            ),
            "presentation_engine_adapter_contract_version": "1.0",
            "presentation_result_contract_version": "1.0",
            "presentation_engine_adapters": [
                dummy_presentation_engine_adapter.provider_name
            ],
            "presentation_engine_external_api_enabled": False,
            "presentation_engine_audit_log": str(
                presentation_engine_audit_log_path
            ),
            "provider_payload_contract_version": "1.0",
            "provider_payload_resolver_version": "1.0.0",
            "provider_payload_preview_policy": "approved_only",
            "data_egress_policy_version": "1.0.0",
            "traceable_response_contract_version": "1.0",
            "provider_payload_output": str(provider_payload_output_directory),
            "presentation_response_output": str(
                presentation_response_output_directory
            ),
            "provider_payload_audit_log": str(
                provider_payload_audit_log_path
            ),
            "presentation_response_audit_log": str(
                presentation_response_audit_log_path
            ),
            "presentation_prompt_contract_version": "1.0",
            "presentation_prompt_builder_version": "1.0.0",
            "presentation_prompt_provider_neutral": True,
            "presentation_prompt_output": str(
                presentation_prompt_output_directory
            ),
            "presentation_prompt_audit_log": str(
                presentation_prompt_audit_log_path
            ),
            "presentation_artifact_contract_version": "1.0",
            "presentation_artifact_builder_version": "1.0.0",
            "presentation_artifact_provider_neutral": True,
            "presentation_artifact_renderer_neutral": True,
            "presentation_artifact_output": str(
                presentation_artifact_output_directory
            ),
            "presentation_artifact_audit_log": str(
                presentation_artifact_audit_log_path
            ),
            "presentation_artifact_registry_version": "1.0",
            "presentation_artifact_registry_storage": "sqlite",
            "presentation_artifact_registry_path": str(
                presentation_artifact_registry.database_path
            ),
            "presentation_artifact_approval_flow": [
                "draft",
                "owner_review",
                "education_review",
                "approved",
                "published",
            ],
            "renderer_artifact_source_policy": "registry_approved_only",
            "gemini_sandbox_adapter_version": "1.0.1",
            "gemini_sandbox_model": gemini_sandbox_adapter.config.model,
            "gemini_sandbox_api_key_configured": bool(
                gemini_sandbox_adapter.config.api_key
            ),
            "gemini_sandbox_external_api_enabled": bool(
                gemini_sandbox_adapter.config.api_key
            ),
            "gemini_sandbox_store_provider_data": False,
            "gemini_sandbox_retry_limit": 1,
            "gemini_sandbox_response_output": str(
                gemini_response_output_directory
            ),
            "gemini_sandbox_audit_log": str(gemini_sandbox_audit_log_path),
            "gemini_acceptance_phase": "5.18.1",
            "gemini_acceptance_fixture_id": (
                resolved_gemini_acceptance_service.fixture_knowledge_id
            ),
            "gemini_acceptance_execution_limit": 1,
        }

    @app.post("/api/gemini-acceptance/preflight")
    def gemini_acceptance_preflight() -> JSONResponse:
        """Prepare an isolated fixture without external communication."""

        try:
            fingerprint = _registry_fingerprint(resolved_registry.snapshot())
            preflight = resolved_gemini_acceptance_service.prepare(fingerprint)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ready" if preflight.can_execute else "blocked",
                    "preflight": preflight.model_dump(mode="json"),
                    "external_ai_called": False,
                    "production_registry_mutated": False,
                },
            )
        except (GeminiAcceptanceError, RegistryOperationError, ValidationError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "gemini_acceptance_preflight_failed",
                            "message": str(error),
                        }
                    ],
                },
            )

    @app.post("/api/gemini-acceptance/execute")
    def execute_gemini_acceptance(
        request: GeminiAcceptanceExecutionRequest,
    ) -> JSONResponse:
        """Execute the explicitly confirmed, one-shot isolated acceptance fixture."""

        try:
            before = _registry_fingerprint(resolved_registry.snapshot())
            result = resolved_gemini_acceptance_service.execute(
                expected_payload_fingerprint=request.payload_fingerprint,
                production_registry_fingerprint=before,
            )
            after = _registry_fingerprint(resolved_registry.snapshot())
            if before != after:
                result = result.model_copy(
                    update={
                        "status": "validation_failed",
                        "production_registry_unchanged": False,
                        "error_code": "production_registry_changed",
                        "error_message": (
                            "実API実行中にProduction RegistryのFingerprintが変化しました。"
                        ),
                    }
                )
            return JSONResponse(
                status_code=200,
                content={
                    "status": result.status,
                    "result": result.model_dump(mode="json"),
                    "external_ai_called": result.transport_result != "not_called",
                    "production_registry_mutated": before != after,
                },
            )
        except GeminiAcceptanceError as error:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "blocked",
                    "errors": [
                        {
                            "code": "gemini_acceptance_execution_blocked",
                            "message": str(error),
                        }
                    ],
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "gemini_acceptance_execution_failed",
                            "message": str(error),
                        }
                    ],
                },
            )

    @app.get("/api/schema/knowledge-1.0")
    def schema_v10() -> dict[str, object]:
        return knowledge_record_json_schema()

    @app.get("/api/schema/knowledge-0.3")
    def schema_v03() -> dict[str, object]:
        return knowledge_record_v03_json_schema()

    @app.get("/api/schema/exam-metadata-1.0")
    def exam_schema_v10() -> dict[str, object]:
        return exam_metadata_json_schema()

    @app.get("/api/schema/knowledge-registry-1.0")
    def registry_schema_v10() -> dict[str, object]:
        return registry_snapshot_json_schema()

    @app.get("/api/schema/knowledge-relation-1.0")
    def relation_schema_v10() -> dict[str, object]:
        return knowledge_relation_v10_json_schema()

    @app.get("/api/schema/knowledge-relation-1.1")
    def relation_schema_v11() -> dict[str, object]:
        return knowledge_relation_v11_json_schema()

    @app.get("/api/schema/knowledge-relation-1.2")
    def relation_schema_v12() -> dict[str, object]:
        return knowledge_relation_v12_json_schema()

    @app.get("/api/schema/relation-vocabulary-disease-1.0")
    def disease_relation_vocabulary_schema() -> dict[str, object]:
        return disease_relation_vocabulary_json_schema()

    @app.get("/api/schema/source-bundle-1.0")
    def source_bundle_schema_v10() -> dict[str, object]:
        return source_bundle_json_schema()

    @app.get("/api/schema/presentation-request-1.0")
    def presentation_request_schema_v10() -> dict[str, object]:
        return presentation_request_json_schema()

    @app.get("/api/schema/presentation-result-1.0")
    def presentation_result_schema_v10() -> dict[str, object]:
        return presentation_result_json_schema()

    @app.get("/api/schema/provider-payload-1.0")
    def provider_payload_schema_v10() -> dict[str, object]:
        return presentation_payload_json_schema()

    @app.get("/api/schema/traceable-response-1.0")
    def traceable_response_schema_v10() -> dict[str, object]:
        return traceable_response_json_schema()

    @app.get("/api/schema/presentation-prompt-1.0")
    def presentation_prompt_schema_v10() -> dict[str, object]:
        return presentation_prompt_json_schema()

    @app.get("/api/schema/presentation-artifact-1.0")
    def presentation_artifact_schema_v10() -> dict[str, object]:
        return presentation_artifact_json_schema()

    @app.get("/api/schema/presentation-artifact-registry-1.0")
    def presentation_artifact_registry_schema_v10() -> dict[str, object]:
        return artifact_registry_json_schema()

    @app.get("/api/schema/approval-contract-1.0")
    def approval_schema_v10() -> dict[str, object]:
        return approval_contract_json_schema()

    @app.get("/api/approval-contract")
    def approval_contract_v10() -> dict[str, object]:
        return approval_contract().model_dump(mode="json")

    @app.get("/api/relation-vocabulary/disease")
    def disease_vocabulary() -> dict[str, object]:
        return disease_relation_vocabulary().model_dump(mode="json")

    @app.get("/api/registry")
    def registry_snapshot() -> dict[str, object]:
        return resolved_registry.snapshot().model_dump(mode="json")

    @app.get("/api/registry/{knowledge_id}")
    def registry_knowledge(knowledge_id: str) -> dict[str, object]:
        return resolved_registry.view(knowledge_id).model_dump(mode="json")

    @app.get("/api/knowledge-relations/{knowledge_id}")
    def knowledge_relations(knowledge_id: str) -> dict[str, object]:
        if resolved_relation_repository is None:
            raise RegistryOperationError("このRegistryはRelation閲覧に未対応です。")
        payload = resolved_relation_repository.view(knowledge_id).model_dump(mode="json")
        payload["network_summary"] = resolved_relation_repository.network_summary(
            knowledge_id
        ).model_dump(mode="json")
        return payload

    @app.get("/api/relation-resolution-reports/{knowledge_id}")
    def relation_resolution_reports(knowledge_id: str) -> list[dict[str, object]]:
        if resolved_relation_repository is None:
            raise RegistryOperationError("このRegistryはResolution Reportに未対応です。")
        return [
            item.model_dump(mode="json")
            for item in resolved_relation_repository.resolution_reports(knowledge_id)
        ]

    def relation_view(knowledge_id: str) -> dict[str, object] | None:
        if resolved_relation_repository is None:
            return None
        payload = resolved_relation_repository.view(knowledge_id).model_dump(mode="json")
        payload["network_summary"] = resolved_relation_repository.network_summary(
            knowledge_id
        ).model_dump(mode="json")
        return payload

    def sync_relations(record: Any, *, actor: str, note: str) -> dict[str, object] | None:
        if relation_service is None:
            return None
        validated = validate_knowledge_record(record)
        payload = relation_service.synchronize(
            validated,
            actor=actor,
            note=note,
        ).model_dump(mode="json")
        if resolved_relation_repository is not None:
            payload["network_summary"] = resolved_relation_repository.network_summary(
                validated.knowledge_id
            ).model_dump(mode="json")
        return payload

    def knowledge_record_response(record: Any) -> dict[str, object]:
        validated = validate_knowledge_record(record)
        completeness = evaluate_knowledge_completeness(validated)
        exam_metadata = DummyExamMetadataProvider().build(
            validated.term.canonical_name,
            validated,
        )
        exam_completeness = evaluate_exam_completeness(exam_metadata, validated)
        registry_view = resolved_registry.view(validated.knowledge_id)
        return {
            "status": "success",
            "schema_valid": True,
            "knowledge_completeness_valid": True,
            "exam_completeness_valid": True,
            "data": validated.model_dump(mode="json"),
            "knowledge_completeness": completeness.model_dump(mode="json"),
            "exam_metadata": exam_metadata.model_dump(mode="json"),
            "exam_completeness": exam_completeness.model_dump(mode="json"),
            "registry": registry_view.model_dump(mode="json"),
            "approval": approval_snapshot_from_registry(
                registry_view.knowledge
            ).model_dump(mode="json"),
            "relations": relation_view(validated.knowledge_id),
            "errors": [],
        }

    @app.get("/api/knowledge-templates/staining-method/gram-stain")
    def gram_stain_starter() -> JSONResponse:
        """Prefer the persisted SSOT; use the starter only before first registration."""

        try:
            persisted = resolved_registry.record("knw_10000004")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(GRAM_STAIN_STARTER_PATH.read_text(encoding="utf-8"))
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/staining-method/acid-fast-stain")
    def acid_fast_stain_starter() -> JSONResponse:
        """Open the persisted acid-fast stain SSOT or its reviewable starter."""

        try:
            persisted = resolved_registry.record("knw_10000010")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(ACID_FAST_STAIN_STARTER_PATH.read_text(encoding="utf-8"))
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/specimen/smear-specimen")
    def specimen_starter() -> JSONResponse:
        """Prefer the persisted Specimen SSOT; otherwise return an editable draft."""

        try:
            persisted = resolved_registry.record("knw_10000005")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(SPECIMEN_STARTER_PATH.read_text(encoding="utf-8"))
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/reagent/{reagent_slug}")
    def reagent_starter(reagent_slug: str) -> JSONResponse:
        """Return one allow-listed Reagent draft, preferring the persisted SSOT."""

        starter_path = REAGENT_STARTER_PATHS.get(reagent_slug)
        if starter_path is None:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "not_found",
                    "schema_valid": False,
                    "errors": [
                        {
                            "code": "reagent_starter_not_found",
                            "message": "指定されたReagent下書きはありません。",
                        }
                    ],
                },
            )
        try:
            draft = validate_knowledge_record(
                json.loads(starter_path.read_text(encoding="utf-8"))
            )
            persisted = resolved_registry.record(draft.knowledge_id)
            record = persisted if persisted is not None else draft
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/biological-structure/bacterial-cell-wall")
    def biological_structure_starter() -> JSONResponse:
        """Open the bacterial-cell-wall SSOT or its editable MVP starter."""

        try:
            persisted = resolved_registry.record("knw_10000011")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(
                        BIOLOGICAL_STRUCTURE_STARTER_PATH.read_text(encoding="utf-8")
                    )
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/disease/iron-deficiency-anemia")
    def disease_starter() -> JSONResponse:
        """Open the iron-deficiency-anemia SSOT or its editable MVP starter."""

        try:
            persisted = resolved_registry.record("knw_10000012")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(DISEASE_STARTER_PATH.read_text(encoding="utf-8"))
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-templates/laboratory-test-item/ferritin")
    def laboratory_test_item_starter() -> JSONResponse:
        """Open the ferritin SSOT or its editable laboratory-test-item starter."""

        try:
            persisted = resolved_registry.record("knw_10000013")
            record = (
                persisted
                if persisted is not None
                else validate_knowledge_record(
                    json.loads(
                        LABORATORY_TEST_ITEM_STARTER_PATH.read_text(encoding="utf-8")
                    )
                )
            )
            completeness = evaluate_knowledge_completeness(record)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "data": record.model_dump(mode="json"),
                    "knowledge_completeness": completeness.model_dump(mode="json"),
                    "relations": relation_view(record.knowledge_id),
                    "persisted": persisted is not None,
                    "errors": [],
                },
            )
        except (OSError, json.JSONDecodeError, KnowledgeSchemaError) as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [{"code": "starter_invalid", "message": str(error)}],
                },
            )

    @app.get("/api/knowledge-records/{knowledge_id}")
    def get_knowledge_record(knowledge_id: str) -> JSONResponse:
        try:
            record = resolved_registry.record(knowledge_id)
            if record is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "not_found",
                        "errors": [
                            {
                                "code": "knowledge_record_not_found",
                                "message": "保存済みKnowledge JSONがありません。",
                            }
                        ],
                    },
                )
            return JSONResponse(status_code=200, content=knowledge_record_response(record))
        except (RegistryOperationError, KnowledgeSchemaError) as error:
            return _registry_error_response(
                error
                if isinstance(error, RegistryOperationError)
                else RegistryOperationError(str(error))
            )

    @app.post("/api/source-bundles/{knowledge_id}")
    def generate_source_bundle(knowledge_id: str) -> JSONResponse:
        """Generate a derived JSON artifact without changing Knowledge or Registry."""

        try:
            record = resolved_registry.record(knowledge_id)
            if record is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "not_found",
                        "errors": [
                            {
                                "code": "knowledge_record_not_found",
                                "message": (
                                    "保存済みKnowledge JSONがありません。"
                                    "先にRegistryへ保存してください。"
                                ),
                            }
                        ],
                    },
                )
            registry_view = resolved_registry.view(knowledge_id)
            exam_metadata = DummyExamMetadataProvider().build(
                record.term.canonical_name,
                record,
            )
            publication = source_bundle_publisher.publish(
                record,
                registry_view,
                exam_metadata,
            )
            publish_decision = source_bundle_publisher.can_publish(registry_view)
            external_ai_decision = (
                source_bundle_publisher.can_send_to_external_ai(registry_view)
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "bundle": publication.bundle.model_dump(mode="json"),
                    "output_path": str(publication.output_path),
                    "approval_gate": {
                        "can_publish": publish_decision.model_dump(mode="json"),
                        "can_send_to_external_ai": external_ai_decision.model_dump(
                            mode="json"
                        ),
                    },
                    "audit_log_path": str(source_bundle_publisher.audit_log_path),
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                },
            )
        except (RegistryOperationError, SourceBundlePublisherError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "source_bundle_generation_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "source_bundle_write_failed",
                            "message": f"Source Bundle JSONを保存できません: {error}",
                        }
                    ],
                },
            )

    @app.post("/api/presentation-requests/{knowledge_id}")
    def generate_presentation_request(
        knowledge_id: str,
        request: PresentationRequestGenerationRequest,
    ) -> JSONResponse:
        """Build a provider-neutral request from the last saved Source Bundle."""

        try:
            record = resolved_registry.record(knowledge_id)
            if record is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "not_found",
                        "errors": [
                            {
                                "code": "knowledge_record_not_found",
                                "message": (
                                    "保存済みKnowledge JSONがありません。"
                                    "先にRegistryへ保存してください。"
                                ),
                            }
                        ],
                    },
                )
            registry_view = resolved_registry.view(knowledge_id)
            source_path = source_bundle_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}"
                ".source-bundle.json"
            )
            if not source_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "source_bundle_required",
                        "errors": [
                            {
                                "code": "source_bundle_required",
                                "message": (
                                    "先に現在のKnowledge Versionから"
                                    "Source Bundleを生成してください。"
                                ),
                            }
                        ],
                    },
                )
            source_bundle = SourceBundle.model_validate_json(
                source_path.read_text(encoding="utf-8")
            )
            exam_metadata = DummyExamMetadataProvider().build(
                record.term.canonical_name,
                record,
            )
            expected_fingerprint = source_bundle_publisher.source_fingerprint(
                record,
                registry_view,
                exam_metadata,
            )
            result = presentation_request_builder.build(
                source_bundle,
                registry_view,
                expected_source_fingerprint=expected_fingerprint,
                profile_id=request.profile_id,
                profile_version=request.profile_version,
                request_mode=request.request_mode,
            )
            return JSONResponse(
                status_code=200,
                content={
                    **result.model_dump(mode="json"),
                    "source_bundle_path": str(source_path),
                    "request_context": {
                        "presentation_type": "presentation_document",
                        "output_format": "structured_json",
                        "profile_id": request.profile_id,
                        "profile_version": request.profile_version,
                        "request_mode": request.request_mode.value,
                        "approval_state": source_bundle.metadata.approval_state.value,
                        "knowledge_version": source_bundle.metadata.version,
                        "source_fingerprint": (
                            source_bundle.metadata.source_fingerprint
                        ),
                        "claim_count": len(source_bundle.claims),
                        "key_message_count": len(source_bundle.key_messages),
                        "diagram_request_count": len(
                            source_bundle.diagram_requests
                        ),
                    },
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                    "external_ai_called": False,
                },
            )

        except (
            RegistryOperationError,
            SourceBundlePublisherError,
            PresentationRequestBuilderError,
            ValidationError,
        ) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_request_generation_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_request_write_failed",
                            "message": (
                                "Presentation Requestを読み書きできません: "
                                f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.post("/api/presentation-artifacts/{knowledge_id}")
    def generate_presentation_artifact(
        knowledge_id: str,
        request: PresentationArtifactGenerationRequest,
    ) -> JSONResponse:
        """Compose and validate the provider-neutral educational SSOT artifact."""

        try:
            record = resolved_registry.record(knowledge_id)
            if record is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "not_found",
                        "errors": [
                            {
                                "code": "knowledge_record_not_found",
                                "message": "保存済みKnowledge JSONがありません。",
                            }
                        ],
                    },
                )
            registry_view = resolved_registry.view(knowledge_id)
            source_path = source_bundle_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}"
                ".source-bundle.json"
            )
            request_path = presentation_request_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}."
                f"{request.request_mode.value}.presentation-request.json"
            )
            if not source_path.is_file() or not request_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "presentation_sources_required",
                        "errors": [
                            {
                                "code": "presentation_sources_required",
                                "message": (
                                    "先に同じ版のSource BundleとPresentation Requestを"
                                    "生成してください。"
                                ),
                            }
                        ],
                    },
                )
            source_bundle = SourceBundle.model_validate_json(
                source_path.read_text(encoding="utf-8")
            )
            presentation_request = PresentationRequest.model_validate_json(
                request_path.read_text(encoding="utf-8")
            )
            result = presentation_artifact_builder.build(
                presentation_request,
                source_bundle,
                record,
            )
            artifact = result.artifact
            if artifact is None or not result.validation.is_valid:
                return JSONResponse(
                    status_code=422,
                    content={
                        **result.model_dump(mode="json"),
                        "status": "artifact_validation_failed",
                        "artifact_registry_mutated": False,
                        "knowledge_mutated": False,
                    },
                )
            registered = presentation_artifact_registry.register(
                artifact,
                owner=request.owner,
                actor=request.actor,
                review_comment=request.review_comment,
                expected_knowledge_version=(
                    registry_view.knowledge.knowledge_version
                ),
            )
            artifact = registered.artifact
            completeness = evaluate_artifact_completeness(artifact)
            registry_validation = presentation_artifact_registry.validate(
                {
                    item.knowledge_id: item.knowledge_version
                    for item in resolved_registry.snapshot().knowledge
                }
            )
            return JSONResponse(
                status_code=200,
                content={
                    **result.model_dump(mode="json"),
                    "artifact": artifact.model_dump(mode="json"),
                    "registry_entry": registered.entry.model_dump(mode="json"),
                    "artifact_completeness": completeness.model_dump(mode="json"),
                    "artifact_registry_validation": registry_validation.model_dump(
                        mode="json"
                    ),
                    "artifact_context": {
                        "artifact_id": (
                            artifact.identity.artifact_id if artifact else None
                        ),
                        "artifact_version": (
                            artifact.identity.artifact_version if artifact else None
                        ),
                        "page_count": len(artifact.pages) if artifact else 0,
                        "claim_count": (
                            len(artifact.claim_catalog) if artifact else 0
                        ),
                        "diagram_count": (
                            sum(
                                len(page.diagram_instruction.items)
                                for page in artifact.pages
                                if page.diagram_instruction is not None
                            )
                            if artifact
                            else 0
                        ),
                        "reference_count": (
                            len(artifact.reference_catalog) if artifact else 0
                        ),
                        "fingerprint": (
                            artifact.metadata.fingerprint if artifact else None
                        ),
                        "validation": (
                            "passed" if result.validation.is_valid else "failed"
                        ),
                        "builder_version": (
                            artifact.metadata.builder_version if artifact else "1.0.0"
                        ),
                    },
                    "source_bundle_path": str(source_path),
                    "presentation_request_path": str(request_path),
                    "builder_output_path": result.output_path,
                    "artifact_registry_path": str(
                        presentation_artifact_registry.database_path
                    ),
                    "registry_mutated": False,
                    "artifact_registry_mutated": True,
                    "knowledge_mutated": False,
                    "external_ai_called": False,
                    "renderer_called": False,
                },
            )
        except (
            ArtifactRegistryError,
            RegistryOperationError,
            ValidationError,
            ValueError,
        ) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_artifact_generation_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_artifact_write_failed",
                            "message": (
                                "Presentation Artifactを読み書きできません: "
                                f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.post("/api/presentation-engine/{knowledge_id}/execute")
    def execute_presentation_engine(
        knowledge_id: str,
        request: PresentationEngineExecutionRequest,
    ) -> JSONResponse:
        """Run a metadata-only Dummy Adapter without any external AI call."""

        try:
            registry_view = resolved_registry.view(knowledge_id)
            request_path = presentation_request_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}."
                f"{request.request_mode.value}.presentation-request.json"
            )

            if not request_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "presentation_request_required",
                        "errors": [
                            {
                                "code": "presentation_request_required",
                                "message": (
                                    "先に同じModeのPresentation Requestを"
                                    "生成してください。"
                                ),
                            }
                        ],
                    },
                )
            presentation_request = PresentationRequest.model_validate_json(
                request_path.read_text(encoding="utf-8")
            )
            outcome = presentation_engine_runner.run(
                presentation_request,
                registry_view,
                dummy_presentation_engine_adapter,
            )
            artifact = (
                outcome.result.generated_artifacts[0]
                if outcome.result.generated_artifacts
                else None
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": outcome.result.status.value,
                    "result": outcome.result.model_dump(mode="json"),
                    "adapter": outcome.adapter.model_dump(mode="json"),
                    "request_fingerprint": outcome.request_fingerprint,
                    "approval_gate": outcome.approval_gate.model_dump(mode="json"),
                    "request_path": str(request_path),
                    "audit_log_path": outcome.audit_log_path,
                    "engine_context": {
                        "mode": request.request_mode.value,
                        "provider": outcome.adapter.provider_name,
                        "provider_version": outcome.adapter.provider_version,
                        "validation": (
                            "passed"
                            if outcome.result.validation_result.is_valid
                            else "failed"
                        ),
                        "pages": artifact.pages if artifact is not None else 0,
                        "claims_used": (
                            artifact.claims_used if artifact is not None else 0
                        ),
                        "diagram_requests": (
                            artifact.diagram_requests if artifact is not None else 0
                        ),
                        "references": (
                            artifact.references if artifact is not None else 0
                        ),
                        "output_type": (
                            artifact.output_type.value
                            if artifact is not None
                            else presentation_request.presentation.presentation_type.value
                        ),
                    },
                    "external_ai_called": False,
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_engine_execution_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_engine_audit_failed",
                            "message": (
                                "Presentation Engine監査ログを保存できません: "
                                f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.get("/api/artifact-registry")
    def artifact_registry_snapshot() -> dict[str, object]:
        knowledge_versions = {
            item.knowledge_id: item.knowledge_version
            for item in resolved_registry.snapshot().knowledge
        }
        return {
            "registry": presentation_artifact_registry.list_artifacts().model_dump(
                mode="json"
            ),
            "validation": presentation_artifact_registry.validate(
                knowledge_versions
            ).model_dump(mode="json"),
            "renderer_source_policy": "registry_approved_only",
        }

    @app.get("/api/artifact-registry/{artifact_id}")
    def artifact_registry_view(artifact_id: str) -> JSONResponse:
        try:
            view = presentation_artifact_registry.view(artifact_id)
            current = presentation_artifact_registry.version(
                artifact_id,
                view.current.artifact_version,
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "registry": view.model_dump(mode="json"),
                    "artifact": current.artifact.model_dump(mode="json"),
                    "completeness": evaluate_artifact_completeness(
                        current.artifact
                    ).model_dump(mode="json"),
                },
            )
        except ArtifactNotFoundError as error:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "errors": [str(error)]},
            )

    @app.get(
        "/api/artifact-registry/{artifact_id}/versions/{artifact_version}"
    )
    def artifact_registry_version(
        artifact_id: str,
        artifact_version: int,
    ) -> JSONResponse:
        try:
            version = presentation_artifact_registry.version(
                artifact_id,
                artifact_version,
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "version": version.model_dump(mode="json"),
                    "completeness": evaluate_artifact_completeness(
                        version.artifact
                    ).model_dump(mode="json"),
                },
            )
        except ArtifactNotFoundError as error:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "errors": [str(error)]},
            )

    @app.post(
        "/api/artifact-registry/{artifact_id}/versions/{artifact_version}/approval"
    )
    def artifact_registry_approval(
        artifact_id: str,
        artifact_version: int,
        request: ArtifactApprovalTransitionApiRequest,
    ) -> JSONResponse:
        try:
            updated = presentation_artifact_registry.transition_approval(
                artifact_id,
                artifact_version,
                request.target_state,
                actor=request.actor,
                review_comment=request.review_comment,
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "version": updated.model_dump(mode="json"),
                    "knowledge_registry_mutated": False,
                },
            )
        except ArtifactNotFoundError as error:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "errors": [str(error)]},
            )
        except ArtifactRegistryError as error:
            return JSONResponse(
                status_code=422,
                content={"status": "invalid_transition", "errors": [str(error)]},
            )

    @app.get("/api/artifact-registry/{artifact_id}/diff")
    def artifact_registry_diff(
        artifact_id: str,
        from_version: int,
        to_version: int,
    ) -> JSONResponse:
        try:
            report = presentation_artifact_registry.diff(
                artifact_id,
                from_version,
                to_version,
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "diff": report.model_dump(mode="json"),
                },
            )
        except ArtifactNotFoundError as error:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "errors": [str(error)]},
            )

    @app.get("/api/artifact-registry/{artifact_id}/render-source")
    def artifact_registry_render_source(
        artifact_id: str,
        artifact_version: int | None = None,
    ) -> JSONResponse:
        try:
            artifact = presentation_artifact_registry.get_approved_for_render(
                artifact_id,
                artifact_version=artifact_version,
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "approved",
                    "renderer_source_policy": "registry_approved_only",
                    "artifact": artifact.model_dump(mode="json"),
                },
            )
        except ArtifactNotFoundError as error:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "errors": [str(error)]},
            )
        except ArtifactRegistryError as error:
            return JSONResponse(
                status_code=403,
                content={"status": "render_blocked", "errors": [str(error)]},
            )

    @app.post("/api/provider-payloads/{knowledge_id}")
    def generate_provider_payload(
        knowledge_id: str,
        request: ProviderPayloadExecutionRequest,
    ) -> JSONResponse:
        """Resolve selected approved SSOT facts without external communication."""

        try:
            record = resolved_registry.record(knowledge_id)
            if record is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "not_found",
                        "errors": [
                            {
                                "code": "knowledge_record_not_found",
                                "message": "保存済みKnowledge JSONがありません。",
                            }
                        ],
                    },
                )
            registry_view = resolved_registry.view(knowledge_id)
            source_path = source_bundle_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}"
                ".source-bundle.json"
            )
            request_path = presentation_request_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}."
                f"{request.request_mode.value}.presentation-request.json"
            )
            if not source_path.is_file() or not request_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "presentation_sources_required",
                        "errors": [
                            {
                                "code": "presentation_sources_required",
                                "message": (
                                    "先に同じ版のSource BundleとPresentation Requestを"
                                    "生成してください。"
                                ),
                            }
                        ],
                    },
                )
            source_bundle = SourceBundle.model_validate_json(
                source_path.read_text(encoding="utf-8")
            )
            presentation_request = PresentationRequest.model_validate_json(
                request_path.read_text(encoding="utf-8")
            )
            exam_metadata = DummyExamMetadataProvider().build(
                record.term.canonical_name,
                record,
            )
            expected_fingerprint = source_bundle_publisher.source_fingerprint(
                record,
                registry_view,
                exam_metadata,
            )
            result = provider_payload_resolver.resolve(
                presentation_request,
                source_bundle,
                registry_view,
                exam_metadata,
                expected_source_fingerprint=expected_fingerprint,
            )
            payload = result.payload
            return JSONResponse(
                status_code=200,
                content={
                    **result.model_dump(mode="json"),
                    "payload_context": {
                        "payload_id": result.attempted_payload_id,
                        "payload_contract_version": "1.0",
                        "request_id": (
                            presentation_request.identity.presentation_request_id
                        ),
                        "knowledge_id": knowledge_id,
                        "knowledge_version": (
                            registry_view.knowledge.knowledge_version
                        ),
                        "approval_state": registry_view.knowledge.status.value,
                        "payload_fingerprint": (
                            payload.metadata.payload_fingerprint if payload else None
                        ),
                        "claim_count": (
                            len(payload.medical_content.selected_claims)
                            if payload
                            else 0
                        ),
                        "key_message_count": (
                            len(payload.medical_content.key_messages)
                            if payload
                            else 0
                        ),
                        "exam_point_count": (
                            len(payload.medical_content.exam_points)
                            if payload
                            else 0
                        ),
                        "diagram_request_count": (
                            len(payload.visual_content.diagram_requests)
                            if payload
                            else 0
                        ),
                        "reference_count": (
                            len(payload.medical_content.references)
                            if payload
                            else 0
                        ),
                        "external_use_allowed": result.external_use_allowed,
                    },
                    "source_bundle_path": str(source_path),
                    "presentation_request_path": str(request_path),
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                    "external_ai_called": False,
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "provider_payload_resolution_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "provider_payload_write_failed",
                            "message": f"Provider Payloadを保存できません: {error}",
                        }
                    ],
                },
            )

    @app.post("/api/provider-payloads/{knowledge_id}/execute-dummy")
    def execute_traceable_dummy(
        knowledge_id: str,
        request: ProviderPayloadExecutionRequest,
    ) -> JSONResponse:
        """Run the traceable Dummy path against a validated saved Payload."""

        try:
            registry_view = resolved_registry.view(knowledge_id)
            payload_path = provider_payload_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}."
                f"{request.request_mode.value}.provider-payload.json"
            )
            if not payload_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "provider_payload_required",
                        "errors": [
                            {
                                "code": "provider_payload_required",
                                "message": (
                                    "先に承認済み正本からProvider Payloadを"
                                    "生成してください。"
                                ),
                            }
                        ],
                    },
                )
            payload = PresentationPayload.model_validate_json(
                payload_path.read_text(encoding="utf-8")
            )
            response = dummy_presentation_engine_adapter.execute_traceable_payload(
                payload
            )
            outcome = traceable_response_service.accept(payload, response)
            trace = outcome.response.traceability
            validation = outcome.response.validation
            return JSONResponse(
                status_code=200,
                content={
                    "status": outcome.status,
                    "response": outcome.response.model_dump(mode="json"),
                    "response_context": {
                        "response_id": outcome.response.identity.response_id,
                        "provider": outcome.response.provider.provider_name,
                        "provider_version": (
                            outcome.response.provider.provider_version
                        ),
                        "execution_status": (
                            outcome.response.execution.status.value
                        ),
                        "payload_fingerprint_match": (
                            validation.fingerprint_result
                        ),
                        "used_claim_count": len(trace.used_claim_ids),
                        "used_diagram_request_count": len(
                            trace.used_diagram_request_ids
                        ),
                        "used_reference_count": len(trace.used_reference_ids),
                        "validation_result": validation.is_valid,
                    },
                    "payload_path": str(payload_path),
                    "output_path": outcome.output_path,
                    "audit_log_path": outcome.audit_log_path,
                    "external_ai_called": False,
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "traceable_dummy_execution_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "traceable_response_write_failed",
                            "message": (
                                "Traceable Responseを保存できません: " f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.post("/api/presentation-prompts/{knowledge_id}")
    def generate_presentation_prompt(
        knowledge_id: str,
        request: PresentationPromptExecutionRequest,
    ) -> JSONResponse:
        """Build a Provider-neutral Presentation Prompt from a saved Payload."""

        try:
            registry_view = resolved_registry.view(knowledge_id)
            payload_path = provider_payload_output_directory / (
                f"{knowledge_id}_v{registry_view.knowledge.knowledge_version}."
                f"{request.request_mode.value}.provider-payload.json"
            )
            if not payload_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "provider_payload_required",
                        "errors": [
                            {
                                "code": "provider_payload_required",
                                "message": (
                                    "先に同じ版・同じModeのProvider Payloadを"
                                    "生成してください。"
                                ),
                            }
                        ],
                    },
                )
            payload = PresentationPayload.model_validate_json(
                payload_path.read_text(encoding="utf-8")
            )
            result = presentation_prompt_builder.build(payload)
            prompt = result.prompt
            return JSONResponse(
                status_code=200,
                content={
                    **result.model_dump(mode="json"),
                    "prompt_context": {
                        "prompt_id": result.attempted_prompt_id,
                        "prompt_contract_version": "1.0",
                        "prompt_builder_version": "1.0.0",
                        "provider_neutral": True,
                        "payload_id": payload.identity.payload_id,
                        "payload_fingerprint": (
                            payload.metadata.payload_fingerprint
                        ),
                        "prompt_fingerprint": (
                            prompt.metadata.prompt_fingerprint if prompt else None
                        ),
                        "request_mode": request.request_mode.value,
                        "approval_state": payload.source.approval_state.value,
                        "claim_count": len(prompt.claims) if prompt else 0,
                        "key_message_count": (
                            len(prompt.key_messages) if prompt else 0
                        ),
                        "diagram_request_count": (
                            len(prompt.diagram_requests) if prompt else 0
                        ),
                        "reference_count": len(prompt.references) if prompt else 0,
                    },
                    "payload_path": str(payload_path),
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                    "provider_called": False,
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_prompt_build_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "presentation_prompt_write_failed",
                            "message": (
                                "Presentation Promptを保存できません: " f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.post("/api/presentation-prompts/{knowledge_id}/execute-gemini")
    def execute_gemini_sandbox(
        knowledge_id: str,
        request: GeminiSandboxExecutionRequest,
    ) -> JSONResponse:
        """Execute Gemini Sandbox after approval and fingerprint preflight."""

        try:
            registry_view = resolved_registry.view(knowledge_id)
            version = registry_view.knowledge.knowledge_version
            payload_path = provider_payload_output_directory / (
                f"{knowledge_id}_v{version}.external.provider-payload.json"
            )
            prompt_path = presentation_prompt_output_directory / (
                f"{knowledge_id}_v{version}.external.presentation-prompt.json"
            )
            if not payload_path.is_file() or not prompt_path.is_file():
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "presentation_prompt_required",
                        "errors": [
                            {
                                "code": "presentation_prompt_required",
                                "message": (
                                    "先に承認済みExternal Provider Payloadと"
                                    "Presentation Promptを生成してください。"
                                ),
                            }
                        ],
                    },
                )
            payload = PresentationPayload.model_validate_json(
                payload_path.read_text(encoding="utf-8")
            )
            prompt = PresentationPrompt.model_validate_json(
                prompt_path.read_text(encoding="utf-8")
            )
            result = gemini_sandbox_adapter.execute(payload, prompt)
            return JSONResponse(
                status_code=200,
                content={
                    "status": result.response.execution.status.value,
                    "response": result.response.model_dump(mode="json"),
                    "sandbox_report": result.report.model_dump(mode="json"),
                    "gemini_prompt_debug": result.gemini_prompt_debug,
                    "gemini_prompt_visible": (
                        result.gemini_prompt_debug is not None
                    ),
                    "payload_path": str(payload_path),
                    "prompt_path": str(prompt_path),
                    "registry_mutated": False,
                    "knowledge_mutated": False,
                },
            )
        except (RegistryOperationError, ValidationError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "gemini_sandbox_execution_failed",
                            "message": str(error),
                        }
                    ],
                },
            )
        except OSError as error:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "gemini_sandbox_audit_failed",
                            "message": (
                                "Gemini Sandbox監査ログを保存できません: " f"{error}"
                            ),
                        }
                    ],
                },
            )

    @app.put("/api/knowledge-records/{knowledge_id}")
    def save_knowledge_record(
        knowledge_id: str, request: KnowledgeRecordSaveRequest
    ) -> JSONResponse:
        try:
            record = validate_knowledge_record(request.record)
            if record.knowledge_id != knowledge_id:
                raise RegistryOperationError(
                    "URLのknowledge_idとJSON内のknowledge_idが一致しません。"
                )
            reconciliation = resolved_registry.reconcile(
                record,
                actor=request.actor.strip(),
                note=request.comment.strip(),
            )
            relations = sync_relations(
                reconciliation.record,
                actor=request.actor.strip(),
                note=request.comment.strip(),
            )
            resolution_report = None
            if relation_service is not None:
                resolution_report = relation_service.resolve_for_target(
                    reconciliation.record,
                    actor=request.actor.strip(),
                    note="Knowledge保存イベントによる索引候補の再評価",
                )
            response = knowledge_record_response(reconciliation.record)
            response["relations"] = relations
            response["resolution_report"] = (
                resolution_report.model_dump(mode="json")
                if resolution_report is not None
                else None
            )
            response["save_comment"] = request.comment.strip()
            return JSONResponse(status_code=200, content=response)
        except KnowledgeSchemaError as error:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "errors": [
                        {
                            "code": "knowledge_schema_error",
                            "message": str(error),
                            "path": error.path,
                        }
                    ],
                },
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/registry/{knowledge_id}/status")
    def registry_knowledge_status(
        knowledge_id: str, request: RegistryStatusRequest
    ) -> JSONResponse:
        try:
            resolved_registry.transition_status(
                RegistryEntityType.KNOWLEDGE,
                knowledge_id,
                request.target_status,
                actor=request.actor.strip(),
                note=request.comment.strip(),
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "registry": resolved_registry.view(knowledge_id).model_dump(mode="json"),
                },
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/registry/{knowledge_id}/claims/status")
    def registry_claim_status(knowledge_id: str, request: ClaimStatusRequest) -> JSONResponse:
        try:
            view = resolved_registry.transition_claims_status(
                request.claim_ids,
                request.target_status,
                actor=request.actor.strip(),
                note=request.comment.strip(),
            )
            if view.knowledge.knowledge_id != knowledge_id:
                raise RegistryOperationError("KnowledgeとClaimの指定が一致しません。")
            return JSONResponse(
                status_code=200,
                content={"status": "success", "registry": view.model_dump(mode="json")},
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/registry/{knowledge_id}/claims/merge")
    def registry_claim_merge(knowledge_id: str, request: ClaimMergeRequest) -> JSONResponse:
        try:
            view = resolved_registry.merge_claims(
                knowledge_id,
                request.target_claim_id,
                request.source_claim_ids,
                actor=request.actor.strip(),
                comment=request.comment.strip(),
            )
            return JSONResponse(
                status_code=200,
                content={"status": "success", "registry": view.model_dump(mode="json")},
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.get("/api/registry-backups")
    def registry_backups() -> dict[str, object]:
        if backup_manager is None:
            return {"status": "unavailable", "backups": []}
        return {
            "status": "success",
            "backups": [item.as_dict() for item in backup_manager.list_backups()],
        }

    @app.post("/api/registry-backups")
    def registry_create_backup() -> JSONResponse:
        if backup_manager is None:
            return _registry_error_response(
                RegistryOperationError("この保存先はBackupに未対応です。")
            )
        try:
            backup = backup_manager.create_backup()
            return JSONResponse(
                status_code=200,
                content={"status": "success", "backup": backup.as_dict()},
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/registry-backups/restore")
    def registry_restore_backup(request: RegistryRestoreRequest) -> JSONResponse:
        nonlocal latest_import_metadata
        if backup_manager is None:
            return _registry_error_response(
                RegistryOperationError("この保存先はRestoreに未対応です。")
            )
        try:
            result = backup_manager.restore(request.filename)
            if resolved_relation_repository is not None:
                resolved_relation_repository.ensure_schema()
            latest_import_metadata = []
            pending_previews.clear()
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "restored": result.restored.as_dict(),
                    "safety_backup": result.safety_backup.as_dict(),
                    "registry": resolved_registry.snapshot().model_dump(mode="json"),
                },
            )
        except RegistryOperationError as error:
            return _registry_error_response(error)

    def create_preview(
        csv_text: str,
        source_file: str,
        import_mode: Literal["append", "replace"],
    ) -> tuple[ExamImportExecutionResult, CsvImportPreview]:
        if not isinstance(resolved_registry, SQLiteKnowledgeRegistry):
            raise RegistryOperationError("現在のRegistry Providerは安全なPreviewに未対応です。")
        before = resolved_registry.snapshot()
        fingerprint = _registry_fingerprint(before)
        with TemporaryDirectory(prefix="bluprnt-import-preview-") as directory:
            preview_registry_path = Path(directory) / "registry-preview.db"
            resolved_registry.backup_to(preview_registry_path)
            preview_registry = SQLiteKnowledgeRegistry(preview_registry_path)
            result = import_exam_csv(
                csv_text,
                source_file,
                previous_metadata=latest_import_metadata,
                registry=preview_registry,
                import_mode=import_mode,
            )
            after = preview_registry.snapshot()
        preview = _build_import_preview(result, before, after, fingerprint)
        pending_previews[preview.preview_id] = _PendingCsvPreview(
            csv_text=csv_text,
            source_file=source_file,
            import_mode=import_mode,
            registry_fingerprint=fingerprint,
            preview=preview,
        )
        return result, preview

    @app.post("/api/import/exam-csv/preview/sample")
    @app.post("/api/import/exam-csv/sample")
    def preview_sample_csv() -> JSONResponse:
        try:
            result, preview = create_preview(
                SAMPLE_CSV_PATH.read_text(encoding="utf-8-sig"),
                SAMPLE_CSV_PATH.name,
                "replace",
            )
            return _import_response(result, phase="preview", preview=preview)
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/import/exam-csv/preview")
    @app.post("/api/import/exam-csv")
    def preview_csv(request: CsvImportRequest) -> JSONResponse:
        mapping = load_exam_csv_mapping()
        try:
            csv_text = base64.b64decode(request.csv_base64, validate=True).decode(mapping.encoding)
        except UnicodeDecodeError:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "errors": [
                        {
                            "code": "csv_encoding_error",
                            "message": (
                                f"CSVを{mapping.encoding}として読めません。"
                                "Mappingのencodingを確認してください。"
                            ),
                        }
                    ],
                },
            )
        try:
            result, preview = create_preview(
                csv_text,
                request.source_file,
                request.import_mode,
            )
            return _import_response(result, phase="preview", preview=preview)
        except RegistryOperationError as error:
            return _registry_error_response(error)

    @app.post("/api/import/exam-csv/commit")
    def commit_csv(request: ImportCommitRequest) -> JSONResponse:
        nonlocal latest_import_metadata
        pending = pending_previews.get(request.preview_id)
        if pending is None:
            return _registry_error_response(
                RegistryOperationError(
                    "Previewが見つかりません。CSVをもう一度Previewしてください。"
                )
            )
        if not pending.preview.can_commit:
            return _registry_error_response(
                RegistryOperationError("Validation ErrorがあるためImportを確定できません。")
            )
        current_fingerprint = _registry_fingerprint(resolved_registry.snapshot())
        if current_fingerprint != pending.registry_fingerprint:
            pending_previews.pop(request.preview_id, None)
            return JSONResponse(
                status_code=409,
                content={
                    "status": "registry_changed",
                    "errors": [
                        {
                            "code": "registry_changed_after_preview",
                            "message": (
                                "Preview後にRegistryが変更されました。"
                                "安全のため再Previewしてください。"
                            ),
                        }
                    ],
                },
            )
        result = import_exam_csv(
            pending.csv_text,
            pending.source_file,
            previous_metadata=latest_import_metadata,
            registry=resolved_registry,
            import_mode=pending.import_mode,
        )
        if result.outcome.report.validation.can_import:
            latest_import_metadata = result.outcome.exam_metadata
            pending_previews.pop(request.preview_id, None)
        return _import_response(result, phase="imported", preview=pending.preview)

    @app.post("/api/generate")
    def generate(request: GenerateRequest) -> JSONResponse:
        try:
            active_service = service
            if active_service is None:
                active_service = GenerateKnowledge(
                    build_provider(resolved_settings),
                    registry=resolved_registry,
                )
            outcome = active_service.execute(request.term)
            relations = sync_relations(
                outcome.record,
                actor="knowledge_workbench",
                note="Knowledge生成後のRelation同期",
            )
            resolution_report = (
                relation_service.resolve_for_target(
                    outcome.record,
                    actor="knowledge_workbench",
                    note="Knowledge生成イベントによる索引候補の再評価",
                )
                if relation_service is not None
                else None
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "schema_valid": True,
                    "completeness_valid": True,
                    "knowledge_completeness_valid": True,
                    "exam_completeness_valid": True,
                    "completeness": outcome.knowledge_completeness.model_dump(mode="json"),
                    "knowledge_completeness": outcome.knowledge_completeness.model_dump(
                        mode="json"
                    ),
                    "exam_completeness": outcome.exam_completeness.model_dump(mode="json"),
                    "data": outcome.record.model_dump(mode="json"),
                    "exam_metadata": outcome.exam_metadata.model_dump(mode="json"),
                    "registry": (
                        outcome.registry.model_dump(mode="json")
                        if outcome.registry is not None
                        else None
                    ),
                    "relations": relations,
                    "resolution_report": (
                        resolution_report.model_dump(mode="json")
                        if resolution_report is not None
                        else None
                    ),
                    "errors": [],
                },
            )
        except WorkbenchError as error:
            return JSONResponse(
                status_code=422 if error.code == "invalid_term" else 503,
                content={
                    "status": "error",
                    "schema_valid": False,
                    "completeness_valid": False,
                    "knowledge_completeness_valid": False,
                    "exam_completeness_valid": False,
                    "completeness": None,
                    "knowledge_completeness": None,
                    "exam_completeness": None,
                    "data": None,
                    "exam_metadata": None,
                    "registry": None,
                    "relations": None,
                    "errors": [{"code": error.code, "message": error.message}],
                },
            )

    return app


app = create_app()
