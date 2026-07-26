"""Deterministic string-to-Knowledge Relation resolver.

The resolver uses exact Registry labels first. For ``uses_specimen`` only, it
may split a registered specimen name from the end of the source label and keep
the preceding words as Relation Context. It never calls AI or fuzzy matching.
"""

import hashlib
import unicodedata
from dataclasses import dataclass

from knowledge_contracts.registry_v10 import RegistrySnapshot
from knowledge_contracts.relation_v11 import (
    RelationContext,
    RelationResolutionStatus,
    RelationType,
)
from knowledge_contracts.v10 import KnowledgeRecord, StainingMethodCategoryContent

from knowledge_workbench.knowledge_relation_repository import RelationCandidate


@dataclass(frozen=True)
class _RegistryTarget:
    knowledge_id: str
    canonical_name: str


def resolve_knowledge_relations(
    record: KnowledgeRecord,
    registry: RegistrySnapshot,
    target_records: list[KnowledgeRecord] | None = None,
) -> list[RelationCandidate]:
    """Resolve explicit category strings against existing Registry Knowledge."""

    content = record.category_content
    if not isinstance(content, StainingMethodCategoryContent):
        return []

    raw_relations: list[tuple[RelationType, str, str, RelationContext]] = []
    staining = content.staining_method
    raw_relations.extend(
        (
            RelationType.USES_SPECIMEN,
            item.specimen,
            item.claim_id,
            RelationContext(qualifiers=[], preparation=item.preparation),
        )
        for item in staining.applicable_specimens
    )
    empty_context = RelationContext(qualifiers=[], preparation=None)
    raw_relations.extend(
        (RelationType.USES_REAGENT, item.reagent_name, item.claim_id, empty_context)
        for item in staining.reagents
    )
    raw_relations.extend(
        (RelationType.TARGETS_STRUCTURE, item.target_name, item.claim_id, empty_context)
        for item in staining.target_structures
    )
    raw_relations.extend(
        (RelationType.RELATED_METHOD, item.method_name, item.claim_id, empty_context)
        for item in staining.related_methods
    )

    exact_index = _registry_name_index(registry)
    specimen_targets = _specimen_targets(target_records or [])
    candidates: list[RelationCandidate] = []
    seen: set[tuple[RelationType, str]] = set()
    for relation_type, source_label, claim_id, context in raw_relations:
        normalized_source_label = _normalize(source_label)
        semantic_key = relation_type, normalized_source_label
        if semantic_key in seen:
            continue
        seen.add(semantic_key)

        target = exact_index.get(normalized_source_label)
        resolved_context = context
        if target is None and relation_type == RelationType.USES_SPECIMEN:
            suffix_match = _registered_specimen_suffix(source_label, specimen_targets)
            if suffix_match is not None:
                target, qualifier = suffix_match
                if qualifier:
                    resolved_context = context.model_copy(update={"qualifiers": [qualifier]})

        if target is not None and target.knowledge_id == record.knowledge_id:
            target = None
        target_id = target.knowledge_id if target is not None else None
        resolution_status = (
            RelationResolutionStatus.RESOLVED
            if target_id is not None
            else RelationResolutionStatus.UNRESOLVED
        )
        candidates.append(
            RelationCandidate(
                relation_id=_stable_relation_id(
                    record.knowledge_id, relation_type, normalized_source_label
                ),
                source_knowledge_id=record.knowledge_id,
                target_knowledge_id=target_id,
                target_label=(target.canonical_name if target is not None else source_label),
                relation_type=relation_type,
                claim_id=claim_id,
                resolution_status=resolution_status,
                context=resolved_context,
            )
        )
    return sorted(candidates, key=lambda item: item.relation_id)


def _registry_name_index(snapshot: RegistrySnapshot) -> dict[str, _RegistryTarget]:
    index: dict[str, _RegistryTarget] = {}
    ambiguous: set[str] = set()
    for knowledge in snapshot.knowledge:
        target = _RegistryTarget(
            knowledge_id=knowledge.knowledge_id,
            canonical_name=knowledge.canonical_name,
        )
        for label in [knowledge.canonical_name, *knowledge.aliases]:
            normalized = _normalize(label)
            existing = index.get(normalized)
            if existing is not None and existing.knowledge_id != knowledge.knowledge_id:
                ambiguous.add(normalized)
            else:
                index[normalized] = target
    for label in ambiguous:
        index.pop(label, None)
    return index


def _specimen_targets(records: list[KnowledgeRecord]) -> list[_RegistryTarget]:
    return [
        _RegistryTarget(
            knowledge_id=item.knowledge_id,
            canonical_name=item.term.canonical_name,
        )
        for item in records
        if item.classification.term_type == "specimen"
    ]


def _registered_specimen_suffix(
    source_label: str,
    specimen_targets: list[_RegistryTarget],
) -> tuple[_RegistryTarget, str] | None:
    normalized_source = _normalize(source_label)
    matches = [
        item
        for item in specimen_targets
        if normalized_source.endswith(_normalize(item.canonical_name))
    ]
    if not matches:
        return None
    longest = max(len(_normalize(item.canonical_name)) for item in matches)
    longest_matches = [item for item in matches if len(_normalize(item.canonical_name)) == longest]
    if len(longest_matches) != 1:
        return None
    target = longest_matches[0]
    qualifier = _prefix_before_suffix(source_label, target.canonical_name)
    return target, qualifier


def _prefix_before_suffix(source_label: str, suffix: str) -> str:
    normalized_source = unicodedata.normalize("NFKC", source_label).strip()
    normalized_suffix = unicodedata.normalize("NFKC", suffix).strip()
    if not normalized_source.endswith(normalized_suffix):
        return ""
    return normalized_source[: -len(normalized_suffix)].strip(" ・、")


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _stable_relation_id(
    source_knowledge_id: str, relation_type: RelationType, normalized_label: str
) -> str:
    identity = f"{source_knowledge_id}|{relation_type.value}|{normalized_label}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"rel_{digest}"
