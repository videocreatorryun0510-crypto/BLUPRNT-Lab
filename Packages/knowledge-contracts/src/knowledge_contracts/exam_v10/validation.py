"""Schema and cross-record validation for Exam Metadata Version 1.0."""

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from knowledge_contracts.exam_v10.models import ExamMetadataRecord
from knowledge_contracts.v10 import KnowledgeRecord, validate_knowledge_record


class ExamMetadataSchemaError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.detail = message
        super().__init__(f"{path}: {message}")


def exam_metadata_json_schema() -> dict[str, Any]:
    schema = ExamMetadataRecord.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://bluprnt-lab.local/schemas/exam-metadata/1.0"
    schema["title"] = "BLUPRNT Lab Exam Metadata Version 1.0"
    return schema


def validate_exam_metadata(
    value: ExamMetadataRecord | dict[str, Any],
) -> ExamMetadataRecord:
    raw = (
        value.model_dump(mode="json")
        if isinstance(value, ExamMetadataRecord)
        else value
    )
    validator = Draft202012Validator(exam_metadata_json_schema())
    errors = sorted(
        validator.iter_errors(raw), key=lambda item: list(item.absolute_path)
    )
    if errors:
        error: ValidationError = errors[0]
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        raise ExamMetadataSchemaError(path or "/", error.message)
    try:
        return ExamMetadataRecord.model_validate(raw)
    except PydanticValidationError as error:
        first_error = error.errors(include_url=False)[0]
        path = "/" + "/".join(str(part) for part in first_error["loc"])
        raise ExamMetadataSchemaError(path or "/", str(first_error["msg"])) from error


def validate_exam_metadata_for_knowledge(
    value: ExamMetadataRecord | dict[str, Any],
    knowledge: KnowledgeRecord | dict[str, Any],
) -> ExamMetadataRecord:
    """Validate the exam component and every reference into medical knowledge."""

    metadata = validate_exam_metadata(value)
    record = validate_knowledge_record(knowledge)
    if metadata.knowledge_id != record.knowledge_id:
        raise ExamMetadataSchemaError(
            "/knowledge_id", "knowledge_id must match the linked Knowledge JSON"
        )
    if metadata.knowledge_content_revision != record.content_revision:
        raise ExamMetadataSchemaError(
            "/knowledge_content_revision",
            "knowledge_content_revision must match the linked Knowledge JSON",
        )

    known_claim_ids = _collect_claim_ids(record.model_dump(mode="json"))
    referenced_claim_ids = _collect_exam_claim_references(metadata)
    unknown = sorted(referenced_claim_ids - known_claim_ids)
    if unknown:
        raise ExamMetadataSchemaError(
            "/claim_references",
            "exam metadata references unknown claim_id values: " + ", ".join(unknown),
        )
    return metadata


def _collect_claim_ids(value: object) -> set[str]:
    claim_ids: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "claim_id" and isinstance(child, str):
                    claim_ids.add(child)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return claim_ids


def _collect_exam_claim_references(metadata: ExamMetadataRecord) -> set[str]:
    references = {
        claim_id
        for occurrence in metadata.history
        for claim_id in occurrence.tested_claim_ids
    }
    references.update(item.claim_id for item in metadata.priority_claims)
    references.update(
        claim_id
        for item in metadata.question_patterns
        for claim_id in item.related_claim_ids
    )
    references.update(
        claim_id
        for item in metadata.common_errors
        for claim_id in item.correction_claim_ids
    )
    return references
