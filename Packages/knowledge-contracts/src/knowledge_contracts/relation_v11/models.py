"""Knowledge Relation Version 1.1 with relation-owned context.

Version 1.1 is additive: the stable Relation identity from 1.0 is retained and
qualifiers that only make sense between two Knowledge records live in context.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from knowledge_contracts.relation_v10.models import (
    KnowledgeRelationRecord as KnowledgeRelationRecordV10,
)
from knowledge_contracts.relation_v10.models import (
    KnowledgeId,
    LongText,
    RelationHistoryAction,
    RelationHistoryEvent,
    RelationResolutionStatus,
    RelationStatus,
    RelationType,
    RelationValidationReport,
    ShortText,
    StrictModel,
)


class RelationContext(StrictModel):
    """Meaning that applies to this connection, not either Knowledge record."""

    qualifiers: list[ShortText] = Field(min_length=0, max_length=20)
    preparation: LongText | None


class KnowledgeRelationRecord(KnowledgeRelationRecordV10):
    context: RelationContext


class KnowledgeRelationSnapshot(StrictModel):
    schema_version: Literal["1.1"] = "1.1"
    relations: list[KnowledgeRelationRecord] = Field(min_length=0, max_length=100000)
    history: list[RelationHistoryEvent] = Field(min_length=0, max_length=500000)

    @model_validator(mode="after")
    def validate_ledger(self) -> Self:
        relation_ids = [item.relation_id for item in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation_id values must be unique")
        semantic_keys = [
            (
                item.source_knowledge_id,
                item.relation_type,
                item.target_label.casefold(),
            )
            for item in self.relations
            if item.status != RelationStatus.DEPRECATED
        ]
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("active semantic relations must be unique")
        known_ids = set(relation_ids)
        unknown_history = sorted(
            {item.relation_id for item in self.history} - known_ids
        )
        if unknown_history:
            raise ValueError(
                "relation history references unknown relation_id: "
                + ", ".join(unknown_history)
            )
        return self


class KnowledgeRelationView(StrictModel):
    schema_version: Literal["1.1"] = "1.1"
    source_knowledge_id: KnowledgeId
    relations: list[KnowledgeRelationRecord]
    history: list[RelationHistoryEvent]
    validation: RelationValidationReport


__all__ = [
    "KnowledgeRelationRecord",
    "KnowledgeRelationSnapshot",
    "KnowledgeRelationView",
    "RelationContext",
    "RelationHistoryAction",
    "RelationHistoryEvent",
    "RelationResolutionStatus",
    "RelationStatus",
    "RelationType",
    "RelationValidationReport",
]
