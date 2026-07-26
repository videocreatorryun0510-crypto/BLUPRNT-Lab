from copy import deepcopy
from datetime import UTC, datetime

import pytest

from knowledge_contracts.relation_v10 import (
    RelationSchemaError,
    knowledge_relation_json_schema,
    validate_knowledge_relation_snapshot,
)


def _snapshot() -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": "1.0",
        "relations": [
            {
                "relation_id": "rel_12345678",
                "source_knowledge_id": "knw_source01",
                "target_knowledge_id": None,
                "target_label": "クリスタルバイオレット",
                "relation_type": "uses_reagent",
                "claim_id": "clm_evidence01",
                "resolution_status": "unresolved_relation",
                "status": "draft",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
        ],
        "history": [
            {
                "event_id": "evt_12345678",
                "relation_id": "rel_12345678",
                "action": "add",
                "from_version": None,
                "to_version": 1,
                "occurred_at": now,
                "actor": "test",
                "note": "Relationを登録",
            }
        ],
    }


def test_relation_contract_is_versioned_and_accepts_unresolved_target() -> None:
    schema = knowledge_relation_json_schema()
    snapshot = validate_knowledge_relation_snapshot(_snapshot())

    assert schema["$id"].endswith("/1.0")
    assert snapshot.relations[0].resolution_status == "unresolved_relation"
    assert snapshot.relations[0].target_knowledge_id is None


def test_relation_type_is_not_free_text() -> None:
    raw = _snapshot()
    raw["relations"][0]["relation_type"] = "uses_anything"  # type: ignore[index]

    with pytest.raises(RelationSchemaError, match="uses_anything"):
        validate_knowledge_relation_snapshot(raw)


def test_resolved_relation_requires_registered_target_id() -> None:
    raw = _snapshot()
    raw["relations"][0]["resolution_status"] = "resolved"  # type: ignore[index]

    with pytest.raises(RelationSchemaError, match="target_knowledge_id"):
        validate_knowledge_relation_snapshot(raw)


def test_active_semantic_relation_cannot_be_duplicated() -> None:
    raw = _snapshot()
    duplicate = deepcopy(raw["relations"][0])  # type: ignore[index]
    duplicate["relation_id"] = "rel_87654321"
    raw["relations"].append(duplicate)  # type: ignore[union-attr]

    with pytest.raises(RelationSchemaError, match="semantic relations must be unique"):
        validate_knowledge_relation_snapshot(raw)
