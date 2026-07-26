"""Provider-neutral semantic meaning models produced before any render planning."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.v10.models import ClaimId, KnowledgeId
from pydantic import Field, StringConstraints, model_validator

from publisher_core.models import (
    ClaimMatchCriterion,
    ClaimReference,
    ConceptRequirement,
    DiagramIntentType,
    FrozenModel,
    ProfileReference,
    SemanticConceptType,
    SemanticRelation,
    SemanticSequence,
    StableKey,
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ConceptResolutionStatus(StrEnum):
    MAPPED = "mapped"
    PARTIAL = "partial"
    MISSING = "missing"


class MissingConceptOrigin(StrEnum):
    KNOWLEDGE = "knowledge"
    INTENT = "intent"


class MissingConceptReason(StrEnum):
    MAPPING_RULE_MISSING = "mapping_rule_missing"
    NO_MATCHING_CLAIM = "no_matching_claim"
    NO_APPROVED_CLAIM = "no_approved_claim"
    MINIMUM_CLAIMS_NOT_MET = "minimum_claims_not_met"


class BlueprintConcept(FrozenModel):
    concept_id: StableKey
    concept_type: SemanticConceptType
    requirement: ConceptRequirement
    resolution_status: ConceptResolutionStatus
    mapped_claim_ids: tuple[ClaimId, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def keep_status_consistent(self) -> Self:
        if self.resolution_status == ConceptResolutionStatus.MISSING and self.mapped_claim_ids:
            raise ValueError("missing Blueprint Concept cannot reference mapped Claims")
        if self.resolution_status == ConceptResolutionStatus.MAPPED and not self.mapped_claim_ids:
            raise ValueError("mapped Blueprint Concept requires at least one Claim")
        if len(self.mapped_claim_ids) != len(set(self.mapped_claim_ids)):
            raise ValueError("Blueprint Concept mapped_claim_ids must be unique")
        return self


class MappedClaim(FrozenModel):
    concept_id: StableKey
    claim_ref: ClaimReference
    matched_by: ClaimMatchCriterion
    source_field_path: StableKey
    exam_priority_rank: int | None = Field(default=None, ge=1, le=10000)


class MissingConceptReport(FrozenModel):
    concept_id: StableKey
    concept_type: SemanticConceptType
    requirement: ConceptRequirement
    origin: MissingConceptOrigin
    reason: MissingConceptReason
    required_minimum_claims: int = Field(ge=0, le=20)
    matched_approved_claims: int = Field(ge=0, le=100)
    matching_unapproved_claims: int = Field(ge=0, le=100)


class BlueprintSemanticRelation(FrozenModel):
    relation_id: StableKey
    source_sequence_id: StableKey
    order: int = Field(ge=1, le=100)
    source_concept_id: StableKey
    relation_type: SemanticRelation
    target_concept_id: StableKey


class SemanticBlueprint(FrozenModel):
    schema_version: Literal["1.0", "1.1"]
    blueprint_id: StableKey
    revision_hash: Sha256
    knowledge_id: KnowledgeId
    knowledge_content_revision: int = Field(ge=1)
    registry_knowledge_version: int = Field(ge=1)
    intent_profile_ref: ProfileReference
    intent_id: StableKey
    visual_id: StableKey
    intent_type: DiagramIntentType
    taxonomy_ref: ProfileReference | None = None
    taxonomy_id: StableKey | None = None
    taxonomy_path: tuple[StableKey, ...] = Field(default=(), max_length=30)
    semantic_sequences: tuple[SemanticSequence, ...] = Field(min_length=1, max_length=20)
    concepts: tuple[BlueprintConcept, ...] = Field(min_length=1, max_length=100)
    mapped_claims: tuple[MappedClaim, ...] = Field(default=(), max_length=1000)
    missing_concepts: tuple[MissingConceptReport, ...] = Field(default=(), max_length=100)
    semantic_relations: tuple[BlueprintSemanticRelation, ...] = Field(default=(), max_length=500)
    is_complete: bool

    @model_validator(mode="after")
    def validate_semantic_graph(self) -> Self:
        has_taxonomy = self.taxonomy_ref is not None
        taxonomy_payload = self.taxonomy_id is not None or bool(self.taxonomy_path)
        if self.schema_version == "1.0" and (has_taxonomy or taxonomy_payload):
            raise ValueError("Semantic Blueprint 1.0 cannot contain Taxonomy data")
        if self.schema_version == "1.1":
            if not has_taxonomy or self.taxonomy_id is None or not self.taxonomy_path:
                raise ValueError("Semantic Blueprint 1.1 requires Taxonomy data")
            if self.taxonomy_path[-1] != self.taxonomy_id:
                raise ValueError("Semantic Blueprint Taxonomy path must end at taxonomy_id")
        concept_ids = tuple(item.concept_id for item in self.concepts)
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("Semantic Blueprint concept_id values must be unique")
        known_concepts = set(concept_ids)
        mapping_pairs = tuple(
            (item.concept_id, item.claim_ref.claim_id) for item in self.mapped_claims
        )
        if len(mapping_pairs) != len(set(mapping_pairs)):
            raise ValueError("Semantic Blueprint Claim mappings must be unique")
        if not {item.concept_id for item in self.mapped_claims}.issubset(known_concepts):
            raise ValueError("mapped Claim references an unknown Blueprint Concept")
        missing_ids = tuple(item.concept_id for item in self.missing_concepts)
        if len(missing_ids) != len(set(missing_ids)):
            raise ValueError("Semantic Blueprint missing Concept reports must be unique")
        if not set(missing_ids).issubset(known_concepts):
            raise ValueError("missing report references an unknown Blueprint Concept")
        relation_ids = tuple(item.relation_id for item in self.semantic_relations)
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("Semantic Blueprint relation_id values must be unique")
        for relation in self.semantic_relations:
            if (
                relation.source_concept_id not in known_concepts
                or relation.target_concept_id not in known_concepts
            ):
                raise ValueError("semantic relation references an unknown Blueprint Concept")
        required_missing = any(
            item.requirement == ConceptRequirement.REQUIRED for item in self.missing_concepts
        )
        if self.is_complete == required_missing:
            raise ValueError("is_complete must reflect required missing Concepts")
        return self


class SemanticBlueprintBundle(FrozenModel):
    schema_version: Literal["1.0"]
    request_id: StableKey
    knowledge_id: KnowledgeId
    source_fingerprint: Sha256
    blueprints: tuple[SemanticBlueprint, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        if any(item.knowledge_id != self.knowledge_id for item in self.blueprints):
            raise ValueError("Semantic Blueprint Bundle cannot mix knowledge_id values")
        blueprint_ids = tuple(item.blueprint_id for item in self.blueprints)
        if len(blueprint_ids) != len(set(blueprint_ids)):
            raise ValueError("Semantic Blueprint Bundle blueprint_id values must be unique")
        return self
