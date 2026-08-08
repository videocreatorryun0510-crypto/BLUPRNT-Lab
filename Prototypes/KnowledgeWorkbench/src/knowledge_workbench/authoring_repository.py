"""Persistent storage boundary for incomplete Knowledge authoring drafts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from knowledge_workbench.authoring_models import KnowledgeAuthoringDraft


class AuthoringDraftNotFoundError(LookupError):
    """Raised when an authoring draft does not exist."""


class AuthoringDraftStorageError(RuntimeError):
    """Raised when a persisted draft cannot be read safely."""


class AuthoringDraftRepository(Protocol):
    def list(self) -> list[KnowledgeAuthoringDraft]: ...

    def get(self, draft_id: str) -> KnowledgeAuthoringDraft: ...

    def save(self, draft: KnowledgeAuthoringDraft) -> KnowledgeAuthoringDraft: ...


class FileAuthoringDraftRepository:
    """One validated JSON file per draft, behind a replaceable repository API."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[KnowledgeAuthoringDraft]:
        drafts = [self._read(path) for path in self.directory.glob("kad_*.json")]
        return sorted(drafts, key=lambda item: item.updated_at, reverse=True)

    def get(self, draft_id: str) -> KnowledgeAuthoringDraft:
        path = self._path(draft_id)
        if not path.is_file():
            raise AuthoringDraftNotFoundError(f"Authoring draft not found: {draft_id}")
        return self._read(path)

    def save(self, draft: KnowledgeAuthoringDraft) -> KnowledgeAuthoringDraft:
        destination = self._path(draft.draft_id)
        temporary = self.directory / f".{draft.draft_id}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(
                draft.model_dump_json(indent=2),
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise AuthoringDraftStorageError(
                f"Could not save authoring draft {draft.draft_id}"
            ) from error
        return draft

    def _path(self, draft_id: str) -> Path:
        if not draft_id.startswith("kad_") or not all(
            character.isalnum() or character in "_-" for character in draft_id
        ):
            raise AuthoringDraftNotFoundError(f"Invalid draft ID: {draft_id}")
        return self.directory / f"{draft_id}.json"

    def _read(self, path: Path) -> KnowledgeAuthoringDraft:
        try:
            return KnowledgeAuthoringDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            raise AuthoringDraftStorageError(
                f"Could not read authoring draft: {path.name}"
            ) from error
