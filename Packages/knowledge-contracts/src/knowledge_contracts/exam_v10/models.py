"""Independent Exam Metadata Version 1.0 contract.

Exam metadata is linked to medical knowledge by knowledge_id and claim_id. It
has its own revision so importing a new exam CSV does not rewrite medical facts.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from knowledge_contracts.v10.models import (
    ClaimId,
    KnowledgeId,
    MediumText,
    NullableText,
    ShortText,
    StrictModel,
)

ExamMetadataId = Annotated[
    str, StringConstraints(pattern=r"^exm_[a-z0-9][a-z0-9_-]{7,63}$")
]
OccurrenceId = Annotated[
    str, StringConstraints(pattern=r"^exo_[a-z0-9][a-z0-9_-]{7,63}$")
]
CommonErrorId = Annotated[
    str, StringConstraints(pattern=r"^err_[a-z0-9][a-z0-9_-]{7,63}$")
]
ImageId = Annotated[str, StringConstraints(pattern=r"^img_[a-z0-9][a-z0-9_-]{7,63}$")]
Sha256Hash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ExamDataSourceType(StrEnum):
    MANUAL_DUMMY = "manual_dummy"
    MANUAL_VERIFIED = "manual_verified"
    CSV_ANALYSIS = "csv_analysis"


class ExamSection(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    UNSPECIFIED = "unspecified"


class QuestionPattern(StrEnum):
    STANDALONE_KNOWLEDGE = "standalone_knowledge"
    DIFFERENTIAL = "differential"
    IMAGE = "image"
    CALCULATION = "calculation"
    ELIMINATION = "elimination"
    COMBINATION = "combination"


class MemorizationPriority(StrEnum):
    HIGHEST = "highest"
    IMPORTANT = "important"
    SUPPLEMENTARY = "supplementary"


class RelatedTermType(StrEnum):
    COMPARISON = "comparison"
    DIFFERENTIAL = "differential"
    COMBINATION = "combination"
    CALCULATION_CONTEXT = "calculation_context"
    BACKGROUND = "background"


class ImageAssetSourceType(StrEnum):
    EMBEDDED_SPREADSHEET = "embedded_spreadsheet"
    EXTERNAL_FILE = "external_file"


class SourceDataset(StrictModel):
    source_type: ExamDataSourceType
    dataset_id: ShortText
    dataset_version: ShortText
    analysis_batch_id: ShortText
    imported_at: datetime | None
    source_row_count: int = Field(ge=0)
    is_production_data: bool

    @model_validator(mode="after")
    def prevent_dummy_production_data(self) -> Self:
        if (
            self.source_type == ExamDataSourceType.MANUAL_DUMMY
            and self.is_production_data
        ):
            raise ValueError("manual_dummy data cannot be marked as production data")
        return self


class ExamImageAsset(StrictModel):
    image_id: ImageId
    image_filename: ShortText
    image_path: MediumText
    image_version: int = Field(ge=1)
    image_hash: Sha256Hash | None
    source_type: ImageAssetSourceType
    source_reference: ShortText

    @model_validator(mode="after")
    def require_safe_relative_path(self) -> Self:
        path = PurePosixPath(self.image_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("image_path must be a safe relative path")
        if path.name != self.image_filename:
            raise ValueError("image_filename must match the final image_path component")
        return self


class ExamOccurrence(StrictModel):
    occurrence_id: OccurrenceId
    source_row_id: ShortText
    session_number: int = Field(ge=1)
    exam_year: int = Field(ge=1950, le=2100)
    section: ExamSection
    question_number: int = Field(ge=1)
    patterns: list[QuestionPattern] = Field(min_length=1, max_length=6)
    tested_claim_ids: list[ClaimId] = Field(min_length=1, max_length=30)
    image_assets: list[ExamImageAsset] = Field(min_length=0, max_length=20)

    @model_validator(mode="after")
    def require_unique_values(self) -> Self:
        if len(self.patterns) != len(set(self.patterns)):
            raise ValueError("patterns must be unique within an exam occurrence")
        if len(self.tested_claim_ids) != len(set(self.tested_claim_ids)):
            raise ValueError(
                "tested_claim_ids must be unique within an exam occurrence"
            )
        image_ids = [item.image_id for item in self.image_assets]
        if len(image_ids) != len(set(image_ids)):
            raise ValueError("image_id values must be unique within an exam occurrence")
        return self


class ExamFrequencySummary(StrictModel):
    appearance_count: int = Field(ge=0)
    first_session_number: int | None = Field(ge=1)
    first_exam_year: int | None = Field(ge=1950, le=2100)
    latest_session_number: int | None = Field(ge=1)
    latest_exam_year: int | None = Field(ge=1950, le=2100)


class ImportanceAssessment(StrictModel):
    importance_score: int = Field(ge=0, le=100)
    calculation_method: Literal[
        "manual_dummy", "manual_verified", "frequency_weighted_v1", "composite_v1"
    ]
    calculation_note: NullableText


class ClaimExamPriority(StrictModel):
    claim_id: ClaimId
    priority: MemorizationPriority
    evidence_occurrence_ids: list[OccurrenceId] = Field(min_length=0, max_length=100)


class QuestionPatternSummary(StrictModel):
    pattern: QuestionPattern
    appearance_count: int = Field(ge=1)
    occurrence_ids: list[OccurrenceId] = Field(min_length=1, max_length=500)
    related_claim_ids: list[ClaimId] = Field(min_length=1, max_length=100)


class RelatedExamTerm(StrictModel):
    term: ShortText
    related_knowledge_id: KnowledgeId | None
    relation_type: RelatedTermType


class CommonExamError(StrictModel):
    error_id: CommonErrorId
    misconception: MediumText
    correction_claim_ids: list[ClaimId] = Field(min_length=1, max_length=20)
    observed_occurrence_ids: list[OccurrenceId] = Field(min_length=0, max_length=100)


class ExamMetadataRecord(StrictModel):
    schema_version: Literal["1.0"]
    metadata_id: ExamMetadataId
    metadata_revision: int = Field(ge=1)
    knowledge_id: KnowledgeId
    knowledge_content_revision: int = Field(ge=1)
    exam_type: Literal["clinical_laboratory_technologist_national_exam"]
    source_dataset: SourceDataset
    frequency: ExamFrequencySummary
    history: list[ExamOccurrence] = Field(min_length=0, max_length=1000)
    importance: ImportanceAssessment | None
    priority_claims: list[ClaimExamPriority] = Field(min_length=0, max_length=200)
    question_patterns: list[QuestionPatternSummary] = Field(min_length=0, max_length=6)
    related_terms: list[RelatedExamTerm] = Field(min_length=0, max_length=100)
    common_errors: list[CommonExamError] = Field(min_length=0, max_length=100)

    @model_validator(mode="after")
    def validate_internal_consistency(self) -> Self:
        occurrence_ids = [item.occurrence_id for item in self.history]
        if len(occurrence_ids) != len(set(occurrence_ids)):
            raise ValueError("occurrence_id values must be unique")
        source_row_ids = [item.source_row_id for item in self.history]
        if len(source_row_ids) != len(set(source_row_ids)):
            raise ValueError("source_row_id values must be unique")

        if self.frequency.appearance_count != len(self.history):
            raise ValueError("frequency.appearance_count must equal history length")
        self._validate_frequency_boundaries()

        known_occurrences = set(occurrence_ids)
        occurrence_by_id = {item.occurrence_id: item for item in self.history}
        priority_claim_ids = [item.claim_id for item in self.priority_claims]
        if len(priority_claim_ids) != len(set(priority_claim_ids)):
            raise ValueError("priority claim_id values must be unique")

        for priority_item in self.priority_claims:
            self._require_occurrences(
                priority_item.evidence_occurrence_ids, known_occurrences
            )
        for error_item in self.common_errors:
            self._require_occurrences(
                error_item.observed_occurrence_ids, known_occurrences
            )

        pattern_values = [item.pattern for item in self.question_patterns]
        if len(pattern_values) != len(set(pattern_values)):
            raise ValueError("question pattern summaries must be unique")
        for summary in self.question_patterns:
            self._require_occurrences(summary.occurrence_ids, known_occurrences)
            if summary.appearance_count != len(summary.occurrence_ids):
                raise ValueError(
                    "question pattern appearance_count must equal occurrence_ids length"
                )
            if any(
                summary.pattern not in occurrence_by_id[occurrence_id].patterns
                for occurrence_id in summary.occurrence_ids
            ):
                raise ValueError(
                    "question pattern summary does not match occurrence data"
                )
        return self

    def _validate_frequency_boundaries(self) -> None:
        fields = (
            self.frequency.first_session_number,
            self.frequency.first_exam_year,
            self.frequency.latest_session_number,
            self.frequency.latest_exam_year,
        )
        if not self.history:
            if any(value is not None for value in fields):
                raise ValueError("empty history requires empty frequency boundaries")
            return
        if any(value is None for value in fields):
            raise ValueError("non-empty history requires all frequency boundaries")

        first = min(
            self.history, key=lambda item: (item.exam_year, item.session_number)
        )
        latest = max(
            self.history, key=lambda item: (item.exam_year, item.session_number)
        )
        if (
            self.frequency.first_session_number != first.session_number
            or self.frequency.first_exam_year != first.exam_year
            or self.frequency.latest_session_number != latest.session_number
            or self.frequency.latest_exam_year != latest.exam_year
        ):
            raise ValueError("frequency boundaries must match the history")

    @staticmethod
    def _require_occurrences(referenced: list[OccurrenceId], known: set[str]) -> None:
        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError("unknown occurrence references: " + ", ".join(unknown))
