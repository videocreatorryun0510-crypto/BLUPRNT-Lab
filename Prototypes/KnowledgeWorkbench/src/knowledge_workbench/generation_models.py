"""Provider output models before mapping into Knowledge JSON Version 0.3.

AI providers may generate medical facts and classification only. Stable IDs,
exam analysis, evidence, and publisher policies remain system-owned.
"""

from typing import Annotated, Literal, Self

from knowledge_contracts.v03.models import ExamDomain, TermType
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
BlankText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class StrictGeneratedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneratedTermInfo(StrictGeneratedModel):
    canonical_name: ShortText
    english_name: BlankText
    aliases: list[ShortText] = Field(min_length=0, max_length=20)


class GeneratedClassification(StrictGeneratedModel):
    term_type: TermType
    primary_exam_domain: ExamDomain
    related_exam_domains: list[ExamDomain] = Field(min_length=0, max_length=5)


class GeneratedFact(StrictGeneratedModel):
    statement: MediumText


class GeneratedCoreFacts(StrictGeneratedModel):
    definitions: list[GeneratedFact] = Field(min_length=1, max_length=5)
    mechanisms: list[GeneratedFact] = Field(min_length=0, max_length=15)
    characteristics: list[GeneratedFact] = Field(min_length=0, max_length=30)


class GeneratedSpecimen(StrictGeneratedModel):
    specimen: ShortText
    container_or_anticoagulant: BlankText
    handling: MediumText
    stability: BlankText


class GeneratedMeasurementMethod(StrictGeneratedModel):
    method_name: ShortText
    standardizing_body: BlankText
    factual_description: MediumText


class GeneratedMeasurementPrinciple(StrictGeneratedModel):
    related_method_names: list[ShortText] = Field(min_length=0, max_length=15)
    measured_quantity: ShortText
    reaction_sequence: MediumText
    detection_signal: MediumText
    wavelength_or_endpoint: BlankText


class GeneratedReferenceRange(StrictGeneratedModel):
    population: ShortText
    specimen: ShortText
    related_method_names: list[ShortText] = Field(min_length=0, max_length=15)
    lower_bound: float | None
    upper_bound: float | None
    qualitative_value: BlankText
    unit: BlankText
    conditions: MediumText

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        has_numeric_value = self.lower_bound is not None or self.upper_bound is not None
        if not has_numeric_value and not self.qualitative_value:
            raise ValueError("reference range requires a numeric bound or qualitative_value")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound must not exceed upper_bound")
        return self


class GeneratedPathophysiologicState(StrictGeneratedModel):
    state_name: ShortText
    factual_relation: MediumText


class GeneratedRepresentativeDisease(StrictGeneratedModel):
    disease_name: ShortText
    factual_relation: MediumText


class GeneratedValueAssociationGroup(StrictGeneratedModel):
    pathophysiologic_states: list[GeneratedPathophysiologicState] = Field(
        min_length=0, max_length=20
    )
    representative_diseases: list[GeneratedRepresentativeDisease] = Field(
        min_length=0, max_length=30
    )
    interpretive_notes: list[GeneratedFact] = Field(min_length=0, max_length=10)


class GeneratedValueAssociations(StrictGeneratedModel):
    high: GeneratedValueAssociationGroup
    low: GeneratedValueAssociationGroup


class GeneratedTestCombination(StrictGeneratedModel):
    related_test_names: list[ShortText] = Field(min_length=1, max_length=10)
    factual_interpretation: MediumText


class GeneratedTestItemContent(StrictGeneratedModel):
    purposes: list[GeneratedFact] = Field(min_length=1, max_length=10)
    specimens: list[GeneratedSpecimen] = Field(min_length=1, max_length=10)
    measurement_methods: list[GeneratedMeasurementMethod] = Field(min_length=1, max_length=15)
    measurement_principles: list[GeneratedMeasurementPrinciple] = Field(min_length=1, max_length=15)
    reference_ranges: list[GeneratedReferenceRange] = Field(min_length=0, max_length=20)
    value_associations: GeneratedValueAssociations
    related_test_combinations: list[GeneratedTestCombination] = Field(min_length=0, max_length=15)
    interpretation_cautions: list[GeneratedFact] = Field(min_length=0, max_length=20)


class GeneratedKnowledgeDraft(StrictGeneratedModel):
    """Structured OpenAI output that cannot set system-owned SSOT fields."""

    term: GeneratedTermInfo
    classification: GeneratedClassification
    core_facts: GeneratedCoreFacts
    template_id: Literal["test_item_v0.3", "generic_facts_v0.3"]
    test_item_content: GeneratedTestItemContent | None

    @model_validator(mode="after")
    def validate_category_template(self) -> Self:
        is_test_item = self.classification.term_type == TermType.TEST_ITEM
        if is_test_item:
            if self.template_id != "test_item_v0.3" or self.test_item_content is None:
                raise ValueError("test_item requires test_item_v0.3 and test_item_content")
        elif self.template_id != "generic_facts_v0.3" or self.test_item_content is not None:
            raise ValueError("non-test-item requires generic_facts_v0.3 and null test_item_content")
        return self
