"""Environment-based prototype configuration."""

import os
from dataclasses import dataclass
from pathlib import Path

from knowledge_workbench.errors import ProviderConfigurationError
from knowledge_workbench.providers.base import KnowledgeProvider
from knowledge_workbench.providers.openai_provider import OpenAIKnowledgeProvider

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_registry.sqlite3"
DEFAULT_REGISTRY_BACKUP_DIR = DEFAULT_REGISTRY_PATH.parent / "backups"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE_BUNDLE_PROFILE_DIR = (
    REPOSITORY_ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
)
DEFAULT_SOURCE_BUNDLE_OUTPUT_DIR = (
    REPOSITORY_ROOT / "Publisher Output" / "source_bundle"
)
DEFAULT_SOURCE_BUNDLE_AUDIT_LOG_PATH = (
    REPOSITORY_ROOT / "Publisher Output" / "logs" / "approval_gate.jsonl"
)
DEFAULT_PRESENTATION_PROFILE_DIR = (
    REPOSITORY_ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
)
DEFAULT_PRESENTATION_REQUEST_OUTPUT_DIR = (
    REPOSITORY_ROOT / "Publisher Output" / "presentation_request"
)
DEFAULT_PRESENTATION_REQUEST_AUDIT_LOG_PATH = (
    REPOSITORY_ROOT / "Publisher Output" / "logs" / "presentation_request.jsonl"
)
DEFAULT_PRESENTATION_ENGINE_AUDIT_LOG_PATH = (
    REPOSITORY_ROOT / "Publisher Output" / "logs" / "presentation_engine.jsonl"
)
DEFAULT_PROVIDER_PAYLOAD_OUTPUT_DIR = (
    REPOSITORY_ROOT / "Publisher Output" / "provider_payload"
)
DEFAULT_PRESENTATION_RESPONSE_OUTPUT_DIR = (
    REPOSITORY_ROOT / "Publisher Output" / "presentation_response"
)
DEFAULT_PROVIDER_PAYLOAD_AUDIT_LOG_PATH = (
    REPOSITORY_ROOT / "Publisher Output" / "logs" / "provider_payload.jsonl"
)
DEFAULT_PRESENTATION_RESPONSE_AUDIT_LOG_PATH = (
    REPOSITORY_ROOT / "Publisher Output" / "logs" / "presentation_response.jsonl"
)


@dataclass(frozen=True)
class Settings:
    provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-terra"
    registry_path: Path = DEFAULT_REGISTRY_PATH
    registry_backup_dir: Path = DEFAULT_REGISTRY_BACKUP_DIR
    source_bundle_profile_dir: Path = DEFAULT_SOURCE_BUNDLE_PROFILE_DIR
    source_bundle_output_dir: Path = DEFAULT_SOURCE_BUNDLE_OUTPUT_DIR
    source_bundle_audit_log_path: Path = DEFAULT_SOURCE_BUNDLE_AUDIT_LOG_PATH
    presentation_profile_dir: Path = DEFAULT_PRESENTATION_PROFILE_DIR
    presentation_request_output_dir: Path = DEFAULT_PRESENTATION_REQUEST_OUTPUT_DIR
    presentation_request_audit_log_path: Path = DEFAULT_PRESENTATION_REQUEST_AUDIT_LOG_PATH
    presentation_engine_audit_log_path: Path = DEFAULT_PRESENTATION_ENGINE_AUDIT_LOG_PATH
    provider_payload_output_dir: Path = DEFAULT_PROVIDER_PAYLOAD_OUTPUT_DIR
    presentation_response_output_dir: Path = DEFAULT_PRESENTATION_RESPONSE_OUTPUT_DIR
    provider_payload_audit_log_path: Path = DEFAULT_PROVIDER_PAYLOAD_AUDIT_LOG_PATH
    presentation_response_audit_log_path: Path = (
        DEFAULT_PRESENTATION_RESPONSE_AUDIT_LOG_PATH
    )

    @classmethod
    def from_environment(cls) -> "Settings":
        registry_path = os.getenv("KNOWLEDGE_REGISTRY_PATH", "").strip()
        backup_path = os.getenv("KNOWLEDGE_REGISTRY_BACKUP_DIR", "").strip()
        source_bundle_profile_path = os.getenv(
            "SOURCE_BUNDLE_PROFILE_DIR", ""
        ).strip()
        source_bundle_output_path = os.getenv(
            "SOURCE_BUNDLE_OUTPUT_DIR", ""
        ).strip()
        source_bundle_audit_log_path = os.getenv(
            "SOURCE_BUNDLE_AUDIT_LOG_PATH", ""
        ).strip()
        presentation_profile_path = os.getenv(
            "PRESENTATION_PROFILE_DIR", ""
        ).strip()
        presentation_request_output_path = os.getenv(
            "PRESENTATION_REQUEST_OUTPUT_DIR", ""
        ).strip()
        presentation_request_audit_log_path = os.getenv(
            "PRESENTATION_REQUEST_AUDIT_LOG_PATH", ""
        ).strip()
        presentation_engine_audit_log_path = os.getenv(
            "PRESENTATION_ENGINE_AUDIT_LOG_PATH", ""
        ).strip()
        provider_payload_output_path = os.getenv(
            "PROVIDER_PAYLOAD_OUTPUT_DIR", ""
        ).strip()
        presentation_response_output_path = os.getenv(
            "PRESENTATION_RESPONSE_OUTPUT_DIR", ""
        ).strip()
        provider_payload_audit_log_path = os.getenv(
            "PROVIDER_PAYLOAD_AUDIT_LOG_PATH", ""
        ).strip()
        presentation_response_audit_log_path = os.getenv(
            "PRESENTATION_RESPONSE_AUDIT_LOG_PATH", ""
        ).strip()
        return cls(
            provider=os.getenv("KNOWLEDGE_PROVIDER", "openai").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip(),
            registry_path=(
                Path(registry_path).expanduser() if registry_path else DEFAULT_REGISTRY_PATH
            ),
            registry_backup_dir=(
                Path(backup_path).expanduser() if backup_path else DEFAULT_REGISTRY_BACKUP_DIR
            ),
            source_bundle_profile_dir=(
                Path(source_bundle_profile_path).expanduser()
                if source_bundle_profile_path
                else DEFAULT_SOURCE_BUNDLE_PROFILE_DIR
            ),
            source_bundle_output_dir=(
                Path(source_bundle_output_path).expanduser()
                if source_bundle_output_path
                else DEFAULT_SOURCE_BUNDLE_OUTPUT_DIR
            ),
            source_bundle_audit_log_path=(
                Path(source_bundle_audit_log_path).expanduser()
                if source_bundle_audit_log_path
                else DEFAULT_SOURCE_BUNDLE_AUDIT_LOG_PATH
            ),
            presentation_profile_dir=(
                Path(presentation_profile_path).expanduser()
                if presentation_profile_path
                else DEFAULT_PRESENTATION_PROFILE_DIR
            ),
            presentation_request_output_dir=(
                Path(presentation_request_output_path).expanduser()
                if presentation_request_output_path
                else DEFAULT_PRESENTATION_REQUEST_OUTPUT_DIR
            ),
            presentation_request_audit_log_path=(
                Path(presentation_request_audit_log_path).expanduser()
                if presentation_request_audit_log_path
                else DEFAULT_PRESENTATION_REQUEST_AUDIT_LOG_PATH
            ),
            presentation_engine_audit_log_path=(
                Path(presentation_engine_audit_log_path).expanduser()
                if presentation_engine_audit_log_path
                else DEFAULT_PRESENTATION_ENGINE_AUDIT_LOG_PATH
            ),
            provider_payload_output_dir=(
                Path(provider_payload_output_path).expanduser()
                if provider_payload_output_path
                else DEFAULT_PROVIDER_PAYLOAD_OUTPUT_DIR
            ),
            presentation_response_output_dir=(
                Path(presentation_response_output_path).expanduser()
                if presentation_response_output_path
                else DEFAULT_PRESENTATION_RESPONSE_OUTPUT_DIR
            ),
            provider_payload_audit_log_path=(
                Path(provider_payload_audit_log_path).expanduser()
                if provider_payload_audit_log_path
                else DEFAULT_PROVIDER_PAYLOAD_AUDIT_LOG_PATH
            ),
            presentation_response_audit_log_path=(
                Path(presentation_response_audit_log_path).expanduser()
                if presentation_response_audit_log_path
                else DEFAULT_PRESENTATION_RESPONSE_AUDIT_LOG_PATH
            ),
        )


def build_provider(settings: Settings) -> KnowledgeProvider:
    if settings.provider == "openai":
        return OpenAIKnowledgeProvider(settings.openai_api_key, settings.openai_model)
    if settings.provider == "fixture":
        from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

        return FixtureKnowledgeProvider()
    raise ProviderConfigurationError(
        f"未対応の生成方法です: {settings.provider}。現在はopenaiのみ利用できます。"
    )
