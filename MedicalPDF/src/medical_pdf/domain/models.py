from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"

    @property
    def display_name(self) -> str:
        return {
            ReviewStatus.UNREVIEWED: "医学監修前",
            ReviewStatus.IN_REVIEW: "医学レビュー中",
            ReviewStatus.APPROVED: "医学監修済み",
        }[self]


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: str
    title: str
    publisher: str
    published_year: int
    url: str

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        _require_text("title", self.title)
        _require_text("publisher", self.publisher)
        _require_text("url", self.url)
        if not 1900 <= self.published_year <= 2100:
            raise ValueError("published_year must be between 1900 and 2100")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceReference:
        return cls(
            source_id=str(value["source_id"]),
            title=str(value["title"]),
            publisher=str(value["publisher"]),
            published_year=int(value["published_year"]),
            url=str(value["url"]),
        )


@dataclass(frozen=True, slots=True)
class DiseaseSheet:
    document_id: str
    content_version: str
    generated_at: datetime
    review_status: ReviewStatus
    disease_name: str
    english_name: str
    aliases: tuple[str, ...]
    one_line_summary: str
    pathophysiology: tuple[str, ...]
    symptoms_and_signs: tuple[str, ...]
    diagnosis: tuple[str, ...]
    treatment: tuple[str, ...]
    red_flags: tuple[str, ...]
    learning_points: tuple[str, ...]
    references: tuple[SourceReference, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "content_version",
            "disease_name",
            "english_name",
            "one_line_summary",
        ):
            _require_text(field_name, str(getattr(self, field_name)))

        for field_name in (
            "pathophysiology",
            "symptoms_and_signs",
            "diagnosis",
            "treatment",
            "red_flags",
            "learning_points",
        ):
            values = getattr(self, field_name)
            if not values:
                raise ValueError(f"{field_name} must contain at least one item")
            for item in values:
                _require_text(field_name, item)

        if len(self.references) < 2:
            raise ValueError("references must contain at least two sources")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DiseaseSheet:
        return cls(
            document_id=str(value["document_id"]),
            content_version=str(value["content_version"]),
            generated_at=datetime.fromisoformat(str(value["generated_at"])),
            review_status=ReviewStatus(str(value["review_status"])),
            disease_name=str(value["disease_name"]),
            english_name=str(value["english_name"]),
            aliases=_string_tuple(value.get("aliases", ())),
            one_line_summary=str(value["one_line_summary"]),
            pathophysiology=_string_tuple(value["pathophysiology"]),
            symptoms_and_signs=_string_tuple(value["symptoms_and_signs"]),
            diagnosis=_string_tuple(value["diagnosis"]),
            treatment=_string_tuple(value["treatment"]),
            red_flags=_string_tuple(value["red_flags"]),
            learning_points=_string_tuple(value["learning_points"]),
            references=tuple(
                SourceReference.from_mapping(item) for item in value["references"]
            ),
        )

    @property
    def required_pdf_labels(self) -> tuple[str, ...]:
        return (
            self.disease_name,
            "ひとことで理解",
            "病態・原因",
            "症状・所見",
            "検査・診断",
            "治療・管理",
            "Red Flags",
            "国家試験ポイント",
            "出典",
            self.review_status.display_name,
        )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("expected an array of strings")
    return tuple(str(item) for item in value)


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
