"""Contracts between CSV parsing and Exam Metadata generation."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from knowledge_contracts.exam_v10 import (
    ExamImageAsset,
    ExamSection,
    QuestionPattern,
)
from knowledge_contracts.v10.models import (
    ClaimId,
    KnowledgeId,
    NullableText,
    ShortText,
    StrictModel,
)

NormalizedRecordId = Annotated[
    str, StringConstraints(pattern=r"^nrm_[a-z0-9][a-z0-9_-]{7,63}$")
]
ImportPreviewId = Annotated[
    str, StringConstraints(pattern=r"^prv_[a-z0-9][a-z0-9_-]{7,63}$")
]


class NormalizedExamRecord(StrictModel):
    """Stable row-level form that is independent from any CSV column names."""

    record_id: NormalizedRecordId
    session_number: int = Field(ge=1)
    exam_year: int = Field(ge=1950, le=2100)
    section: ExamSection
    question_number: int = Field(ge=1)
    theme: ShortText
    source_file: ShortText
    source_row_number: int = Field(ge=2)
    source_row_id: ShortText
    patterns: list[QuestionPattern] = Field(min_length=1, max_length=6)
    related_terms: list[ShortText] = Field(min_length=0, max_length=100)
    image_reference: NullableText
    tested_claims: list[ShortText] = Field(min_length=1, max_length=30)


class MappedExamRecord(StrictModel):
    normalized: NormalizedExamRecord
    canonical_theme: ShortText
    knowledge_id: KnowledgeId
    tested_claim_ids: list[ClaimId] = Field(min_length=1, max_length=30)
    image_assets: list[ExamImageAsset] = Field(min_length=0, max_length=20)


class ImportIssue(StrictModel):
    severity: Literal["error", "warning"]
    code: ShortText
    message: str
    source_row_number: int | None = Field(ge=2)
    column_name: NullableText


class ColumnResolution(StrictModel):
    internal_field: ShortText
    source_column: NullableText
    status: Literal["mapped", "missing_required", "missing_optional"]


class CsvValidationReport(StrictModel):
    mapping_version: ShortText
    source_file: ShortText
    can_import: bool
    header_columns: list[ShortText]
    column_resolutions: list[ColumnResolution]
    required_columns_missing: list[ShortText]
    optional_fields_unmapped: list[ShortText]
    unused_columns: list[ShortText]
    unknown_columns: list[ShortText]
    duplicate_columns: list[ShortText]
    ambiguous_mappings: list[ShortText]
    source_row_count: int = Field(ge=0)
    valid_row_count: int = Field(ge=0)
    invalid_row_count: int = Field(ge=0)
    issues: list[ImportIssue]


class ImportDiff(StrictModel):
    added_source_row_ids: list[ShortText]
    removed_source_row_ids: list[ShortText]
    unchanged_source_row_ids: list[ShortText]


class KnowledgeMappingSummary(StrictModel):
    source_theme: ShortText
    canonical_theme: ShortText
    knowledge_id: KnowledgeId


class CsvImportReport(StrictModel):
    import_id: ShortText
    dataset_hash: str
    validation: CsvValidationReport
    knowledge_mappings: list[KnowledgeMappingSummary]
    normalized_record_count: int = Field(ge=0)
    mapped_record_count: int = Field(ge=0)
    metadata_record_count: int = Field(ge=0)
    image_mapped_count: int = Field(ge=0)
    image_warning_count: int = Field(ge=0)
    diff: ImportDiff


class CsvImportPreview(StrictModel):
    preview_id: ImportPreviewId
    can_commit: bool
    registry_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    new_knowledge_ids: list[KnowledgeId]
    updated_knowledge_ids: list[KnowledgeId]
    unknown_terms: list[ShortText]
    mapping_failures: list[str]
    missing_images: list[str]
    unsupported_claims: list[str]
