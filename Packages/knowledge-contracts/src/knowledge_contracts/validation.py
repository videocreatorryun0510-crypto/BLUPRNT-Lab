"""Draft 2020-12 JSON Schema validation for Knowledge JSON Version 0.2."""

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from knowledge_contracts.models import KnowledgeRecord


class KnowledgeSchemaError(ValueError):
    """A stable, user-displayable representation of a schema failure."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.detail = message
        super().__init__(f"{path}: {message}")


def knowledge_record_json_schema() -> dict[str, Any]:
    """Return the v0.2 schema with an explicit category-template condition."""

    schema = KnowledgeRecord.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://bluprnt-lab.local/schemas/knowledge-record/0.2"
    schema["title"] = "BLUPRNT Lab Knowledge JSON Version 0.2"
    schema["allOf"] = [
        {
            "if": {
                "properties": {
                    "classification": {
                        "properties": {"term_type": {"const": "test_item"}},
                        "required": ["term_type"],
                    }
                },
                "required": ["classification"],
            },
            "then": {
                "properties": {
                    "template_id": {"const": "test_item_v0.2"},
                    "test_item_content": {"$ref": "#/$defs/TestItemContent"},
                }
            },
            "else": {
                "properties": {
                    "template_id": {"const": "generic_v0.1"},
                    "test_item_content": {"type": "null"},
                }
            },
        }
    ]
    return schema


def validate_knowledge_record(
    value: KnowledgeRecord | dict[str, Any],
) -> KnowledgeRecord:
    """Validate with JSON Schema and the category-template business rule."""

    raw = value.model_dump(mode="json") if isinstance(value, KnowledgeRecord) else value
    validator = Draft202012Validator(knowledge_record_json_schema())
    errors = sorted(
        validator.iter_errors(raw), key=lambda item: list(item.absolute_path)
    )
    if errors:
        error: ValidationError = errors[0]
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        raise KnowledgeSchemaError(path or "/", error.message)
    try:
        return KnowledgeRecord.model_validate(raw)
    except PydanticValidationError as error:
        first_error = error.errors(include_url=False)[0]
        path = "/" + "/".join(str(part) for part in first_error["loc"])
        raise KnowledgeSchemaError(path or "/", str(first_error["msg"])) from error
