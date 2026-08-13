"""Independent, append-only Medical Review Registry boundaries."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Protocol

from knowledge_workbench.medical_review_models import (
    MedicalReviewRecord,
    ReviewerProfile,
    ReviewerRole,
)


class MedicalReviewRegistryError(RuntimeError):
    """Raised when an immutable review ledger operation fails."""


class MedicalReviewRegistry(Protocol):
    def append(self, record: MedicalReviewRecord) -> None: ...

    def get(self, review_id: str) -> MedicalReviewRecord | None: ...

    def list_for_knowledge(self, knowledge_id: str) -> list[MedicalReviewRecord]: ...

    def latest_for_knowledge(self, knowledge_id: str) -> MedicalReviewRecord | None: ...

    def next_version(self, knowledge_id: str) -> int: ...


class ReviewerRegistry(Protocol):
    """Future Auth/Identity Provider adapters implement this read-only contract."""

    def get(self, reviewer_id: str) -> ReviewerProfile | None: ...

    def list_active(self) -> list[ReviewerProfile]: ...


class FixtureReviewerRegistry:
    """MVP fixture IDs; display names are not the identity source of truth."""

    def __init__(self, reviewers: list[ReviewerProfile] | None = None) -> None:
        values = reviewers or _default_reviewers()
        self._reviewers = {item.reviewer_id: item for item in values}

    def get(self, reviewer_id: str) -> ReviewerProfile | None:
        return self._reviewers.get(reviewer_id)

    def list_active(self) -> list[ReviewerProfile]:
        return sorted(
            (item for item in self._reviewers.values() if item.active),
            key=lambda item: item.reviewer_id,
        )


class SQLiteMedicalReviewRegistry:
    """SQLite append-only adapter; no update/delete method is exposed."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append(self, record: MedicalReviewRecord) -> None:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                expected = self._next_version(connection, record.knowledge_id)
                if record.review_version != expected:
                    raise MedicalReviewRegistryError(
                        f"review_versionは{expected}である必要があります"
                    )
                connection.execute(
                    """
                    INSERT INTO medical_review_records(
                        review_id, knowledge_id, review_version, record_json, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.review_id,
                        record.knowledge_id,
                        record.review_version,
                        json.dumps(
                            record.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        record.reviewed_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise MedicalReviewRegistryError(
                "review_idまたはreview_versionが重複しています"
            ) from error
        except sqlite3.Error as error:
            raise MedicalReviewRegistryError(f"Review Registry保存失敗: {error}") from error

    def get(self, review_id: str) -> MedicalReviewRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM medical_review_records WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        return self._record_from_row(row)

    def list_for_knowledge(self, knowledge_id: str) -> list[MedicalReviewRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_json FROM medical_review_records
                WHERE knowledge_id = ? ORDER BY review_version
                """,
                (knowledge_id,),
            ).fetchall()
        return [MedicalReviewRecord.model_validate_json(str(row["record_json"])) for row in rows]

    def latest_for_knowledge(self, knowledge_id: str) -> MedicalReviewRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT record_json FROM medical_review_records
                WHERE knowledge_id = ? ORDER BY review_version DESC LIMIT 1
                """,
                (knowledge_id,),
            ).fetchone()
        return self._record_from_row(row)

    def next_version(self, knowledge_id: str) -> int:
        with self._connect() as connection:
            return self._next_version(connection, knowledge_id)

    def _next_version(self, connection: sqlite3.Connection, knowledge_id: str) -> int:
        row = connection.execute(
            """
            SELECT MAX(review_version) AS latest FROM medical_review_records
            WHERE knowledge_id = ?
            """,
            (knowledge_id,),
        ).fetchone()
        latest = None if row is None else row["latest"]
        return 1 if latest is None else int(latest) + 1

    def _record_from_row(self, row: sqlite3.Row | None) -> MedicalReviewRecord | None:
        if row is None:
            return None
        return MedicalReviewRecord.model_validate_json(str(row["record_json"]))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_review_records(
                    review_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    review_version INTEGER NOT NULL CHECK(review_version >= 1),
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(knowledge_id, review_version)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_medical_review_knowledge_version
                ON medical_review_records(knowledge_id, review_version DESC)
                """
            )


def _default_reviewers() -> list[ReviewerProfile]:
    def reviewer(
        reviewer_id: str, display_name: str, categories: list[str]
    ) -> ReviewerProfile:
        return ReviewerProfile(
            reviewer_id=reviewer_id,
            display_name=display_name,
            specialty_categories=categories,
            roles=[ReviewerRole.MEDICAL_REVIEWER, ReviewerRole.FINAL_APPROVER],
            identity_provider="fixture_identity_provider",
            identity_assurance="mvp_fixture",
            active=True,
        )

    return [
        reviewer(
            "reviewer_fixture_microbiology_001",
            "微生物分野レビュー担当（MVP Fixture）",
            [
                "staining_method",
                "specimen",
                "reagent",
                "biological_structure",
            ],
        ),
        reviewer(
            "reviewer_fixture_chemistry_001",
            "臨床化学分野レビュー担当（MVP Fixture）",
            ["test_item", "laboratory_test_item"],
        ),
        reviewer(
            "reviewer_fixture_hematology_001",
            "血液分野レビュー担当（MVP Fixture）",
            ["disease"],
        ),
    ]
