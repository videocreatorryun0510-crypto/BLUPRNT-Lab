"""Persistent SQLite Presentation Artifact Registry."""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from presentation_artifact import (
    PresentationArtifact,
    artifact_fingerprint,
)

from presentation_artifact_registry.diff import compare_artifacts
from presentation_artifact_registry.errors import (
    ArtifactApprovalError,
    ArtifactImmutableError,
    ArtifactNotFoundError,
    ArtifactRegistryError,
)
from presentation_artifact_registry.models import (
    ArtifactApprovalState,
    ArtifactDiffReport,
    ArtifactHistoryEvent,
    ArtifactHistoryEventType,
    ArtifactRegistryEntry,
    ArtifactRegistrySnapshot,
    ArtifactRegistryStatus,
    ArtifactRegistryValidationReport,
    ArtifactRegistryView,
    ArtifactVersionRecord,
    RegistryValidationIssue,
)

_APPROVAL_ORDER = (
    ArtifactApprovalState.DRAFT,
    ArtifactApprovalState.OWNER_REVIEW,
    ArtifactApprovalState.EDUCATION_REVIEW,
    ArtifactApprovalState.APPROVED,
    ArtifactApprovalState.PUBLISHED,
)


class SQLitePresentationArtifactRegistry:
    """Append-only Artifact versions with an independent approval ledger."""

    registry_version = "1.0"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def register(
        self,
        artifact: PresentationArtifact,
        *,
        owner: str,
        actor: str,
        review_comment: str,
        expected_knowledge_version: int,
        registered_at: datetime | None = None,
    ) -> ArtifactVersionRecord:
        validated = PresentationArtifact.model_validate(
            artifact.model_dump(mode="json")
        )
        if validated.source.knowledge_version != expected_knowledge_version:
            raise ArtifactRegistryError(
                "ArtifactのKnowledge Versionが現在のRegistryと一致しません。"
            )
        timestamp = registered_at or datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            series = connection.execute(
                """
                SELECT artifact_id, current_version, status
                FROM artifact_series
                WHERE knowledge_id = ? AND profile_id = ?
                """,
                (
                    validated.source.knowledge_id,
                    validated.presentation_profile.profile_id,
                ),
            ).fetchone()
            if series is None:
                artifact_id = validated.identity.artifact_id
                artifact_version = 1
                created_at = timestamp
            else:
                if series["status"] == ArtifactRegistryStatus.DEPRECATED.value:
                    raise ArtifactRegistryError(
                        "deprecatedのArtifact Seriesへ新Versionは追加できません。"
                    )
                artifact_id = str(series["artifact_id"])
                artifact_version = int(series["current_version"]) + 1
                created_at = timestamp
            canonical = _with_registry_identity(
                validated,
                artifact_id,
                artifact_version,
                timestamp,
            )
            duplicate = connection.execute(
                "SELECT artifact_id, artifact_version FROM artifact_versions WHERE fingerprint = ?",
                (canonical.metadata.fingerprint,),
            ).fetchone()
            if duplicate is not None:
                raise ArtifactRegistryError(
                    "同じFingerprintのArtifact Versionは登録できません。"
                )
            if series is None:
                connection.execute(
                    """
                    INSERT INTO artifact_series (
                        artifact_id, knowledge_id, profile_id, current_version,
                        owner, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        canonical.source.knowledge_id,
                        canonical.presentation_profile.profile_id,
                        artifact_version,
                        owner,
                        ArtifactRegistryStatus.ACTIVE.value,
                        _iso(timestamp),
                        _iso(timestamp),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE artifact_series
                    SET current_version = ?, owner = ?, updated_at = ?
                    WHERE artifact_id = ?
                    """,
                    (artifact_version, owner, _iso(timestamp), artifact_id),
                )
            connection.execute(
                """
                INSERT INTO artifact_versions (
                    artifact_id, artifact_version, source_bundle_id,
                    presentation_request_id, knowledge_id, knowledge_version,
                    profile_id, profile_version, fingerprint, approval_state,
                    created_at, updated_at, owner, review_comment, status,
                    immutable, artifact_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    artifact_version,
                    canonical.identity.source_bundle_id,
                    canonical.identity.request_id,
                    canonical.source.knowledge_id,
                    canonical.source.knowledge_version,
                    canonical.presentation_profile.profile_id,
                    canonical.presentation_profile.profile_version,
                    canonical.metadata.fingerprint,
                    ArtifactApprovalState.DRAFT.value,
                    _iso(created_at),
                    _iso(timestamp),
                    owner,
                    review_comment,
                    ArtifactRegistryStatus.ACTIVE.value,
                    0,
                    canonical.model_dump_json(),
                ),
            )
            self._insert_history(
                connection,
                artifact_id=artifact_id,
                artifact_version=artifact_version,
                event_type=ArtifactHistoryEventType.VERSION_CREATED,
                changed_at=timestamp,
                changed_by=actor,
                review_comment=review_comment,
                fingerprint=canonical.metadata.fingerprint,
                from_state=None,
                to_state=ArtifactApprovalState.DRAFT,
            )
        return self.version(artifact_id, artifact_version)

    def transition_approval(
        self,
        artifact_id: str,
        artifact_version: int,
        target_state: ArtifactApprovalState,
        *,
        actor: str,
        review_comment: str,
        changed_at: datetime | None = None,
    ) -> ArtifactVersionRecord:
        timestamp = changed_at or datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._version_row(connection, artifact_id, artifact_version)
            current = ArtifactApprovalState(row["approval_state"])
            _validate_transition(current, target_state)
            immutable = bool(row["immutable"]) or target_state in {
                ArtifactApprovalState.APPROVED,
                ArtifactApprovalState.PUBLISHED,
            }
            connection.execute(
                """
                UPDATE artifact_versions
                SET approval_state = ?, updated_at = ?, review_comment = ?, immutable = ?
                WHERE artifact_id = ? AND artifact_version = ?
                """,
                (
                    target_state.value,
                    _iso(timestamp),
                    review_comment,
                    int(immutable),
                    artifact_id,
                    artifact_version,
                ),
            )
            connection.execute(
                "UPDATE artifact_series SET updated_at = ? WHERE artifact_id = ?",
                (_iso(timestamp), artifact_id),
            )
            self._insert_history(
                connection,
                artifact_id=artifact_id,
                artifact_version=artifact_version,
                event_type=ArtifactHistoryEventType.APPROVAL_TRANSITION,
                changed_at=timestamp,
                changed_by=actor,
                review_comment=review_comment,
                fingerprint=str(row["fingerprint"]),
                from_state=current,
                to_state=target_state,
            )
        return self.version(artifact_id, artifact_version)

    def list_artifacts(self) -> ArtifactRegistrySnapshot:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT versions.*
                FROM artifact_series AS series
                JOIN artifact_versions AS versions
                  ON versions.artifact_id = series.artifact_id
                 AND versions.artifact_version = series.current_version
                ORDER BY series.updated_at DESC, series.artifact_id
                """
            ).fetchall()
        return ArtifactRegistrySnapshot(
            artifacts=tuple(_entry_from_row(row) for row in rows)
        )

    def view(self, artifact_id: str) -> ArtifactRegistryView:
        with self._connect() as connection:
            series = connection.execute(
                "SELECT current_version FROM artifact_series WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if series is None:
                raise ArtifactNotFoundError(f"Artifactが見つかりません: {artifact_id}")
            rows = connection.execute(
                """
                SELECT * FROM artifact_versions
                WHERE artifact_id = ? ORDER BY artifact_version DESC
                """,
                (artifact_id,),
            ).fetchall()
            history_rows = connection.execute(
                """
                SELECT * FROM artifact_history
                WHERE artifact_id = ? ORDER BY history_id DESC
                """,
                (artifact_id,),
            ).fetchall()
        entries = tuple(_entry_from_row(row) for row in rows)
        current_version = int(series["current_version"])
        current = next(
            item for item in entries if item.artifact_version == current_version
        )
        return ArtifactRegistryView(
            current=current,
            versions=entries,
            history=tuple(_history_from_row(row) for row in history_rows),
        )

    def version(self, artifact_id: str, artifact_version: int) -> ArtifactVersionRecord:
        with self._connect() as connection:
            row = self._version_row(connection, artifact_id, artifact_version)
        return ArtifactVersionRecord(
            entry=_entry_from_row(row),
            artifact=PresentationArtifact.model_validate_json(row["artifact_json"]),
        )

    def diff(
        self,
        artifact_id: str,
        from_version: int,
        to_version: int,
    ) -> ArtifactDiffReport:
        before = self.version(artifact_id, from_version).artifact
        after = self.version(artifact_id, to_version).artifact
        return compare_artifacts(before, after)

    def get_approved_for_render(
        self,
        artifact_id: str,
        *,
        artifact_version: int | None = None,
    ) -> PresentationArtifact:
        with self._connect() as connection:
            if artifact_version is None:
                row = connection.execute(
                    """
                    SELECT * FROM artifact_versions
                    WHERE artifact_id = ? AND approval_state = ? AND status = ?
                    ORDER BY artifact_version DESC LIMIT 1
                    """,
                    (
                        artifact_id,
                        ArtifactApprovalState.APPROVED.value,
                        ArtifactRegistryStatus.ACTIVE.value,
                    ),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM artifact_versions
                    WHERE artifact_id = ? AND artifact_version = ?
                    """,
                    (artifact_id, artifact_version),
                ).fetchone()
            if row is None:
                raise ArtifactApprovalError(
                    "Rendererが利用できるapproved Artifactがありません。"
                )
            if (
                row["approval_state"] != ArtifactApprovalState.APPROVED.value
                or row["status"] != ArtifactRegistryStatus.ACTIVE.value
            ):
                raise ArtifactApprovalError(
                    "RendererはactiveかつapprovedのArtifactだけ利用できます。"
                )
            artifact = PresentationArtifact.model_validate_json(row["artifact_json"])
            if (
                artifact.metadata.fingerprint != row["fingerprint"]
                or artifact_fingerprint(artifact) != row["fingerprint"]
            ):
                raise ArtifactImmutableError(
                    "approved ArtifactのFingerprint整合性が失われています。"
                )
            return artifact

    def validate(
        self,
        current_knowledge_versions: Mapping[str, int] | None = None,
    ) -> ArtifactRegistryValidationReport:
        issues: list[RegistryValidationIssue] = []
        with self._connect() as connection:
            series_rows = connection.execute(
                "SELECT * FROM artifact_series ORDER BY artifact_id"
            ).fetchall()
            fingerprint_duplicates = connection.execute(
                """
                SELECT fingerprint, COUNT(*) AS count
                FROM artifact_versions GROUP BY fingerprint HAVING COUNT(*) > 1
                """
            ).fetchall()
            for duplicate in fingerprint_duplicates:
                issues.append(
                    RegistryValidationIssue(
                        code="fingerprint_duplicate",
                        artifact_id=None,
                        artifact_version=None,
                        message=f"Fingerprintが重複しています: {duplicate['fingerprint']}",
                    )
                )
            for series in series_rows:
                artifact_id = str(series["artifact_id"])
                versions = connection.execute(
                    """
                    SELECT * FROM artifact_versions
                    WHERE artifact_id = ? ORDER BY artifact_version
                    """,
                    (artifact_id,),
                ).fetchall()
                numbers = [int(row["artifact_version"]) for row in versions]
                if numbers != list(range(1, len(numbers) + 1)):
                    issues.append(
                        _validation_issue(
                            "version_sequence_invalid",
                            artifact_id,
                            None,
                            "Artifact Versionが1から連続していません。",
                        )
                    )
                if not numbers or int(series["current_version"]) != max(numbers):
                    issues.append(
                        _validation_issue(
                            "current_version_mismatch",
                            artifact_id,
                            None,
                            "Seriesのcurrent_versionが最新版と一致しません。",
                        )
                    )
                for row in versions:
                    self._validate_version_row(
                        connection,
                        row,
                        issues,
                        current_knowledge_versions,
                    )
        return ArtifactRegistryValidationReport(
            is_valid=not issues,
            issues=tuple(issues),
        )

    def _validate_version_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        issues: list[RegistryValidationIssue],
        current_knowledge_versions: Mapping[str, int] | None,
    ) -> None:
        artifact_id = str(row["artifact_id"])
        version = int(row["artifact_version"])
        try:
            artifact = PresentationArtifact.model_validate_json(row["artifact_json"])
        except ValueError as error:
            issues.append(
                _validation_issue(
                    "artifact_json_invalid",
                    artifact_id,
                    version,
                    f"Artifact JSONを検証できません: {error}",
                )
            )
            return
        if (
            artifact.identity.artifact_id != artifact_id
            or artifact.identity.artifact_version != version
            or artifact.metadata.artifact_version != version
        ):
            issues.append(
                _validation_issue(
                    "artifact_identity_mismatch",
                    artifact_id,
                    version,
                    "Artifact IDまたはVersionがRegistry行と一致しません。",
                )
            )
        if (
            artifact.metadata.fingerprint != row["fingerprint"]
            or artifact_fingerprint(artifact) != row["fingerprint"]
        ):
            issues.append(
                _validation_issue(
                    "fingerprint_mismatch",
                    artifact_id,
                    version,
                    "Artifact FingerprintがRegistryと一致しません。",
                )
            )
        if (
            row["approval_state"]
            in {
                ArtifactApprovalState.APPROVED.value,
                ArtifactApprovalState.PUBLISHED.value,
            }
            and not bool(row["immutable"])
        ):
            issues.append(
                _validation_issue(
                    "approved_artifact_not_immutable",
                    artifact_id,
                    version,
                    "approved ArtifactがImmutableになっていません。",
                )
            )
        history_rows = connection.execute(
            """
            SELECT * FROM artifact_history
            WHERE artifact_id = ? AND artifact_version = ?
            ORDER BY history_id
            """,
            (artifact_id, version),
        ).fetchall()
        if not history_rows:
            issues.append(
                _validation_issue(
                    "history_missing",
                    artifact_id,
                    version,
                    "Artifact VersionのHistoryがありません。",
                )
            )
        else:
            self._validate_history_rows(row, history_rows, issues)
        if current_knowledge_versions is not None:
            current = current_knowledge_versions.get(artifact.source.knowledge_id)
            if current is None or artifact.source.knowledge_version > current:
                issues.append(
                    _validation_issue(
                        "knowledge_version_inconsistent",
                        artifact_id,
                        version,
                        "Artifactが存在しない将来のKnowledge Versionを参照しています。",
                    )
                )

    @staticmethod
    def _validate_history_rows(
        version_row: sqlite3.Row,
        history_rows: list[sqlite3.Row],
        issues: list[RegistryValidationIssue],
    ) -> None:
        artifact_id = str(version_row["artifact_id"])
        version = int(version_row["artifact_version"])
        first = history_rows[0]
        valid = (
            first["event_type"] == ArtifactHistoryEventType.VERSION_CREATED.value
            and first["from_approval_state"] is None
            and first["to_approval_state"] == ArtifactApprovalState.DRAFT.value
        )
        current = ArtifactApprovalState.DRAFT
        for event in history_rows[1:]:
            if event["event_type"] != ArtifactHistoryEventType.APPROVAL_TRANSITION.value:
                continue
            from_state = ArtifactApprovalState(event["from_approval_state"])
            to_state = ArtifactApprovalState(event["to_approval_state"])
            if from_state != current or not _transition_allowed(from_state, to_state):
                valid = False
            current = to_state
        if current.value != version_row["approval_state"]:
            valid = False
        if any(event["fingerprint"] != version_row["fingerprint"] for event in history_rows):
            valid = False
        if not valid:
            issues.append(
                _validation_issue(
                    "history_inconsistent",
                    artifact_id,
                    version,
                    "History、Approval遷移、Fingerprintが現在状態と整合しません。",
                )
            )

    @staticmethod
    def _insert_history(
        connection: sqlite3.Connection,
        *,
        artifact_id: str,
        artifact_version: int,
        event_type: ArtifactHistoryEventType,
        changed_at: datetime,
        changed_by: str,
        review_comment: str,
        fingerprint: str,
        from_state: ArtifactApprovalState | None,
        to_state: ArtifactApprovalState,
    ) -> None:
        connection.execute(
            """
            INSERT INTO artifact_history (
                artifact_id, artifact_version, event_type, changed_at,
                changed_by, review_comment, fingerprint,
                from_approval_state, to_approval_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                artifact_version,
                event_type.value,
                _iso(changed_at),
                changed_by,
                review_comment,
                fingerprint,
                from_state.value if from_state is not None else None,
                to_state.value,
            ),
        )

    @staticmethod
    def _version_row(
        connection: sqlite3.Connection,
        artifact_id: str,
        artifact_version: int,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM artifact_versions
            WHERE artifact_id = ? AND artifact_version = ?
            """,
            (artifact_id, artifact_version),
        ).fetchone()
        if row is None:
            raise ArtifactNotFoundError(
                f"Artifact Versionが見つかりません: {artifact_id} v{artifact_version}"
            )
        return cast(sqlite3.Row, row)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifact_series (
                    artifact_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    current_version INTEGER NOT NULL CHECK (current_version >= 1),
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'deprecated')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (knowledge_id, profile_id)
                );

                CREATE TABLE IF NOT EXISTS artifact_versions (
                    artifact_id TEXT NOT NULL,
                    artifact_version INTEGER NOT NULL CHECK (artifact_version >= 1),
                    source_bundle_id TEXT NOT NULL,
                    presentation_request_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    knowledge_version INTEGER NOT NULL CHECK (knowledge_version >= 1),
                    profile_id TEXT NOT NULL,
                    profile_version TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    approval_state TEXT NOT NULL CHECK (
                        approval_state IN (
                            'draft', 'owner_review', 'education_review',
                            'approved', 'published'
                        )
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    review_comment TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK (status IN ('active', 'deprecated')),
                    immutable INTEGER NOT NULL DEFAULT 0 CHECK (immutable IN (0, 1)),
                    artifact_json TEXT NOT NULL,
                    PRIMARY KEY (artifact_id, artifact_version),
                    FOREIGN KEY (artifact_id) REFERENCES artifact_series(artifact_id)
                );

                CREATE TABLE IF NOT EXISTS artifact_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    artifact_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL CHECK (
                        event_type IN (
                            'version_created', 'approval_transition', 'deprecated'
                        )
                    ),
                    changed_at TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    review_comment TEXT NOT NULL DEFAULT '',
                    fingerprint TEXT NOT NULL,
                    from_approval_state TEXT,
                    to_approval_state TEXT NOT NULL,
                    FOREIGN KEY (artifact_id, artifact_version)
                        REFERENCES artifact_versions(artifact_id, artifact_version)
                );

                CREATE INDEX IF NOT EXISTS idx_artifact_versions_approval
                    ON artifact_versions(artifact_id, approval_state, artifact_version);
                CREATE INDEX IF NOT EXISTS idx_artifact_history_lookup
                    ON artifact_history(artifact_id, artifact_version, history_id);

                CREATE TRIGGER IF NOT EXISTS prevent_approved_artifact_content_update
                BEFORE UPDATE OF
                    artifact_json, fingerprint, source_bundle_id,
                    presentation_request_id, knowledge_id, knowledge_version,
                    profile_id, profile_version
                ON artifact_versions
                WHEN OLD.immutable = 1
                BEGIN
                    SELECT RAISE(ABORT, 'approved artifact content is immutable');
                END;
                """
            )


def _with_registry_identity(
    artifact: PresentationArtifact,
    artifact_id: str,
    artifact_version: int,
    created_at: datetime,
) -> PresentationArtifact:
    identity = artifact.identity.model_copy(
        update={
            "artifact_id": artifact_id,
            "artifact_version": artifact_version,
        }
    )
    metadata = artifact.metadata.model_copy(
        update={
            "fingerprint": "0" * 64,
            "created_at": created_at,
            "artifact_version": artifact_version,
        }
    )
    unsigned = artifact.model_copy(
        update={"identity": identity, "metadata": metadata}
    )
    return unsigned.model_copy(
        update={
            "metadata": metadata.model_copy(
                update={"fingerprint": artifact_fingerprint(unsigned)}
            )
        }
    )


def _entry_from_row(row: sqlite3.Row) -> ArtifactRegistryEntry:
    return ArtifactRegistryEntry(
        artifact_id=row["artifact_id"],
        artifact_version=row["artifact_version"],
        source_bundle_id=row["source_bundle_id"],
        presentation_request_id=row["presentation_request_id"],
        knowledge_id=row["knowledge_id"],
        knowledge_version=row["knowledge_version"],
        profile_id=row["profile_id"],
        profile_version=row["profile_version"],
        fingerprint=row["fingerprint"],
        approval_state=ArtifactApprovalState(row["approval_state"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        owner=row["owner"],
        review_comment=row["review_comment"],
        status=ArtifactRegistryStatus(row["status"]),
        immutable=bool(row["immutable"]),
    )


def _history_from_row(row: sqlite3.Row) -> ArtifactHistoryEvent:
    from_state = row["from_approval_state"]
    return ArtifactHistoryEvent(
        history_id=row["history_id"],
        artifact_id=row["artifact_id"],
        artifact_version=row["artifact_version"],
        event_type=ArtifactHistoryEventType(row["event_type"]),
        changed_at=datetime.fromisoformat(row["changed_at"]),
        changed_by=row["changed_by"],
        review_comment=row["review_comment"],
        fingerprint=row["fingerprint"],
        from_approval_state=(
            ArtifactApprovalState(from_state) if from_state is not None else None
        ),
        to_approval_state=ArtifactApprovalState(row["to_approval_state"]),
    )


def _validate_transition(
    current: ArtifactApprovalState,
    target: ArtifactApprovalState,
) -> None:
    if current == target:
        raise ArtifactApprovalError("同じApproval Stateへは変更できません。")
    if not _transition_allowed(current, target):
        raise ArtifactApprovalError(
            "Approval Stateは前方へ1段階ずつ進めてください。"
        )


def _transition_allowed(
    current: ArtifactApprovalState,
    target: ArtifactApprovalState,
) -> bool:
    if current == target:
        return False
    current_index = _APPROVAL_ORDER.index(current)
    target_index = _APPROVAL_ORDER.index(target)
    return target_index <= current_index + 1


def _validation_issue(
    code: str,
    artifact_id: str | None,
    artifact_version: int | None,
    message: str,
) -> RegistryValidationIssue:
    return RegistryValidationIssue(
        code=code,
        artifact_id=artifact_id,
        artifact_version=artifact_version,
        message=message,
    )


def _iso(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat()
