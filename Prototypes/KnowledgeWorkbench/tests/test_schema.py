import pytest
from knowledge_contracts.v10 import (
    KnowledgeSchemaError,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

from knowledge_workbench.application import GenerateKnowledge
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def test_schema_is_versioned_draft_2020_12() -> None:
    schema = knowledge_record_json_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/1.0")


def test_unknown_property_is_rejected() -> None:
    record = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST").record
    raw = record.model_dump(mode="json")
    raw["unexpected"] = "must fail"

    with pytest.raises(KnowledgeSchemaError, match="Additional properties"):
        validate_knowledge_record(raw)


def test_missing_required_property_is_rejected() -> None:
    record = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST").record
    raw = record.model_dump(mode="json")
    del raw["core_facts"]

    with pytest.raises(KnowledgeSchemaError, match="required property"):
        validate_knowledge_record(raw)


def test_test_item_requires_the_category_specific_content() -> None:
    record = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST").record
    raw = record.model_dump(mode="json")
    raw["category_content"] = {"template_id": "test_item_v0.3"}

    with pytest.raises(KnowledgeSchemaError):
        validate_knowledge_record(raw)
