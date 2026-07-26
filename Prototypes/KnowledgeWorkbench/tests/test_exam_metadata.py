from copy import deepcopy

import pytest
from knowledge_contracts.exam_v10 import (
    ExamDataSourceType,
    ExamMetadataSchemaError,
    exam_metadata_json_schema,
    validate_exam_metadata,
    validate_exam_metadata_for_knowledge,
)

from knowledge_workbench.application import GenerateKnowledge
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def test_exam_metadata_schema_is_versioned_draft_2020_12() -> None:
    schema = exam_metadata_json_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/1.0")


@pytest.mark.parametrize("term", ["AST", "HbA1c"])
def test_exam_metadata_links_to_generated_knowledge(term: str) -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider()).execute(term)
    metadata = outcome.exam_metadata

    assert validate_exam_metadata_for_knowledge(metadata, outcome.record) == metadata
    assert metadata.schema_version == "1.0"
    assert metadata.knowledge_id == outcome.record.knowledge_id
    assert metadata.source_dataset.source_type == ExamDataSourceType.MANUAL_DUMMY
    assert metadata.source_dataset.is_production_data is False
    assert metadata.frequency.appearance_count == 2
    assert len(metadata.priority_claims) >= 3
    assert outcome.exam_completeness.validation_status == "completed"
    assert outcome.exam_completeness.score == 79
    assert outcome.exam_completeness.is_ready_for_publisher is False
    assert {item.requirement_id for item in outcome.exam_completeness.improvement_candidates} == {
        "exam.provenance",
        "exam.history",
    }


def test_exam_metadata_rejects_frequency_history_mismatch() -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST")
    raw = outcome.exam_metadata.model_dump(mode="json")
    raw["frequency"]["appearance_count"] = 99

    with pytest.raises(ExamMetadataSchemaError, match="appearance_count"):
        validate_exam_metadata(raw)


def test_exam_metadata_rejects_unknown_knowledge_claim() -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST")
    raw = deepcopy(outcome.exam_metadata.model_dump(mode="json"))
    raw["priority_claims"][0]["claim_id"] = "clm_unknown_exam_claim"

    with pytest.raises(ExamMetadataSchemaError, match="unknown claim_id"):
        validate_exam_metadata_for_knowledge(raw, outcome.record)


def test_knowledge_completeness_does_not_include_exam_requirements() -> None:
    outcome = GenerateKnowledge(FixtureKnowledgeProvider()).execute("AST")

    requirement_ids = {
        item.requirement_id for item in outcome.knowledge_completeness.requirement_results
    }
    assert outcome.knowledge_completeness.profile_id == "knowledge_completeness.test_item"
    assert not any(item.startswith("exam.") for item in requirement_ids)
