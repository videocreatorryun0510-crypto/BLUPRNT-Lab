"""Database-neutral Knowledge Registry boundary."""

from dataclasses import dataclass
from typing import Protocol

from knowledge_contracts.registry_v10 import (
    ClaimRegistryEntry,
    KnowledgeRegistryEntry,
    RegistryEntityType,
    RegistryKnowledgeView,
    RegistrySnapshot,
    RegistryStatus,
)
from knowledge_contracts.v10 import KnowledgeRecord


@dataclass(frozen=True)
class RegistryReconciliation:
    record: KnowledgeRecord
    view: RegistryKnowledgeView


class KnowledgeRegistry(Protocol):
    """SQLite and a future server database implement the same operations."""

    def reconcile(
        self,
        record: KnowledgeRecord,
        *,
        actor: str = "knowledge_workbench",
        note: str = "",
    ) -> RegistryReconciliation:
        """Reuse semantic keys and persist new claims before downstream use."""

    def snapshot(self) -> RegistrySnapshot:
        """Return a fully validated ledger snapshot."""

    def view(self, knowledge_id: str) -> RegistryKnowledgeView:
        """Return one Knowledge Dictionary with its history."""

    def record(self, knowledge_id: str) -> KnowledgeRecord | None:
        """Return the latest persisted Knowledge JSON document."""

    def resolve_claim_id(self, knowledge_id: str, claim_key: str) -> str | None:
        """Resolve a semantic claim_key to its stable internal claim_id."""

    def canonical_claim_id(self, claim_id: str) -> str | None:
        """Follow merge redirects while preserving the original ID ledger entry."""

    def merge_claims(
        self,
        knowledge_id: str,
        target_claim_id: str,
        source_claim_ids: list[str],
        *,
        actor: str,
        comment: str,
    ) -> RegistryKnowledgeView:
        """Deprecate source claims and redirect them to the unchanged target ID."""

    def transition_status(
        self,
        entity_type: RegistryEntityType,
        entity_id: str,
        status: RegistryStatus,
        *,
        actor: str,
        note: str = "",
    ) -> None:
        """Move Knowledge or Claim through the approval workflow."""

    def transition_claims_status(
        self,
        claim_ids: list[str],
        status: RegistryStatus,
        *,
        actor: str,
        note: str,
    ) -> RegistryKnowledgeView:
        """Move multiple claims atomically through one approval step."""

    def update_claim(
        self,
        claim_key: str,
        assertion: str,
        *,
        actor: str,
        semantic_change: bool,
        note: str = "",
    ) -> ClaimRegistryEntry:
        """Keep claim_key stable and bump version only for semantic change."""

    def deprecate_claim(self, claim_key: str, *, actor: str, note: str = "") -> None:
        """Keep the old claim in history while preventing new use."""

    def mark_claim_deleted(self, claim_key: str, *, actor: str, note: str = "") -> None:
        """Record a soft deletion without erasing history."""

    def add_alias(self, alias: str, target: str) -> KnowledgeRegistryEntry:
        """Add a directed knowledge alias and reject cycles."""

    def knowledge_by_id(self, knowledge_id: str) -> KnowledgeRegistryEntry | None:
        """Return a registry entry without resolving an alias."""
