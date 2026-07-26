"""Versioned, file-based configuration for yearly exam imports."""

import json
from pathlib import Path
from typing import Self

from knowledge_contracts.registry_v10 import ClaimKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

MAPPING_DIR = Path(__file__).resolve().parents[2] / "imports" / "mappings"
DEFAULT_MAPPING_PATH = MAPPING_DIR / "exam_csv_v1.json"


class StrictMappingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimSelector(StrictMappingModel):
    claim_keys: list[ClaimKey] = Field(min_length=1, max_length=20)


class ImportanceProfile(StrictMappingModel):
    profile_id: str
    profile_version: str
    formula_type: str
    base_score: int = Field(ge=0, le=100)
    appearance_weight: int = Field(ge=0, le=100)
    appearance_cap: int = Field(ge=1)
    recency_window_years: int = Field(ge=0)
    recency_bonus: int = Field(ge=0, le=100)
    pattern_weights: dict[str, int]
    maximum_score: int = Field(ge=1, le=100)


class ImageMapping(StrictMappingModel):
    section_codes: dict[str, str]
    filename_template: str
    extensions: list[str] = Field(min_length=1)


class ExamCsvMapping(StrictMappingModel):
    mapping_id: str
    mapping_version: str
    encoding: str
    delimiter: str = Field(min_length=1, max_length=1)
    required_fields: list[str]
    column_aliases: dict[str, list[str]]
    ignored_columns: list[str]
    list_separator: str = Field(min_length=1, max_length=3)
    section_aliases: dict[str, str]
    pattern_aliases: dict[str, str]
    knowledge_aliases: dict[str, list[str]]
    claim_selectors: dict[str, dict[str, ClaimSelector]]
    importance_profile: ImportanceProfile
    image_mapping: ImageMapping

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        missing = sorted(set(self.required_fields) - set(self.column_aliases))
        if missing:
            raise ValueError("required_fields are missing column_aliases: " + ", ".join(missing))
        aliases: dict[str, str] = {}
        for field, values in self.column_aliases.items():
            for alias in values:
                normalized = alias.strip().casefold()
                previous = aliases.get(normalized)
                if previous is not None and previous != field:
                    raise ValueError(f"column alias {alias!r} is shared by {previous} and {field}")
                aliases[normalized] = field
        if set(self.knowledge_aliases) != set(self.claim_selectors):
            raise ValueError(
                "knowledge_aliases and claim_selectors must use identical canonical keys"
            )
        return self


def load_exam_csv_mapping(path: Path | None = None) -> ExamCsvMapping:
    mapping_path = path or DEFAULT_MAPPING_PATH
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    return ExamCsvMapping.model_validate(raw)
