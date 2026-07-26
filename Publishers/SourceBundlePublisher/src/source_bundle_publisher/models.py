"""Versioned Source Bundle JSON contracts."""

from datetime import datetime
from typing import Annotated, Literal, Self

from knowledge_contracts.approval_v10 import ApprovalState
from knowledge_contracts.registry_v10 import ClaimKey, RegistryStatus
from knowledge_contracts.v10 import EvidenceReference
from knowledge_contracts.v10.models import ClaimId, KnowledgeId, ShortText
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
StableId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9_]+)+$",
        max_length=180,
    ),
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceBundleClaim(FrozenModel):
    """An unchanged Registry claim prepared for downstream selection."""

    claim_id: ClaimId
    claim_key: ClaimKey
    field_path: str
    assertion: NonEmptyText


class ExamPoint(FrozenModel):
    """Exam Metadata projected without creating new medical prose."""

    claim_id: ClaimId
    claim_key: ClaimKey
    assertion: NonEmptyText
    priority: Literal["highest", "important", "supplementary"]
    evidence_occurrence_ids: tuple[str, ...] = ()


class DiagramRequest(FrozenModel):
    """Publisher-owned request; it contains no rendered image or provider prompt."""

    request_id: StableId
    diagram_type: StableId
    title: NonEmptyText
    learning_goal: NonEmptyText
    source_claim_ids: tuple[ClaimId, ...] = Field(min_length=1, max_length=30)


class SourceBundleMetadata(FrozenModel):
    source_bundle_schema_version: Literal["1.0"]
    knowledge_id: KnowledgeId
    version: int = Field(ge=1)
    category: Literal[
        "test_item",
        "staining_method",
        "specimen",
        "reagent",
        "biological_structure",
        "disease",
        "laboratory_test_item",
    ]
    status: RegistryStatus
    publisher_version: Literal["1.0.0", "1.1.0"]
    generated_at: datetime
    source_fingerprint: Annotated[
        str, StringConstraints(pattern=r"^[a-f0-9]{64}$")
    ]
    approval_state: ApprovalState = ApprovalState.DRAFT
    approved_at: datetime | None = None
    approved_by: ShortText | None = None
    review_version: int = Field(default=1, ge=1)
    review_required: bool = True


class SourceBundle(FrozenModel):
    schema_version: Literal["1.0"]
    title: NonEmptyText
    summary: NonEmptyText
    learning_objective: NonEmptyText
    target_audience: NonEmptyText
    claims: tuple[SourceBundleClaim, ...] = Field(min_length=1, max_length=500)
    key_messages: tuple[SourceBundleClaim, ...] = Field(min_length=1, max_length=30)
    exam_points: tuple[ExamPoint, ...] = Field(max_length=100)
    diagram_requests: tuple[DiagramRequest, ...] = Field(max_length=20)
    references: tuple[EvidenceReference, ...] = Field(max_length=500)
    metadata: SourceBundleMetadata

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        claim_ids = {item.claim_id for item in self.claims}
        if not {item.claim_id for item in self.key_messages}.issubset(claim_ids):
            raise ValueError("key_messages must reference claims in this Source Bundle")
        if not {item.claim_id for item in self.exam_points}.issubset(claim_ids):
            raise ValueError("exam_points must reference claims in this Source Bundle")
        for request in self.diagram_requests:
            unknown = set(request.source_claim_ids) - claim_ids
            if unknown:
                raise ValueError(
                    "diagram_requests contain unknown source_claim_ids: "
                    + ", ".join(sorted(unknown))
                )
        return self


class DiagramRequestProfile(FrozenModel):
    request_id: StableId
    diagram_type: StableId
    title: NonEmptyText
    learning_goal: NonEmptyText
    source_claim_keys: tuple[ClaimKey, ...] = Field(min_length=1, max_length=30)


class SourceBundleProfile(FrozenModel):
    profile_id: StableId
    profile_version: Literal["1.0"]
    knowledge_id: KnowledgeId
    summary_claim_key: ClaimKey
    learning_objective: NonEmptyText
    target_audience: NonEmptyText
    key_claim_keys: tuple[ClaimKey, ...] = Field(min_length=1, max_length=30)
    diagram_requests: tuple[DiagramRequestProfile, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def require_unique_profile_references(self) -> Self:
        if len(self.key_claim_keys) != len(set(self.key_claim_keys)):
            raise ValueError("key_claim_keys must be unique")
        request_ids = [item.request_id for item in self.diagram_requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("diagram request_id values must be unique")
        return self


def source_bundle_json_schema() -> dict[str, object]:
    return SourceBundle.model_json_schema(mode="serialization")
