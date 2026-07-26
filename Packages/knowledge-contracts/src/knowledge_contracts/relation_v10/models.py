"""Knowledge Relation Version 1.0 contracts.

Relations are independent assets that connect registered Knowledge records.
They deliberately do not modify Knowledge JSON or carry presentation data.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

RelationId = Annotated[
    str, StringConstraints(pattern=r"^rel_[a-z0-9][a-z0-9_-]{7,63}$")
]
KnowledgeId = Annotated[
    str, StringConstraints(pattern=r"^knw_[a-z0-9][a-z0-9_-]{7,63}$")
]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")]
EventId = Annotated[str, StringConstraints(pattern=r"^evt_[a-z0-9][a-z0-9_-]{7,63}$")]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationType(StrEnum):
    """Controlled vocabulary for the first Knowledge Network slice."""

    USES_SPECIMEN = "uses_specimen"
    USES_REAGENT = "uses_reagent"
    TARGETS_STRUCTURE = "targets_structure"
    RELATED_METHOD = "related_method"


class RelationResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved_relation"


class RelationStatus(StrEnum):
    DRAFT = "draft"
    OWNER_REVIEW = "owner_review"
    MEDICAL_REVIEW = "medical_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class RelationHistoryAction(StrEnum):
    ADD = "add"
    UPDATE = "update"
    DEPRECATE = "deprecated"


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


class RelationValidationReport(StrictModel):
    is_valid: bool
    relation_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    history_count: int = Field(ge=0)
    errors: list[ShortText] = Field(min_length=0, max_length=200)


class KnowledgeRelationSnapshot(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
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
    schema_version: Literal["1.0"] = "1.0"
    source_knowledge_id: KnowledgeId
    relations: list[KnowledgeRelationRecord]
    history: list[RelationHistoryEvent]
    validation: RelationValidationReport
