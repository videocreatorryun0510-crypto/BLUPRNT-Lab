"""Knowledge JSON Version 0.2 models.

Version 0.2 adds a category-specific template for laboratory test items. Other
categories keep the generic Version 0.1 content shape and must not populate the
test-item block.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
]
MediumText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=180)]


class StrictModel(BaseModel):
    """Reject unknown properties so contract changes remain explicit."""

    model_config = ConfigDict(extra="forbid")


class TermType(StrEnum):
    """Content category, not the national-exam subject area."""

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
    """Clinical laboratory technologist national-exam subject area."""

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
    input: ShortText
    canonical_name: ShortText
    english_name: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=180)
    ]
    aliases: list[ShortText] = Field(min_length=0, max_length=5)


class Classification(StrictModel):
    term_type: TermType
    primary_exam_domain: ExamDomain
    related_exam_domains: list[ExamDomain] = Field(min_length=0, max_length=3)
    rationale: ShortText
    confidence: float = Field(ge=0, le=1)


class ExamEssential(StrictModel):
    point: ShortText
    why_it_matters: ShortText


class VisualHook(StrictModel):
    title: ShortText
    relation: ShortText


class StudyContent(StrictModel):
    definition: MediumText
    mechanism_or_principle: MediumText
    specimen_or_target: MediumText
    key_findings: list[ShortText] = Field(min_length=1, max_length=5)
    related_terms: list[ShortText] = Field(min_length=0, max_length=5)
    exam_pitfalls: list[ShortText] = Field(min_length=1, max_length=4)


class SpecimenInfo(StrictModel):
    specimen: ShortText
    anticoagulant_or_container: ShortText
    handling_and_stability: MediumText
    exam_focus: ShortText


class MeasurementMethod(StrictModel):
    method_name: ShortText
    standardizing_body: OptionalText
    method_summary: MediumText
    exam_focus: ShortText


class MeasurementPrinciple(StrictModel):
    measured_quantity: ShortText
    reaction_sequence: MediumText
    detection_signal: MediumText
    wavelength_or_endpoint: OptionalText


class ReferenceRange(StrictModel):
    population: ShortText
    specimen: ShortText
    display_value: ShortText
    unit: OptionalText
    conditions: ShortText
    verification_status: Literal["requires_source_check"]
    source_note: ShortText


class ConditionAssociation(StrictModel):
    condition: ShortText
    expected_change: Literal["high", "low"]
    reason: MediumText


class TestCombination(StrictModel):
    tests: list[ShortText] = Field(min_length=2, max_length=5)
    interpretation: MediumText
    exam_focus: ShortText


class ComparisonTest(StrictModel):
    test_name: ShortText
    comparison_axis: ShortText
    key_difference: MediumText


class TestItemContent(StrictModel):
    """Required standard template only for the ``test_item`` category."""

    purpose: list[ShortText] = Field(min_length=1, max_length=4)
    specimens: list[SpecimenInfo] = Field(min_length=1, max_length=4)
    measurement_methods: list[MeasurementMethod] = Field(min_length=1, max_length=6)
    measurement_principle: MeasurementPrinciple
    reference_ranges: list[ReferenceRange] = Field(min_length=1, max_length=4)
    high_conditions: list[ConditionAssociation] = Field(min_length=1, max_length=8)
    low_conditions: list[ConditionAssociation] = Field(min_length=0, max_length=6)
    low_value_note: MediumText
    related_test_combinations: list[TestCombination] = Field(min_length=1, max_length=6)
    interpretation_cautions: list[ShortText] = Field(min_length=2, max_length=8)
    frequent_exam_points: list[ShortText] = Field(min_length=5, max_length=10)
    comparison_tests: list[ComparisonTest] = Field(min_length=1, max_length=6)
    exam_keywords: list[ShortText] = Field(min_length=5, max_length=15)


class WarningItem(StrictModel):
    code: Literal[
        "ambiguous_term", "uncertain_fact", "needs_source_check", "test_fixture"
    ]
    message: ShortText


class KnowledgeDraft(StrictModel):
    """AI-produced, exam-focused content without system-owned metadata."""

    term: TermInfo
    classification: Classification
    template_id: Literal["test_item_v0.2", "generic_v0.1"]
    quick_summary: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=140)
    ]
    exam_essentials: list[ExamEssential] = Field(min_length=3, max_length=5)
    visual_hooks: list[VisualHook] = Field(min_length=1, max_length=4)
    study_content: StudyContent
    test_item_content: TestItemContent | None
    warnings: list[WarningItem] = Field(min_length=0, max_length=5)

    @model_validator(mode="after")
    def validate_category_template(self) -> Self:
        is_test_item = self.classification.term_type == TermType.TEST_ITEM
        if is_test_item:
            if self.template_id != "test_item_v0.2" or self.test_item_content is None:
                raise ValueError(
                    "test_item requires template_id test_item_v0.2 and test_item_content"
                )
        elif self.template_id != "generic_v0.1" or self.test_item_content is not None:
            raise ValueError(
                "non-test-item categories require generic_v0.1 and null test_item_content"
            )
        return self


class EvidenceReference(StrictModel):
    source_id: Annotated[str, StringConstraints(pattern=r"^src_[a-zA-Z0-9_-]{8,64}$")]
    source_priority_rank: int = Field(ge=1, le=6)
    title: ShortText
    locator: ShortText


class Provenance(StrictModel):
    provider: ShortText
    model: ShortText
    prompt_version: Literal["knowledge_generation_v0.2"]
    provider_request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=180)
    ]


class MedicalReview(StrictModel):
    status: Literal["unreviewed"]
    reviewer: Literal[""]
    reviewed_at: None


class KnowledgeRecord(KnowledgeDraft):
    """Validated Knowledge JSON Version 0.2 record shown in the workbench."""

    schema_version: Literal["0.2"]
    record_id: Annotated[str, StringConstraints(pattern=r"^mk_[a-f0-9]{16}$")]
    status: Literal["ai_draft"]
    source_status: Literal["ai_unverified"]
    generated_at: datetime
    evidence: list[EvidenceReference] = Field(min_length=0, max_length=20)
    provenance: Provenance
    medical_review: MedicalReview
