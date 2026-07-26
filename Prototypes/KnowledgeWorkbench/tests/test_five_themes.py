import pytest
from knowledge_contracts.v03 import KnowledgeRecord, validate_knowledge_record
from knowledge_contracts.v10 import (
    KnowledgeRecord as KnowledgeRecordV10,
)
from knowledge_contracts.v10 import (
    validate_knowledge_record as validate_knowledge_record_v10,
)

from knowledge_workbench.application import GenerateKnowledge
from knowledge_workbench.errors import KnowledgeMappingError
from knowledge_workbench.knowledge_mapper import map_to_knowledge_record
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider

THEMES = ["AST", "HbA1c", "巨赤芽球性貧血", "Gram染色", "蟯虫"]


@pytest.mark.parametrize("term", THEMES)
def test_five_themes_remain_valid_in_legacy_v03(term: str) -> None:
    draft = FixtureKnowledgeProvider().generate(term).draft
    record = map_to_knowledge_record(draft)

    assert isinstance(validate_knowledge_record(record), KnowledgeRecord)
    assert record.schema_version == "0.3"
    assert record.content_revision == 1
    assert record.evidence == []
    assert record.exam_metadata.analysis_batch_id == ""
    assert record.exam_metadata.related_questions == []
    assert record.publish_targets.pdf.priority_claim_ids == []
    assert record.core_facts.definitions
    assert "quick_summary" not in record.model_dump(mode="json")
    assert "visual_hooks" not in record.model_dump(mode="json")


@pytest.mark.parametrize("term", ["AST", "HbA1c"])
def test_test_items_generate_v10_with_completeness(term: str) -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider()).execute(term)
    record = outcome.record

    assert isinstance(validate_knowledge_record_v10(record), KnowledgeRecordV10)
    assert record.schema_version == "1.0"
    assert record.classification.term_type == "test_item"
    assert record.category_content.template_id == "test_item_v1.0"

    content = record.category_content.test_item
    assert content.biological_basis
    assert content.analyte_characteristics
    assert content.purposes
    assert content.specimens
    assert content.measurement_methods
    assert content.measurement_principles
    assert content.value_associations.high.pathophysiologic_states
    assert content.value_associations.high.representative_diseases
    assert content.related_test_combinations
    assert content.interpretation_cautions
    assert outcome.completeness.validation_status == "completed"
    assert outcome.completeness.improvement_candidates


@pytest.mark.parametrize("term", ["巨赤芽球性貧血", "Gram染色", "蟯虫"])
def test_non_test_items_are_outside_the_v10_mvp(term: str) -> None:
    with pytest.raises(KnowledgeMappingError, match="検査項目だけ"):
        GenerateKnowledge(FixtureKnowledgeProvider()).execute(term)


def test_system_ids_are_deterministic_for_the_same_fixture() -> None:
    service = GenerateKnowledge(FixtureKnowledgeProvider())

    first = service.execute("AST").record
    second = service.execute("AST").record

    assert first.knowledge_id == second.knowledge_id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_unsupported_fixture_theme_returns_clear_error() -> None:
    with pytest.raises(Exception, match="固定テスト"):
        GenerateKnowledge(FixtureKnowledgeProvider()).execute("存在しないテスト用語")
