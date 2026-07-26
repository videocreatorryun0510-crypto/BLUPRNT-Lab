from datetime import UTC, datetime
import json

from knowledge_contracts.relation_v10 import (
    knowledge_relation_json_schema as relation_v10_json_schema,
)
from knowledge_contracts.relation_v11 import (
    knowledge_relation_json_schema as relation_v11_json_schema,
)
from knowledge_contracts.relation_v12 import (
    RelationType,
    disease_relation_vocabulary,
    disease_relation_vocabulary_json_schema,
    knowledge_relation_json_schema,
)
from knowledge_contracts.relation_v12 import validate_knowledge_relation_snapshot


def test_disease_vocabulary_defines_exactly_the_approved_seven_types() -> None:
    catalog = disease_relation_vocabulary()

    assert catalog.schema_version == "1.0"
    assert catalog.vocabulary_id == "relation_vocabulary.disease"
    assert {item.relation_type for item in catalog.entries} == {
        RelationType.HAS_HIGH_TEST_ITEM,
        RelationType.HAS_LOW_TEST_ITEM,
        RelationType.DIAGNOSED_BY,
        RelationType.CAUSED_BY,
        RelationType.RELATED_DISEASE,
        RelationType.AFFECTS_STRUCTURE,
        RelationType.HAS_PATHOPHYSIOLOGY,
    }
    assert all(item.source_categories == ["disease"] for item in catalog.entries)


def test_disease_vocabulary_fixes_direction_and_category_scope() -> None:
    entries = {
        item.relation_type: item for item in disease_relation_vocabulary().entries
    }

    assert entries[RelationType.HAS_HIGH_TEST_ITEM].target_categories == [
        "laboratory_test_item"
    ]
    assert entries[RelationType.HAS_LOW_TEST_ITEM].target_categories == [
        "laboratory_test_item"
    ]
    assert entries[RelationType.RELATED_DISEASE].direction.value == "symmetric"
    assert entries[RelationType.AFFECTS_STRUCTURE].target_categories == [
        "biological_structure"
    ]
    assert entries[RelationType.HAS_PATHOPHYSIOLOGY].target_categories == [
        "biological_process"
    ]


def test_relation_contract_accepts_disease_type_without_creating_a_relation() -> None:
    now = datetime.now(UTC).isoformat()
    snapshot = validate_knowledge_relation_snapshot(
        {
            "schema_version": "1.2",
            "relations": [
                {
                    "relation_id": "rel_disease01",
                    "source_knowledge_id": "knw_disease01",
                    "target_knowledge_id": None,
                    "target_label": "フェリチン",
                    "relation_type": "has_low_test_item",
                    "claim_id": "clm_finding01",
                    "resolution_status": "unresolved_relation",
                    "status": "draft",
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "context": {"qualifiers": [], "preparation": None},
                }
            ],
            "history": [
                {
                    "event_id": "evt_disease01",
                    "relation_id": "rel_disease01",
                    "action": "add",
                    "from_version": None,
                    "to_version": 1,
                    "occurred_at": now,
                    "actor": "test",
                    "note": "Contractだけを検証",
                }
            ],
        }
    )

    assert snapshot.relations[0].relation_type == RelationType.HAS_LOW_TEST_ITEM


def test_disease_vocabulary_has_a_standalone_versioned_schema() -> None:
    schema = disease_relation_vocabulary_json_schema()
    relation_schema = knowledge_relation_json_schema()

    assert schema["$id"].endswith("/relation-vocabulary/disease/1.0")
    assert schema["title"] == "BLUPRNT Lab Disease Relation Vocabulary Version 1.0"
    assert disease_relation_vocabulary().relation_contract_version == "1.2"
    assert relation_schema["$id"].endswith("/knowledge-relation/1.2")


def test_old_relation_contracts_remain_immutable() -> None:
    old_schema_text = json.dumps(
        [relation_v10_json_schema(), relation_v11_json_schema()]
    )
    new_schema_text = json.dumps(knowledge_relation_json_schema())

    assert "has_low_test_item" not in old_schema_text
    assert "has_low_test_item" in new_schema_text


def test_callers_receive_an_isolated_catalog_copy() -> None:
    first = disease_relation_vocabulary()
    first.entries[0].target_categories.append("should_not_leak")

    second = disease_relation_vocabulary()
    assert "should_not_leak" not in second.entries[0].target_categories
