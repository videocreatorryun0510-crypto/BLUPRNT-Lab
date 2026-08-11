"""Workbench-owned contracts for safe Authoring Draft promotion."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PromotionOperation(StrEnum):
    CREATE = "create"
    VERSION_UPDATE = "version_update"


class DraftDisposition(StrEnum):
    KEEP = "keep"
    ARCHIVE = "archive"


class PromotionCheck(StrictModel):
    code: str
    passed: bool
    message: str


class PromotionValidationReport(StrictModel):
    schema_valid: bool
    category_valid: bool
    claim_valid: bool
    reference_valid: bool
    registry_valid: bool
    fingerprint_valid: bool
    knowledge_id_valid: bool
    promotion_allowed: bool
    checks: list[PromotionCheck]


class PromotionPreview(StrictModel):
    preview_version: Literal["1.0"] = "1.0"
    preview_id: str
    draft_id: str
    created_at: datetime
    knowledge_name: str
    category: str
    claim_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    completeness_score: int = Field(ge=0, le=100)
    validation: PromotionValidationReport
    registry_key: str
    operation: PromotionOperation
    target_knowledge_id: str
    target_version: int = Field(ge=1)
    draft_fingerprint: str
    registry_fingerprint: str
    knowledge_fingerprint: str
    review_state: Literal["draft"] = "draft"


class CommitPromotionRequest(StrictModel):
    preview_id: str
    draft_disposition: DraftDisposition = DraftDisposition.KEEP
    actor: str = Field(default="knowledge_author", min_length=1, max_length=120)
    comment: str = Field(default="", max_length=500)


class PromotionResult(StrictModel):
    promotion_version: Literal["1.0"] = "1.0"
    promotion_id: str
    preview_id: str
    draft_id: str
    promoted_at: datetime
    operation: PromotionOperation
    registry_key: str
    knowledge_id: str
    knowledge_version: int = Field(ge=1)
    approval_state: Literal["draft"] = "draft"
    draft_disposition_requested: DraftDisposition
    draft_lifecycle_state: Literal["active", "archived"]
    registry_saved: Literal[True] = True
    fingerprint: str
    warnings: list[str] = Field(default_factory=list)


class PromotionLogEvent(StrictModel):
    log_version: Literal["1.0"] = "1.0"
    event_id: str
    occurred_at: datetime
    event_type: Literal["preview", "promotion"]
    status: Literal["ready", "blocked", "success", "failed"]
    draft_id: str
    preview_id: str | None
    promotion_id: str | None
    registry_key: str
    operation: PromotionOperation
    knowledge_id: str
    knowledge_version: int
    approval_state: Literal["draft"] | None
    actor: str
    reason_codes: list[str] = Field(default_factory=list)
