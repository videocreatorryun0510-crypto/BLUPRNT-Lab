"""Deterministic Claim-to-Concept mapping without medical inference."""

import hashlib
import json
from dataclasses import dataclass
from itertools import pairwise

from knowledge_contracts.registry_v10 import ClaimRegistryEntry, RegistryStatus

from publisher_core.models import (
    ClaimMatchCriterion,
    ClaimReference,
    ConceptClaimMappingRule,
    ConceptRequirement,
    PlannedDiagramIntent,
    PlannedDiagramTaxonomy,
    ProfileReference,
    PublicationPlan,
    SemanticSequence,
)
from publisher_core.semantic_blueprint import (
    BlueprintConcept,
    BlueprintSemanticRelation,
    ConceptResolutionStatus,
    MappedClaim,
    MissingConceptOrigin,
    MissingConceptReason,
    MissingConceptReport,
    SemanticBlueprint,
    SemanticBlueprintBundle,
)
from publisher_core.source import PublicationSourceBundle, publication_source_fingerprint


class ClaimMappingError(ValueError):
    """Raised when source identity or Diagram Intent contracts are inconsistent."""


@dataclass(frozen=True)
class _Candidate:
    claim: ClaimRegistryEntry
    matched_by: ClaimMatchCriterion
    criterion_rank: int
    exam_priority_rank: int | None


class ClaimMappingResolver:
    """Map only explicitly selected approved Claims; never inspect assertion text."""

    def resolve(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
    ) -> SemanticBlueprintBundle:
        self._validate_source(plan, source)
        if plan.diagram_intent_profile_ref is None or not plan.diagram_intent_bindings:
            raise ClaimMappingError("Publication Plan does not contain Diagram Intent data")
        intent_profile_ref = plan.diagram_intent_profile_ref
        taxonomy_by_visual = {item.visual_id: item for item in plan.diagram_taxonomy_bindings}
        priority_ranks = _exam_priority_ranks(source)
        blueprints = tuple(
            self._resolve_intent(
                plan,
                source,
                intent,
                intent_profile_ref,
                taxonomy_by_visual.get(intent.visual_id),
                priority_ranks,
            )
            for intent in plan.diagram_intent_bindings
        )
        return SemanticBlueprintBundle(
            schema_version="1.0",
            request_id=plan.request_id,
            knowledge_id=plan.knowledge_id,
            source_fingerprint=plan.source_fingerprint,
            blueprints=blueprints,
        )

    def _validate_source(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
    ) -> None:
        if plan.knowledge_id != source.knowledge.knowledge_id:
            raise ClaimMappingError("Publication Plan and source knowledge_id do not match")
        if plan.knowledge_content_revision != source.knowledge.content_revision:
            raise ClaimMappingError("Publication Plan and Knowledge revision do not match")
        if plan.registry_knowledge_version != source.registry.knowledge.knowledge_version:
            raise ClaimMappingError("Publication Plan and Registry version do not match")
        if plan.source_fingerprint != publication_source_fingerprint(source):
            raise ClaimMappingError("Publication Plan source fingerprint does not match")

    def _resolve_intent(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
        intent: PlannedDiagramIntent,
        intent_profile_ref: ProfileReference,
        taxonomy: PlannedDiagramTaxonomy | None,
        priority_ranks: dict[str, int],
    ) -> SemanticBlueprint:
        if plan.diagram_taxonomy_ref is not None and taxonomy is None:
            raise ClaimMappingError(
                f"Publication Plan Taxonomy binding is missing: {intent.visual_id}"
            )
        intent_type = taxonomy.root_intent_type if taxonomy is not None else intent.intent_type
        if intent_type is None:
            raise ClaimMappingError(
                f"Diagram Intent classification is unresolved: {intent.intent_id}"
            )
        rules = {item.concept_id: item for item in intent.claim_mapping_strategy.concept_rules}
        active_claims = tuple(
            item
            for item in source.registry.claims
            if item.status == RegistryStatus.APPROVED and not item.is_deleted
        )
        unavailable_claims = tuple(
            item
            for item in source.registry.claims
            if item.status != RegistryStatus.APPROVED or item.is_deleted
        )
        used_claim_ids: set[str] = set()
        concepts: list[BlueprintConcept] = []
        mapped_claims: list[MappedClaim] = []
        missing: list[MissingConceptReport] = []
        for concept in intent.concepts:
            rule = rules.get(concept.concept_id)
            if rule is None:
                concepts.append(
                    BlueprintConcept(
                        concept_id=concept.concept_id,
                        concept_type=concept.concept_type,
                        requirement=concept.requirement,
                        resolution_status=ConceptResolutionStatus.MISSING,
                        mapped_claim_ids=(),
                    )
                )
                missing.append(
                    MissingConceptReport(
                        concept_id=concept.concept_id,
                        concept_type=concept.concept_type,
                        requirement=concept.requirement,
                        origin=MissingConceptOrigin.INTENT,
                        reason=MissingConceptReason.MAPPING_RULE_MISSING,
                        required_minimum_claims=0,
                        matched_approved_claims=0,
                        matching_unapproved_claims=0,
                    )
                )
                continue
            candidates = _select_candidates(
                rule,
                active_claims,
                priority_ranks,
                intent.claim_mapping_strategy.matching_order,
            )
            if not intent.claim_mapping_strategy.allow_claim_reuse:
                candidates = tuple(
                    item for item in candidates if item.claim.claim_id not in used_claim_ids
                )
            selected = candidates[: rule.maximum_claims]
            selected_ids = tuple(item.claim.claim_id for item in selected)
            used_claim_ids.update(selected_ids)
            mapped_claims.extend(
                MappedClaim(
                    concept_id=concept.concept_id,
                    claim_ref=ClaimReference(
                        claim_id=item.claim.claim_id,
                        claim_key=item.claim.claim_key,
                        claim_version=item.claim.claim_version,
                    ),
                    matched_by=item.matched_by,
                    source_field_path=item.claim.field_path,
                    exam_priority_rank=item.exam_priority_rank,
                )
                for item in selected
            )
            status = _resolution_status(len(selected), rule.minimum_claims)
            concepts.append(
                BlueprintConcept(
                    concept_id=concept.concept_id,
                    concept_type=concept.concept_type,
                    requirement=concept.requirement,
                    resolution_status=status,
                    mapped_claim_ids=selected_ids,
                )
            )
            if status != ConceptResolutionStatus.MAPPED:
                unapproved_count = len(
                    _select_candidates(
                        rule,
                        unavailable_claims,
                        priority_ranks,
                        intent.claim_mapping_strategy.matching_order,
                    )
                )
                missing.append(
                    MissingConceptReport(
                        concept_id=concept.concept_id,
                        concept_type=concept.concept_type,
                        requirement=concept.requirement,
                        origin=MissingConceptOrigin.KNOWLEDGE,
                        reason=_missing_reason(
                            selected_count=len(selected),
                            unapproved_count=unapproved_count,
                        ),
                        required_minimum_claims=rule.minimum_claims,
                        matched_approved_claims=len(selected),
                        matching_unapproved_claims=unapproved_count,
                    )
                )
        relations = _semantic_relations(intent.semantic_sequences)
        blueprint_payload = {
            "source_fingerprint": plan.source_fingerprint,
            "knowledge_id": plan.knowledge_id,
            "knowledge_content_revision": plan.knowledge_content_revision,
            "registry_knowledge_version": plan.registry_knowledge_version,
            "intent_profile_ref": intent_profile_ref.model_dump(mode="json"),
            "intent": intent.model_dump(mode="json"),
            "taxonomy": (taxonomy.model_dump(mode="json") if taxonomy is not None else None),
            "mapped_claims": [item.model_dump(mode="json") for item in mapped_claims],
            "missing": [item.model_dump(mode="json") for item in missing],
        }
        required_missing = any(item.requirement == ConceptRequirement.REQUIRED for item in missing)
        return SemanticBlueprint(
            schema_version="1.1" if taxonomy is not None else "1.0",
            blueprint_id=f"blueprint.{plan.knowledge_id}.{intent.intent_id}",
            revision_hash=_fingerprint(blueprint_payload),
            knowledge_id=plan.knowledge_id,
            knowledge_content_revision=plan.knowledge_content_revision,
            registry_knowledge_version=plan.registry_knowledge_version,
            intent_profile_ref=intent_profile_ref,
            intent_id=intent.intent_id,
            visual_id=intent.visual_id,
            intent_type=intent_type,
            taxonomy_ref=plan.diagram_taxonomy_ref,
            taxonomy_id=(taxonomy.taxonomy_id if taxonomy is not None else None),
            taxonomy_path=(taxonomy.taxonomy_path if taxonomy is not None else ()),
            semantic_sequences=intent.semantic_sequences,
            concepts=tuple(concepts),
            mapped_claims=tuple(mapped_claims),
            missing_concepts=tuple(missing),
            semantic_relations=relations,
            is_complete=not required_missing,
        )


def _select_candidates(
    rule: ConceptClaimMappingRule,
    claims: tuple[ClaimRegistryEntry, ...],
    priority_ranks: dict[str, int],
    matching_order: tuple[ClaimMatchCriterion, ...],
) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    for claim in claims:
        matched = _match_criterion(rule, claim, matching_order)
        if matched is None:
            continue
        criterion, rank = matched
        candidates.append(
            _Candidate(
                claim=claim,
                matched_by=criterion,
                criterion_rank=rank,
                exam_priority_rank=(
                    priority_ranks.get(claim.claim_id)
                    if ClaimMatchCriterion.EXAM_PRIORITY in matching_order
                    else None
                ),
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.criterion_rank,
                item.exam_priority_rank if item.exam_priority_rank is not None else 10001,
                item.claim.claim_key,
                item.claim.claim_id,
            ),
        )
    )


def _match_criterion(
    rule: ConceptClaimMappingRule,
    claim: ClaimRegistryEntry,
    matching_order: tuple[ClaimMatchCriterion, ...],
) -> tuple[ClaimMatchCriterion, int] | None:
    checks = {
        ClaimMatchCriterion.FIELD_PATH_PREFIX: any(
            claim.field_path.startswith(prefix) for prefix in rule.source_field_path_prefixes
        ),
        ClaimMatchCriterion.CLAIM_KEY_PREFIX: any(
            claim.claim_key.startswith(prefix) for prefix in rule.source_claim_key_prefixes
        ),
    }
    for rank, criterion in enumerate(matching_order):
        if criterion in checks and checks[criterion]:
            return criterion, rank
    return None


def _exam_priority_ranks(source: PublicationSourceBundle) -> dict[str, int]:
    if source.exam_metadata is None:
        return {}
    return {
        item.claim_id: rank
        for rank, item in enumerate(source.exam_metadata.priority_claims, start=1)
    }


def _resolution_status(
    selected_count: int,
    minimum_claims: int,
) -> ConceptResolutionStatus:
    if selected_count == 0:
        return ConceptResolutionStatus.MISSING
    if selected_count < minimum_claims:
        return ConceptResolutionStatus.PARTIAL
    return ConceptResolutionStatus.MAPPED


def _missing_reason(
    *,
    selected_count: int,
    unapproved_count: int,
) -> MissingConceptReason:
    if selected_count > 0:
        return MissingConceptReason.MINIMUM_CLAIMS_NOT_MET
    if unapproved_count > 0:
        return MissingConceptReason.NO_APPROVED_CLAIM
    return MissingConceptReason.NO_MATCHING_CLAIM


def _semantic_relations(
    sequences: tuple[SemanticSequence, ...],
) -> tuple[BlueprintSemanticRelation, ...]:
    relations: list[BlueprintSemanticRelation] = []
    for sequence in sequences:
        ordered = sorted(sequence.steps, key=lambda item: item.order)
        for source_step, target_step in pairwise(ordered):
            if source_step.relation_to_next is None:
                raise ClaimMappingError("non-final Semantic Sequence step has no relation")
            relations.append(
                BlueprintSemanticRelation(
                    relation_id=f"relation.{sequence.sequence_id}.{source_step.order}",
                    source_sequence_id=sequence.sequence_id,
                    order=source_step.order,
                    source_concept_id=source_step.concept_id,
                    relation_type=source_step.relation_to_next,
                    target_concept_id=target_step.concept_id,
                )
            )
    return tuple(relations)


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
