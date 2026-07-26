import json
import sqlite3
from pathlib import Path

from knowledge_contracts.registry_v10 import KnowledgeRegistryEntry
from knowledge_contracts.relation_v11 import (
    RelationResolutionStatus,
    RelationType,
)
from knowledge_contracts.v10 import validate_knowledge_record

from knowledge_workbench.knowledge_relation_resolver import (
    resolve_knowledge_relations,
)
from knowledge_workbench.knowledge_relation_service import KnowledgeRelationService
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry
from knowledge_workbench.sqlite_knowledge_relation_repository import (
    SQLiteKnowledgeRelationRepository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GRAM_PATH = (
    REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0" / "staining-method.example.json"
)
SPECIMEN_PATH = (
    REPOSITORY_ROOT / "Docs" / "examples" / "knowledge-json-v1.0" / "specimen.example.json"
)
REAGENT_PATHS = sorted(
    (
        REPOSITORY_ROOT
        / "Docs"
        / "examples"
        / "knowledge-json-v1.0"
        / "reagents"
    ).glob("*.example.json")
)
ACID_FAST_PATH = (
    REPOSITORY_ROOT
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "acid-fast-staining-method.example.json"
)


def _gram_record():  # type: ignore[no-untyped-def]
    return validate_knowledge_record(json.loads(GRAM_PATH.read_text(encoding="utf-8")))


def _specimen_record():  # type: ignore[no-untyped-def]
    return validate_knowledge_record(json.loads(SPECIMEN_PATH.read_text(encoding="utf-8")))


def _reagent_records():  # type: ignore[no-untyped-def]
    return [
        validate_knowledge_record(json.loads(path.read_text(encoding="utf-8")))
        for path in REAGENT_PATHS
    ]


def _acid_fast_record():  # type: ignore[no-untyped-def]
    return validate_knowledge_record(json.loads(ACID_FAST_PATH.read_text(encoding="utf-8")))


def test_gram_relations_are_persisted_without_creating_missing_knowledge(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    reconciliation = registry.reconcile(
        _gram_record(), actor="relation_test", note="Gram染色を登録"
    )
    repository = SQLiteKnowledgeRelationRepository(database_path)
    candidates = resolve_knowledge_relations(reconciliation.record, registry.snapshot())

    first = repository.reconcile(
        reconciliation.record.knowledge_id,
        candidates,
        registry.snapshot(),
        actor="relation_test",
        note="Relationを同期",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE knowledge_relations
            SET context_json = '{"qualifiers":[],"preparation":null}'
            WHERE relation_type != 'uses_specimen'
            """
        )
    second = repository.reconcile(
        reconciliation.record.knowledge_id,
        candidates,
        registry.snapshot(),
        actor="relation_test",
        note="同じRelationを再同期",
    )

    assert len(first.relations) == 7
    assert {item.relation_type for item in first.relations} == {
        RelationType.USES_SPECIMEN,
        RelationType.USES_REAGENT,
        RelationType.TARGETS_STRUCTURE,
        RelationType.RELATED_METHOD,
    }
    assert all(
        item.resolution_status == RelationResolutionStatus.UNRESOLVED
        and item.target_knowledge_id is None
        for item in first.relations
    )
    assert len(registry.snapshot().knowledge) == 1
    assert [item.relation_id for item in first.relations] == [
        item.relation_id for item in second.relations
    ]
    assert all(item.version == 1 for item in second.relations)
    assert len(second.history) == 7
    specimen_relation = next(
        item for item in second.relations if item.relation_type == RelationType.USES_SPECIMEN
    )
    assert specimen_relation.context.preparation == "薄く均一に塗抹する。"
    assert specimen_relation.context.qualifiers == []
    assert second.schema_version == "1.1"
    assert second.validation.is_valid is True


def test_resolver_uses_exact_registry_name_without_ai_or_fuzzy_matching(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    reconciliation = registry.reconcile(_gram_record())
    snapshot = registry.snapshot()
    exact_target = KnowledgeRegistryEntry(
        knowledge_id="knw_target01",
        registry_key="acid.fast.stain",
        canonical_name="抗酸菌染色",
        knowledge_version=1,
        status="draft",
        created_at=snapshot.knowledge[0].created_at,
        updated_at=snapshot.knowledge[0].updated_at,
        aliases=[],
        approval=[],
    )
    extended_snapshot = snapshot.model_copy(
        update={"knowledge": [*snapshot.knowledge, exact_target]}
    )

    relations = resolve_knowledge_relations(reconciliation.record, extended_snapshot)
    related_method = next(
        item for item in relations if item.relation_type == RelationType.RELATED_METHOD
    )

    assert related_method.target_knowledge_id == "knw_target01"
    assert related_method.resolution_status == RelationResolutionStatus.RESOLVED


def test_ast_does_not_receive_staining_method_relations(tmp_path: Path) -> None:
    from knowledge_workbench.application import GenerateKnowledge
    from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    outcome = GenerateKnowledge(FixtureKnowledgeProvider(), registry=registry).execute("AST")

    assert resolve_knowledge_relations(outcome.record, registry.snapshot()) == []


def test_registering_specimen_resolves_relation_without_rewriting_gram_knowledge(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    gram = registry.reconcile(_gram_record(), actor="relation_test", note="Gram染色を登録").record
    repository = SQLiteKnowledgeRelationRepository(database_path)
    service = KnowledgeRelationService(registry, repository)
    initial = service.synchronize(
        gram,
        actor="relation_test",
        note="未解決Relationを登録",
    )
    gram_before = registry.record(gram.knowledge_id)
    assert gram_before is not None
    gram_before_json = gram_before.model_dump(mode="json")

    specimen = registry.reconcile(
        _specimen_record(), actor="relation_test", note="塗抹標本を登録"
    ).record
    indexed = repository.find_unresolved_for_target("specimen", ["塗抹標本"])
    report = service.resolve_for_target(
        specimen,
        actor="relation_test",
        note="Specimen登録後に再解決",
    )

    gram_after = registry.record(gram.knowledge_id)
    assert gram_after is not None
    assert gram_after.model_dump(mode="json") == gram_before_json
    assert len(indexed) == 1
    assert report.evaluated_count == 1
    assert report.resolved_count == 1
    assert report.unresolved_count == 0
    resolved_view = repository.view(gram.knowledge_id)
    assert resolved_view.validation.resolved_count == 1
    assert resolved_view.validation.unresolved_count == 6
    specimen_relation = next(
        item for item in resolved_view.relations if item.relation_type == RelationType.USES_SPECIMEN
    )
    initial_specimen_relation = next(
        item for item in initial.relations if item.relation_type == RelationType.USES_SPECIMEN
    )
    assert specimen_relation.relation_id == initial_specimen_relation.relation_id
    assert specimen_relation.version == 2
    assert specimen_relation.target_knowledge_id == specimen.knowledge_id
    assert specimen_relation.target_label == "塗抹標本"
    assert specimen_relation.resolution_status == RelationResolutionStatus.RESOLVED
    assert specimen_relation.context.qualifiers == ["細菌を含む"]
    assert specimen_relation.context.preparation == "薄く均一に塗抹する。"
    assert len(resolved_view.history) == 8
    summary = repository.network_summary(gram.knowledge_id)
    assert summary.relation_count == 7
    assert summary.resolved_count == 1
    assert summary.unresolved_count == 6
    assert summary.network_completeness == 14.3
    persisted_reports = SQLiteKnowledgeRelationRepository(database_path).resolution_reports(
        specimen.knowledge_id
    )
    assert persisted_reports == [report]


def test_resolution_event_uses_index_without_loading_every_knowledge(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    gram = registry.reconcile(_gram_record(), actor="relation_test", note="Gram染色を登録").record
    repository = SQLiteKnowledgeRelationRepository(database_path)
    service = KnowledgeRelationService(registry, repository)
    service.synchronize(gram, actor="relation_test", note="未解決Relationを登録")
    specimen = registry.reconcile(
        _specimen_record(), actor="relation_test", note="塗抹標本を登録"
    ).record

    def fail_on_record_read(*_args):  # type: ignore[no-untyped-def]
        raise AssertionError("Knowledge本文の全件読込は禁止")

    monkeypatch.setattr(registry, "record", fail_on_record_read)
    monkeypatch.setattr(registry, "snapshot", fail_on_record_read)
    report = service.resolve_for_target(
        specimen,
        actor="relation_test",
        note="索引だけで再評価",
    )

    assert report.evaluated_count == 1
    assert report.resolved_count == 1
    with sqlite3.connect(database_path) as connection:
        index_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_relation_resolution_index"
        ).fetchone()[0]
        unresolved_count = connection.execute(
            """
            SELECT COUNT(*) FROM knowledge_relation_resolution_index
            WHERE resolution_status = 'unresolved_relation'
            """
        ).fetchone()[0]
    assert index_count == 7
    assert unresolved_count == 6


def test_registering_reagents_incrementally_resolves_only_indexed_uses_reagent(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    gram = registry.reconcile(
        _gram_record(), actor="relation_test", note="Gram染色を登録"
    ).record
    repository = SQLiteKnowledgeRelationRepository(database_path)
    service = KnowledgeRelationService(registry, repository)
    service.synchronize(gram, actor="relation_test", note="未解決Relationを登録")
    gram_before = registry.record(gram.knowledge_id)
    assert gram_before is not None
    gram_before_json = gram_before.model_dump(mode="json")

    reports = []
    for reagent_record in _reagent_records():
        reagent = registry.reconcile(
            reagent_record,
            actor="relation_test",
            note="Reagentを正式登録",
        ).record

        def fail_on_registry_scan(*_args):  # type: ignore[no-untyped-def]
            raise AssertionError("Relation再解決でKnowledge全件走査は禁止")

        with monkeypatch.context() as scoped:
            scoped.setattr(registry, "record", fail_on_registry_scan)
            scoped.setattr(registry, "snapshot", fail_on_registry_scan)
            reports.append(
                service.resolve_for_target(
                    reagent,
                    actor="relation_test",
                    note="Reagent保存イベントによる索引候補の再評価",
                )
            )

    gram_after = registry.record(gram.knowledge_id)
    assert gram_after is not None
    assert gram_after.model_dump(mode="json") == gram_before_json
    report_counts = [
        (item.evaluated_count, item.resolved_count, item.unresolved_count)
        for item in reports
    ]
    assert report_counts == [
        (1, 1, 0),
        (1, 1, 0),
        (1, 1, 0),
        (1, 1, 0),
    ]

    view = repository.view(gram.knowledge_id)
    reagent_relations = [
        item for item in view.relations if item.relation_type == RelationType.USES_REAGENT
    ]
    assert len(reagent_relations) == 4
    assert all(
        item.resolution_status == RelationResolutionStatus.RESOLVED
        and item.target_knowledge_id is not None
        and item.version == 2
        for item in reagent_relations
    )
    summary = repository.network_summary(gram.knowledge_id)
    assert summary.relation_count == 7
    assert summary.resolved_count == 4
    assert summary.unresolved_count == 3
    assert summary.network_completeness == 57.1
    assert sum(
        len(repository.resolution_reports(item.knowledge_id))
        for item in _reagent_records()
    ) == 4


def test_existing_staining_category_resolves_only_indexed_related_method(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "registry.sqlite3"
    registry = SQLiteKnowledgeRegistry(database_path)
    repository = SQLiteKnowledgeRelationRepository(database_path)
    service = KnowledgeRelationService(registry, repository)
    gram = registry.reconcile(
        _gram_record(), actor="relation_test", note="Gram染色を登録"
    ).record
    service.synchronize(gram, actor="relation_test", note="未解決Relationを登録")
    gram_before = registry.record(gram.knowledge_id)
    assert gram_before is not None
    gram_before_json = gram_before.model_dump(mode="json")

    specimen = registry.reconcile(
        _specimen_record(), actor="relation_test", note="塗抹標本を登録"
    ).record
    service.resolve_for_target(specimen, actor="relation_test", note="Specimen再解決")
    for reagent_record in _reagent_records():
        reagent = registry.reconcile(
            reagent_record, actor="relation_test", note="Reagentを登録"
        ).record
        service.resolve_for_target(reagent, actor="relation_test", note="Reagent再解決")

    before_summary = repository.network_summary(gram.knowledge_id)
    assert before_summary.resolved_count == 5
    assert before_summary.unresolved_count == 2
    assert before_summary.network_completeness == 71.4

    acid_fast = registry.reconcile(
        _acid_fast_record(), actor="relation_test", note="既存CategoryへKnowledge追加"
    ).record
    indexed = repository.find_unresolved_for_target(
        "staining_method",
        [acid_fast.term.canonical_name, *acid_fast.term.aliases],
    )
    assert len(indexed) == 1
    assert indexed[0].relation_type == RelationType.RELATED_METHOD

    def fail_on_registry_scan(*_args):  # type: ignore[no-untyped-def]
        raise AssertionError("Relation再解決でKnowledge全件走査は禁止")

    with monkeypatch.context() as scoped:
        scoped.setattr(registry, "record", fail_on_registry_scan)
        scoped.setattr(registry, "snapshot", fail_on_registry_scan)
        report = service.resolve_for_target(
            acid_fast,
            actor="relation_test",
            note="抗酸菌染色保存イベントによる索引候補の再評価",
        )

    assert (report.evaluated_count, report.resolved_count, report.unresolved_count) == (
        1,
        1,
        0,
    )
    gram_after = registry.record(gram.knowledge_id)
    assert gram_after is not None
    assert gram_after.model_dump(mode="json") == gram_before_json
    related_method = next(
        item
        for item in repository.view(gram.knowledge_id).relations
        if item.relation_type == RelationType.RELATED_METHOD
    )
    assert related_method.target_knowledge_id == acid_fast.knowledge_id
    assert related_method.target_label == "抗酸菌染色"
    assert related_method.resolution_status == RelationResolutionStatus.RESOLVED
    assert related_method.version == 2
    after_summary = repository.network_summary(gram.knowledge_id)
    assert after_summary.relation_count == 7
    assert after_summary.resolved_count == 6
    assert after_summary.unresolved_count == 1
    assert after_summary.network_completeness == 85.7
    assert repository.resolution_reports(acid_fast.knowledge_id) == [report]
