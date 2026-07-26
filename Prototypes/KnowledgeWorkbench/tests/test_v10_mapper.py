import pytest
from knowledge_contracts.v10 import validate_knowledge_record

from knowledge_workbench.errors import KnowledgeMappingError
from knowledge_workbench.knowledge_mapper import map_to_knowledge_record
from knowledge_workbench.knowledge_v10_mapper import map_v03_to_v10
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


@pytest.mark.parametrize("term", ["AST", "HbA1c"])
def test_v03_test_item_maps_to_valid_v10(term: str) -> None:
    draft = FixtureKnowledgeProvider().generate(term).draft
    legacy_record = map_to_knowledge_record(draft)

    record = map_v03_to_v10(legacy_record)

    assert validate_knowledge_record(record) == record
    assert legacy_record.schema_version == "0.3"
    assert record.schema_version == "1.0"
    assert record.knowledge_id == legacy_record.knowledge_id
    assert record.category_content.template_id == "test_item_v1.0"
    assert (
        record.core_facts.definitions[0].claim_id
        == legacy_record.core_facts.definitions[0].claim_id
    )
    assert record.category_content.test_item.standardization_and_traceability == []
    assert record.category_content.test_item.analytical_interferences == []


def test_v10_mapper_rejects_non_test_item_without_changing_v03() -> None:
    draft = FixtureKnowledgeProvider().generate("Gram染色").draft
    legacy_record = map_to_knowledge_record(draft)

    with pytest.raises(KnowledgeMappingError, match="検査項目だけ"):
        map_v03_to_v10(legacy_record)

    assert legacy_record.schema_version == "0.3"
    assert legacy_record.category_content.template_id == "generic_facts_v0.3"
