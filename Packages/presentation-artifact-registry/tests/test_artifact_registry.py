import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.v10 import validate_knowledge_record
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from presentation_artifact import (
    LayoutComposition,
    PresentationArtifact,
    PresentationArtifactBuilder,
    RenderResult,
    artifact_fingerprint,
)
from presentation_request_builder import PresentationRequestBuilder, RequestMode
from source_bundle_publisher import SourceBundlePublisherAdapter

from presentation_artifact_registry import (
    ArtifactApprovalError,
    ArtifactApprovalState,
    ArtifactRegistryError,
    ArtifactRendererGateway,
    ArtifactVersionRecord,
    SQLitePresentationArtifactRegistry,
    evaluate_artifact_completeness,
)

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "Docs" / "examples" / "knowledge-json-v1.0"
SOURCE_PROFILES = ROOT / "Publishers" / "SourceBundlePublisher" / "profiles"
REQUEST_PROFILES = ROOT / "Publishers" / "PresentationRequestBuilder" / "profiles"
NOW = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def _artifact(tmp_path: Path) -> PresentationArtifact:
    record = validate_knowledge_record(
        json.loads(
            (EXAMPLES / "laboratory-test-item.example.json").read_text(
                encoding="utf-8"
            )
        )
    )
    knowledge_registry = SQLiteKnowledgeRegistry(tmp_path / "knowledge.sqlite3")
    reconciled = knowledge_registry.reconcile(
        record,
        actor="artifact_registry_test",
        note="Artifact Registryテスト",
    )
    source_publisher = SourceBundlePublisherAdapter.from_directories(
        SOURCE_PROFILES,
        tmp_path / "source",
        tmp_path / "logs" / "source.jsonl",
    )
    bundle = source_publisher.publish(
        reconciled.record,
        reconciled.view,
        None,
        generated_at=NOW,
    ).bundle
    request_result = PresentationRequestBuilder.from_directories(
        REQUEST_PROFILES,
        tmp_path / "request",
        tmp_path / "logs" / "request.jsonl",
        source_publisher,
    ).build(
        bundle,
        reconciled.view,
        expected_source_fingerprint=bundle.metadata.source_fingerprint,
        request_mode=RequestMode.PREVIEW,
        created_at=NOW,
    )
    assert request_result.request is not None
    build = PresentationArtifactBuilder.from_directories(
        tmp_path / "build",
        tmp_path / "logs" / "artifact.jsonl",
    ).build(
        request_result.request,
        bundle,
        reconciled.record,
        created_at=NOW,
    )
    assert build.artifact is not None
    return build.artifact


def _register(
    registry: SQLitePresentationArtifactRegistry,
    artifact: PresentationArtifact,
) -> ArtifactVersionRecord:
    return registry.register(
        artifact,
        owner="product_owner",
        actor="product_owner",
        review_comment="初版登録",
        expected_knowledge_version=artifact.source.knowledge_version,
        registered_at=NOW,
    )


def test_registry_assigns_stable_id_and_append_only_versions(tmp_path: Path) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    artifact = _artifact(tmp_path)

    first = _register(registry, artifact)
    second = _register(registry, artifact)
    view = registry.view(first.entry.artifact_id)

    assert first.entry.artifact_version == 1
    assert second.entry.artifact_id == first.entry.artifact_id
    assert second.entry.artifact_version == 2
    assert first.entry.fingerprint != second.entry.fingerprint
    assert [item.artifact_version for item in view.versions] == [2, 1]
    assert len(view.history) == 2
    assert registry.validate({artifact.source.knowledge_id: 1}).is_valid is True


def test_approval_flow_is_independent_and_records_history(tmp_path: Path) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    record = _register(registry, _artifact(tmp_path))
    artifact_id = record.entry.artifact_id

    for target in (
        ArtifactApprovalState.OWNER_REVIEW,
        ArtifactApprovalState.EDUCATION_REVIEW,
        ArtifactApprovalState.APPROVED,
    ):
        record = registry.transition_approval(
            artifact_id,
            1,
            target,
            actor="education_reviewer",
            review_comment=f"{target.value}へ変更",
            changed_at=NOW,
        )

    assert record.entry.approval_state == ArtifactApprovalState.APPROVED
    assert record.entry.immutable is True
    history = registry.view(artifact_id).history
    assert len(history) == 4
    assert history[0].to_approval_state == ArtifactApprovalState.APPROVED

    returned = registry.transition_approval(
        artifact_id,
        1,
        ArtifactApprovalState.EDUCATION_REVIEW,
        actor="education_reviewer",
        review_comment="差し戻し",
        changed_at=NOW,
    )
    assert returned.entry.approval_state == ArtifactApprovalState.EDUCATION_REVIEW
    assert returned.entry.immutable is True


def test_forward_approval_cannot_skip_a_required_review(tmp_path: Path) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    record = _register(registry, _artifact(tmp_path))

    with pytest.raises(ArtifactApprovalError, match="1段階"):
        registry.transition_approval(
            record.entry.artifact_id,
            1,
            ArtifactApprovalState.APPROVED,
            actor="owner",
            review_comment="Review省略",
        )


def test_approved_artifact_content_is_protected_by_sqlite_trigger(
    tmp_path: Path,
) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    record = _register(registry, _artifact(tmp_path))
    for target in (
        ArtifactApprovalState.OWNER_REVIEW,
        ArtifactApprovalState.EDUCATION_REVIEW,
        ArtifactApprovalState.APPROVED,
    ):
        registry.transition_approval(
            record.entry.artifact_id,
            1,
            target,
            actor="reviewer",
            review_comment="承認",
        )

    with (
        sqlite3.connect(registry.database_path) as connection,
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
    ):
        connection.execute(
            """
            UPDATE artifact_versions SET artifact_json = ?
            WHERE artifact_id = ? AND artifact_version = 1
            """,
            ("{}", record.entry.artifact_id),
        )


def test_renderer_gateway_rejects_draft_and_uses_latest_approved(
    tmp_path: Path,
) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    artifact = _artifact(tmp_path)
    first = _register(registry, artifact)
    gateway = ArtifactRendererGateway(registry)

    class RecordingRenderer:
        def render(self, source: PresentationArtifact) -> RenderResult:
            return RenderResult(
                renderer_name="recording",
                artifact_id=source.identity.artifact_id,
                output_paths=(f"version-{source.identity.artifact_version}",),
            )

    with pytest.raises(ArtifactApprovalError, match="approved"):
        gateway.render(first.entry.artifact_id, RecordingRenderer())

    for target in (
        ArtifactApprovalState.OWNER_REVIEW,
        ArtifactApprovalState.EDUCATION_REVIEW,
        ArtifactApprovalState.APPROVED,
    ):
        registry.transition_approval(
            first.entry.artifact_id,
            1,
            target,
            actor="reviewer",
            review_comment="承認",
        )
    _register(registry, artifact)

    rendered = gateway.render(first.entry.artifact_id, RecordingRenderer())
    assert rendered.output_paths == ("version-1",)


def test_diff_reports_required_educational_changes(tmp_path: Path) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    artifact = _artifact(tmp_path)
    first = _register(registry, artifact)
    changed_page = artifact.pages[0].model_copy(update={"headline": "改訂見出し"})
    layout_page = artifact.pages[2].model_copy(
        update={
            "layout_hint": artifact.pages[2].layout_hint.model_copy(
                update={"composition": LayoutComposition.TWO_COLUMN}
            )
        }
    )
    removed_claim = artifact.claim_catalog[-1]
    changed_pages = tuple(
        changed_page
        if index == 0
        else layout_page
        if index == 2
        else page.model_copy(
            update={
                "supporting_claim_ids": tuple(
                    claim_id
                    for claim_id in page.supporting_claim_ids
                    if claim_id != removed_claim.claim_id
                ),
                "body_blocks": tuple(
                    block
                    for block in page.body_blocks
                    if block.claim_id != removed_claim.claim_id
                ),
            }
        )
        for index, page in enumerate(artifact.pages)
    )
    changed = artifact.model_copy(
        update={
            "pages": changed_pages,
            "claim_catalog": artifact.claim_catalog[:-1],
        }
    )
    second = _register(registry, changed)

    report = registry.diff(first.entry.artifact_id, 1, 2)

    assert second.entry.artifact_version == 2
    assert report.has_changes is True
    assert report.headline_changes[0].page_number == 1
    assert report.claim_ids_removed == (removed_claim.claim_id,)
    assert report.layout_changes[0].page_number == 3


def test_completeness_scores_structure_not_educational_quality(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)

    complete = evaluate_artifact_completeness(artifact)
    without_diagram = artifact.model_copy(
        update={
            "pages": tuple(
                page.model_copy(update={"diagram_instruction": None})
                if page.diagram_instruction is not None
                else page
                for page in artifact.pages
            )
        }
    )
    unsigned = without_diagram.model_copy(
        update={
            "metadata": without_diagram.metadata.model_copy(
                update={"fingerprint": "0" * 64}
            )
        }
    )
    without_diagram = unsigned.model_copy(
        update={
            "metadata": unsigned.metadata.model_copy(
                update={"fingerprint": artifact_fingerprint(unsigned)}
            )
        }
    )
    incomplete = evaluate_artifact_completeness(without_diagram)

    assert complete.score == 100
    assert complete.is_complete is True
    assert "教育品質を保証しません" in complete.disclaimer
    assert incomplete.score == 87.5
    assert "Diagram" in incomplete.improvement_candidates[0]


def test_registration_requires_current_knowledge_version(tmp_path: Path) -> None:
    registry = SQLitePresentationArtifactRegistry(tmp_path / "artifact.sqlite3")
    artifact = _artifact(tmp_path)

    with pytest.raises(ArtifactRegistryError, match="Knowledge Version"):
        registry.register(
            artifact,
            owner="owner",
            actor="owner",
            review_comment="不整合",
            expected_knowledge_version=2,
        )
