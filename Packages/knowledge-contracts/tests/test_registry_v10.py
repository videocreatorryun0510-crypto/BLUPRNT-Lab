from copy import deepcopy
from datetime import UTC, datetime

import pytest

from knowledge_contracts.registry_v10 import (
    RegistrySchemaError,
    registry_snapshot_json_schema,
    validate_registry_snapshot,
)


def _snapshot() -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "registry_version": "1.0",
        "knowledge": [
            {
                "knowledge_id": "knw_registry_ast1",
                "registry_key": "ast",
                "canonical_name": "AST",
                "knowledge_version": 1,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "aliases": ["GOT"],
                "approval": [],
            }
        ],
        "claims": [
            {
                "knowledge_id": "knw_registry_ast1",
                "claim_id": "clm_registry_claim1",
                "claim_key": "ast.is_leakage_enzyme",
                "claim_version": 1,
                "field_path": "category_content.test_item.biological_basis",
                "assertion": "ASTは逸脱酵素である。",
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "aliases": [],
                "approval": [],
                "fact_payload": {
                    "claim_id": "clm_registry_claim1",
                    "assertion": "ASTは逸脱酵素である。",
                },
                "is_deleted": False,
            }
        ],
        "alias_bindings": [{"alias": "GOT", "target": "ast"}],
        "history": [
            {
                "event_id": "his_registry_event1",
                "entity_type": "knowledge",
                "entity_id": "knw_registry_ast1",
                "action": "add",
                "from_version": None,
                "to_version": 1,
                "occurred_at": now,
                "actor": "test",
                "details": {},
            },
            {
                "event_id": "his_registry_event2",
                "entity_type": "claim",
                "entity_id": "clm_registry_claim1",
                "action": "add",
                "from_version": None,
                "to_version": 1,
                "occurred_at": now,
                "actor": "test",
                "details": {},
            },
        ],
    }


def test_registry_schema_is_versioned_and_validates_snapshot() -> None:
    schema = registry_snapshot_json_schema()
    snapshot = validate_registry_snapshot(_snapshot())

    assert schema["$id"].endswith("/1.0")
    assert snapshot.registry_version == "1.0"
    assert snapshot.claims[0].claim_key == "ast.is_leakage_enzyme"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("claim_id", "clm_registry_claim1", "claim_id values must be unique"),
        ("claim_key", "ast.is_leakage_enzyme", "claim_key values must be unique"),
    ],
)
def test_registry_rejects_duplicate_claim_identity(
    field: str, value: str, message: str
) -> None:
    raw = _snapshot()
    duplicate = deepcopy(raw["claims"][0])  # type: ignore[index]
    duplicate["claim_id"] = "clm_registry_claim2"
    duplicate["claim_key"] = "ast.second_claim"
    duplicate[field] = value
    duplicate["fact_payload"]["claim_id"] = duplicate["claim_id"]
    raw["claims"].append(duplicate)  # type: ignore[union-attr]

    with pytest.raises(RegistrySchemaError, match=message):
        validate_registry_snapshot(raw)


def test_registry_rejects_duplicate_knowledge_id() -> None:
    raw = _snapshot()
    duplicate = deepcopy(raw["knowledge"][0])  # type: ignore[index]
    duplicate["registry_key"] = "alt"
    raw["knowledge"].append(duplicate)  # type: ignore[union-attr]

    with pytest.raises(RegistrySchemaError, match="knowledge_id values must be unique"):
        validate_registry_snapshot(raw)


def test_registry_rejects_orphan_claim() -> None:
    raw = _snapshot()
    raw["claims"][0]["knowledge_id"] = "knw_registry_orphan"  # type: ignore[index]

    with pytest.raises(RegistrySchemaError, match="unknown knowledge_id"):
        validate_registry_snapshot(raw)


def test_registry_rejects_alias_cycle() -> None:
    raw = _snapshot()
    raw["alias_bindings"] = [
        {"alias": "got", "target": "旧ast"},
        {"alias": "旧ast", "target": "got"},
    ]

    with pytest.raises(RegistrySchemaError, match="alias cycle detected"):
        validate_registry_snapshot(raw)


def test_registry_rejects_history_version_ahead_of_current_entity() -> None:
    raw = _snapshot()
    raw["history"][0]["to_version"] = 2  # type: ignore[index]

    with pytest.raises(RegistrySchemaError, match="history version exceeds"):
        validate_registry_snapshot(raw)


def test_registry_rejects_missing_history() -> None:
    raw = _snapshot()
    raw["history"] = raw["history"][:1]  # type: ignore[index]

    with pytest.raises(RegistrySchemaError, match="history add event is missing"):
        validate_registry_snapshot(raw)


def test_registry_rejects_merge_redirect_without_deprecated_source() -> None:
    raw = _snapshot()
    duplicate = deepcopy(raw["claims"][0])  # type: ignore[index]
    duplicate["claim_id"] = "clm_registry_claim2"
    duplicate["claim_key"] = "ast.second_claim"
    duplicate["fact_payload"]["claim_id"] = duplicate["claim_id"]
    raw["claims"].append(duplicate)  # type: ignore[union-attr]
    now = datetime.now(UTC).isoformat()
    raw["history"].append(  # type: ignore[union-attr]
        {
            "event_id": "his_registry_event3",
            "entity_type": "claim",
            "entity_id": "clm_registry_claim2",
            "action": "add",
            "from_version": None,
            "to_version": 1,
            "occurred_at": now,
            "actor": "test",
            "details": {},
        }
    )
    raw["merge_redirects"] = [
        {
            "source_claim_id": "clm_registry_claim2",
            "source_claim_key": "ast.second_claim",
            "target_claim_id": "clm_registry_claim1",
            "target_claim_key": "ast.is_leakage_enzyme",
            "merged_at": now,
            "actor": "owner",
            "comment": "同義",
        }
    ]

    with pytest.raises(
        RegistrySchemaError, match="merged source claim must be deprecated"
    ):
        validate_registry_snapshot(raw)


def test_registry_rejects_deprecated_reference_without_merge_redirect() -> None:
    raw = _snapshot()
    deprecated = deepcopy(raw["claims"][0])  # type: ignore[index]
    deprecated["claim_id"] = "clm_registry_claim2"
    deprecated["claim_key"] = "ast.second_claim"
    deprecated["status"] = "deprecated"
    deprecated["fact_payload"]["claim_id"] = deprecated["claim_id"]
    raw["claims"].append(deprecated)  # type: ignore[union-attr]
    raw["claims"][0]["fact_payload"]["related_claim_ids"] = [  # type: ignore[index]
        "clm_registry_claim2"
    ]
    now = datetime.now(UTC).isoformat()
    raw["history"].extend(  # type: ignore[union-attr]
        [
            {
                "event_id": "his_registry_event3",
                "entity_type": "claim",
                "entity_id": "clm_registry_claim2",
                "action": "add",
                "from_version": None,
                "to_version": 1,
                "occurred_at": now,
                "actor": "test",
                "details": {},
            },
            {
                "event_id": "his_registry_event4",
                "entity_type": "claim",
                "entity_id": "clm_registry_claim2",
                "action": "deprecated",
                "from_version": 1,
                "to_version": 1,
                "occurred_at": now,
                "actor": "test",
                "details": {},
            },
        ]
    )

    with pytest.raises(RegistrySchemaError, match="no active merge target"):
        validate_registry_snapshot(raw)
