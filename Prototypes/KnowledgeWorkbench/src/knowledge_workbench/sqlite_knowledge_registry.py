"""Persistent SQLite implementation of the Knowledge Registry boundary."""

import hashlib
import json
import sqlite3
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from knowledge_contracts.approval_v10 import approval_transition_is_allowed
from knowledge_contracts.registry_v10 import (
    ApprovalDecision,
    ClaimMergeCandidate,
    ClaimMergeRedirect,
    ClaimRegistryEntry,
    KnowledgeRegistryEntry,
    RegistryAliasBinding,
    RegistryEntityType,
    RegistryHistoryAction,
    RegistryHistoryEvent,
    RegistryKnowledgeView,
    RegistrySnapshot,
    RegistryStatus,
    registry_validation_report,
    validate_registry_snapshot,
)
from knowledge_contracts.v10 import KnowledgeRecord, validate_knowledge_record

from knowledge_workbench.claim_key_resolver import (
    ClaimCandidate,
    collapse_semantic_duplicates,
    extract_claim_candidates,
    registry_key_for_record,
)
from knowledge_workbench.errors import RegistryOperationError
from knowledge_workbench.knowledge_registry import RegistryReconciliation


class SQLiteKnowledgeRegistry:
    """A durable local registry; a future database can replace this adapter."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def reconcile(
        self,
        record: KnowledgeRecord,
        *,
        actor: str = "knowledge_workbench",
        note: str = "",
    ) -> RegistryReconciliation:
        raw = record.model_dump(mode="json")
        registry_key = registry_key_for_record(raw)
        now = _now()
        try:
            with self._connect() as connection:
                knowledge_row, knowledge_created = self._ensure_knowledge(
                    connection, raw, registry_key, actor, now, note
                )
                registered_knowledge_id = str(knowledge_row["knowledge_id"])
                _rewrite_knowledge_id(raw, record.knowledge_id, registered_knowledge_id)
                candidates = extract_claim_candidates(raw, registry_key)
                self._canonicalize_merged_candidates(connection, candidates)
                candidates = collapse_semantic_duplicates(candidates)
                mappings, existing = self._plan_claims(
                    connection, candidates, registered_knowledge_id
                )
                _rewrite_claim_ids(raw, mappings)
                new_claim_count, updated_claim_count = self._persist_candidates(
                    connection,
                    candidates,
                    existing,
                    registered_knowledge_id,
                    actor,
                    now,
                    note,
                )
                self._merge_registry_claims(
                    connection,
                    raw,
                    candidates,
                    registered_knowledge_id,
                )
                if (new_claim_count or updated_claim_count) and not knowledge_created:
                    self._bump_knowledge_version(
                        connection,
                        registered_knowledge_id,
                        actor,
                        now,
                        (
                            f"Claim変更: 新規{new_claim_count}件、"
                            f"更新{updated_claim_count}件"
                            + (f" · {note.strip()}" if note.strip() else "")
                        ),
                    )
                knowledge_version = self._knowledge_version(connection, registered_knowledge_id)
                raw["content_revision"] = knowledge_version
                validated_record = validate_knowledge_record(raw)
                self._persist_record(connection, validated_record, now)
                snapshot = self._snapshot(connection)
                view = self._view_from_snapshot(snapshot, registered_knowledge_id)
            return RegistryReconciliation(validated_record, view)
        except RegistryOperationError:
            raise
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(
                f"Knowledge Registryへの保存に失敗しました: {error}"
            ) from error

    def snapshot(self) -> RegistrySnapshot:
        try:
            with self._connect() as connection:
                return self._snapshot(connection)
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Knowledge Registryを読み込めません: {error}") from error

    def backup_to(self, destination: Path) -> None:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise RegistryOperationError(
                f"同名のRegistry Backupがすでに存在します: {destination.name}"
            )
        try:
            with self._connect() as source, sqlite3.connect(destination) as target:
                source.backup(target)
            SQLiteKnowledgeRegistry(destination).snapshot()
        except (sqlite3.Error, ValueError) as error:
            destination.unlink(missing_ok=True)
            raise RegistryOperationError(f"Registry Backupを作成できません: {error}") from error

    def restore_from(self, source_path: Path) -> None:
        source_path = source_path.resolve()
        if not source_path.is_file():
            raise RegistryOperationError(f"Registry Backupが見つかりません: {source_path.name}")
        validation_copy = self.database_path.with_name(
            f".registry-restore-validation-{uuid4().hex}.db"
        )
        try:
            with sqlite3.connect(source_path) as source, sqlite3.connect(validation_copy) as target:
                source.backup(target)
            SQLiteKnowledgeRegistry(validation_copy).snapshot()
            with sqlite3.connect(source_path) as source, self._connect() as target:
                source.backup(target)
            self._initialize()
            self.snapshot()
        except (sqlite3.Error, ValueError) as error:
            raise RegistryOperationError(f"Registry Backupを復元できません: {error}") from error
        finally:
            validation_copy.unlink(missing_ok=True)
            validation_copy.with_name(validation_copy.name + "-wal").unlink(missing_ok=True)
            validation_copy.with_name(validation_copy.name + "-shm").unlink(missing_ok=True)

    def view(self, knowledge_id: str) -> RegistryKnowledgeView:
        return self._view_from_snapshot(self.snapshot(), knowledge_id)

    def record(self, knowledge_id: str) -> KnowledgeRecord | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT record_json FROM knowledge_records WHERE knowledge_id = ?",
                    (knowledge_id,),
                ).fetchone()
                if row is None:
                    return None
                return validate_knowledge_record(json.loads(str(row["record_json"])))
        except (sqlite3.Error, ValueError, json.JSONDecodeError) as error:
            raise RegistryOperationError(f"Knowledge JSONを読み込めません: {error}") from error

    def resolve_claim_id(self, knowledge_id: str, claim_key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT claim_id, status, is_deleted FROM claim_registry
                WHERE knowledge_id = ? AND claim_key = ?
                """,
                (knowledge_id, claim_key),
            ).fetchone()
            if row is None or bool(row["is_deleted"]):
                return None
            claim_id = str(row["claim_id"])
            if RegistryStatus(str(row["status"])) != RegistryStatus.DEPRECATED:
                return claim_id
            return self._canonical_claim_id(connection, claim_id)

    def canonical_claim_id(self, claim_id: str) -> str | None:
        with self._connect() as connection:
            return self._canonical_claim_id(connection, claim_id)

    def merge_claims(
        self,
        knowledge_id: str,
        target_claim_id: str,
        source_claim_ids: list[str],
        *,
        actor: str,
        comment: str,
    ) -> RegistryKnowledgeView:
        actor = actor.strip()
        comment = comment.strip()
        sources = list(dict.fromkeys(source_claim_ids))
        if not actor or not comment:
            raise RegistryOperationError("操作者と統合コメントを入力してください。")
        if not sources:
            raise RegistryOperationError("統合元Claimを1件以上選択してください。")
        if target_claim_id in sources:
            raise RegistryOperationError("統合先を統合元として選択できません。")

        now = _now()
        with self._connect() as connection:
            target = self._claim_row_by_id(connection, target_claim_id)
            if target is None or str(target["knowledge_id"]) != knowledge_id:
                raise RegistryOperationError("統合先Claimが対象Knowledgeにありません。")
            if (
                bool(target["is_deleted"])
                or RegistryStatus(str(target["status"])) == RegistryStatus.DEPRECATED
            ):
                raise RegistryOperationError("deprecatedまたは削除済みClaimは統合先にできません。")

            source_rows: list[sqlite3.Row] = []
            for source_id in sources:
                source = self._claim_row_by_id(connection, source_id)
                if source is None or str(source["knowledge_id"]) != knowledge_id:
                    raise RegistryOperationError(
                        f"統合元Claimが対象Knowledgeにありません: {source_id}"
                    )
                if bool(source["is_deleted"]):
                    raise RegistryOperationError(f"削除済みClaimは統合できません: {source_id}")
                existing_redirect = connection.execute(
                    "SELECT target_claim_id FROM claim_merge_redirects WHERE source_claim_id = ?",
                    (source_id,),
                ).fetchone()
                if existing_redirect is not None:
                    raise RegistryOperationError(f"すでに統合済みのClaimです: {source_id}")
                source_rows.append(source)

            target_aliases = _string_list(target["aliases_json"])
            for source in source_rows:
                source_id = str(source["claim_id"])
                source_key = str(source["claim_key"])
                source_version = int(source["claim_version"])
                target_aliases.extend(
                    [source_key, str(source["assertion"]), *_string_list(source["aliases_json"])]
                )
                connection.execute(
                    """
                    UPDATE claim_registry
                    SET status = ?, updated_at = ?
                    WHERE claim_id = ?
                    """,
                    (RegistryStatus.DEPRECATED.value, now, source_id),
                )
                connection.execute(
                    """
                    INSERT INTO claim_merge_redirects(
                        source_claim_id, source_claim_key, target_claim_id,
                        target_claim_key, merged_at, actor, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        source_key,
                        target_claim_id,
                        str(target["claim_key"]),
                        now,
                        actor,
                        comment,
                    ),
                )
                self._history(
                    connection,
                    RegistryEntityType.CLAIM,
                    source_id,
                    RegistryHistoryAction.MERGE,
                    source_version,
                    source_version,
                    actor,
                    now,
                    {
                        "target_claim_id": target_claim_id,
                        "target_claim_key": str(target["claim_key"]),
                        "comment": comment,
                    },
                )

            connection.execute(
                "UPDATE claim_registry SET aliases_json = ?, updated_at = ? WHERE claim_id = ?",
                (_json(_unique(target_aliases)[:100]), now, target_claim_id),
            )
            target_version = int(target["claim_version"])
            self._history(
                connection,
                RegistryEntityType.CLAIM,
                target_claim_id,
                RegistryHistoryAction.MERGE,
                target_version,
                target_version,
                actor,
                now,
                {
                    "source_claim_ids": ",".join(sources),
                    "comment": comment,
                },
            )
            self._rewrite_stored_claim_references(
                connection,
                {source_id: target_claim_id for source_id in sources},
                actor,
                now,
            )
            self._bump_knowledge_version(
                connection,
                knowledge_id,
                actor,
                now,
                f"{len(sources)}件のClaimを{target_claim_id}へ統合",
            )
            self._sync_stored_record_after_merge(
                connection,
                knowledge_id,
                {source_id: target_claim_id for source_id in sources},
                now,
            )
            snapshot = self._snapshot(connection)
            return self._view_from_snapshot(snapshot, knowledge_id)

    def transition_status(
        self,
        entity_type: RegistryEntityType,
        entity_id: str,
        status: RegistryStatus,
        *,
        actor: str,
        note: str = "",
    ) -> None:
        table, id_column, version_column = _entity_columns(entity_type)
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {id_column} = ?",  # noqa: S608
                (entity_id,),
            ).fetchone()
            if row is None:
                raise RegistryOperationError(f"Registry対象が見つかりません: {entity_id}")
            current = RegistryStatus(str(row["status"]))
            _require_transition(current, status)
            if entity_type == RegistryEntityType.KNOWLEDGE and status == RegistryStatus.APPROVED:
                self._require_all_claims_approved(connection, entity_id)
            approvals = _approval_list(row["approval_json"])
            approvals.append(
                ApprovalDecision(
                    status=status,
                    actor=actor,
                    decided_at=datetime.fromisoformat(now),
                    note=note,
                )
            )
            connection.execute(
                f"UPDATE {table} SET status = ?, updated_at = ?, approval_json = ? "  # noqa: S608
                f"WHERE {id_column} = ?",
                (
                    status.value,
                    now,
                    _json([item.model_dump(mode="json") for item in approvals]),
                    entity_id,
                ),
            )
            version = int(row[version_column])
            self._history(
                connection,
                entity_type,
                entity_id,
                RegistryHistoryAction.STATUS_CHANGE,
                version,
                version,
                actor,
                now,
                {"from_status": current.value, "to_status": status.value, "note": note},
            )
            self._snapshot(connection)

    def transition_claims_status(
        self,
        claim_ids: list[str],
        status: RegistryStatus,
        *,
        actor: str,
        note: str,
    ) -> RegistryKnowledgeView:
        actor = actor.strip()
        note = note.strip()
        ids = list(dict.fromkeys(claim_ids))
        if not ids or not actor or not note:
            raise RegistryOperationError("Claim、操作者、承認コメントをすべて入力してください。")
        now = _now()
        with self._connect() as connection:
            rows: list[sqlite3.Row] = []
            knowledge_ids: set[str] = set()
            for claim_id in ids:
                row = self._claim_row_by_id(connection, claim_id)
                if row is None:
                    raise RegistryOperationError(f"Registry対象が見つかりません: {claim_id}")
                if bool(row["is_deleted"]):
                    raise RegistryOperationError(f"削除済みClaimの状態は変更できません: {claim_id}")
                current = RegistryStatus(str(row["status"]))
                _require_transition(current, status)
                rows.append(row)
                knowledge_ids.add(str(row["knowledge_id"]))
            if len(knowledge_ids) != 1:
                raise RegistryOperationError(
                    "一度に状態変更できるのは同じKnowledgeのClaimだけです。"
                )

            for row in rows:
                current = RegistryStatus(str(row["status"]))
                approvals = _approval_list(row["approval_json"])
                approvals.append(
                    ApprovalDecision(
                        status=status,
                        actor=actor,
                        decided_at=datetime.fromisoformat(now),
                        note=note,
                    )
                )
                connection.execute(
                    """
                    UPDATE claim_registry
                    SET status = ?, updated_at = ?, approval_json = ?
                    WHERE claim_id = ?
                    """,
                    (
                        status.value,
                        now,
                        _json([item.model_dump(mode="json") for item in approvals]),
                        str(row["claim_id"]),
                    ),
                )
                version = int(row["claim_version"])
                self._history(
                    connection,
                    RegistryEntityType.CLAIM,
                    str(row["claim_id"]),
                    RegistryHistoryAction.STATUS_CHANGE,
                    version,
                    version,
                    actor,
                    now,
                    {
                        "from_status": current.value,
                        "to_status": status.value,
                        "note": note,
                    },
                )
            knowledge_id = next(iter(knowledge_ids))
            snapshot = self._snapshot(connection)
            return self._view_from_snapshot(snapshot, knowledge_id)

    def update_claim(
        self,
        claim_key: str,
        assertion: str,
        *,
        actor: str,
        semantic_change: bool,
        note: str = "",
    ) -> ClaimRegistryEntry:
        now = _now()
        with self._connect() as connection:
            row = self._claim_row_by_key(connection, claim_key)
            if row is None:
                raise RegistryOperationError(f"claim_keyが見つかりません: {claim_key}")
            old_version = int(row["claim_version"])
            new_version = old_version + 1 if semantic_change else old_version
            payload = _object(row["payload_json"])
            if "assertion" in payload:
                payload["assertion"] = assertion
            aliases = _string_list(row["aliases_json"])
            aliases = _unique([*aliases, str(row["assertion"]), assertion])
            connection.execute(
                """
                UPDATE claim_registry
                SET assertion = ?, claim_version = ?, status = ?, updated_at = ?,
                    aliases_json = ?, payload_json = ?
                WHERE claim_key = ?
                """,
                (
                    assertion,
                    new_version,
                    RegistryStatus.DRAFT.value,
                    now,
                    _json(aliases),
                    _json(payload),
                    claim_key,
                ),
            )
            if semantic_change:
                self._bump_knowledge_version(
                    connection,
                    str(row["knowledge_id"]),
                    actor,
                    now,
                    f"{claim_key}の医学的意味を更新",
                )
            self._replace_stored_claim_payload(
                connection,
                str(row["knowledge_id"]),
                str(row["claim_id"]),
                payload,
                now,
            )
            self._history(
                connection,
                RegistryEntityType.CLAIM,
                str(row["claim_id"]),
                RegistryHistoryAction.UPDATE,
                old_version,
                new_version,
                actor,
                now,
                {
                    "semantic_change": str(semantic_change).lower(),
                    "note": note,
                },
            )
            snapshot = self._snapshot(connection)
            return next(item for item in snapshot.claims if item.claim_key == claim_key)

    def deprecate_claim(self, claim_key: str, *, actor: str, note: str = "") -> None:
        self._set_claim_lifecycle(
            claim_key,
            actor,
            note,
            RegistryHistoryAction.DEPRECATED,
            deleted=False,
        )

    def mark_claim_deleted(self, claim_key: str, *, actor: str, note: str = "") -> None:
        self._set_claim_lifecycle(
            claim_key,
            actor,
            note,
            RegistryHistoryAction.DELETE,
            deleted=True,
        )

    def add_alias(self, alias: str, target: str) -> KnowledgeRegistryEntry:
        alias_key = _normalized(alias)
        target_key = _normalized(target)
        if alias_key == target_key:
            raise RegistryOperationError("aliasとtargetを同じ値にはできません。")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO knowledge_aliases(alias_key, alias_display, target_key)
                    VALUES (?, ?, ?)
                    ON CONFLICT(alias_key) DO UPDATE SET
                        alias_display = excluded.alias_display,
                        target_key = excluded.target_key
                    """,
                    (alias_key, alias.strip(), target_key),
                )
                snapshot = self._snapshot(connection)
                resolved = _resolve_alias(snapshot, alias)
                return next(item for item in snapshot.knowledge if item.registry_key == resolved)
        except ValueError as error:
            raise RegistryOperationError(f"aliasを登録できません: {error}") from error

    def knowledge_by_id(self, knowledge_id: str) -> KnowledgeRegistryEntry | None:
        snapshot = self.snapshot()
        return next(
            (item for item in snapshot.knowledge if item.knowledge_id == knowledge_id),
            None,
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS knowledge_registry (
                    knowledge_id TEXT PRIMARY KEY,
                    registry_key TEXT NOT NULL UNIQUE,
                    canonical_name TEXT NOT NULL,
                    knowledge_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approval_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_aliases (
                    alias_key TEXT PRIMARY KEY,
                    alias_display TEXT NOT NULL,
                    target_key TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    knowledge_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    content_revision INTEGER NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_id) REFERENCES knowledge_registry(knowledge_id)
                );
                CREATE TABLE IF NOT EXISTS claim_registry (
                    claim_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    claim_key TEXT NOT NULL UNIQUE,
                    claim_version INTEGER NOT NULL,
                    field_path TEXT NOT NULL,
                    assertion TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    approval_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(knowledge_id) REFERENCES knowledge_registry(knowledge_id)
                );
                CREATE INDEX IF NOT EXISTS idx_claim_knowledge
                    ON claim_registry(knowledge_id);
                CREATE TABLE IF NOT EXISTS claim_merge_redirects (
                    source_claim_id TEXT PRIMARY KEY,
                    source_claim_key TEXT NOT NULL,
                    target_claim_id TEXT NOT NULL,
                    target_claim_key TEXT NOT NULL,
                    merged_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    FOREIGN KEY(source_claim_id) REFERENCES claim_registry(claim_id),
                    FOREIGN KEY(target_claim_id) REFERENCES claim_registry(claim_id)
                );
                CREATE INDEX IF NOT EXISTS idx_merge_target
                    ON claim_merge_redirects(target_claim_id);
                CREATE TABLE IF NOT EXISTS registry_history (
                    event_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    from_version INTEGER,
                    to_version INTEGER,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_history_entity
                    ON registry_history(entity_type, entity_id, occurred_at);
                PRAGMA user_version = 3;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_knowledge(
        self,
        connection: sqlite3.Connection,
        raw: dict[str, Any],
        registry_key: str,
        actor: str,
        now: str,
        note: str,
    ) -> tuple[sqlite3.Row, bool]:
        row = connection.execute(
            "SELECT * FROM knowledge_registry WHERE registry_key = ?",
            (registry_key,),
        ).fetchone()
        term = cast(dict[str, Any], raw["term"])
        canonical_name = str(term["canonical_name"])
        if row is None:
            connection.execute(
                """
                INSERT INTO knowledge_registry(
                    knowledge_id, registry_key, canonical_name, knowledge_version,
                    status, created_at, updated_at, approval_json
                ) VALUES (?, ?, ?, 1, ?, ?, ?, '[]')
                """,
                (
                    raw["knowledge_id"],
                    registry_key,
                    canonical_name,
                    RegistryStatus.DRAFT.value,
                    now,
                    now,
                ),
            )
            self._history(
                connection,
                RegistryEntityType.KNOWLEDGE,
                str(raw["knowledge_id"]),
                RegistryHistoryAction.ADD,
                None,
                1,
                actor,
                now,
                {"registry_key": registry_key, "note": note},
            )
            created = True
            row = connection.execute(
                "SELECT * FROM knowledge_registry WHERE registry_key = ?",
                (registry_key,),
            ).fetchone()
        else:
            created = False
        if row is None:
            raise RegistryOperationError("Knowledge Registryの初期登録に失敗しました。")
        names = [canonical_name, *(str(item) for item in term.get("aliases", []))]
        self._ensure_aliases(connection, registry_key, names)
        return row, created

    def _ensure_aliases(
        self, connection: sqlite3.Connection, registry_key: str, names: list[str]
    ) -> None:
        for display in _unique(names):
            alias_key = _normalized(display)
            if alias_key == registry_key:
                continue
            existing = connection.execute(
                "SELECT target_key FROM knowledge_aliases WHERE alias_key = ?",
                (alias_key,),
            ).fetchone()
            if existing is not None and str(existing["target_key"]) != registry_key:
                raise RegistryOperationError(f"aliasが別Knowledgeへ登録済みです: {display}")
            connection.execute(
                """
                INSERT INTO knowledge_aliases(alias_key, alias_display, target_key)
                VALUES (?, ?, ?)
                ON CONFLICT(alias_key) DO UPDATE SET alias_display = excluded.alias_display
                """,
                (alias_key, display, registry_key),
            )

    def _canonicalize_merged_candidates(
        self,
        connection: sqlite3.Connection,
        candidates: list[ClaimCandidate],
    ) -> None:
        for candidate in candidates:
            row = self._claim_row_by_key(connection, candidate.claim_key)
            if row is None or RegistryStatus(str(row["status"])) != RegistryStatus.DEPRECATED:
                continue
            target_id = self._canonical_claim_id(connection, str(row["claim_id"]))
            if target_id is None:
                continue
            target = self._claim_row_by_id(connection, target_id)
            if target is not None:
                candidate.claim_key = str(target["claim_key"])

    def _canonical_claim_id(self, connection: sqlite3.Connection, claim_id: str) -> str | None:
        current = claim_id
        seen: set[str] = set()
        while True:
            if current in seen:
                raise RegistryOperationError(f"Claim統合の循環を検出しました: {claim_id}")
            seen.add(current)
            row = self._claim_row_by_id(connection, current)
            if row is None:
                return None
            redirect = connection.execute(
                "SELECT target_claim_id FROM claim_merge_redirects WHERE source_claim_id = ?",
                (current,),
            ).fetchone()
            if redirect is None:
                if (
                    bool(row["is_deleted"])
                    or RegistryStatus(str(row["status"])) == RegistryStatus.DEPRECATED
                ):
                    return None
                return current
            current = str(redirect["target_claim_id"])

    def _rewrite_stored_claim_references(
        self,
        connection: sqlite3.Connection,
        mappings: dict[str, str],
        actor: str,
        now: str,
    ) -> None:
        rows = connection.execute("SELECT * FROM claim_registry WHERE is_deleted = 0").fetchall()
        for row in rows:
            payload = _object(row["payload_json"])
            before = _json(payload)
            _rewrite_claim_references(payload, mappings)
            if _json(payload) == before:
                continue
            connection.execute(
                "UPDATE claim_registry SET payload_json = ?, updated_at = ? WHERE claim_id = ?",
                (_json(payload), now, str(row["claim_id"])),
            )
            version = int(row["claim_version"])
            self._history(
                connection,
                RegistryEntityType.CLAIM,
                str(row["claim_id"]),
                RegistryHistoryAction.UPDATE,
                version,
                version,
                actor,
                now,
                {"change_type": "merge_reference_rewrite"},
            )

    def _plan_claims(
        self,
        connection: sqlite3.Connection,
        candidates: list[ClaimCandidate],
        knowledge_id: str,
    ) -> tuple[dict[str, str], dict[str, sqlite3.Row | None]]:
        mappings: dict[str, str] = {}
        existing: dict[str, sqlite3.Row | None] = {}
        for candidate in candidates:
            row = self._claim_row_by_key(connection, candidate.claim_key)
            if row is not None and str(row["knowledge_id"]) != knowledge_id:
                raise RegistryOperationError(
                    f"claim_keyが別Knowledgeで使用されています: {candidate.claim_key}"
                )
            claim_id = (
                str(row["claim_id"])
                if row is not None
                else _claim_id(knowledge_id, candidate.claim_key)
            )
            for old_claim_id in candidate.old_claim_ids:
                mappings[old_claim_id] = claim_id
            existing[candidate.claim_key] = row
        return mappings, existing

    def _persist_candidates(
        self,
        connection: sqlite3.Connection,
        candidates: list[ClaimCandidate],
        existing: dict[str, sqlite3.Row | None],
        knowledge_id: str,
        actor: str,
        now: str,
        note: str,
    ) -> tuple[int, int]:
        new_count = 0
        updated_count = 0
        for candidate in candidates:
            row = existing[candidate.claim_key]
            if row is None:
                new_count += 1
                claim_id = str(candidate.payload["claim_id"])
                connection.execute(
                    """
                    INSERT INTO claim_registry(
                        claim_id, knowledge_id, claim_key, claim_version, field_path,
                        assertion, status, created_at, updated_at, aliases_json,
                        approval_json, payload_json, is_deleted
                    ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, '[]', ?, 0)
                    """,
                    (
                        claim_id,
                        knowledge_id,
                        candidate.claim_key,
                        candidate.field_path,
                        candidate.assertion,
                        RegistryStatus.DRAFT.value,
                        now,
                        now,
                        _json([candidate.assertion]),
                        _json(candidate.payload),
                    ),
                )
                self._history(
                    connection,
                    RegistryEntityType.CLAIM,
                    claim_id,
                    RegistryHistoryAction.ADD,
                    None,
                    1,
                    actor,
                    now,
                    {"claim_key": candidate.claim_key, "note": note},
                )
                continue
            status = RegistryStatus(str(row["status"]))
            stored_payload = _object(row["payload_json"])
            if status != RegistryStatus.DRAFT:
                candidate.container[candidate.index] = stored_payload
                continue
            payload_changed = _json(stored_payload) != _json(candidate.payload)
            assertion_changed = str(row["assertion"]) != candidate.assertion
            if not payload_changed and not assertion_changed:
                continue
            updated_count += 1
            aliases = _unique(
                [
                    *_string_list(row["aliases_json"]),
                    str(row["assertion"]),
                    candidate.assertion,
                ]
            )
            connection.execute(
                """
                UPDATE claim_registry
                SET assertion = ?, updated_at = ?, aliases_json = ?, payload_json = ?
                WHERE claim_key = ?
                """,
                (
                    candidate.assertion,
                    now,
                    _json(aliases),
                    _json(candidate.payload),
                    candidate.claim_key,
                ),
            )
            version = int(row["claim_version"])
            self._history(
                connection,
                RegistryEntityType.CLAIM,
                str(row["claim_id"]),
                RegistryHistoryAction.UPDATE,
                version,
                version,
                actor,
                now,
                {
                    "change_type": "expression_or_structure",
                    "claim_key": candidate.claim_key,
                    "note": note,
                },
            )
        return new_count, updated_count

    def _persist_record(
        self,
        connection: sqlite3.Connection,
        record: KnowledgeRecord,
        now: str,
    ) -> None:
        """Persist the validated document next to, but separate from, the ID ledger."""

        raw = record.model_dump(mode="json")
        connection.execute(
            """
            INSERT INTO knowledge_records(
                knowledge_id, schema_version, category_id, content_revision,
                record_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(knowledge_id) DO UPDATE SET
                schema_version = excluded.schema_version,
                category_id = excluded.category_id,
                content_revision = excluded.content_revision,
                record_json = excluded.record_json,
                updated_at = excluded.updated_at
            """,
            (
                record.knowledge_id,
                record.schema_version,
                record.classification.term_type,
                record.content_revision,
                _json(raw),
                now,
                now,
            ),
        )

    def _sync_stored_record_after_merge(
        self,
        connection: sqlite3.Connection,
        knowledge_id: str,
        mappings: dict[str, str],
        now: str,
    ) -> None:
        row = connection.execute(
            "SELECT record_json FROM knowledge_records WHERE knowledge_id = ?",
            (knowledge_id,),
        ).fetchone()
        if row is None:
            return
        raw = json.loads(str(row["record_json"]))
        _rewrite_record_merge(raw, mappings)
        raw["content_revision"] = self._knowledge_version(connection, knowledge_id)
        self._persist_record(connection, validate_knowledge_record(raw), now)

    def _replace_stored_claim_payload(
        self,
        connection: sqlite3.Connection,
        knowledge_id: str,
        claim_id: str,
        payload: dict[str, Any],
        now: str,
    ) -> None:
        row = connection.execute(
            "SELECT record_json FROM knowledge_records WHERE knowledge_id = ?",
            (knowledge_id,),
        ).fetchone()
        if row is None:
            return
        raw = json.loads(str(row["record_json"]))
        if not _replace_claim_payload(raw, claim_id, payload):
            raise RegistryOperationError(f"保存済みKnowledge JSON内にClaimがありません: {claim_id}")
        raw["content_revision"] = self._knowledge_version(connection, knowledge_id)
        self._persist_record(connection, validate_knowledge_record(raw), now)

    def _merge_registry_claims(
        self,
        connection: sqlite3.Connection,
        raw: dict[str, Any],
        candidates: list[ClaimCandidate],
        knowledge_id: str,
    ) -> None:
        incoming = {item.claim_key for item in candidates}
        rows = connection.execute(
            """
            SELECT * FROM claim_registry
            WHERE knowledge_id = ? AND is_deleted = 0 AND status != ?
            """,
            (knowledge_id, RegistryStatus.DEPRECATED.value),
        ).fetchall()
        for row in rows:
            if str(row["claim_key"]) in incoming:
                continue
            container = _list_at_path(raw, str(row["field_path"]))
            payload = _object(row["payload_json"])
            known_ids = {
                str(item.get("claim_id"))
                for item in container
                if isinstance(item, dict) and item.get("claim_id")
            }
            if str(row["claim_id"]) not in known_ids:
                container.append(payload)

    def _bump_knowledge_version(
        self,
        connection: sqlite3.Connection,
        knowledge_id: str,
        actor: str,
        now: str,
        reason: str,
    ) -> None:
        row = connection.execute(
            "SELECT knowledge_version FROM knowledge_registry WHERE knowledge_id = ?",
            (knowledge_id,),
        ).fetchone()
        if row is None:
            raise RegistryOperationError(f"knowledge_idが見つかりません: {knowledge_id}")
        old_version = int(row["knowledge_version"])
        new_version = old_version + 1
        connection.execute(
            """
            UPDATE knowledge_registry
            SET knowledge_version = ?, status = ?, updated_at = ?
            WHERE knowledge_id = ?
            """,
            (new_version, RegistryStatus.DRAFT.value, now, knowledge_id),
        )
        self._history(
            connection,
            RegistryEntityType.KNOWLEDGE,
            knowledge_id,
            RegistryHistoryAction.UPDATE,
            old_version,
            new_version,
            actor,
            now,
            {"reason": reason},
        )

    def _knowledge_version(self, connection: sqlite3.Connection, knowledge_id: str) -> int:
        row = connection.execute(
            "SELECT knowledge_version FROM knowledge_registry WHERE knowledge_id = ?",
            (knowledge_id,),
        ).fetchone()
        if row is None:
            raise RegistryOperationError(f"knowledge_idが見つかりません: {knowledge_id}")
        return int(row["knowledge_version"])

    def _snapshot(self, connection: sqlite3.Connection) -> RegistrySnapshot:
        alias_rows = connection.execute(
            "SELECT * FROM knowledge_aliases ORDER BY alias_key"
        ).fetchall()
        bindings = [
            RegistryAliasBinding(alias=str(row["alias_display"]), target=str(row["target_key"]))
            for row in alias_rows
        ]
        knowledge_rows = connection.execute(
            "SELECT * FROM knowledge_registry ORDER BY registry_key"
        ).fetchall()
        knowledge = [
            _knowledge_entry(row, _aliases_for_key(bindings, str(row["registry_key"])))
            for row in knowledge_rows
        ]
        claim_rows = connection.execute(
            "SELECT * FROM claim_registry ORDER BY claim_key"
        ).fetchall()
        claims = [_claim_entry(row) for row in claim_rows]
        redirect_rows = connection.execute(
            "SELECT * FROM claim_merge_redirects ORDER BY merged_at, source_claim_id"
        ).fetchall()
        merge_redirects = [_merge_redirect(row) for row in redirect_rows]
        history_rows = connection.execute(
            "SELECT * FROM registry_history ORDER BY occurred_at, event_id"
        ).fetchall()
        history = [_history_event(row) for row in history_rows]
        return validate_registry_snapshot(
            RegistrySnapshot(
                registry_version="1.0",
                knowledge=knowledge,
                claims=claims,
                alias_bindings=bindings,
                merge_redirects=merge_redirects,
                history=history,
            )
        )

    def _view_from_snapshot(
        self, snapshot: RegistrySnapshot, knowledge_id: str
    ) -> RegistryKnowledgeView:
        knowledge = next(
            (item for item in snapshot.knowledge if item.knowledge_id == knowledge_id),
            None,
        )
        if knowledge is None:
            raise RegistryOperationError(f"knowledge_idが見つかりません: {knowledge_id}")
        claims = [item for item in snapshot.claims if item.knowledge_id == knowledge_id]
        entity_ids = {knowledge_id, *(item.claim_id for item in claims)}
        history = [item for item in snapshot.history if item.entity_id in entity_ids]
        claim_ids = {item.claim_id for item in claims}
        merge_redirects = [
            item for item in snapshot.merge_redirects if item.source_claim_id in claim_ids
        ]
        return RegistryKnowledgeView(
            knowledge=knowledge,
            claims=claims,
            merge_redirects=merge_redirects,
            merge_candidates=_merge_candidates(claims),
            history=history,
            validation=registry_validation_report(snapshot),
        )

    def _claim_row_by_key(
        self, connection: sqlite3.Connection, claim_key: str
    ) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                "SELECT * FROM claim_registry WHERE claim_key = ?",
                (claim_key,),
            ).fetchone(),
        )

    def _claim_row_by_id(self, connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                "SELECT * FROM claim_registry WHERE claim_id = ?",
                (claim_id,),
            ).fetchone(),
        )

    def _history(
        self,
        connection: sqlite3.Connection,
        entity_type: RegistryEntityType,
        entity_id: str,
        action: RegistryHistoryAction,
        from_version: int | None,
        to_version: int | None,
        actor: str,
        occurred_at: str,
        details: dict[str, str],
    ) -> None:
        connection.execute(
            """
            INSERT INTO registry_history(
                event_id, entity_type, entity_id, action, from_version, to_version,
                occurred_at, actor, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"his_{uuid4().hex[:16]}",
                entity_type.value,
                entity_id,
                action.value,
                from_version,
                to_version,
                occurred_at,
                actor,
                _json(details),
            ),
        )

    def _require_all_claims_approved(
        self, connection: sqlite3.Connection, knowledge_id: str
    ) -> None:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count FROM claim_registry
            WHERE knowledge_id = ? AND is_deleted = 0 AND status NOT IN (?, ?)
            """,
            (
                knowledge_id,
                RegistryStatus.APPROVED.value,
                RegistryStatus.DEPRECATED.value,
            ),
        ).fetchone()
        if row is not None and int(row["count"]) > 0:
            raise RegistryOperationError(
                "Knowledgeをapprovedにする前に全Claimの医学レビューが必要です。"
            )

    def _set_claim_lifecycle(
        self,
        claim_key: str,
        actor: str,
        note: str,
        action: RegistryHistoryAction,
        *,
        deleted: bool,
    ) -> None:
        now = _now()
        with self._connect() as connection:
            row = self._claim_row_by_key(connection, claim_key)
            if row is None:
                raise RegistryOperationError(f"claim_keyが見つかりません: {claim_key}")
            if deleted and RegistryStatus(str(row["status"])) != RegistryStatus.DEPRECATED:
                raise RegistryOperationError(
                    "Claimを削除扱いにする前にdeprecatedへ変更してください。"
                )
            connection.execute(
                """
                UPDATE claim_registry
                SET status = ?, is_deleted = ?, updated_at = ?
                WHERE claim_key = ?
                """,
                (
                    RegistryStatus.DEPRECATED.value,
                    1 if deleted else int(row["is_deleted"]),
                    now,
                    claim_key,
                ),
            )
            version = int(row["claim_version"])
            self._history(
                connection,
                RegistryEntityType.CLAIM,
                str(row["claim_id"]),
                action,
                version,
                version,
                actor,
                now,
                {"claim_key": claim_key, "note": note},
            )
            self._snapshot(connection)


def _knowledge_entry(row: sqlite3.Row, aliases: list[str]) -> KnowledgeRegistryEntry:
    return KnowledgeRegistryEntry(
        knowledge_id=str(row["knowledge_id"]),
        registry_key=str(row["registry_key"]),
        canonical_name=str(row["canonical_name"]),
        knowledge_version=int(row["knowledge_version"]),
        status=RegistryStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        aliases=aliases,
        approval=_approval_list(row["approval_json"]),
    )


def _claim_entry(row: sqlite3.Row) -> ClaimRegistryEntry:
    return ClaimRegistryEntry(
        knowledge_id=str(row["knowledge_id"]),
        claim_id=str(row["claim_id"]),
        claim_key=str(row["claim_key"]),
        claim_version=int(row["claim_version"]),
        field_path=str(row["field_path"]),
        assertion=str(row["assertion"]),
        status=RegistryStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        aliases=_string_list(row["aliases_json"]),
        approval=_approval_list(row["approval_json"]),
        fact_payload=_object(row["payload_json"]),
        is_deleted=bool(row["is_deleted"]),
    )


def _merge_redirect(row: sqlite3.Row) -> ClaimMergeRedirect:
    return ClaimMergeRedirect(
        source_claim_id=str(row["source_claim_id"]),
        source_claim_key=str(row["source_claim_key"]),
        target_claim_id=str(row["target_claim_id"]),
        target_claim_key=str(row["target_claim_key"]),
        merged_at=datetime.fromisoformat(str(row["merged_at"])),
        actor=str(row["actor"]),
        comment=str(row["comment"]),
    )


def _merge_candidates(claims: list[ClaimRegistryEntry]) -> list[ClaimMergeCandidate]:
    active = [
        item for item in claims if not item.is_deleted and item.status != RegistryStatus.DEPRECATED
    ]
    candidates: list[ClaimMergeCandidate] = []
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if left.field_path != right.field_path:
                continue
            score = round(
                SequenceMatcher(
                    None,
                    _normalized(left.assertion),
                    _normalized(right.assertion),
                ).ratio()
                * 100
            )
            if score < 45:
                continue
            target, source = sorted(
                (left, right),
                key=lambda item: (item.created_at, item.claim_key),
            )
            candidates.append(
                ClaimMergeCandidate(
                    source_claim_id=source.claim_id,
                    source_claim_key=source.claim_key,
                    target_claim_id=target.claim_id,
                    target_claim_key=target.claim_key,
                    similarity_score=score,
                    reason="同じ保存項目内で文章が類似",
                )
            )
    return sorted(
        candidates,
        key=lambda item: (-item.similarity_score, item.source_claim_key),
    )[:30]


def _history_event(row: sqlite3.Row) -> RegistryHistoryEvent:
    return RegistryHistoryEvent(
        event_id=str(row["event_id"]),
        entity_type=RegistryEntityType(str(row["entity_type"])),
        entity_id=str(row["entity_id"]),
        action=RegistryHistoryAction(str(row["action"])),
        from_version=(int(row["from_version"]) if row["from_version"] is not None else None),
        to_version=int(row["to_version"]) if row["to_version"] is not None else None,
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        actor=str(row["actor"]),
        details=_string_dict(row["details_json"]),
    )


def _rewrite_knowledge_id(raw: object, old_id: str, new_id: str) -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if (
                key in {"knowledge_id", "related_knowledge_id", "disease_knowledge_id"}
                and value == old_id
            ):
                raw[key] = new_id
            else:
                _rewrite_knowledge_id(value, old_id, new_id)
    elif isinstance(raw, list):
        for value in raw:
            _rewrite_knowledge_id(value, old_id, new_id)


def _rewrite_claim_ids(raw: object, mappings: dict[str, str]) -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "claim_id" and isinstance(value, str):
                raw[key] = mappings.get(value, value)
            elif key.endswith("_claim_ids") and isinstance(value, list):
                raw[key] = [
                    mappings.get(item, item) if isinstance(item, str) else item for item in value
                ]
            else:
                _rewrite_claim_ids(value, mappings)
    elif isinstance(raw, list):
        for value in raw:
            _rewrite_claim_ids(value, mappings)


def _rewrite_claim_references(raw: object, mappings: dict[str, str]) -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key.endswith("_claim_ids") and isinstance(value, list):
                raw[key] = list(
                    dict.fromkeys(
                        mappings.get(item, item) if isinstance(item, str) else item
                        for item in value
                    )
                )
            else:
                _rewrite_claim_references(value, mappings)
    elif isinstance(raw, list):
        for value in raw:
            _rewrite_claim_references(value, mappings)


def _rewrite_record_merge(raw: object, mappings: dict[str, str]) -> None:
    """Remove merged source facts and redirect every stored claim reference."""

    if isinstance(raw, dict):
        for key, value in raw.items():
            if key.endswith("_claim_ids") and isinstance(value, list):
                raw[key] = list(
                    dict.fromkeys(
                        mappings.get(item, item) if isinstance(item, str) else item
                        for item in value
                    )
                )
            else:
                _rewrite_record_merge(value, mappings)
    elif isinstance(raw, list):
        retained: list[object] = []
        for value in raw:
            if (
                isinstance(value, dict)
                and isinstance(value.get("claim_id"), str)
                and value["claim_id"] in mappings
            ):
                continue
            _rewrite_record_merge(value, mappings)
            retained.append(value)
        raw[:] = retained


def _replace_claim_payload(
    raw: object,
    claim_id: str,
    payload: dict[str, Any],
) -> bool:
    if isinstance(raw, dict):
        if raw.get("claim_id") == claim_id:
            raw.clear()
            raw.update(payload)
            return True
        return any(_replace_claim_payload(value, claim_id, payload) for value in raw.values())
    if isinstance(raw, list):
        return any(_replace_claim_payload(value, claim_id, payload) for value in raw)
    return False


def _list_at_path(raw: dict[str, Any], path: str) -> list[object]:
    current: object = raw
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise RegistryOperationError(f"保存済みClaimのfield_pathが不正です: {path}")
        current = current[part]
    if not isinstance(current, list):
        raise RegistryOperationError(f"保存済みClaimのfield_pathが配列ではありません: {path}")
    return current


def _claim_id(knowledge_id: str, claim_key: str) -> str:
    seed = f"{knowledge_id}:{claim_key}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"clm_{digest}"


def _entity_columns(entity_type: RegistryEntityType) -> tuple[str, str, str]:
    if entity_type == RegistryEntityType.KNOWLEDGE:
        return "knowledge_registry", "knowledge_id", "knowledge_version"
    return "claim_registry", "claim_id", "claim_version"


def _require_transition(current: RegistryStatus, target: RegistryStatus) -> None:
    if not approval_transition_is_allowed(current, target):
        raise RegistryOperationError(
            f"Registry statusを{current.value}から{target.value}へ変更できません。"
        )


def _aliases_for_key(bindings: list[RegistryAliasBinding], registry_key: str) -> list[str]:
    return _unique([item.alias for item in bindings if _normalized(item.target) == registry_key])


def _resolve_alias(snapshot: RegistrySnapshot, alias: str) -> str:
    canonical = {_normalized(item.registry_key) for item in snapshot.knowledge}
    bindings = {
        _normalized(item.alias): _normalized(item.target) for item in snapshot.alias_bindings
    }
    current = _normalized(alias)
    seen: set[str] = set()
    while current not in canonical:
        if current in seen or current not in bindings:
            raise RegistryOperationError(f"aliasを解決できません: {alias}")
        seen.add(current)
        current = bindings[current]
    return current


def _approval_list(value: object) -> list[ApprovalDecision]:
    raw = _list(value)
    return [ApprovalDecision.model_validate(item) for item in raw]


def _string_list(value: object) -> list[str]:
    return [str(item) for item in _list(value)]


def _string_dict(value: object) -> dict[str, str]:
    return {str(key): str(item) for key, item in _object(value).items()}


def _list(value: object) -> list[object]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError("stored JSON must be a list")
    return cast(list[object], parsed)


def _object(value: object) -> dict[str, Any]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise ValueError("stored JSON must be an object")
    return cast(dict[str, Any], parsed)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _normalized(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def _now() -> str:
    return datetime.now(UTC).isoformat()
