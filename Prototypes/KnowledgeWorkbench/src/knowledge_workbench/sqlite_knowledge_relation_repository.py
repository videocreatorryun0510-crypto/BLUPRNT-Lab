"""SQLite adapter for the independent Knowledge Relation ledger."""

import json
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from knowledge_contracts.registry_v10 import RegistrySnapshot
from knowledge_contracts.relation_growth_v10 import NetworkSummary, ResolutionReport
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationRecord,
    KnowledgeRelationSnapshot,
    KnowledgeRelationView,
    RelationHistoryAction,
    RelationHistoryEvent,
    RelationResolutionStatus,
    RelationStatus,
    RelationType,
    relation_validation_report,
    validate_knowledge_relation_snapshot,
)

from knowledge_workbench.errors import RegistryOperationError
from knowledge_workbench.knowledge_relation_repository import (
    RelationCandidate,
    RelationResolutionUpdate,
)

_TARGET_CATEGORY_BY_RELATION_TYPE = {
    RelationType.USES_SPECIMEN: "specimen",
    RelationType.USES_REAGENT: "reagent",
    RelationType.TARGETS_STRUCTURE: "biological_structure",
    RelationType.RELATED_METHOD: "staining_method",
}


class SQLiteKnowledgeRelationRepository:
    """Store Relations apart from Knowledge JSON and the Claim Dictionary."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def reconcile(
        self,
        source_knowledge_id: str,
        candidates: list[RelationCandidate],
        registry: RegistrySnapshot,
        *,
        actor: str,
        note: str,
    ) -> KnowledgeRelationView:
        actor = actor.strip()
        note = note.strip()
        if not actor or not note:
            raise RegistryOperationError("Relation保存には操作者と変更理由が必要です。")
        self._validate_candidates(source_knowledge_id, candidates, registry)
        now = _now()
        try:
            with self._connect() as connection:
                existing_rows = {
                    str(row["relation_id"]): row
                    for row in connection.execute(
                        "SELECT * FROM knowledge_relations WHERE source_knowledge_id = ?",
                        (source_knowledge_id,),
                    ).fetchall()
                }
                incoming_ids = {item.relation_id for item in candidates}
                for candidate in candidates:
                    current = existing_rows.get(candidate.relation_id)
                    if current is None:
                        self._insert_relation(connection, candidate, actor, note, now)
                    else:
                        self._update_if_changed(connection, current, candidate, actor, note, now)
                for relation_id, current in existing_rows.items():
                    if (
                        relation_id in incoming_ids
                        or RelationStatus(str(current["status"])) == RelationStatus.DEPRECATED
                    ):
                        continue
                    self._deprecate(connection, current, actor, note, now)
            return self.view(source_knowledge_id)
        except RegistryOperationError:
            raise
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(
                f"Knowledge Relationの保存に失敗しました: {error}"
            ) from error

    def snapshot(self) -> KnowledgeRelationSnapshot:
        try:
            with self._connect() as connection:
                relations = [
                    _relation_record(row)
                    for row in connection.execute(
                        "SELECT * FROM knowledge_relations ORDER BY relation_id"
                    ).fetchall()
                ]
                history = [
                    _history_event(row)
                    for row in connection.execute(
                        "SELECT * FROM knowledge_relation_history ORDER BY occurred_at, event_id"
                    ).fetchall()
                ]
            return validate_knowledge_relation_snapshot(
                KnowledgeRelationSnapshot(relations=relations, history=history)
            )
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Knowledge Relationを読み込めません: {error}") from error

    def view(self, source_knowledge_id: str) -> KnowledgeRelationView:
        try:
            with self._connect() as connection:
                relations = [
                    _relation_record(row)
                    for row in connection.execute(
                        """
                        SELECT * FROM knowledge_relations
                        WHERE source_knowledge_id = ?
                        ORDER BY relation_id
                        """,
                        (source_knowledge_id,),
                    ).fetchall()
                ]
                history = [
                    _history_event(row)
                    for row in connection.execute(
                        """
                        SELECT h.* FROM knowledge_relation_history h
                        JOIN knowledge_relations r ON r.relation_id = h.relation_id
                        WHERE r.source_knowledge_id = ?
                        ORDER BY h.occurred_at, h.event_id
                        """,
                        (source_knowledge_id,),
                    ).fetchall()
                ]
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Knowledge Relationを読み込めません: {error}") from error
        scoped = KnowledgeRelationSnapshot(relations=relations, history=history)
        return KnowledgeRelationView(
            source_knowledge_id=source_knowledge_id,
            relations=relations,
            history=history,
            validation=relation_validation_report(scoped),
        )

    def find_unresolved_for_target(
        self,
        target_category: str,
        target_labels: list[str],
    ) -> list[KnowledgeRelationRecord]:
        """Read candidate rows from the derived index, never from all Knowledge."""

        labels = sorted({_normalize(item) for item in target_labels if item.strip()})
        relation_types = [
            relation_type.value
            for relation_type, category in _TARGET_CATEGORY_BY_RELATION_TYPE.items()
            if category == target_category
        ]
        if not labels or not relation_types:
            return []
        found: dict[str, KnowledgeRelationRecord] = {}
        relation_placeholders = ",".join("?" for _ in relation_types)
        label_placeholders = ",".join("?" for _ in labels)
        try:
            with self._connect() as connection:
                exact_rows = connection.execute(
                    f"""
                    SELECT r.* FROM knowledge_relation_resolution_index i
                    JOIN knowledge_relations r ON r.relation_id = i.relation_id
                    WHERE i.target_category = ?
                      AND i.relation_type IN ({relation_placeholders})
                      AND i.resolution_status = ?
                      AND i.relation_status != ?
                      AND i.target_key IN ({label_placeholders})
                    """,  # noqa: S608 - placeholders are generated, values stay parameterized
                    (
                        target_category,
                        *relation_types,
                        RelationResolutionStatus.UNRESOLVED.value,
                        RelationStatus.DEPRECATED.value,
                        *labels,
                    ),
                ).fetchall()
                for row in exact_rows:
                    record = _relation_record(row)
                    found[record.relation_id] = record

                if target_category == "specimen":
                    for label in labels:
                        prefix = label[::-1]
                        suffix_rows = connection.execute(
                            f"""
                            SELECT r.* FROM knowledge_relation_resolution_index i
                            JOIN knowledge_relations r ON r.relation_id = i.relation_id
                            WHERE i.target_category = ?
                              AND i.relation_type IN ({relation_placeholders})
                              AND i.resolution_status = ?
                              AND i.relation_status != ?
                              AND i.target_reverse_key >= ?
                              AND i.target_reverse_key < ?
                            """,  # noqa: S608 - placeholders are generated only for enum values
                            (
                                target_category,
                                *relation_types,
                                RelationResolutionStatus.UNRESOLVED.value,
                                RelationStatus.DEPRECATED.value,
                                prefix,
                                prefix + "\U0010ffff",
                            ),
                        ).fetchall()
                        for row in suffix_rows:
                            record = _relation_record(row)
                            found[record.relation_id] = record
            return [found[key] for key in sorted(found)]
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(
                f"Relation Resolution Indexを検索できません: {error}"
            ) from error

    def resolve_indexed(
        self,
        target_knowledge_id: str,
        target_category: str,
        evaluated_relation_ids: list[str],
        updates: list[RelationResolutionUpdate],
        *,
        actor: str,
        note: str,
    ) -> ResolutionReport:
        actor = actor.strip()
        note = note.strip()
        evaluated_ids = list(dict.fromkeys(evaluated_relation_ids))
        update_by_id = {item.relation_id: item for item in updates}
        if not actor or not note:
            raise RegistryOperationError("Resolution Reportには操作者と理由が必要です。")
        if len(update_by_id) != len(updates):
            raise RegistryOperationError("同じRelationを2回解決しようとしています。")
        if not set(update_by_id).issubset(evaluated_ids):
            raise RegistryOperationError("未評価のRelationを解決できません。")
        now = _now()
        report_id = f"rpt_{uuid4().hex[:20]}"
        try:
            with self._connect() as connection:
                rows: dict[str, sqlite3.Row] = {}
                if evaluated_ids:
                    placeholders = ",".join("?" for _ in evaluated_ids)
                    rows = {
                        str(row["relation_id"]): row
                        for row in connection.execute(
                            (
                                "SELECT * FROM knowledge_relations "
                                f"WHERE relation_id IN ({placeholders})"  # noqa: S608
                            ),
                            evaluated_ids,
                        ).fetchall()
                    }
                missing = sorted(set(evaluated_ids) - set(rows))
                if missing:
                    raise RegistryOperationError(
                        "Resolution Indexが存在しないRelationを返しました: " + ", ".join(missing)
                    )
                for relation_id, update in update_by_id.items():
                    current = rows[relation_id]
                    if (
                        RelationResolutionStatus(str(current["resolution_status"]))
                        != RelationResolutionStatus.UNRESOLVED
                        or RelationStatus(str(current["status"])) == RelationStatus.DEPRECATED
                    ):
                        raise RegistryOperationError(
                            f"未解決かつ有効なRelationだけ更新できます: {relation_id}"
                        )
                    old_version = int(current["relation_version"])
                    new_version = old_version + 1
                    connection.execute(
                        """
                        UPDATE knowledge_relations
                        SET target_knowledge_id = ?, target_label = ?, target_key = ?,
                            resolution_status = ?, relation_version = ?, context_json = ?,
                            updated_at = ?
                        WHERE relation_id = ?
                        """,
                        (
                            update.target_knowledge_id,
                            update.target_label,
                            _normalize(update.target_label),
                            RelationResolutionStatus.RESOLVED.value,
                            new_version,
                            _json(update.context.model_dump(mode="json")),
                            now,
                            relation_id,
                        ),
                    )
                    self._history(
                        connection,
                        relation_id,
                        RelationHistoryAction.UPDATE,
                        old_version,
                        new_version,
                        actor,
                        note,
                        now,
                    )
                    self._sync_index_for_relation_id(connection, relation_id)

                resolved_ids = sorted(update_by_id)
                unresolved_ids = sorted(set(evaluated_ids) - set(update_by_id))
                connection.execute(
                    """
                    INSERT INTO knowledge_relation_resolution_reports(
                        report_id, target_knowledge_id, target_category,
                        evaluated_count, resolved_count, unresolved_count,
                        evaluated_relation_ids_json, resolved_relation_ids_json,
                        unresolved_relation_ids_json, created_at, actor, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        target_knowledge_id,
                        target_category,
                        len(evaluated_ids),
                        len(resolved_ids),
                        len(unresolved_ids),
                        _json(sorted(evaluated_ids)),
                        _json(resolved_ids),
                        _json(unresolved_ids),
                        now,
                        actor,
                        note,
                    ),
                )
            return ResolutionReport(
                report_id=report_id,
                target_knowledge_id=target_knowledge_id,
                target_category=target_category,
                evaluated_count=len(evaluated_ids),
                resolved_count=len(resolved_ids),
                unresolved_count=len(unresolved_ids),
                evaluated_relation_ids=sorted(evaluated_ids),
                resolved_relation_ids=resolved_ids,
                unresolved_relation_ids=unresolved_ids,
                created_at=datetime.fromisoformat(now),
                actor=actor,
                note=note,
            )
        except RegistryOperationError:
            raise
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Indexed Relationを解決できません: {error}") from error

    def resolution_reports(
        self, target_knowledge_id: str | None = None
    ) -> list[ResolutionReport]:
        query = "SELECT * FROM knowledge_relation_resolution_reports"
        parameters: tuple[str, ...] = ()
        if target_knowledge_id is not None:
            query += " WHERE target_knowledge_id = ?"
            parameters = (target_knowledge_id,)
        query += " ORDER BY created_at, report_id"
        try:
            with self._connect() as connection:
                return [
                    _resolution_report(row)
                    for row in connection.execute(query, parameters).fetchall()
                ]
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Resolution Reportを読み込めません: {error}") from error

    def network_summary(self, source_knowledge_id: str) -> NetworkSummary:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS relation_count,
                        SUM(CASE WHEN resolution_status = 'resolved' THEN 1 ELSE 0 END)
                            AS resolved_count
                    FROM knowledge_relations
                    WHERE source_knowledge_id = ? AND status != ?
                    """,
                    (source_knowledge_id, RelationStatus.DEPRECATED.value),
                ).fetchone()
            relation_count = int(row["relation_count"] if row is not None else 0)
            resolved_count = int((row["resolved_count"] if row is not None else 0) or 0)
            unresolved_count = relation_count - resolved_count
            completeness = (
                round((resolved_count / relation_count) * 100, 1)
                if relation_count
                else 0.0
            )
            return NetworkSummary(
                knowledge_id=source_knowledge_id,
                relation_count=relation_count,
                resolved_count=resolved_count,
                unresolved_count=unresolved_count,
                network_completeness=completeness,
            )
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Network Summaryを計算できません: {error}") from error

    def ensure_schema(self) -> None:
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    relation_id TEXT PRIMARY KEY,
                    source_knowledge_id TEXT NOT NULL,
                    target_knowledge_id TEXT,
                    target_label TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    resolution_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    relation_version INTEGER NOT NULL,
                    context_json TEXT NOT NULL DEFAULT '{"qualifiers":[],"preparation":null}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(source_knowledge_id)
                        REFERENCES knowledge_registry(knowledge_id),
                    FOREIGN KEY(target_knowledge_id)
                        REFERENCES knowledge_registry(knowledge_id),
                    FOREIGN KEY(claim_id) REFERENCES claim_registry(claim_id),
                    UNIQUE(source_knowledge_id, relation_type, target_key)
                );
                CREATE INDEX IF NOT EXISTS idx_relation_source
                    ON knowledge_relations(source_knowledge_id, status);
                CREATE INDEX IF NOT EXISTS idx_relation_target
                    ON knowledge_relations(target_knowledge_id, status);
                CREATE TABLE IF NOT EXISTS knowledge_relation_history (
                    event_id TEXT PRIMARY KEY,
                    relation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    from_version INTEGER,
                    to_version INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    note TEXT NOT NULL,
                    FOREIGN KEY(relation_id) REFERENCES knowledge_relations(relation_id)
                );
                CREATE INDEX IF NOT EXISTS idx_relation_history
                    ON knowledge_relation_history(relation_id, occurred_at);
                CREATE TABLE IF NOT EXISTS knowledge_relation_resolution_index (
                    relation_id TEXT PRIMARY KEY,
                    source_knowledge_id TEXT NOT NULL,
                    target_label TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    target_reverse_key TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_category TEXT NOT NULL,
                    resolution_status TEXT NOT NULL,
                    relation_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(relation_id) REFERENCES knowledge_relations(relation_id)
                );
                CREATE INDEX IF NOT EXISTS idx_resolution_exact
                    ON knowledge_relation_resolution_index(
                        target_category, relation_type, resolution_status, target_key
                    );
                CREATE INDEX IF NOT EXISTS idx_resolution_suffix
                    ON knowledge_relation_resolution_index(
                        target_category, relation_type, resolution_status, target_reverse_key
                    );
                CREATE TABLE IF NOT EXISTS knowledge_relation_resolution_reports (
                    report_id TEXT PRIMARY KEY,
                    target_knowledge_id TEXT NOT NULL,
                    target_category TEXT NOT NULL,
                    evaluated_count INTEGER NOT NULL,
                    resolved_count INTEGER NOT NULL,
                    unresolved_count INTEGER NOT NULL,
                    evaluated_relation_ids_json TEXT NOT NULL,
                    resolved_relation_ids_json TEXT NOT NULL,
                    unresolved_relation_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    note TEXT NOT NULL,
                    FOREIGN KEY(target_knowledge_id) REFERENCES knowledge_registry(knowledge_id)
                );
                CREATE INDEX IF NOT EXISTS idx_resolution_report_target
                    ON knowledge_relation_resolution_reports(target_knowledge_id, created_at);
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(knowledge_relations)").fetchall()
            }
            if "context_json" not in columns:
                connection.execute(
                    """
                    ALTER TABLE knowledge_relations
                    ADD COLUMN context_json TEXT NOT NULL
                    DEFAULT '{"qualifiers":[],"preparation":null}'
                    """
                )
            for row in connection.execute("SELECT relation_id FROM knowledge_relations").fetchall():
                self._sync_index_for_relation_id(connection, str(row["relation_id"]))
            connection.execute("PRAGMA user_version = 6")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _validate_candidates(
        self,
        source_knowledge_id: str,
        candidates: list[RelationCandidate],
        registry: RegistrySnapshot,
    ) -> None:
        knowledge_ids = {item.knowledge_id for item in registry.knowledge}
        if source_knowledge_id not in knowledge_ids:
            raise RegistryOperationError(
                f"Relation元KnowledgeがRegistryにありません: {source_knowledge_id}"
            )
        claim_owners = {item.claim_id: item.knowledge_id for item in registry.claims}
        relation_ids = [item.relation_id for item in candidates]
        if len(relation_ids) != len(set(relation_ids)):
            raise RegistryOperationError("Resolverが重複relation_idを返しました。")
        for candidate in candidates:
            if candidate.source_knowledge_id != source_knowledge_id:
                raise RegistryOperationError("Relation元Knowledgeが一致しません。")
            if claim_owners.get(candidate.claim_id) != source_knowledge_id:
                raise RegistryOperationError(
                    f"Relation根拠Claimが元Knowledgeにありません: {candidate.claim_id}"
                )
            if candidate.resolution_status == RelationResolutionStatus.RESOLVED:
                if candidate.target_knowledge_id not in knowledge_ids:
                    raise RegistryOperationError(
                        "resolved Relationの対象KnowledgeがRegistryにありません。"
                    )
            elif candidate.target_knowledge_id is not None:
                raise RegistryOperationError(
                    "unresolved_relationへtarget_knowledge_idは保存できません。"
                )

    def _insert_relation(
        self,
        connection: sqlite3.Connection,
        candidate: RelationCandidate,
        actor: str,
        note: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO knowledge_relations(
                relation_id, source_knowledge_id, target_knowledge_id,
                target_label, target_key, relation_type, claim_id,
                resolution_status, status, relation_version, context_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                candidate.relation_id,
                candidate.source_knowledge_id,
                candidate.target_knowledge_id,
                candidate.target_label,
                _normalize(candidate.target_label),
                candidate.relation_type.value,
                candidate.claim_id,
                candidate.resolution_status.value,
                RelationStatus.DRAFT.value,
                _json(candidate.context.model_dump(mode="json")),
                now,
                now,
            ),
        )
        self._history(
            connection,
            candidate.relation_id,
            RelationHistoryAction.ADD,
            None,
            1,
            actor,
            note,
            now,
        )
        self._sync_index_for_relation_id(connection, candidate.relation_id)

    def _update_if_changed(
        self,
        connection: sqlite3.Connection,
        current: sqlite3.Row,
        candidate: RelationCandidate,
        actor: str,
        note: str,
        now: str,
    ) -> None:
        current_values = (
            current["source_knowledge_id"],
            current["target_knowledge_id"],
            current["target_label"],
            current["relation_type"],
            current["claim_id"],
            current["resolution_status"],
            _json(json.loads(str(current["context_json"]))),
        )
        candidate_values = (
            candidate.source_knowledge_id,
            candidate.target_knowledge_id,
            candidate.target_label,
            candidate.relation_type.value,
            candidate.claim_id,
            candidate.resolution_status.value,
            _json(candidate.context.model_dump(mode="json")),
        )
        if (
            current_values == candidate_values
            and RelationStatus(str(current["status"])) != RelationStatus.DEPRECATED
        ):
            return
        old_version = int(current["relation_version"])
        new_version = old_version + 1
        connection.execute(
            """
            UPDATE knowledge_relations
            SET target_knowledge_id = ?, target_label = ?, target_key = ?,
                relation_type = ?, claim_id = ?, resolution_status = ?,
                status = ?, relation_version = ?, context_json = ?, updated_at = ?
            WHERE relation_id = ?
            """,
            (
                candidate.target_knowledge_id,
                candidate.target_label,
                _normalize(candidate.target_label),
                candidate.relation_type.value,
                candidate.claim_id,
                candidate.resolution_status.value,
                RelationStatus.DRAFT.value,
                new_version,
                _json(candidate.context.model_dump(mode="json")),
                now,
                candidate.relation_id,
            ),
        )
        self._history(
            connection,
            candidate.relation_id,
            RelationHistoryAction.UPDATE,
            old_version,
            new_version,
            actor,
            note,
            now,
        )
        self._sync_index_for_relation_id(connection, candidate.relation_id)

    def _deprecate(
        self,
        connection: sqlite3.Connection,
        current: sqlite3.Row,
        actor: str,
        note: str,
        now: str,
    ) -> None:
        old_version = int(current["relation_version"])
        new_version = old_version + 1
        relation_id = str(current["relation_id"])
        connection.execute(
            """
            UPDATE knowledge_relations
            SET status = ?, relation_version = ?, updated_at = ?
            WHERE relation_id = ?
            """,
            (RelationStatus.DEPRECATED.value, new_version, now, relation_id),
        )
        self._history(
            connection,
            relation_id,
            RelationHistoryAction.DEPRECATE,
            old_version,
            new_version,
            actor,
            note,
            now,
        )
        self._sync_index_for_relation_id(connection, relation_id)

    def _sync_index_for_relation_id(
        self, connection: sqlite3.Connection, relation_id: str
    ) -> None:
        row = connection.execute(
            "SELECT * FROM knowledge_relations WHERE relation_id = ?",
            (relation_id,),
        ).fetchone()
        if row is None:
            connection.execute(
                "DELETE FROM knowledge_relation_resolution_index WHERE relation_id = ?",
                (relation_id,),
            )
            return
        relation_type = RelationType(str(row["relation_type"]))
        target_key = _normalize(str(row["target_label"]))
        connection.execute(
            """
            INSERT INTO knowledge_relation_resolution_index(
                relation_id, source_knowledge_id, target_label, target_key,
                target_reverse_key, relation_type, target_category,
                resolution_status, relation_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relation_id) DO UPDATE SET
                source_knowledge_id = excluded.source_knowledge_id,
                target_label = excluded.target_label,
                target_key = excluded.target_key,
                target_reverse_key = excluded.target_reverse_key,
                relation_type = excluded.relation_type,
                target_category = excluded.target_category,
                resolution_status = excluded.resolution_status,
                relation_status = excluded.relation_status,
                updated_at = excluded.updated_at
            """,
            (
                relation_id,
                str(row["source_knowledge_id"]),
                str(row["target_label"]),
                target_key,
                target_key[::-1],
                relation_type.value,
                _TARGET_CATEGORY_BY_RELATION_TYPE[relation_type],
                str(row["resolution_status"]),
                str(row["status"]),
                str(row["updated_at"]),
            ),
        )

    def _history(
        self,
        connection: sqlite3.Connection,
        relation_id: str,
        action: RelationHistoryAction,
        from_version: int | None,
        to_version: int,
        actor: str,
        note: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO knowledge_relation_history(
                event_id, relation_id, action, from_version, to_version,
                occurred_at, actor, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"evt_{uuid4().hex[:20]}",
                relation_id,
                action.value,
                from_version,
                to_version,
                now,
                actor,
                note,
            ),
        )


def _relation_record(row: sqlite3.Row) -> KnowledgeRelationRecord:
    return KnowledgeRelationRecord(
        relation_id=str(row["relation_id"]),
        source_knowledge_id=str(row["source_knowledge_id"]),
        target_knowledge_id=(
            str(row["target_knowledge_id"]) if row["target_knowledge_id"] is not None else None
        ),
        target_label=str(row["target_label"]),
        relation_type=RelationType(str(row["relation_type"])),
        claim_id=str(row["claim_id"]),
        resolution_status=RelationResolutionStatus(str(row["resolution_status"])),
        status=RelationStatus(str(row["status"])),
        version=int(row["relation_version"]),
        context=json.loads(str(row["context_json"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def _history_event(row: sqlite3.Row) -> RelationHistoryEvent:
    return RelationHistoryEvent(
        event_id=str(row["event_id"]),
        relation_id=str(row["relation_id"]),
        action=RelationHistoryAction(str(row["action"])),
        from_version=(int(row["from_version"]) if row["from_version"] is not None else None),
        to_version=int(row["to_version"]),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        actor=str(row["actor"]),
        note=str(row["note"]),
    )


def _resolution_report(row: sqlite3.Row) -> ResolutionReport:
    return ResolutionReport(
        report_id=str(row["report_id"]),
        target_knowledge_id=str(row["target_knowledge_id"]),
        target_category=str(row["target_category"]),
        evaluated_count=int(row["evaluated_count"]),
        resolved_count=int(row["resolved_count"]),
        unresolved_count=int(row["unresolved_count"]),
        evaluated_relation_ids=json.loads(str(row["evaluated_relation_ids_json"])),
        resolved_relation_ids=json.loads(str(row["resolved_relation_ids_json"])),
        unresolved_relation_ids=json.loads(str(row["unresolved_relation_ids_json"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        actor=str(row["actor"]),
        note=str(row["note"]),
    )


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()
