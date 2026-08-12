"""Persistent storage boundary for validated Knowledge Drafts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from knowledge_workbench.knowledge_draft_models import KnowledgeDraft


class KnowledgeDraftNotFoundError(LookupError):
    """Raised when an assembled Knowledge Draft does not exist."""


class KnowledgeDraftStorageError(RuntimeError):
    """Raised when an assembled Knowledge Draft cannot be read or written."""


class KnowledgeDraftRepository(Protocol):
    def list(self) -> list[KnowledgeDraft]: ...

    def get(self, knowledge_draft_id: str) -> KnowledgeDraft: ...

    def save(self, draft: KnowledgeDraft) -> KnowledgeDraft: ...


class FileKnowledgeDraftRepository:
    """One immutable, validated JSON document per assembled Draft."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[KnowledgeDraft]:
        drafts = [self._read(path) for path in self.directory.glob("kdr_*.json")]
        return sorted(drafts, key=lambda item: item.metadata.assembled_at, reverse=True)

    def get(self, knowledge_draft_id: str) -> KnowledgeDraft:
        path = self._path(knowledge_draft_id)
        if not path.is_file():
            raise KnowledgeDraftNotFoundError(
                f"Knowledge Draft not found: {knowledge_draft_id}"
            )
        return self._read(path)

    def save(self, draft: KnowledgeDraft) -> KnowledgeDraft:
        destination = self._path(draft.knowledge_draft_id)
        temporary = self.directory / f".{draft.knowledge_draft_id}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise KnowledgeDraftStorageError(
                f"Could not save Knowledge Draft {draft.knowledge_draft_id}"
            ) from error
        return draft

    def _path(self, knowledge_draft_id: str) -> Path:
        if not knowledge_draft_id.startswith("kdr_") or not all(
            character.isalnum() or character in "_-" for character in knowledge_draft_id
        ):
            raise KnowledgeDraftNotFoundError(
                f"Invalid Knowledge Draft ID: {knowledge_draft_id}"
            )
        return self.directory / f"{knowledge_draft_id}.json"

    @staticmethod
    def _read(path: Path) -> KnowledgeDraft:
        try:
            return KnowledgeDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            raise KnowledgeDraftStorageError(
                f"Could not read Knowledge Draft: {path.name}"
            ) from error

