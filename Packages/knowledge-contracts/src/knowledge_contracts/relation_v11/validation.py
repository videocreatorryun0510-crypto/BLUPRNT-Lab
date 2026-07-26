"""Schema and validation helpers for Knowledge Relation Version 1.1."""

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from knowledge_contracts.relation_v11.models import (
    KnowledgeRelationSnapshot,
    RelationResolutionStatus,
    RelationValidationReport,
)


class RelationSchemaError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.detail = message
        super().__init__(f"{path}: {message}")


def knowledge_relation_json_schema() -> dict[str, Any]:
    schema = KnowledgeRelationSnapshot.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://bluprnt-lab.local/schemas/knowledge-relation/1.1"
    schema["title"] = "BLUPRNT Lab Knowledge Relation Version 1.1"
    return schema


def validate_knowledge_relation_snapshot(
    value: KnowledgeRelationSnapshot | dict[str, Any],
) -> KnowledgeRelationSnapshot:
    raw = (
        value.model_dump(mode="json")
        if isinstance(value, KnowledgeRelationSnapshot)
        else value
    )
    validator = Draft202012Validator(knowledge_relation_json_schema())
    errors = sorted(
        validator.iter_errors(raw), key=lambda item: list(item.absolute_path)
    )
    if errors:
        error: ValidationError = errors[0]
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        raise RelationSchemaError(path or "/", error.message)
    try:
        return KnowledgeRelationSnapshot.model_validate(raw)
    except PydanticValidationError as error:
        first_error = error.errors(include_url=False)[0]
        path = "/" + "/".join(str(part) for part in first_error["loc"])
        raise RelationSchemaError(path or "/", str(first_error["msg"])) from error


def relation_validation_report(
    snapshot: KnowledgeRelationSnapshot,
) -> RelationValidationReport:
    try:
        validated = validate_knowledge_relation_snapshot(snapshot)
    except RelationSchemaError as error:
        return RelationValidationReport(
            is_valid=False,
            relation_count=len(snapshot.relations),
            resolved_count=0,
            unresolved_count=0,
            history_count=len(snapshot.history),
            errors=[str(error)[:180]],
        )
    resolved = sum(
        item.resolution_status == RelationResolutionStatus.RESOLVED
        for item in validated.relations
    )
    return RelationValidationReport(
        is_valid=True,
        relation_count=len(validated.relations),
        resolved_count=resolved,
        unresolved_count=len(validated.relations) - resolved,
        history_count=len(validated.history),
        errors=[],
    )
