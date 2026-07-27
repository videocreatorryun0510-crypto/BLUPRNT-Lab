"""Versioned Presentation Profile catalog."""

import json
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from presentation_request_builder.models import PresentationProfile


class PresentationProfileCatalog:
    def __init__(self, profiles: tuple[PresentationProfile, ...]) -> None:
        by_identity = {(item.profile_id, item.profile_version): item for item in profiles}
        if len(by_identity) != len(profiles):
            raise ValueError("Presentation Profile ID and Version must be unique")
        self._profiles = by_identity

    @classmethod
    def from_directory(cls, directory: Path) -> "PresentationProfileCatalog":
        if not directory.is_dir():
            raise ValueError(f"Presentation Profile directory not found: {directory}")
        profiles: list[PresentationProfile] = []
        for path in sorted(directory.glob("*.json")):
            try:
                profiles.append(
                    PresentationProfile.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError, ValidationError) as error:
                raise ValueError(
                    f"Presentation Profileを読み込めません: {path.name}: {error}"
                ) from error
        if not profiles:
            raise ValueError("Presentation Profileが1件もありません。")
        return cls(tuple(profiles))

    def resolve(
        self,
        profile_id: str,
        profile_version: Literal["1.0"],
    ) -> PresentationProfile:
        profile = self._profiles.get((profile_id, profile_version))
        if profile is None:
            raise KeyError((profile_id, profile_version))
        return profile

    @property
    def profile_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item[0] for item in self._profiles}))
