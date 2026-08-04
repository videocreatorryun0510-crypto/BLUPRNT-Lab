import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from knowledge_contracts.v10 import KnowledgeRecord, validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_request_builder import (
    PresentationRequest,
    PresentationRequestBuilder,
    RequestMode,
)
from source_bundle_publisher import SourceBundle, SourceBundlePublisherAdapter

from presentation_artifact import (
    ArtifactValidationReport,
    JsonlArtifactAuditLogger,
    LayoutComposition,
    PresentationArtifact,
    PresentationArtifactBuilder,
    PresentationArtifactJsonWriter,
    PresentationArtifactValidator,
    Renderer,
    RenderResult,
    artifact_fingerprint,
)

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "Docs" / "examples" / "knowledge-json-v1.0"
SOURCE_PROFILES = ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
REQUEST_PROFILES = ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


def _sources(
    tmp_path: Path,
    example: str = "laboratory-test-item.example.json",
) -> tuple[KnowledgeRecord, SourceBundle, PresentationRequest]:
    record = validate_knowledge_record(json.loads((EXAMPLES / example).read_text(encoding="utf-8")))
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    reconciled = registry.reconcile(
        record,
        actor="artifact_test",
        note="Presentation Artifactテスト",
    )
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        SOURCE_PROFILES,
        tmp_path / "source_bundle",
        tmp_path / "logs" / "source.jsonl",
    )
    bundle = source_publisher.publish(
        reconciled.record,
        reconciled.view,
        None,
        generated_at=NOW,
    ).bundle
    request_builder = PresentationRequestBuilder.from_directories(
        REQUEST_PROFILES,
        tmp_path / "request",
        tmp_path / "logs" / "request.jsonl",
        source_publisher,
    )
    request_result = request_builder.build(
        bundle,
        reconciled.view,
        expected_source_fingerprint=bundle.metadata.source_fingerprint,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )
    assert request_result.request is not None
    return reconciled.record, bundle, request_result.request


@pytest.mark.parametrize(
    "example",
    ["laboratory-test-item.example.json", "disease.example.json"],
)
def test_builder_creates_provider_neutral_traceable_artifact(
    tmp_path: Path,
    example: str,
) -> None:
    record, bundle, request = _sources(tmp_path, example)
    builder = PresentationArtifactBuilder.from_directories(
        tmp_path / "artifact",
        tmp_path / "logs" / "artifact.jsonl",
    )
    before = record.model_dump(mode="json")

    result = builder.build(request, bundle, record, created_at=NOW)

    assert result.status == "success"
    assert result.validation.is_valid is True
    assert result.output_path is not None
    assert Path(result.output_path).is_file()
    assert result.artifact is not None
    artifact = result.artifact
    assert len(artifact.pages) == request.layout_policy.page_or_slide_count
    assert {claim.claim_id for claim in artifact.claim_catalog} == set(
        request.content_policy.selected_claim_ids
    )
    source_text = {claim.claim_id: claim.assertion for claim in bundle.claims}
    assert all(
        block.exact_text == source_text[block.claim_id]
        for page in artifact.pages
        for block in page.body_blocks
    )
    assert artifact.metadata.fingerprint == artifact_fingerprint(artifact)
    assert record.model_dump(mode="json") == before
    assert not _has_provider_key(artifact.model_dump(mode="json"))


def test_fingerprint_is_stable_for_same_sources(tmp_path: Path) -> None:
    record, bundle, request = _sources(tmp_path)
    builder = PresentationArtifactBuilder.from_directories(
        tmp_path / "artifact",
        tmp_path / "logs" / "artifact.jsonl",
    )

    first = builder.build(request, bundle, record, created_at=NOW)
    second = builder.build(request, bundle, record, created_at=NOW)

    assert first.artifact is not None and second.artifact is not None
    assert first.artifact.identity.artifact_id != second.artifact.identity.artifact_id
    assert first.artifact.metadata.fingerprint == second.artifact.metadata.fingerprint


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("duplicate_page", "duplicate_page_number"),
        ("unknown_claim", "claim_catalog_mismatch"),
        ("unknown_reference", "unknown_reference_id"),
        ("fingerprint", "artifact_fingerprint_mismatch"),
        ("layout", "layout_requires_diagram"),
    ],
)
def test_validator_rejects_broken_artifact(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    record, bundle, request = _sources(tmp_path)
    builder = PresentationArtifactBuilder.from_directories(
        tmp_path / "artifact",
        tmp_path / "logs" / "artifact.jsonl",
    )
    result = builder.build(request, bundle, record, created_at=NOW)
    assert result.artifact is not None
    artifact = result.artifact

    if mutation == "duplicate_page":
        page = artifact.pages[1].model_copy(update={"page_number": 1})
        artifact = artifact.model_copy(
            update={"pages": (artifact.pages[0], page, *artifact.pages[2:])}
        )
    elif mutation == "unknown_claim":
        artifact = artifact.model_copy(update={"claim_catalog": artifact.claim_catalog[:-1]})
    elif mutation == "unknown_reference":
        page = artifact.pages[0].model_copy(update={"reference_ids": ("source.unknown",)})
        artifact = artifact.model_copy(update={"pages": (page, *artifact.pages[1:])})
    elif mutation == "fingerprint":
        artifact = artifact.model_copy(
            update={"metadata": artifact.metadata.model_copy(update={"fingerprint": "f" * 64})}
        )
    else:
        page = artifact.pages[0].model_copy(
            update={
                "layout_hint": artifact.pages[1].layout_hint.model_copy(
                    update={"composition": LayoutComposition.DIAGRAM_FOCUS}
                )
            }
        )
        artifact = artifact.model_copy(update={"pages": (page, *artifact.pages[1:])})

    report = PresentationArtifactValidator().validate(artifact, request, bundle, record)

    assert report.is_valid is False
    assert expected_code in {issue.code for issue in report.issues}


class RejectingValidator(PresentationArtifactValidator):
    def validate(
        self,
        artifact: PresentationArtifact,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        knowledge: KnowledgeRecord,
    ) -> ArtifactValidationReport:
        return ArtifactValidationReport(
            is_valid=False,
            issues=(),
        )


def test_validation_failure_is_never_saved(tmp_path: Path) -> None:
    record, bundle, request = _sources(tmp_path)
    builder = PresentationArtifactBuilder(
        writer=PresentationArtifactJsonWriter(tmp_path / "artifact"),
        audit_logger=JsonlArtifactAuditLogger(tmp_path / "logs" / "artifact.jsonl"),
        validator=RejectingValidator(),
    )

    result = builder.build(request, bundle, record, created_at=NOW)

    assert result.status == "validation_failed"
    assert result.output_path is None
    assert not (tmp_path / "artifact").exists()


def test_renderer_contract_accepts_one_artifact_for_future_media(tmp_path: Path) -> None:
    record, bundle, request = _sources(tmp_path)
    result = PresentationArtifactBuilder.from_directories(
        tmp_path / "artifact",
        tmp_path / "logs" / "artifact.jsonl",
    ).build(request, bundle, record, created_at=NOW)
    assert result.artifact is not None

    class DummyRenderer:
        def render(self, artifact: PresentationArtifact) -> RenderResult:
            return RenderResult(
                renderer_name="contract_test",
                artifact_id=artifact.identity.artifact_id,
                output_paths=(),
            )

    renderer: Renderer = DummyRenderer()
    rendered = renderer.render(result.artifact)
    assert rendered.artifact_id == result.artifact.identity.artifact_id


def _has_provider_key(value: Any) -> bool:
    forbidden = {"provider", "gemini", "api", "model", "endpoint"}
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _has_provider_key(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_provider_key(item) for item in value)
    return False
