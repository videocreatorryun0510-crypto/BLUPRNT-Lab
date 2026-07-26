"""Versioned Source Bundle Profile catalog."""

import json
from pathlib import Path

from pydantic import ValidationError

from source_bundle_publisher.models import SourceBundleProfile


class SourceBundleProfileCatalog:
    def __init__(self, profiles: tuple[SourceBundleProfile, ...]) -> None:
        by_knowledge_id = {item.knowledge_id: item for item in profiles}
        if len(by_knowledge_id) != len(profiles):
            raise ValueError("Source Bundle Profile knowledge_id values must be unique")
        self._profiles = by_knowledge_id

    @classmethod
    def from_directory(cls, directory: Path) -> "SourceBundleProfileCatalog":
        if not directory.is_dir():
            raise ValueError(f"Source Bundle Profile directory not found: {directory}")
        profiles: list[SourceBundleProfile] = []
        for path in sorted(directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(SourceBundleProfile.model_validate(raw))
            except (OSError, json.JSONDecodeError, ValidationError) as error:
                raise ValueError(
                    f"Source Bundle Profileを読み込めません: {path.name}: {error}"
                ) from error
        if not profiles:
            raise ValueError("Source Bundle Profileが1件もありません。")
        return cls(tuple(profiles))

    def resolve(self, knowledge_id: str) -> SourceBundleProfile:
        profile = self._profiles.get(knowledge_id)
        if profile is None:
            raise KeyError(knowledge_id)
        return profile

    @property
    def supported_knowledge_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))
