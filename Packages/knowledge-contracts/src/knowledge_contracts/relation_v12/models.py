"""Knowledge Relation Version 1.2 with Disease vocabulary support.

Version 1.2 is additive. Versions 1.0 and 1.1 remain immutable so saved
Relations keep the exact contract under which they were created.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from knowledge_contracts.relation_v10.models import (
    ClaimId,
    EventId,
    KnowledgeId,
    LongText,
    RelationId,
    RelationHistoryAction,
    RelationResolutionStatus,
    RelationStatus,
    RelationValidationReport,
    ShortText,
    StrictModel,
)
from knowledge_contracts.relation_v11.models import RelationContext


class RelationType(StrEnum):
    USES_SPECIMEN = "uses_specimen"
    USES_REAGENT = "uses_reagent"
    TARGETS_STRUCTURE = "targets_structure"
    RELATED_METHOD = "related_method"
    HAS_HIGH_TEST_ITEM = "has_high_test_item"
    HAS_LOW_TEST_ITEM = "has_low_test_item"
    DIAGNOSED_BY = "diagnosed_by"
    CAUSED_BY = "caused_by"
    RELATED_DISEASE = "related_disease"
    AFFECTS_STRUCTURE = "affects_structure"
    HAS_PATHOPHYSIOLOGY = "has_pathophysiology"


class KnowledgeRelationRecord(StrictModel):
    relation_id: RelationId
    source_knowledge_id: KnowledgeId
    target_knowledge_id: KnowledgeId | None
    target_label: ShortText
    relation_type: RelationType
    claim_id: ClaimId
    resolution_status: RelationResolutionStatus
    status: RelationStatus
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    context: RelationContext

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if self.resolution_status == RelationResolutionStatus.RESOLVED:
            if self.target_knowledge_id is None:
                raise ValueError("resolved relation requires target_knowledge_id")
            if self.source_knowledge_id == self.target_knowledge_id:
                raise ValueError("a relation cannot target its source Knowledge")
        elif self.target_knowledge_id is not None:
            raise ValueError("unresolved_relation must not contain target_knowledge_id")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class RelationHistoryEvent(StrictModel):
    event_id: EventId
    relation_id: RelationId
    action: RelationHistoryAction
    from_version: int | None = Field(ge=1)
    to_version: int = Field(ge=1)
    occurred_at: datetime
    actor: ShortText
    note: LongText

    @model_validator(mode="after")
    def validate_versions(self) -> Self:
        if self.action == RelationHistoryAction.ADD:
            if self.from_version is not None or self.to_version != 1:
                raise ValueError("add history must create version 1")
        elif self.from_version is None or self.to_version != self.from_version + 1:
            raise ValueError("relation update history must advance exactly one version")
        return self


class KnowledgeRelationSnapshot(StrictModel):
    schema_version: Literal["1.2"] = "1.2"
    relations: list[KnowledgeRelationRecord] = Field(min_length=0, max_length=100000)
    history: list[RelationHistoryEvent] = Field(min_length=0, max_length=500000)

    @model_validator(mode="after")
    def validate_ledger(self) -> Self:
        relation_ids = [item.relation_id for item in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation_id values must be unique")
        semantic_keys = [
            (item.source_knowledge_id, item.relation_type, item.target_label.casefold())
            for item in self.relations
            if item.status != RelationStatus.DEPRECATED
        ]
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("active semantic relations must be unique")
        unknown_history = sorted(
            {item.relation_id for item in self.history} - set(relation_ids)
        )
        if unknown_history:
            raise ValueError(
                "relation history references unknown relation_id: "
                + ", ".join(unknown_history)
            )
        return self


class KnowledgeRelationView(StrictModel):
    schema_version: Literal["1.2"] = "1.2"
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
