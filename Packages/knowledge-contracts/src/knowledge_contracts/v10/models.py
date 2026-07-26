"""Knowledge JSON Version 1.0 models and the category union.

Version 1.0 keeps medical facts separate from presentation and stores each
independently sourceable fact under a category-specific semantic field.
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
NullableText = (
    Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]
    | None
)
KnowledgeId = Annotated[
    str, StringConstraints(pattern=r"^knw_[a-z0-9][a-z0-9_-]{7,63}$")
]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm_[a-z0-9][a-z0-9_-]{7,63}$")]
SourceId = Annotated[str, StringConstraints(pattern=r"^src_[a-z0-9][a-z0-9_-]{7,63}$")]
QuestionId = Annotated[
    str, StringConstraints(pattern=r"^qst_[a-z0-9][a-z0-9_-]{7,63}$")
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    english_name: NullableText
    aliases: list[ShortText] = Field(min_length=0, max_length=20)


class Classification(StrictModel):
    term_type: Literal[
        "test_item",
        "staining_method",
        "specimen",
        "reagent",
        "biological_structure",
        "disease",
        "laboratory_test_item",
    ]
    primary_exam_domain: ExamDomain
    related_exam_domains: list[ExamDomain] = Field(min_length=0, max_length=5)


class FactClaim(StrictModel):
    claim_id: ClaimId
    assertion: MediumText


class CoreFacts(StrictModel):
    definitions: list[FactClaim] = Field(min_length=0, max_length=5)


class SpecimenFact(StrictModel):
    claim_id: ClaimId
    specimen: ShortText
    container_or_anticoagulant: NullableText
    handling: MediumText
    stability: NullableText


class MeasurementMethodFact(StrictModel):
    claim_id: ClaimId
    method_name: ShortText
    method_family: NullableText
    assertion: MediumText


class MeasurementPrincipleFact(StrictModel):
    claim_id: ClaimId
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=15)
    measured_quantity: ShortText
    reaction_sequence: MediumText
    detection_signal: MediumText
    wavelength_or_endpoint: NullableText
    assertion: MediumText


class StandardizationTraceabilityFact(StrictModel):
    claim_id: ClaimId
    related_method_claim_ids: list[ClaimId] = Field(min_length=1, max_length=15)
    framework_or_body: ShortText
    traceability: MediumText
    assertion: MediumText


class ReportingSystemFact(StrictModel):
    claim_id: ClaimId
    system_name: ShortText
    unit: ShortText
    conditions: NullableText
    assertion: MediumText


class ReferenceRangeFact(StrictModel):
    claim_id: ClaimId
    population: ShortText
    specimen: ShortText
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=15)
    lower_bound: float | None
    upper_bound: float | None
    qualitative_value: NullableText
    unit: NullableText
    conditions: MediumText

    @model_validator(mode="after")
    def require_value(self) -> Self:
        has_numeric_value = self.lower_bound is not None or self.upper_bound is not None
        if not has_numeric_value and self.qualitative_value is None:
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


class ClinicalDecisionLimitFact(StrictModel):
    claim_id: ClaimId
    limit_name: ShortText
    population: ShortText
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=15)
    comparator: Literal[
        "less_than", "less_than_or_equal", "greater_than", "greater_than_or_equal"
    ]
    value: float | None
    qualitative_value: NullableText
    unit: NullableText
    conditions: MediumText
    assertion: MediumText

    @model_validator(mode="after")
    def require_value(self) -> Self:
        if self.value is None and self.qualitative_value is None:
            raise ValueError(
                "clinical decision limit requires value or qualitative_value"
            )
        return self


class PathophysiologicStateAssociation(StrictModel):
    claim_id: ClaimId
    state_name: ShortText
    related_knowledge_id: KnowledgeId | None
    assertion: MediumText


class RepresentativeDiseaseAssociation(StrictModel):
    claim_id: ClaimId
    disease_name: ShortText
    disease_knowledge_id: KnowledgeId | None
    assertion: MediumText


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
    assertion: MediumText


class AnalyticalInterferenceFact(StrictModel):
    claim_id: ClaimId
    interference_name: ShortText
    effect_direction: Literal[
        "positive_bias", "negative_bias", "method_dependent", "unreliable", "other"
    ]
    related_method_claim_ids: list[ClaimId] = Field(min_length=0, max_length=15)
    conditions: NullableText
    assertion: MediumText


class TimeCourseFact(StrictModel):
    claim_id: ClaimId
    event_or_condition: ShortText
    time_course: MediumText
    assertion: MediumText


class IsoenzymeFact(StrictModel):
    claim_id: ClaimId
    isoenzyme_name: ShortText
    distribution_or_property: MediumText
    assertion: MediumText


class TestItemContent(StrictModel):
    biological_basis: list[FactClaim] = Field(min_length=0, max_length=15)
    analyte_characteristics: list[FactClaim] = Field(min_length=0, max_length=30)
    purposes: list[FactClaim] = Field(min_length=0, max_length=10)
    specimens: list[SpecimenFact] = Field(min_length=0, max_length=10)
    measurement_methods: list[MeasurementMethodFact] = Field(
        min_length=0, max_length=15
    )
    measurement_principles: list[MeasurementPrincipleFact] = Field(
        min_length=0, max_length=15
    )
    standardization_and_traceability: list[StandardizationTraceabilityFact] = Field(
        min_length=0, max_length=15
    )
    reporting_systems: list[ReportingSystemFact] = Field(min_length=0, max_length=10)
    reference_ranges: list[ReferenceRangeFact] = Field(min_length=0, max_length=20)
    clinical_decision_limits: list[ClinicalDecisionLimitFact] = Field(
        min_length=0, max_length=20
    )
    value_associations: ValueAssociations
    related_test_combinations: list[TestCombinationFact] = Field(
        min_length=0, max_length=15
    )
    analytical_interferences: list[AnalyticalInterferenceFact] = Field(
        min_length=0, max_length=20
    )
    interpretation_cautions: list[FactClaim] = Field(min_length=0, max_length=20)
    time_course: list[TimeCourseFact] = Field(min_length=0, max_length=10)
    isoenzymes: list[IsoenzymeFact] = Field(min_length=0, max_length=20)


class CategoryContentEnvelope(StrictModel):
    """Common envelope contract; category facts remain in a dedicated model."""

    template_id: str


class TestItemCategoryContent(CategoryContentEnvelope):
    template_id: Literal["test_item_v1.0"]
    test_item: TestItemContent


class StainingPurposeFact(StrictModel):
    claim_id: ClaimId
    use_case: ShortText
    assertion: MediumText


class TargetStructureFact(StrictModel):
    claim_id: ClaimId
    target_name: ShortText
    target_kind: ShortText
    assertion: MediumText


class ApplicableSpecimenFact(StrictModel):
    claim_id: ClaimId
    specimen: ShortText
    preparation: MediumText
    assertion: MediumText


class FixationRequirementFact(StrictModel):
    claim_id: ClaimId
    fixative_or_method: ShortText
    conditions: MediumText
    assertion: MediumText


class StainingPrincipleFact(StrictModel):
    claim_id: ClaimId
    mechanism: ShortText
    affected_target: ShortText
    resulting_effect: MediumText
    assertion: MediumText


class StainingReagentFact(StrictModel):
    claim_id: ClaimId
    reagent_name: ShortText
    reagent_role: Literal[
        "primary_stain", "mordant", "decolorizer", "counterstain", "other"
    ]
    assertion: MediumText


class StainingProcedureStepFact(StrictModel):
    claim_id: ClaimId
    step_order: int = Field(ge=1, le=100)
    action: MediumText
    reagent_claim_ids: list[ClaimId] = Field(min_length=0, max_length=10)
    duration: NullableText
    conditions: NullableText
    assertion: MediumText


class StainingResultInterpretationFact(StrictModel):
    claim_id: ClaimId
    target_name: ShortText
    observed_color_or_pattern: ShortText
    interpretation: MediumText
    assertion: MediumText


class StainingQualityControlFact(StrictModel):
    claim_id: ClaimId
    control_material: ShortText
    expected_result: MediumText
    assertion: MediumText


class StainingErrorCauseFact(StrictModel):
    claim_id: ClaimId
    error_type: ShortText
    cause: MediumText
    observed_effect: MediumText
    assertion: MediumText


class StainingLimitationFact(StrictModel):
    claim_id: ClaimId
    scope_or_target: ShortText
    limitation: MediumText
    assertion: MediumText


class RelatedStainingMethodFact(StrictModel):
    claim_id: ClaimId
    method_name: ShortText
    method_knowledge_id: KnowledgeId | None
    relation_type: ShortText
    assertion: MediumText


class StainingMethodContent(StrictModel):
    purposes: list[StainingPurposeFact] = Field(min_length=0, max_length=10)
    target_structures: list[TargetStructureFact] = Field(min_length=0, max_length=20)
    applicable_specimens: list[ApplicableSpecimenFact] = Field(
        min_length=0, max_length=20
    )
    fixation_requirements: list[FixationRequirementFact] = Field(
        min_length=0, max_length=20
    )
    staining_principles: list[StainingPrincipleFact] = Field(
        min_length=0, max_length=20
    )
    reagents: list[StainingReagentFact] = Field(min_length=0, max_length=30)
    procedure_steps: list[StainingProcedureStepFact] = Field(
        min_length=0, max_length=50
    )
    result_interpretations: list[StainingResultInterpretationFact] = Field(
        min_length=0, max_length=30
    )
    quality_controls: list[StainingQualityControlFact] = Field(
        min_length=0, max_length=20
    )
    error_causes: list[StainingErrorCauseFact] = Field(min_length=0, max_length=30)
    limitations: list[StainingLimitationFact] = Field(min_length=0, max_length=20)
    safety_considerations: list[FactClaim] = Field(min_length=0, max_length=20)
    related_methods: list[RelatedStainingMethodFact] = Field(
        min_length=0, max_length=20
    )

    @model_validator(mode="after")
    def validate_step_order(self) -> Self:
        orders = [step.step_order for step in self.procedure_steps]
        if len(orders) != len(set(orders)):
            raise ValueError("procedure step_order values must be unique")
        return self


class StainingMethodCategoryContent(CategoryContentEnvelope):
    template_id: Literal["staining_method_v1.0"]
    staining_method: StainingMethodContent


class SpecimenKind(StrEnum):
    SERUM = "serum"
    PLASMA = "plasma"
    WHOLE_BLOOD = "whole_blood"
    URINE = "urine"
    STOOL = "stool"
    SPUTUM = "sputum"
    CEREBROSPINAL_FLUID = "cerebrospinal_fluid"
    SMEAR_SPECIMEN = "smear_specimen"
    OTHER = "other"


class SpecimenUseFact(StrictModel):
    claim_id: ClaimId
    use_case: ShortText
    assertion: MediumText


class SpecimenCollectionFact(StrictModel):
    claim_id: ClaimId
    source_material: ShortText
    collection_or_preparation_method: MediumText
    container_or_device: NullableText
    assertion: MediumText


class SpecimenStorageConditionFact(StrictModel):
    claim_id: ClaimId
    temperature: NullableText
    maximum_duration: NullableText
    conditions: MediumText
    assertion: MediumText


class SpecimenContent(StrictModel):
    specimen_kind: SpecimenKind
    overview: list[FactClaim] = Field(min_length=0, max_length=10)
    uses: list[SpecimenUseFact] = Field(min_length=0, max_length=20)
    collection_methods: list[SpecimenCollectionFact] = Field(
        min_length=0, max_length=20
    )
    storage_conditions: list[SpecimenStorageConditionFact] = Field(
        min_length=0, max_length=20
    )
    cautions: list[FactClaim] = Field(min_length=0, max_length=30)


class SpecimenCategoryContent(CategoryContentEnvelope):
    template_id: Literal["specimen_v1.0"]
    specimen: SpecimenContent


class ReagentKind(StrEnum):
    PRIMARY_STAIN = "primary_stain"
    MORDANT = "mordant"
    DECOLORIZER = "decolorizer"
    COUNTERSTAIN = "counterstain"
    OTHER = "other"


class ReagentPurposeFact(StrictModel):
    claim_id: ClaimId
    use_case: ShortText
    assertion: MediumText


class ReagentTargetFact(StrictModel):
    claim_id: ClaimId
    target_name: ShortText
    target_kind: ShortText
    assertion: MediumText


class ReagentUsageStepFact(StrictModel):
    claim_id: ClaimId
    usage_phase: Literal[
        "primary_staining",
        "mordant_treatment",
        "decolorization",
        "counterstaining",
        "other",
    ]
    application: MediumText
    conditions: NullableText
    assertion: MediumText


class ReagentStorageConditionFact(StrictModel):
    claim_id: ClaimId
    temperature: NullableText
    conditions: MediumText
    assertion: MediumText


class ReagentContent(StrictModel):
    reagent_kind: ReagentKind
    purposes: list[ReagentPurposeFact] = Field(min_length=0, max_length=20)
    targets: list[ReagentTargetFact] = Field(min_length=0, max_length=20)
    usage_steps: list[ReagentUsageStepFact] = Field(min_length=0, max_length=20)
    cautions: list[FactClaim] = Field(min_length=0, max_length=30)
    storage_conditions: list[ReagentStorageConditionFact] = Field(
        min_length=0, max_length=20
    )


class ReagentCategoryContent(CategoryContentEnvelope):
    template_id: Literal["reagent_v1.0"]
    reagent: ReagentContent


class StructureFunctionFact(StrictModel):
    claim_id: ClaimId
    function_name: ShortText
    assertion: MediumText


class StructureComponentFact(StrictModel):
    claim_id: ClaimId
    component_name: ShortText
    assertion: MediumText


class StructureOrganismFact(StrictModel):
    claim_id: ClaimId
    organism_name: ShortText
    assertion: MediumText


class BiologicalStructureContent(StrictModel):
    """Phase 5.8 minimum facts shared by biological structures.

    Structure class and taxon scope are deliberately deferred. The MVP stores
    reviewable medical facts without pretending that the future classification
    vocabularies have already been approved.
    """

    overview: list[FactClaim] = Field(min_length=0, max_length=10)
    main_functions: list[StructureFunctionFact] = Field(min_length=0, max_length=20)
    main_components: list[StructureComponentFact] = Field(min_length=0, max_length=30)
    organisms_present: list[StructureOrganismFact] = Field(min_length=0, max_length=30)


class BiologicalStructureCategoryContent(CategoryContentEnvelope):
    template_id: Literal["biological_structure_v1.0"]
    biological_structure: BiologicalStructureContent


class DiseaseCauseFact(StrictModel):
    claim_id: ClaimId
    cause_name: ShortText
    assertion: MediumText


class DiseasePathophysiologyFact(StrictModel):
    claim_id: ClaimId
    process_name: ShortText
    upstream_claim_ids: list[ClaimId] = Field(min_length=0, max_length=20)
    assertion: MediumText


class DiseaseClinicalFindingFact(StrictModel):
    claim_id: ClaimId
    finding_name: ShortText
    assertion: MediumText


class DiseaseLaboratoryFindingFact(StrictModel):
    claim_id: ClaimId
    test_name: ShortText
    direction_or_result: ShortText
    specimen: NullableText
    conditions: NullableText
    assertion: MediumText


class DiseaseDifferentialFact(StrictModel):
    claim_id: ClaimId
    compared_disease_name: ShortText
    distinguishing_feature: MediumText
    assertion: MediumText


class DiseaseContent(StrictModel):
    """Phase 5.10 minimum facts for a named disease.

    Classification systems, severity and treatment guidance are deliberately
    outside this MVP. National-exam points reference medical Claim IDs instead
    of duplicating presentation text.
    """

    overview: list[FactClaim] = Field(min_length=0, max_length=10)
    pathophysiology: list[DiseasePathophysiologyFact] = Field(
        min_length=0, max_length=30
    )
    causes: list[DiseaseCauseFact] = Field(min_length=0, max_length=30)
    main_symptoms: list[DiseaseClinicalFindingFact] = Field(
        min_length=0, max_length=30
    )
    main_laboratory_findings: list[DiseaseLaboratoryFindingFact] = Field(
        min_length=0, max_length=50
    )
    differential_points: list[DiseaseDifferentialFact] = Field(
        min_length=0, max_length=30
    )
    national_exam_point_claim_ids: list[ClaimId] = Field(
        min_length=0, max_length=30
    )


class DiseaseCategoryContent(CategoryContentEnvelope):
    template_id: Literal["disease_v1.0"]
    disease: DiseaseContent


class LaboratoryTestMeasuredTargetFact(StrictModel):
    claim_id: ClaimId
    analyte_name: ShortText
    typical_specimens: list[ShortText] = Field(min_length=0, max_length=10)
    assertion: MediumText


class LaboratoryTestClinicalSignificanceFact(StrictModel):
    claim_id: ClaimId
    significance_name: ShortText
    assertion: MediumText


class LaboratoryTestConditionFact(StrictModel):
    claim_id: ClaimId
    condition_name: ShortText
    assertion: MediumText


class LaboratoryTestItemContent(StrictModel):
    """Phase 5.11 minimum facts for a production laboratory test item.

    Reference ranges, units, principles, devices and external terminology are
    deliberately deferred. Those contracts require method- and jurisdiction-
    specific review beyond this MVP.
    """

    overview: list[FactClaim] = Field(min_length=0, max_length=10)
    measured_targets: list[LaboratoryTestMeasuredTargetFact] = Field(
        min_length=0, max_length=20
    )
    clinical_significance: list[LaboratoryTestClinicalSignificanceFact] = Field(
        min_length=0, max_length=30
    )
    high_conditions: list[LaboratoryTestConditionFact] = Field(
        min_length=0, max_length=40
    )
    low_conditions: list[LaboratoryTestConditionFact] = Field(
        min_length=0, max_length=40
    )
    measurement_methods: list[MeasurementMethodFact] = Field(
        min_length=0, max_length=20
    )


class LaboratoryTestItemCategoryContent(CategoryContentEnvelope):
    template_id: Literal["laboratory_test_item_v1.0"]
    laboratory_test_item: LaboratoryTestItemContent


CategoryContent = Annotated[
    TestItemCategoryContent
    | StainingMethodCategoryContent
    | SpecimenCategoryContent
    | ReagentCategoryContent
    | BiologicalStructureCategoryContent
    | DiseaseCategoryContent
    | LaboratoryTestItemCategoryContent,
    Field(discriminator="template_id"),
]


class ExamImportanceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ExamImportanceAssessment(StrictModel):
    level: ExamImportanceLevel
    score: float | None = Field(ge=0)
    score_scale_max: float | None = Field(gt=0)
    calculation_method: NullableText


class ExamFrequency(StrictModel):
    appearance_count: int = Field(ge=0)
    analyzed_question_count: int = Field(ge=1)
    frequency_rate: float | None = Field(ge=0, le=1)
    calculation_method: NullableText

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


class ExamBlueprintReference(StrictModel):
    blueprint_id: ShortText
    section_code: ShortText
    label: ShortText


class ExamMetadata(StrictModel):
    analysis_batch_id: NullableText
    importance: ExamImportanceAssessment | None
    first_appearance_session: int | None = Field(ge=1)
    last_appearance_session: int | None = Field(ge=1)
    appearance_frequency: ExamFrequency | None
    blueprint_references: list[ExamBlueprintReference] = Field(
        min_length=0, max_length=50
    )
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
    source_id: SourceId
    source_priority_rank: int = Field(ge=1, le=6)
    title: ShortText
    issuing_organization: NullableText
    edition: NullableText
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
    chapter: NullableText
    pages: NullableText
    supported_claim_ids: list[ClaimId] = Field(min_length=1, max_length=200)
    evidence_role: EvidenceRole


class ExamMetadataField(StrEnum):
    IMPORTANCE = "importance"
    FIRST_APPEARANCE = "first_appearance_session"
    LAST_APPEARANCE = "last_appearance_session"
    FREQUENCY = "appearance_frequency"
    BLUEPRINT_REFERENCES = "blueprint_references"
    RELATED_QUESTIONS = "related_questions"
    COMPARISON_TARGETS = "comparison_targets"
    RELATED_KNOWLEDGE = "related_knowledge"
    KEYWORDS = "keywords"


class PublisherUseProfile(StrictModel):
    priority_claim_ids: list[ClaimId] = Field(min_length=0, max_length=100)
    priority_exam_metadata: list[ExamMetadataField] = Field(min_length=0, max_length=9)


class PublishTargets(StrictModel):
    pdf: PublisherUseProfile
    note: PublisherUseProfile
    training_video: PublisherUseProfile
    national_exam: PublisherUseProfile


class KnowledgeRecord(StrictModel):
    schema_version: Literal["1.0"]
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
        expected_type = {
            "test_item_v1.0": "test_item",
            "staining_method_v1.0": "staining_method",
            "specimen_v1.0": "specimen",
            "reagent_v1.0": "reagent",
            "biological_structure_v1.0": "biological_structure",
            "disease_v1.0": "disease",
            "laboratory_test_item_v1.0": "laboratory_test_item",
        }[self.category_content.template_id]
        if self.classification.term_type != expected_type:
            raise ValueError(
                "classification.term_type must match category_content.template_id"
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
