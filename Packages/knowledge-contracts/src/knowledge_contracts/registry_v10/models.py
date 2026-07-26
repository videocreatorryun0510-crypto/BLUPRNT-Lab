"""Knowledge Registry Version 1.0 contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import Field, StringConstraints, model_validator

from knowledge_contracts.v10.models import (
    ClaimId,
    KnowledgeId,
    MediumText,
    ShortText,
    StrictModel,
)

ClaimKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9]*(?:\.[a-z0-9_]+)+$",
        max_length=180,
    ),
]
HistoryEventId = Annotated[
    str, StringConstraints(pattern=r"^his_[a-z0-9][a-z0-9_-]{7,63}$")
]


class RegistryStatus(StrEnum):
    DRAFT = "draft"
    OWNER_REVIEW = "owner_review"
    MEDICAL_REVIEW = "medical_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


ApprovalState = RegistryStatus


class RegistryEntityType(StrEnum):
    KNOWLEDGE = "knowledge"
    CLAIM = "claim"


class RegistryHistoryAction(StrEnum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    DEPRECATED = "deprecated"
    STATUS_CHANGE = "status_change"
    MERGE = "merge"


class ApprovalDecision(StrictModel):
    status: RegistryStatus
    actor: ShortText
    decided_at: datetime
    note: str = Field(max_length=1000)


class RegistryAliasBinding(StrictModel):
    alias: ShortText
    target: ShortText


class ClaimMergeRedirect(StrictModel):
    source_claim_id: ClaimId
    source_claim_key: ClaimKey
    target_claim_id: ClaimId
    target_claim_key: ClaimKey
    merged_at: datetime
    actor: ShortText
    comment: str = Field(min_length=1, max_length=1000)


class ClaimMergeCandidate(StrictModel):
    source_claim_id: ClaimId
    source_claim_key: ClaimKey
    target_claim_id: ClaimId
    target_claim_key: ClaimKey
    similarity_score: int = Field(ge=0, le=100)
    reason: ShortText


class ClaimRegistryEntry(StrictModel):
    knowledge_id: KnowledgeId
    claim_id: ClaimId
    claim_key: ClaimKey
    claim_version: int = Field(ge=1)
    field_path: ShortText
    assertion: MediumText
    status: RegistryStatus
    created_at: datetime
    updated_at: datetime
    aliases: list[MediumText] = Field(min_length=0, max_length=100)
    approval: list[ApprovalDecision] = Field(min_length=0, max_length=100)
    fact_payload: dict[str, Any]
    is_deleted: bool = False

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("claim aliases must be unique")
        if self.fact_payload.get("claim_id") != self.claim_id:
            raise ValueError("fact_payload.claim_id must match claim_id")
        return self


class KnowledgeRegistryEntry(StrictModel):
    knowledge_id: KnowledgeId
    registry_key: ShortText
    canonical_name: ShortText
    knowledge_version: int = Field(ge=1)
    status: RegistryStatus
    created_at: datetime
    updated_at: datetime
    aliases: list[ShortText] = Field(min_length=0, max_length=100)
    approval: list[ApprovalDecision] = Field(min_length=0, max_length=100)

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        normalized = [_normalized(item) for item in self.aliases]
        if len(normalized) != len(set(normalized)):
            raise ValueError("knowledge aliases must be unique")
        return self


class RegistryHistoryEvent(StrictModel):
    event_id: HistoryEventId
    entity_type: RegistryEntityType
    entity_id: ShortText
    action: RegistryHistoryAction
    from_version: int | None = Field(ge=1)
    to_version: int | None = Field(ge=1)
    occurred_at: datetime
    actor: ShortText
    details: dict[str, str]

    @model_validator(mode="after")
    def validate_versions(self) -> Self:
        if (
            self.from_version is not None
            and self.to_version is not None
            and self.to_version < self.from_version
        ):
            raise ValueError("history to_version must not be less than from_version")
        return self


class RegistrySnapshot(StrictModel):
    registry_version: str = Field(pattern=r"^1\.0$")
    knowledge: list[KnowledgeRegistryEntry]
    claims: list[ClaimRegistryEntry]
    alias_bindings: list[RegistryAliasBinding]
    merge_redirects: list[ClaimMergeRedirect] = Field(default_factory=list)
    history: list[RegistryHistoryEvent]

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        _require_unique([item.knowledge_id for item in self.knowledge], "knowledge_id")
        _require_unique(
            [_normalized(item.registry_key) for item in self.knowledge],
            "registry_key",
        )
        _require_unique([item.claim_id for item in self.claims], "claim_id")
        _require_unique([item.claim_key for item in self.claims], "claim_key")
        knowledge_ids = {item.knowledge_id for item in self.knowledge}
        unknown_claim_owners = sorted(
            {item.knowledge_id for item in self.claims} - knowledge_ids
        )
        if unknown_claim_owners:
            raise ValueError(
                "claims reference unknown knowledge_id values: "
                + ", ".join(unknown_claim_owners)
            )
        self._validate_aliases()
        self._validate_merge_redirects()
        self._validate_claim_references()
        self._validate_history_versions()
        self._validate_history_completeness()
        return self

    def _validate_aliases(self) -> None:
        aliases: dict[str, str] = {}
        canonical = {_normalized(item.registry_key) for item in self.knowledge}
        for binding in self.alias_bindings:
            alias = _normalized(binding.alias)
            target = _normalized(binding.target)
            if alias in aliases:
                raise ValueError(f"alias values must be unique: {binding.alias}")
            if alias in canonical:
                raise ValueError(f"alias must not shadow registry_key: {binding.alias}")
            aliases[alias] = target
        for alias in aliases:
            seen: set[str] = set()
            current = alias
            while current not in canonical:
                if current in seen:
                    raise ValueError(f"alias cycle detected: {alias}")
                seen.add(current)
                next_target = aliases.get(current)
                if next_target is None:
                    raise ValueError(f"alias target cannot be resolved: {current}")
                current = next_target

    def _validate_history_versions(self) -> None:
        current_versions = {
            (RegistryEntityType.KNOWLEDGE, item.knowledge_id): item.knowledge_version
            for item in self.knowledge
        }
        current_versions.update(
            {
                (RegistryEntityType.CLAIM, item.claim_id): item.claim_version
                for item in self.claims
            }
        )
        for event in self.history:
            current = current_versions.get((event.entity_type, event.entity_id))
            if current is None:
                if event.action != RegistryHistoryAction.DELETE:
                    raise ValueError(
                        f"history references unknown entity: {event.entity_id}"
                    )
                continue
            if event.to_version is not None and event.to_version > current:
                raise ValueError(
                    f"history version exceeds current entity version: {event.entity_id}"
                )

    def _validate_merge_redirects(self) -> None:
        claims = {item.claim_id: item for item in self.claims}
        redirects: dict[str, str] = {}
        for redirect in self.merge_redirects:
            if redirect.source_claim_id in redirects:
                raise ValueError(
                    "merge source_claim_id values must be unique: "
                    + redirect.source_claim_id
                )
            source = claims.get(redirect.source_claim_id)
            target = claims.get(redirect.target_claim_id)
            if source is None or target is None:
                raise ValueError("merge redirect references an unknown claim_id")
            if source.claim_key != redirect.source_claim_key:
                raise ValueError("merge source_claim_key does not match Registry")
            if target.claim_key != redirect.target_claim_key:
                raise ValueError("merge target_claim_key does not match Registry")
            if source.knowledge_id != target.knowledge_id:
                raise ValueError(
                    "claims from different knowledge_id values cannot merge"
                )
            if source.claim_id == target.claim_id:
                raise ValueError("merge source and target must be different claims")
            if source.status != RegistryStatus.DEPRECATED:
                raise ValueError("merged source claim must be deprecated")
            if target.status == RegistryStatus.DEPRECATED or target.is_deleted:
                raise ValueError("merge target claim must remain active")
            redirects[source.claim_id] = target.claim_id

        for source_id in redirects:
            seen: set[str] = set()
            current = source_id
            while current in redirects:
                if current in seen:
                    raise ValueError(f"claim merge cycle detected: {source_id}")
                seen.add(current)
                current = redirects[current]

    def _validate_claim_references(self) -> None:
        claims = {item.claim_id: item for item in self.claims}
        redirects = {
            item.source_claim_id: item.target_claim_id for item in self.merge_redirects
        }
        for claim in self.claims:
            if claim.is_deleted:
                continue
            for reference in _referenced_claim_ids(claim.fact_payload):
                target = claims.get(reference)
                if target is None:
                    raise ValueError(
                        f"claim reference points to an unknown claim_id: {reference}"
                    )
                if target.status != RegistryStatus.DEPRECATED:
                    continue
                resolved = _resolve_claim_redirect(reference, redirects)
                resolved_claim = claims.get(resolved)
                if (
                    resolved_claim is None
                    or resolved_claim.status == RegistryStatus.DEPRECATED
                    or resolved_claim.is_deleted
                ):
                    raise ValueError(
                        f"deprecated claim reference has no active merge target: {reference}"
                    )

    def _validate_history_completeness(self) -> None:
        events: dict[tuple[RegistryEntityType, str], list[RegistryHistoryEvent]] = {}
        for event in self.history:
            events.setdefault((event.entity_type, event.entity_id), []).append(event)

        entities: list[tuple[RegistryEntityType, str, int, RegistryStatus, bool]] = [
            (
                RegistryEntityType.KNOWLEDGE,
                item.knowledge_id,
                item.knowledge_version,
                item.status,
                False,
            )
            for item in self.knowledge
        ]
        entities.extend(
            (
                RegistryEntityType.CLAIM,
                item.claim_id,
                item.claim_version,
                item.status,
                item.is_deleted,
            )
            for item in self.claims
        )
        merged_sources = {item.source_claim_id for item in self.merge_redirects}
        for entity_type, entity_id, version, status, is_deleted in entities:
            entity_events = events.get((entity_type, entity_id), [])
            if not any(
                item.action == RegistryHistoryAction.ADD for item in entity_events
            ):
                raise ValueError(f"history add event is missing: {entity_id}")
            recorded_versions = [
                item.to_version for item in entity_events if item.to_version is not None
            ]
            if not recorded_versions or max(recorded_versions) != version:
                raise ValueError(f"history does not reach current version: {entity_id}")
            if is_deleted and not any(
                item.action == RegistryHistoryAction.DELETE for item in entity_events
            ):
                raise ValueError(f"delete history is missing: {entity_id}")
            if status == RegistryStatus.DEPRECATED and not any(
                item.action
                in {
                    RegistryHistoryAction.DEPRECATED,
                    RegistryHistoryAction.MERGE,
                    RegistryHistoryAction.STATUS_CHANGE,
                }
                for item in entity_events
            ):
                raise ValueError(f"deprecated history is missing: {entity_id}")
            if entity_id in merged_sources and not any(
                item.action == RegistryHistoryAction.MERGE for item in entity_events
            ):
                raise ValueError(f"merge history is missing: {entity_id}")


class RegistryValidationReport(StrictModel):
    is_valid: bool
    knowledge_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    alias_count: int = Field(ge=0)
    merge_redirect_count: int = Field(ge=0)
    history_count: int = Field(ge=0)
    errors: list[str]


class RegistryKnowledgeView(StrictModel):
    knowledge: KnowledgeRegistryEntry
    claims: list[ClaimRegistryEntry]
    merge_redirects: list[ClaimMergeRedirect]
    merge_candidates: list[ClaimMergeCandidate]
    history: list[RegistryHistoryEvent]
    validation: RegistryValidationReport


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} values must be unique")


def _normalized(value: str) -> str:
    return "".join(value.strip().casefold().split())


def _referenced_claim_ids(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_claim_ids") and isinstance(child, list):
                references.extend(str(item) for item in child if isinstance(item, str))
            else:
                references.extend(_referenced_claim_ids(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_referenced_claim_ids(child))
    return references


def _resolve_claim_redirect(claim_id: str, redirects: dict[str, str]) -> str:
    current = claim_id
    seen: set[str] = set()
    while current in redirects:
        if current in seen:
            return current
        seen.add(current)
        current = redirects[current]
    return current
