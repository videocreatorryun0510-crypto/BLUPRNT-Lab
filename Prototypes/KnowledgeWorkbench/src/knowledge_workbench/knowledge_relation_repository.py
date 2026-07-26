"""Database-neutral boundary for the independent Knowledge Relation ledger."""

from dataclasses import dataclass
from typing import Protocol

from knowledge_contracts.registry_v10 import RegistrySnapshot
from knowledge_contracts.relation_growth_v10 import NetworkSummary, ResolutionReport
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationRecord,
    KnowledgeRelationSnapshot,
    KnowledgeRelationView,
    RelationContext,
    RelationResolutionStatus,
    RelationType,
)


@dataclass(frozen=True)
class RelationCandidate:
    relation_id: str
    source_knowledge_id: str
    target_knowledge_id: str | None
    target_label: str
    relation_type: RelationType
    claim_id: str
    resolution_status: RelationResolutionStatus
    context: RelationContext


@dataclass(frozen=True)
class RelationResolutionUpdate:
    relation_id: str
    target_knowledge_id: str
    target_label: str
    context: RelationContext


class KnowledgeRelationRepository(Protocol):
    """SQLite and a future server database implement the same operations."""

    def reconcile(
        self,
        source_knowledge_id: str,
        candidates: list[RelationCandidate],
        registry: RegistrySnapshot,
        *,
        actor: str,
        note: str,
    ) -> KnowledgeRelationView:
        """Persist the exact resolver output without inventing target Knowledge."""

    def snapshot(self) -> KnowledgeRelationSnapshot:
        """Return the fully validated Relation ledger."""

    def view(self, source_knowledge_id: str) -> KnowledgeRelationView:
        """Return Relations and history for one source Knowledge."""

    def find_unresolved_for_target(
        self,
        target_category: str,
        target_labels: list[str],
    ) -> list[KnowledgeRelationRecord]:
        """Use the Resolution Index to find only relevant unresolved Relations."""

    def resolve_indexed(
        self,
        target_knowledge_id: str,
        target_category: str,
        evaluated_relation_ids: list[str],
        updates: list[RelationResolutionUpdate],
        *,
        actor: str,
        note: str,
    ) -> ResolutionReport:
        """Resolve rows after the target Knowledge has been durably registered."""

    def resolution_reports(
        self, target_knowledge_id: str | None = None
    ) -> list[ResolutionReport]:
        """Return saved Knowledge-added resolution reports."""

    def network_summary(self, source_knowledge_id: str) -> NetworkSummary:
        """Return active outgoing Relation coverage without reading Knowledge JSON."""

    def ensure_schema(self) -> None:
        """Recreate Relation tables after restoring an older Registry backup."""
