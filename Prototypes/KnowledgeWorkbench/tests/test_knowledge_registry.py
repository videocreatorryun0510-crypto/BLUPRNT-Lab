from pathlib import Path

from knowledge_contracts.registry_v10 import (
    RegistryEntityType,
    RegistryHistoryAction,
    RegistryStatus,
)

from knowledge_workbench.application import GenerateKnowledge
from knowledge_workbench.providers.base import GenerationResult
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.registry_backup import SQLiteRegistryBackupManager
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry


class _ReorderedAstProvider:
    def generate(self, term: str) -> GenerationResult:
        original = FixtureKnowledgeProvider().generate(term)
        raw = original.draft.model_dump(mode="json")
        content = raw["test_item_content"]
        content["measurement_methods"].reverse()
        content["interpretation_cautions"].reverse()
        content["value_associations"]["high"]["pathophysiologic_states"].reverse()
        raw["core_facts"]["characteristics"].reverse()
        return GenerationResult(
            draft=original.draft.model_validate(raw),
            provider="reordered_fixture",
            model="registry-order-test",
        )


class _DuplicatedAstProvider:
    def generate(self, term: str) -> GenerationResult:
        original = FixtureKnowledgeProvider().generate(term)
        raw = original.draft.model_dump(mode="json")
        raw["core_facts"]["definitions"].append(
            {
                "statement": (
                    "ASTはアスパラギン酸とα-ケトグルタル酸のアミノ基転移反応を触媒する酵素である。"
                )
            }
        )
        raw["test_item_content"]["measurement_principles"].append(
            {
                "related_method_names": ["IFCC勧告法に基づく方法"],
                "measured_quantity": "AST酵素活性",
                "reaction_sequence": "共役反応によりNADHを消費する。",
                "detection_signal": "NADHの吸光度減少を測定する。",
                "wavelength_or_endpoint": "340 nm",
            }
        )
        return GenerationResult(
            draft=original.draft.model_validate(raw),
            provider="duplicate_fixture",
            model="registry-duplicate-test",
        )


def _registry(path: Path) -> SQLiteKnowledgeRegistry:
    return SQLiteKnowledgeRegistry(path / "knowledge_registry.sqlite3")


def test_ast_claim_key_and_id_survive_ai_reordering_and_registry_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "knowledge_registry.sqlite3"
    first_registry = SQLiteKnowledgeRegistry(database_path)
    first = GenerateKnowledge(FixtureKnowledgeProvider(), registry=first_registry).execute("AST")
    first_claim = next(
        item
        for item in first.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )

    restarted_registry = SQLiteKnowledgeRegistry(database_path)
    reordered = GenerateKnowledge(_ReorderedAstProvider(), registry=restarted_registry).execute(
        "AST"
    )
    reordered_claim = next(
        item
        for item in reordered.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )

    assert first_claim.claim_id == reordered_claim.claim_id
    assert first_claim.claim_key == reordered_claim.claim_key
    assert reordered.registry.knowledge.knowledge_version == 1  # type: ignore[union-attr]
    assert (
        restarted_registry.resolve_claim_id(reordered.record.knowledge_id, "ast.is_leakage_enzyme")
        == first_claim.claim_id
    )


def test_registry_contains_required_ast_semantic_dictionary(tmp_path: Path) -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider(), registry=_registry(tmp_path)).execute(
        "AST"
    )
    keys = {item.claim_key for item in outcome.registry.claims}  # type: ignore[union-attr]

    assert keys >= {
        "ast.is_leakage_enzyme",
        "ast.measurement.340nm",
        "ast.jscc",
        "ast.ifcc",
        "ast.high.hepatocyte_damage",
    }


def test_repeated_semantic_facts_are_collapsed_without_creating_order_ids(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    outcome = GenerateKnowledge(_DuplicatedAstProvider(), registry=registry).execute("AST")
    keys = [item.claim_key for item in outcome.registry.claims]  # type: ignore[union-attr]

    assert keys.count("ast.definition.aminotransferase_enzyme") == 1
    assert keys.count("ast.measurement.340nm") == 1
    assert len(keys) == len(set(keys))


def test_expression_update_keeps_versions_but_semantic_update_bumps_them(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    generated = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    knowledge_id = generated.record.knowledge_id
    original = next(
        item
        for item in generated.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )

    wording = registry.update_claim(
        original.claim_key,
        "ASTは代表的な逸脱酵素である。",
        actor="owner",
        semantic_change=False,
    )
    after_wording = registry.knowledge_by_id(knowledge_id)
    semantic = registry.update_claim(
        original.claim_key,
        "ASTは細胞障害時に血中で上昇する逸脱酵素である。",
        actor="medical_reviewer",
        semantic_change=True,
    )
    after_semantic = registry.knowledge_by_id(knowledge_id)

    assert wording.claim_key == original.claim_key
    assert wording.claim_id == original.claim_id
    assert wording.claim_version == original.claim_version
    assert after_wording is not None and after_wording.knowledge_version == 1
    assert semantic.claim_version == original.claim_version + 1
    assert after_semantic is not None and after_semantic.knowledge_version == 2


def test_claim_approval_workflow_is_persisted(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    outcome = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    claim = next(
        item
        for item in outcome.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )

    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        registry.transition_status(
            RegistryEntityType.CLAIM,
            claim.claim_id,
            status,
            actor="reviewer",
            note="MVP workflow test",
        )

    approved = next(item for item in registry.snapshot().claims if item.claim_id == claim.claim_id)
    assert approved.status == RegistryStatus.APPROVED
    assert [item.status for item in approved.approval] == [
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ]


def test_approved_claim_can_return_to_medical_review_with_history(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    outcome = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    claim = next(
        item
        for item in outcome.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )
    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
        RegistryStatus.MEDICAL_REVIEW,
    ):
        registry.transition_status(
            RegistryEntityType.CLAIM,
            claim.claim_id,
            status,
            actor="reviewer",
            note="差し戻し履歴テスト",
        )

    reviewed = next(
        item for item in registry.snapshot().claims if item.claim_id == claim.claim_id
    )
    status_events = [
        item
        for item in registry.snapshot().history
        if item.entity_id == claim.claim_id
        and item.action == RegistryHistoryAction.STATUS_CHANGE
    ]
    assert reviewed.status == RegistryStatus.MEDICAL_REVIEW
    assert [item.status for item in reviewed.approval][-2:] == [
        RegistryStatus.APPROVED,
        RegistryStatus.MEDICAL_REVIEW,
    ]
    assert status_events[-1].details["from_status"] == "approved"
    assert status_events[-1].details["to_status"] == "medical_review"


def test_deprecated_and_deleted_actions_remain_in_history(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    outcome = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    claim = next(
        item
        for item in outcome.registry.claims  # type: ignore[union-attr]
        if item.claim_key == "ast.is_leakage_enzyme"
    )

    registry.deprecate_claim(claim.claim_key, actor="owner", note="superseded")
    registry.mark_claim_deleted(claim.claim_key, actor="owner", note="soft delete")

    snapshot = registry.snapshot()
    stored = next(item for item in snapshot.claims if item.claim_id == claim.claim_id)
    actions = {item.action for item in snapshot.history if item.entity_id == claim.claim_id}
    assert stored.is_deleted is True
    assert actions >= {
        RegistryHistoryAction.ADD,
        RegistryHistoryAction.DEPRECATED,
        RegistryHistoryAction.DELETE,
    }


def test_claim_merge_keeps_target_id_and_redirects_old_links(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    generated = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    characteristics = [
        item
        for item in generated.registry.claims  # type: ignore[union-attr]
        if item.field_path.endswith("analyte_characteristics")
    ]
    target, source = characteristics[:2]

    merged = registry.merge_claims(
        generated.record.knowledge_id,
        target.claim_id,
        [source.claim_id],
        actor="owner",
        comment="同じ分布特性として統合",
    )

    source_after = next(item for item in merged.claims if item.claim_id == source.claim_id)
    assert source_after.status == RegistryStatus.DEPRECATED
    assert merged.knowledge.knowledge_version == 2
    assert merged.merge_redirects[0].target_claim_id == target.claim_id
    assert registry.canonical_claim_id(source.claim_id) == target.claim_id
    assert (
        registry.resolve_claim_id(generated.record.knowledge_id, source.claim_key)
        == target.claim_id
    )
    assert any(
        item.action == RegistryHistoryAction.MERGE and item.entity_id == source.claim_id
        for item in merged.history
    )

    regenerated = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    active_ids = {
        item.claim_id
        for item in regenerated.registry.claims  # type: ignore[union-attr]
        if item.status != RegistryStatus.DEPRECATED
    }
    assert target.claim_id in active_ids
    assert source.claim_id not in active_ids


def test_batch_approval_records_actor_comment_and_every_transition(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    generated = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    claim = generated.registry.claims[0]  # type: ignore[union-attr]

    for status in (
        RegistryStatus.OWNER_REVIEW,
        RegistryStatus.MEDICAL_REVIEW,
        RegistryStatus.APPROVED,
    ):
        registry.transition_claims_status(
            [claim.claim_id],
            status,
            actor="medical-owner",
            note=f"{status.value}へ進める",
        )

    approved = next(item for item in registry.snapshot().claims if item.claim_id == claim.claim_id)
    assert approved.status == RegistryStatus.APPROVED
    assert [item.actor for item in approved.approval] == ["medical-owner"] * 3
    assert [item.note for item in approved.approval] == [
        "owner_reviewへ進める",
        "medical_reviewへ進める",
        "approvedへ進める",
    ]


def test_backup_restore_returns_to_selected_registry_generation(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    manager = SQLiteRegistryBackupManager(registry, tmp_path / "backups")
    ast = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")
    backup = manager.create_backup()
    GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("HbA1c")

    result = manager.restore(backup.filename)
    snapshot = registry.snapshot()

    assert result.restored.filename == backup.filename
    assert result.safety_backup.filename != backup.filename
    assert {item.knowledge_id for item in snapshot.knowledge} == {ast.record.knowledge_id}
