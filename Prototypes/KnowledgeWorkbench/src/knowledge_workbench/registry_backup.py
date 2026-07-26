"""Generation-managed SQLite backup and restore operations."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from knowledge_workbench.errors import RegistryOperationError
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry

BACKUP_FILENAME = re.compile(r"^registry_\d{8}_\d{6}(?:_\d{2})?\.db$")


@dataclass(frozen=True)
class RegistryBackupInfo:
    filename: str
    created_at: datetime
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class RegistryRestoreResult:
    restored: RegistryBackupInfo
    safety_backup: RegistryBackupInfo


class SQLiteRegistryBackupManager:
    def __init__(self, registry: SQLiteKnowledgeRegistry, backup_directory: Path) -> None:
        self.registry = registry
        self.backup_directory = backup_directory.resolve()
        self.backup_directory.mkdir(parents=True, exist_ok=True)

    def list_backups(self) -> list[RegistryBackupInfo]:
        backups = [
            self._info(path)
            for path in self.backup_directory.glob("registry_*.db")
            if BACKUP_FILENAME.fullmatch(path.name)
        ]
        return sorted(backups, key=lambda item: item.created_at, reverse=True)

    def create_backup(self) -> RegistryBackupInfo:
        destination = self._next_path()
        self.registry.backup_to(destination)
        return self._info(destination)

    def restore(self, filename: str) -> RegistryRestoreResult:
        source = self._safe_path(filename)
        if not source.is_file():
            raise RegistryOperationError(f"Registry Backupが見つかりません: {filename}")
        safety_backup = self.create_backup()
        self.registry.restore_from(source)
        return RegistryRestoreResult(
            restored=self._info(source),
            safety_backup=safety_backup,
        )

    def _next_path(self) -> Path:
        prefix = datetime.now().astimezone().strftime("registry_%Y%m%d_%H%M%S")
        candidate = self.backup_directory / f"{prefix}.db"
        counter = 2
        while candidate.exists():
            candidate = self.backup_directory / f"{prefix}_{counter:02d}.db"
            counter += 1
        return candidate

    def _safe_path(self, filename: str) -> Path:
        if not BACKUP_FILENAME.fullmatch(filename):
            raise RegistryOperationError("Backupファイル名が不正です。")
        path = (self.backup_directory / filename).resolve()
        if path.parent != self.backup_directory:
            raise RegistryOperationError("Backupフォルダ外のファイルは復元できません。")
        return path

    @staticmethod
    def _info(path: Path) -> RegistryBackupInfo:
        stat = path.stat()
        return RegistryBackupInfo(
            filename=path.name,
            created_at=datetime.fromtimestamp(stat.st_mtime).astimezone(),
            size_bytes=stat.st_size,
        )
