"""Persistent SQLite Presentation Artifact Registry."""

import json
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
from presentation_artifact_registry.eligibility import (
    KnowledgeArtifactSourceSnapshot,
    RendererEligibility,
    evaluate_renderer_eligibility,
)
from presentation_artifact_registry.errors import (
    ArtifactApprovalError,
    ArtifactNotFoundError,
    ArtifactRegistryError,
)
from presentation_artifact_registry.models import (
    ArtifactApprovalState,
    ArtifactDiffReport,
    ArtifactGateAuditRecord,
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
        source_review_version: int | None = None,
        source_claim_versions: Mapping[str, int] | None = None,
        registered_at: datetime | None = None,
    ) -> ArtifactVersionRecord:
        validated = PresentationArtifact.model_validate(artifact.model_dump(mode="json"))
        if validated.source.knowledge_version != expected_knowledge_version:
            raise ArtifactRegistryError(
                "ArtifactのKnowledge Versionが現在のRegistryと一致しません。"
            )
        timestamp = registered_at or datetime.now(UTC)
        review_version = source_review_version or expected_knowledge_version
        artifact_claim_ids = {item.claim_id for item in validated.claim_catalog}
        claim_versions = dict(source_claim_versions or {})
        if set(claim_versions) != artifact_claim_ids or any(
            value < 1 for value in claim_versions.values()
        ):
            raise ArtifactRegistryError(
                "Artifact登録には全参照Claimの現在Versionが必要です。"
            )
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
                raise ArtifactRegistryError("同じFingerprintのArtifact Versionは登録できません。")
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
                    source_review_version, source_claim_versions_json,
                    profile_id, profile_version,
                    fingerprint, approval_state,
                    created_at, updated_at, owner, review_comment, status,
                    immutable, artifact_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    artifact_version,
                    canonical.identity.source_bundle_id,
                    canonical.identity.request_id,
                    canonical.source.knowledge_id,
                    canonical.source.knowledge_version,
                    review_version,
                    json.dumps(claim_versions, ensure_ascii=False, sort_keys=True),
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
        source_snapshot: KnowledgeArtifactSourceSnapshot | None = None,
        changed_at: datetime | None = None,
    ) -> ArtifactVersionRecord:
        timestamp = changed_at or datetime.now(UTC)
        rejection: RendererEligibility | None = None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._version_row(connection, artifact_id, artifact_version)
            current = ArtifactApprovalState(row["approval_state"])
            _validate_transition(current, target_state)
            if target_state in {
                ArtifactApprovalState.APPROVED,
                ArtifactApprovalState.PUBLISHED,
            }:
                if source_snapshot is None:
                    raise ArtifactApprovalError(
                        "Artifact承認には現在のKnowledge承認情報が必要です。",
                        reason_codes=("knowledge_approval_context_required",),
                    )
                record = _version_record_from_row(row)
                rejection = evaluate_renderer_eligibility(
                    record.entry,
                    record.artifact,
                    source_snapshot,
                    artifact_approved_at=timestamp,
                    evaluated_at=timestamp,
                    approval_state_override=ArtifactApprovalState.APPROVED,
                )
                if not rejection.eligible:
                    self._insert_gate_audit(
                        connection,
                        artifact_id=artifact_id,
                        artifact_version=artifact_version,
                        action="approval_transition",
                        outcome="blocked",
                        reason_codes=rejection.reasons,
                        evaluated_at=timestamp,
                        actor=actor,
                        review_comment=review_comment,
                    )
            if rejection is None or rejection.eligible:
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
                self._insert_gate_audit(
                    connection,
                    artifact_id=artifact_id,
                    artifact_version=artifact_version,
                    action="approval_transition",
                    outcome="allowed",
                    reason_codes=(),
                    evaluated_at=timestamp,
                    actor=actor,
                    review_comment=review_comment,
                )
        if rejection is not None and not rejection.eligible:
            raise ArtifactApprovalError(
                "Artifact承認を停止しました: " + ", ".join(rejection.reasons),
                reason_codes=rejection.reasons,
                eligibility=rejection,
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
        return ArtifactRegistrySnapshot(artifacts=tuple(_entry_from_row(row) for row in rows))

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
            audit_rows = connection.execute(
                """
                SELECT * FROM artifact_gate_audit
                WHERE artifact_id = ? ORDER BY audit_id DESC
                """,
                (artifact_id,),
            ).fetchall()
        entries = tuple(_entry_from_row(row) for row in rows)
        current_version = int(series["current_version"])
        current = next(item for item in entries if item.artifact_version == current_version)
        return ArtifactRegistryView(
            current=current,
            versions=entries,
            history=tuple(_history_from_row(row) for row in history_rows),
            gate_audit=tuple(_gate_audit_from_row(row) for row in audit_rows),
        )

    def version(self, artifact_id: str, artifact_version: int) -> ArtifactVersionRecord:
        with self._connect() as connection:
            row = self._version_row(connection, artifact_id, artifact_version)
        return _version_record_from_row(row)

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
        source_snapshot: KnowledgeArtifactSourceSnapshot,
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
                if row is None:
                    row = connection.execute(
                        """
                        SELECT versions.*
                        FROM artifact_series AS series
                        JOIN artifact_versions AS versions
                          ON versions.artifact_id = series.artifact_id
                         AND versions.artifact_version = series.current_version
                        WHERE series.artifact_id = ?
                        """,
                        (artifact_id,),
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
                raise ArtifactNotFoundError(f"Artifactが見つかりません: {artifact_id}")
            record = _version_record_from_row(row)
            approved_at = self._approved_at(
                connection,
                record.entry.artifact_id,
                record.entry.artifact_version,
            )
            eligibility = evaluate_renderer_eligibility(
                record.entry,
                record.artifact,
                source_snapshot,
                artifact_approved_at=approved_at,
            )
            self._insert_gate_audit(
                connection,
                artifact_id=record.entry.artifact_id,
                artifact_version=record.entry.artifact_version,
                action="renderer_access",
                outcome="allowed" if eligibility.eligible else "blocked",
                reason_codes=eligibility.reasons,
                evaluated_at=eligibility.evaluated_at,
                actor="renderer_gateway",
                review_comment="Dual Approval Gate判定",
            )
        if not eligibility.eligible:
            raise ArtifactApprovalError(
                "Renderer利用を停止しました: " + ", ".join(eligibility.reasons),
                reason_codes=eligibility.reasons,
                eligibility=eligibility,
            )
        return record.artifact

    def renderer_eligibility(
        self,
        artifact_id: str,
        *,
        source_snapshot: KnowledgeArtifactSourceSnapshot,
        artifact_version: int,
        audited: bool = False,
        actor: str = "knowledge_workbench",
    ) -> RendererEligibility:
        """Evaluate derived eligibility without changing Artifact approval state."""

        with self._connect() as connection:
            row = self._version_row(connection, artifact_id, artifact_version)
            record = _version_record_from_row(row)
            eligibility = evaluate_renderer_eligibility(
                record.entry,
                record.artifact,
                source_snapshot,
                artifact_approved_at=self._approved_at(
                    connection,
                    artifact_id,
                    artifact_version,
                ),
            )
            if audited:
                self._insert_gate_audit(
                    connection,
                    artifact_id=artifact_id,
                    artifact_version=artifact_version,
                    action="renderer_access",
                    outcome="allowed" if eligibility.eligible else "blocked",
                    reason_codes=eligibility.reasons,
                    evaluated_at=eligibility.evaluated_at,
                    actor=actor,
                    review_comment="Dual Approval Gate判定",
                )
        return eligibility

    def backup_to(self, destination: Path) -> None:
        """Create and validate a transactionally consistent Registry backup."""

        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ArtifactRegistryError(
                f"同名のArtifact Registry Backupが存在します: {destination.name}"
            )
        try:
            with self._connect() as source, sqlite3.connect(destination) as target:
                source.backup(target)
            SQLitePresentationArtifactRegistry(destination).validate()
        except (sqlite3.Error, ValueError) as error:
            destination.unlink(missing_ok=True)
            raise ArtifactRegistryError(
                f"Artifact Registry Backupを作成できません: {error}"
            ) from error

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
        try:
            source_claim_versions = json.loads(
                str(row["source_claim_versions_json"])
            )
        except (TypeError, json.JSONDecodeError):
            source_claim_versions = {}
        artifact_claim_ids = {item.claim_id for item in artifact.claim_catalog}
        if (
            set(source_claim_versions) != artifact_claim_ids
            or any(
                not isinstance(value, int) or value < 1
                for value in source_claim_versions.values()
            )
        ):
            issues.append(
                _validation_issue(
                    "source_claim_versions_inconsistent",
                    artifact_id,
                    version,
                    "Artifact参照ClaimのVersion Snapshotが不完全です。",
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
        if row["approval_state"] in {
            ArtifactApprovalState.APPROVED.value,
            ArtifactApprovalState.PUBLISHED.value,
        } and not bool(row["immutable"]):
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
    def _insert_gate_audit(
        connection: sqlite3.Connection,
        *,
        artifact_id: str,
        artifact_version: int,
        action: str,
        outcome: str,
        reason_codes: tuple[str, ...],
        evaluated_at: datetime,
        actor: str,
        review_comment: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO artifact_gate_audit (
                artifact_id, artifact_version, action, outcome,
                reason_codes_json, evaluated_at, actor, review_comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                artifact_version,
                action,
                outcome,
                json.dumps(reason_codes, ensure_ascii=False),
                _iso(evaluated_at),
                actor,
                review_comment,
            ),
        )

    @staticmethod
    def _approved_at(
        connection: sqlite3.Connection,
        artifact_id: str,
        artifact_version: int,
    ) -> datetime | None:
        row = connection.execute(
            """
            SELECT changed_at FROM artifact_history
            WHERE artifact_id = ? AND artifact_version = ?
              AND event_type = ? AND to_approval_state = ?
            ORDER BY history_id DESC LIMIT 1
            """,
            (
                artifact_id,
                artifact_version,
                ArtifactHistoryEventType.APPROVAL_TRANSITION.value,
                ArtifactApprovalState.APPROVED.value,
            ),
        ).fetchone()
        return datetime.fromisoformat(str(row["changed_at"])) if row else None

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
                    source_review_version INTEGER NOT NULL CHECK (
                        source_review_version >= 1
                    ),
                    source_claim_versions_json TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS artifact_gate_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    artifact_version INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK (
                        action IN ('approval_transition', 'renderer_access')
                    ),
                    outcome TEXT NOT NULL CHECK (outcome IN ('allowed', 'blocked')),
                    reason_codes_json TEXT NOT NULL DEFAULT '[]',
                    evaluated_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    review_comment TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (artifact_id, artifact_version)
                        REFERENCES artifact_versions(artifact_id, artifact_version)
                );

                CREATE INDEX IF NOT EXISTS idx_artifact_versions_approval
                    ON artifact_versions(artifact_id, approval_state, artifact_version);
                CREATE INDEX IF NOT EXISTS idx_artifact_history_lookup
                    ON artifact_history(artifact_id, artifact_version, history_id);
                CREATE INDEX IF NOT EXISTS idx_artifact_gate_audit_lookup
                    ON artifact_gate_audit(artifact_id, artifact_version, audit_id);

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
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(artifact_versions)").fetchall()
            }
            if "source_review_version" not in columns:
                connection.execute(
                    "ALTER TABLE artifact_versions ADD COLUMN source_review_version INTEGER"
                )
                connection.execute(
                    "UPDATE artifact_versions "
                    "SET source_review_version = knowledge_version "
                    "WHERE source_review_version IS NULL"
                )
            if "source_claim_versions_json" not in columns:
                connection.execute(
                    "ALTER TABLE artifact_versions "
                    "ADD COLUMN source_claim_versions_json TEXT"
                )
                rows = connection.execute(
                    "SELECT artifact_id, artifact_version, artifact_json "
                    "FROM artifact_versions"
                ).fetchall()
                for row in rows:
                    artifact = PresentationArtifact.model_validate_json(
                        row["artifact_json"]
                    )
                    versions = {
                        item.claim_id: 1 for item in artifact.claim_catalog
                    }
                    connection.execute(
                        "UPDATE artifact_versions "
                        "SET source_claim_versions_json = ? "
                        "WHERE artifact_id = ? AND artifact_version = ?",
                        (
                            json.dumps(versions, sort_keys=True),
                            row["artifact_id"],
                            row["artifact_version"],
                        ),
                    )
            connection.executescript(
                """
                DROP TRIGGER IF EXISTS prevent_approved_artifact_content_update;
                CREATE TRIGGER prevent_approved_artifact_content_update
                BEFORE UPDATE OF
                    artifact_json, fingerprint, source_bundle_id,
                    presentation_request_id, knowledge_id, knowledge_version,
                    source_review_version, source_claim_versions_json,
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
    unsigned = artifact.model_copy(update={"identity": identity, "metadata": metadata})
    return unsigned.model_copy(
        update={
            "metadata": metadata.model_copy(update={"fingerprint": artifact_fingerprint(unsigned)})
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
        source_review_version=(
            row["source_review_version"]
            if row["source_review_version"] is not None
            else row["knowledge_version"]
        ),
        source_claim_versions=json.loads(str(row["source_claim_versions_json"])),
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
        from_approval_state=(ArtifactApprovalState(from_state) if from_state is not None else None),
        to_approval_state=ArtifactApprovalState(row["to_approval_state"]),
    )


def _gate_audit_from_row(row: sqlite3.Row) -> ArtifactGateAuditRecord:
    return ArtifactGateAuditRecord(
        audit_id=row["audit_id"],
        artifact_id=row["artifact_id"],
        artifact_version=row["artifact_version"],
        action=row["action"],
        outcome=row["outcome"],
        reason_codes=tuple(json.loads(str(row["reason_codes_json"]))),
        evaluated_at=datetime.fromisoformat(str(row["evaluated_at"])),
        actor=row["actor"],
        review_comment=row["review_comment"],
    )


def _version_record_from_row(row: sqlite3.Row) -> ArtifactVersionRecord:
    return ArtifactVersionRecord(
        entry=_entry_from_row(row),
        artifact=PresentationArtifact.model_validate_json(row["artifact_json"]),
    )


def _validate_transition(
    current: ArtifactApprovalState,
    target: ArtifactApprovalState,
) -> None:
    if current == target:
        raise ArtifactApprovalError("同じApproval Stateへは変更できません。")
    if not _transition_allowed(current, target):
        raise ArtifactApprovalError("Approval Stateは前方へ1段階ずつ進めてください。")


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
