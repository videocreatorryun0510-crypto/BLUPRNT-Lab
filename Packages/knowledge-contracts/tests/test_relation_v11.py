from datetime import UTC, datetime

from knowledge_contracts.relation_v11 import (
    KnowledgeRelationRecord,
    KnowledgeRelationSnapshot,
    RelationContext,
    knowledge_relation_json_schema,
    validate_knowledge_relation_snapshot,
)


def test_relation_v11_adds_context_without_knowledge_content() -> None:
    now = datetime.now(UTC)
    snapshot = KnowledgeRelationSnapshot(
        relations=[
            KnowledgeRelationRecord(
                relation_id="rel_context001",
                source_knowledge_id="knw_source001",
                target_knowledge_id="knw_target001",
                target_label="塗抹標本",
                relation_type="uses_specimen",
                claim_id="clm_source001",
                resolution_status="resolved",
                status="draft",
                version=2,
                context=RelationContext(
                    qualifiers=["細菌を含む"],
                    preparation="薄く均一に塗抹する。",
                ),
                created_at=now,
                updated_at=now,
            )
        ],
        history=[],
    )

    validated = validate_knowledge_relation_snapshot(snapshot)
    schema = knowledge_relation_json_schema()

    assert validated.schema_version == "1.1"
    assert validated.relations[0].context.qualifiers == ["細菌を含む"]
    assert schema["$id"].endswith("/1.1")
