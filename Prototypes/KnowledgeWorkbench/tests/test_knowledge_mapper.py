import pytest

from knowledge_workbench.errors import KnowledgeMappingError
from knowledge_workbench.generation_models import GeneratedKnowledgeDraft
from knowledge_workbench.knowledge_mapper import map_to_knowledge_record
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def test_mapper_adds_only_system_owned_v03_sections() -> None:
    draft = FixtureKnowledgeProvider().generate("AST").draft

    record = map_to_knowledge_record(draft)

    assert record.schema_version == "0.3"
    assert record.knowledge_id.startswith("knw_")
    assert record.exam_metadata.importance is None
    assert record.evidence == []
    assert record.publish_targets.note.priority_claim_ids == []
    assert all(claim.claim_id.startswith("clm_") for claim in record.core_facts.definitions)


def test_mapper_rejects_unknown_measurement_method_reference() -> None:
    draft = FixtureKnowledgeProvider().generate("AST").draft
    raw = draft.model_dump(mode="json")
    raw["test_item_content"]["measurement_principles"][0]["related_method_names"] = [
        "存在しない測定方法"
    ]
    invalid_reference = GeneratedKnowledgeDraft.model_validate(raw)

    with pytest.raises(KnowledgeMappingError, match="対応する測定原理"):
        map_to_knowledge_record(invalid_reference)
