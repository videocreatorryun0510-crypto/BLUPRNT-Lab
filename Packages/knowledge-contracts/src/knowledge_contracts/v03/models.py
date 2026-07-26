"""Long-lived Knowledge JSON Version 0.3 models.

Version 0.3 stores atomic medical facts, national-exam alignment, evidence, and
publisher selection hints. It intentionally excludes rendered prose, mnemonics,
scripts, questions, and other channel-specific output.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
]
MediumText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)
]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
KnowledgeId = Annotated[
    str, StringConstraints(pattern=r"^knw_[a-z0-9][a-z0-9_-]{7,63}$")
]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")]
SourceId = Annotated[str, StringConstraints(pattern=r"^src_[a-z0-9][a-z0-9_-]{7,63}$")]
QuestionId = Annotated[
    str, StringConstraints(pattern=r"^qst_[a-z0-9][a-z0-9_-]{7,63}$")
]


class StrictModel(BaseModel):
    """Reject unknown properties so contract changes remain explicit."""

    model_config = ConfigDict(extra="forbid")


class TermType(StrEnum):
    TEST_ITEM = "test_item"
    DISEASE = "disease"
    PARASITE = "parasite"
    MICROORGANISM = "microorganism"
    PATHOLOGY = "pathology"
    STAINING_METHOD = "staining_method"
    BIOCHEMISTRY = "biochemistry"
    HEMATOLOGY = "hematology"
    TRANSFUSION = "transfusion"
    IMMUNOLOGY = "immunology"
    PUBLIC_HEALTH = "public_health"
    OTHER = "other"


class ExamDomain(StrEnum):
    CLINICAL_CHEMISTRY = "clinical_chemistry"
    HEMATOLOGY = "hematology"
    MICROBIOLOGY = "microbiology"
    IMMUNOLOGY = "immunology"
    TRANSFUSION = "transfusion"
    PATHOLOGY_CYTOLOGY = "pathology_cytology"
    PHYSIOLOGY = "physiology"
    PUBLIC_HEALTH = "public_health"
    MEDICAL_ENGINEERING = "medical_engineering"
    OTHER = "other"


class TermInfo(StrictModel):
    canonical_name: ShortText
    english_name: OptionalText
    aliases: list[ShortText] = Field(min_length=0, max_length=20)


class Classification(StrictModel):
    """Factual classification without AI confidence or explanatory prose."""

    term_type: TermType
    primary_exam_domain: ExamDomain
    related_exam_domains: list[ExamDomain] = Field(min_length=0, max_length=5)


class FactClaim(StrictModel):
    """Smallest independently sourceable unit of medical knowledge."""

    claim_id: ClaimId
    statement: MediumText


class CoreFacts(StrictModel):
    """Category-independent facts; not a ready-to-publish article."""

    definitions: list[FactClaim] = Field(min_length=1, max_length=5)
    mechanisms: list[FactClaim] = Field(min_length=0, max_length=15)
    characteristics: list[FactClaim] = Field(min_length=0, max_length=30)


class SpecimenFact(StrictModel):
    claim_id: ClaimId
    specimen: ShortText
    container_or_anticoagulant: OptionalText
    handling: MediumText
    stability: OptionalText


class MeasurementMethodFact(StrictModel):
    claim_id: ClaimId
    method_name: ShortText
    standardizing_body: OptionalText
    factual_description: MediumText


class MeasurementPrincipleFact(StrictModel):
    claim_id: ClaimId
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=10)
    measured_quantity: ShortText
    reaction_sequence: MediumText
    detection_signal: MediumText
    wavelength_or_endpoint: OptionalText


class ReferenceRangeFact(StrictModel):
    claim_id: ClaimId
    population: ShortText
    specimen: ShortText
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=10)
    lower_bound: float | None
    upper_bound: float | None
    qualitative_value: OptionalText
    unit: OptionalText
    conditions: MediumText

    @model_validator(mode="after")
    def require_value(self) -> Self:
        has_numeric_value = self.lower_bound is not None or self.upper_bound is not None
        if not has_numeric_value and not self.qualitative_value:
            raise ValueError(
                "reference range requires a numeric bound or qualitative_value"
            )
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound must not exceed upper_bound")
        return self


class PathophysiologicStateAssociation(StrictModel):
    """A mechanism/state such as hepatocellular injury or muscle injury."""

    claim_id: ClaimId
    state_name: ShortText
    related_knowledge_id: KnowledgeId | None
    factual_relation: MediumText


class RepresentativeDiseaseAssociation(StrictModel):
    """A named disease kept separate from its underlying pathophysiology."""

    claim_id: ClaimId
    disease_name: ShortText
    disease_knowledge_id: KnowledgeId | None
    factual_relation: MediumText


class ValueAssociationGroup(StrictModel):
    pathophysiologic_states: list[PathophysiologicStateAssociation] = Field(
        min_length=0, max_length=20
    )
    representative_diseases: list[RepresentativeDiseaseAssociation] = Field(
        min_length=0, max_length=30
    )
    interpretive_notes: list[FactClaim] = Field(min_length=0, max_length=10)


class ValueAssociations(StrictModel):
    high: ValueAssociationGroup
    low: ValueAssociationGroup


class TestCombinationFact(StrictModel):
    claim_id: ClaimId
    related_test_names: list[ShortText] = Field(min_length=1, max_length=10)
    related_knowledge_ids: list[KnowledgeId] = Field(min_length=0, max_length=10)
    factual_interpretation: MediumText


class TestItemContent(StrictModel):
    """Medical facts specific to laboratory test items."""

    purposes: list[FactClaim] = Field(min_length=1, max_length=10)
    specimens: list[SpecimenFact] = Field(min_length=1, max_length=10)
    measurement_methods: list[MeasurementMethodFact] = Field(
        min_length=1, max_length=15
    )
    measurement_principles: list[MeasurementPrincipleFact] = Field(
        min_length=1, max_length=15
    )
    reference_ranges: list[ReferenceRangeFact] = Field(min_length=0, max_length=20)
    value_associations: ValueAssociations
    related_test_combinations: list[TestCombinationFact] = Field(
        min_length=0, max_length=15
    )
    interpretation_cautions: list[FactClaim] = Field(min_length=0, max_length=20)


class TestItemCategoryContent(StrictModel):
    template_id: Literal["test_item_v0.3"]
    test_item: TestItemContent


class GenericCategoryContent(StrictModel):
    """Stable placeholder until a category receives its own fact template."""

    template_id: Literal["generic_facts_v0.3"]


CategoryContent = Annotated[
    TestItemCategoryContent | GenericCategoryContent,
    Field(discriminator="template_id"),
]


class ExamImportanceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ExamImportanceAssessment(StrictModel):
    """Normalized level plus optional raw score from a future analysis batch."""

    level: ExamImportanceLevel
    score: float | None = Field(ge=0)
    score_scale_max: float | None = Field(gt=0)
    calculation_method: OptionalText


class ExamFrequency(StrictModel):
    appearance_count: int = Field(ge=0)
    analyzed_question_count: int = Field(ge=1)
    frequency_rate: float | None = Field(ge=0, le=1)
    calculation_method: OptionalText

    @model_validator(mode="after")
    def validate_frequency(self) -> Self:
        if self.appearance_count > self.analyzed_question_count:
            raise ValueError("appearance_count cannot exceed analyzed_question_count")
        return self


class ExamQuestionReference(StrictModel):
    question_id: QuestionId
    exam_session: int = Field(ge=1)
    question_number: int = Field(ge=1)
    tested_claim_ids: list[ClaimId] = Field(min_length=0, max_length=30)


class KnowledgeRelation(StrictModel):
    knowledge_id: KnowledgeId
    label: ShortText


class ExamMetadata(StrictModel):
    """Category-independent destination for future national-exam CSV analysis."""

    analysis_batch_id: OptionalText
    importance: ExamImportanceAssessment | None
    first_appearance_session: int | None = Field(ge=1)
    last_appearance_session: int | None = Field(ge=1)
    appearance_frequency: ExamFrequency | None
    related_questions: list[ExamQuestionReference] = Field(min_length=0, max_length=500)
    comparison_targets: list[KnowledgeRelation] = Field(min_length=0, max_length=50)
    related_knowledge: list[KnowledgeRelation] = Field(min_length=0, max_length=100)
    priority_claim_ids: list[ClaimId] = Field(min_length=0, max_length=100)
    keywords: list[ShortText] = Field(min_length=0, max_length=100)

    @model_validator(mode="after")
    def validate_appearance_order(self) -> Self:
        if (
            self.first_appearance_session is not None
            and self.last_appearance_session is not None
            and self.first_appearance_session > self.last_appearance_session
        ):
            raise ValueError(
                "first_appearance_session must not exceed last_appearance_session"
            )
        return self


class EvidenceRole(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"


class EvidenceReference(StrictModel):
    """Bibliographic source plus the exact claims it supports."""

    source_id: SourceId
    source_priority_rank: int = Field(ge=1, le=6)
    title: ShortText
    issuing_organization: OptionalText
    edition: OptionalText
    publication_year: int | None = Field(ge=1800)
    url: HttpUrl | None
    doi: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/\S+$"),
    ]
    pmid: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{1,12}$"),
    ]
    accessed_at: date | None
    chapter: OptionalText
    pages: OptionalText
    supported_claim_ids: list[ClaimId] = Field(min_length=1, max_length=200)
    evidence_role: EvidenceRole


class ExamMetadataField(StrEnum):
    IMPORTANCE = "importance"
    FIRST_APPEARANCE = "first_appearance_session"
    LAST_APPEARANCE = "last_appearance_session"
    FREQUENCY = "appearance_frequency"
    RELATED_QUESTIONS = "related_questions"
    COMPARISON_TARGETS = "comparison_targets"
    RELATED_KNOWLEDGE = "related_knowledge"
    KEYWORDS = "keywords"


class PublisherUseProfile(StrictModel):
    """References only; no publisher-generated body or presentation text."""

    priority_claim_ids: list[ClaimId] = Field(min_length=0, max_length=100)
    priority_exam_metadata: list[ExamMetadataField] = Field(min_length=0, max_length=8)


class PublishTargets(StrictModel):
    pdf: PublisherUseProfile
    note: PublisherUseProfile
    training_video: PublisherUseProfile
    national_exam: PublisherUseProfile


class KnowledgeRecord(StrictModel):
    """Pure knowledge payload for the Version 0.3 Single Source of Truth."""

    schema_version: Literal["0.3"]
    knowledge_id: KnowledgeId
    content_revision: int = Field(ge=1)
    term: TermInfo
    classification: Classification
    core_facts: CoreFacts
    category_content: CategoryContent
    exam_metadata: ExamMetadata
    evidence: list[EvidenceReference] = Field(min_length=0, max_length=500)
    publish_targets: PublishTargets

    @model_validator(mode="after")
    def validate_record_references(self) -> Self:
        is_test_item = self.classification.term_type == TermType.TEST_ITEM
        if is_test_item != isinstance(self.category_content, TestItemCategoryContent):
            raise ValueError(
                "test_item classification and test_item_v0.3 category content must match"
            )

        raw = self.model_dump(mode="json")
        claim_ids, referenced_claim_ids = _collect_claim_ids(raw)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique within a knowledge record")

        unknown_claim_ids = sorted(set(referenced_claim_ids) - set(claim_ids))
        if unknown_claim_ids:
            raise ValueError(
                "claim references must exist in the same record: "
                + ", ".join(unknown_claim_ids)
            )

        source_ids = [source.source_id for source in self.evidence]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                "source_id values must be unique within a knowledge record"
            )

        question_ids = [
            item.question_id for item in self.exam_metadata.related_questions
        ]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question_id values must be unique within exam_metadata")
        return self


def _collect_claim_ids(value: Any) -> tuple[list[str], list[str]]:
    claim_ids: list[str] = []
    references: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "claim_id" and isinstance(child, str):
                    claim_ids.append(child)
                elif key.endswith("_claim_ids") and isinstance(child, list):
                    references.extend(
                        entry for entry in child if isinstance(entry, str)
                    )
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return claim_ids, references
