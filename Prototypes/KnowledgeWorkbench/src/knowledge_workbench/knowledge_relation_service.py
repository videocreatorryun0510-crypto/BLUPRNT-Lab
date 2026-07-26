"""Application service that synchronizes and incrementally grows Relations."""

import unicodedata
from dataclasses import replace

from knowledge_contracts.relation_growth_v10 import ResolutionReport
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationRecord,
    KnowledgeRelationView,
    RelationResolutionStatus,
    RelationType,
)
from knowledge_contracts.v10 import KnowledgeRecord

from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.knowledge_relation_repository import (
    KnowledgeRelationRepository,
    RelationResolutionUpdate,
)
from knowledge_workbench.knowledge_relation_resolver import (
    resolve_knowledge_relations,
)


class KnowledgeRelationService:
    """Keep relation resolution outside Knowledge and Publisher responsibilities."""

    def __init__(
        self,
        registry: KnowledgeRegistry,
        repository: KnowledgeRelationRepository,
    ) -> None:
        self.registry = registry
        self.repository = repository

    def synchronize(
        self,
        record: KnowledgeRecord,
        *,
        actor: str,
        note: str,
    ) -> KnowledgeRelationView:
        snapshot = self.registry.snapshot()
        existing = {
            item.relation_id: item
            for item in self.repository.view(record.knowledge_id).relations
        }
        candidates = resolve_knowledge_relations(
            record,
            snapshot,
        )
        candidates = [
            replace(
                candidate,
                target_knowledge_id=existing[candidate.relation_id].target_knowledge_id,
                target_label=existing[candidate.relation_id].target_label,
                resolution_status=RelationResolutionStatus.RESOLVED,
                context=existing[candidate.relation_id].context,
            )
            if (
                candidate.resolution_status == RelationResolutionStatus.UNRESOLVED
                and candidate.relation_id in existing
                and existing[candidate.relation_id].resolution_status
                == RelationResolutionStatus.RESOLVED
            )
            else candidate
            for candidate in candidates
        ]
        return self.repository.reconcile(
            record.knowledge_id,
            candidates,
            snapshot,
            actor=actor,
            note=note,
        )

    def resolve_for_target(
        self,
        target: KnowledgeRecord,
        *,
        actor: str,
        note: str,
    ) -> ResolutionReport:
        """Re-evaluate only unresolved rows selected by the Resolution Index."""

        target_category = str(target.classification.term_type)
        target_labels = [target.term.canonical_name, *target.term.aliases]
        indexed = self.repository.find_unresolved_for_target(
            target_category,
            target_labels,
        )
        updates: list[RelationResolutionUpdate] = []
        for relation in indexed:
            resolved = _match_indexed_relation(relation, target, target_labels)
            if resolved is not None:
                updates.append(resolved)
        return self.repository.resolve_indexed(
            target.knowledge_id,
            target_category,
            [item.relation_id for item in indexed],
            updates,
            actor=actor,
            note=note,
        )


def _match_indexed_relation(
    relation: KnowledgeRelationRecord,
    target: KnowledgeRecord,
    target_labels: list[str],
) -> RelationResolutionUpdate | None:
    source_label = _normalize(relation.target_label)
    normalized_targets = sorted(
        {_normalize(item): item.strip() for item in target_labels if item.strip()}.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    exact = next(
        (
            display
            for normalized, display in normalized_targets
            if source_label == normalized
        ),
        None,
    )
    qualifier = ""
    if exact is None and relation.relation_type == RelationType.USES_SPECIMEN:
        suffixes = [
            (normalized, display)
            for normalized, display in normalized_targets
            if source_label.endswith(normalized)
        ]
        if suffixes:
            longest = len(suffixes[0][0])
            longest_matches = [item for item in suffixes if len(item[0]) == longest]
            if len(longest_matches) == 1:
                normalized_suffix, exact = longest_matches[0]
                qualifier = source_label[: -len(normalized_suffix)].strip(" ・、")
    if exact is None or relation.source_knowledge_id == target.knowledge_id:
        return None
    qualifiers = list(relation.context.qualifiers)
    if qualifier and qualifier not in qualifiers:
        qualifiers.append(qualifier)
    return RelationResolutionUpdate(
        relation_id=relation.relation_id,
        target_knowledge_id=target.knowledge_id,
        target_label=target.term.canonical_name,
        context=relation.context.model_copy(update={"qualifiers": qualifiers}),
    )


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
