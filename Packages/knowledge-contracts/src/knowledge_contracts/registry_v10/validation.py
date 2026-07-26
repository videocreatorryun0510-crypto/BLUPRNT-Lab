"""JSON Schema and validation helpers for Knowledge Registry Version 1.0."""

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from knowledge_contracts.registry_v10.models import (
    RegistrySnapshot,
    RegistryValidationReport,
)


class RegistrySchemaError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.detail = message
        super().__init__(f"{path}: {message}")


def registry_snapshot_json_schema() -> dict[str, Any]:
    schema = RegistrySnapshot.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://bluprnt-lab.local/schemas/knowledge-registry/1.0"
    schema["title"] = "BLUPRNT Lab Knowledge Registry Version 1.0"
    return schema


def validate_registry_snapshot(
    value: RegistrySnapshot | dict[str, Any],
) -> RegistrySnapshot:
    raw = (
        value.model_dump(mode="json") if isinstance(value, RegistrySnapshot) else value
    )
    validator = Draft202012Validator(registry_snapshot_json_schema())
    errors = sorted(
        validator.iter_errors(raw), key=lambda item: list(item.absolute_path)
    )
    if errors:
        error: ValidationError = errors[0]
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        raise RegistrySchemaError(path or "/", error.message)
    try:
        return RegistrySnapshot.model_validate(raw)
    except PydanticValidationError as error:
        first_error = error.errors(include_url=False)[0]
        path = "/" + "/".join(str(part) for part in first_error["loc"])
        raise RegistrySchemaError(path or "/", str(first_error["msg"])) from error


def registry_validation_report(snapshot: RegistrySnapshot) -> RegistryValidationReport:
    try:
        validated = validate_registry_snapshot(snapshot)
    except RegistrySchemaError as error:
        return RegistryValidationReport(
            is_valid=False,
            knowledge_count=len(snapshot.knowledge),
            claim_count=len(snapshot.claims),
            alias_count=len(snapshot.alias_bindings),
            merge_redirect_count=len(snapshot.merge_redirects),
            history_count=len(snapshot.history),
            errors=[str(error)],
        )
    return RegistryValidationReport(
        is_valid=True,
        knowledge_count=len(validated.knowledge),
        claim_count=len(validated.claims),
        alias_count=len(validated.alias_bindings),
        merge_redirect_count=len(validated.merge_redirects),
        history_count=len(validated.history),
        errors=[],
    )
