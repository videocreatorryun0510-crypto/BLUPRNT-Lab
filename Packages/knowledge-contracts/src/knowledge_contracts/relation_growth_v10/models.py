"""Contracts for indexed Knowledge Relation growth operations."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from knowledge_contracts.relation_v10.models import KnowledgeId, RelationId, StrictModel

ReportId = Annotated[
    str, StringConstraints(pattern=r"^rpt_[a-z0-9][a-z0-9_-]{7,63}$")
]
CategoryName = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,63}$")
]


class ResolutionReport(StrictModel):
    """Durable result of one Knowledge-added resolution event."""

    schema_version: Literal["1.0"] = "1.0"
    report_id: ReportId
    target_knowledge_id: KnowledgeId
    target_category: CategoryName
    evaluated_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    evaluated_relation_ids: list[RelationId] = Field(min_length=0, max_length=100000)
    resolved_relation_ids: list[RelationId] = Field(min_length=0, max_length=100000)
    unresolved_relation_ids: list[RelationId] = Field(min_length=0, max_length=100000)
    created_at: datetime
    actor: str = Field(min_length=1, max_length=180)
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_counts(self) -> "ResolutionReport":
        if self.evaluated_count != len(self.evaluated_relation_ids):
            raise ValueError("evaluated_count must match evaluated_relation_ids")
        if self.resolved_count != len(self.resolved_relation_ids):
            raise ValueError("resolved_count must match resolved_relation_ids")
        if self.unresolved_count != len(self.unresolved_relation_ids):
            raise ValueError("unresolved_count must match unresolved_relation_ids")
        if self.evaluated_count != self.resolved_count + self.unresolved_count:
            raise ValueError("evaluated_count must equal resolved plus unresolved")
        if set(self.resolved_relation_ids) & set(self.unresolved_relation_ids):
            raise ValueError("resolved and unresolved relation IDs must not overlap")
        if set(self.evaluated_relation_ids) != (
            set(self.resolved_relation_ids) | set(self.unresolved_relation_ids)
        ):
            raise ValueError("evaluated relation IDs must equal the report outcome IDs")
        return self


class NetworkSummary(StrictModel):
    """Information coverage of outgoing active Relations for one Knowledge."""

    schema_version: Literal["1.0"] = "1.0"
    knowledge_id: KnowledgeId
    relation_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    network_completeness: float = Field(ge=0, le=100)


__all__ = ["NetworkSummary", "ResolutionReport"]
