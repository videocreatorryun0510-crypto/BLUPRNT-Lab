"""Map a validated Version 0.3 test-item record into Version 1.0."""

from knowledge_contracts.v03 import KnowledgeRecord as KnowledgeRecordV03
from knowledge_contracts.v03.models import (
    EvidenceReference as EvidenceReferenceV03,
)
from knowledge_contracts.v03.models import (
    FactClaim as FactClaimV03,
)
from knowledge_contracts.v03.models import (
    PublisherUseProfile as PublisherUseProfileV03,
)
from knowledge_contracts.v03.models import (
    TestItemCategoryContent as TestItemCategoryContentV03,
)
from knowledge_contracts.v03.models import (
    ValueAssociationGroup as ValueAssociationGroupV03,
)
from knowledge_contracts.v10 import KnowledgeSchemaError, validate_knowledge_record
from knowledge_contracts.v10.models import (
    Classification,
    CoreFacts,
    EvidenceReference,
    ExamDomain,
    ExamFrequency,
    ExamImportanceAssessment,
    ExamImportanceLevel,
    ExamMetadata,
    ExamQuestionReference,
    FactClaim,
    KnowledgeRecord,
    KnowledgeRelation,
    MeasurementMethodFact,
    MeasurementPrincipleFact,
    PathophysiologicStateAssociation,
    PublisherUseProfile,
    PublishTargets,
    ReferenceRangeFact,
    RepresentativeDiseaseAssociation,
    SpecimenFact,
    TermInfo,
    TestCombinationFact,
    TestItemCategoryContent,
    TestItemContent,
    ValueAssociationGroup,
    ValueAssociations,
)

from knowledge_workbench.errors import KnowledgeMappingError


def map_v03_to_v10(record: KnowledgeRecordV03) -> KnowledgeRecord:
    """Preserve Version 0.3 and create a separate Version 1.0 record."""

    if not isinstance(record.category_content, TestItemCategoryContentV03):
        raise KnowledgeMappingError(
            "Knowledge JSON Version 1.0 MVPは検査項目だけに対応しています。"
        )
    old = record.category_content.test_item
    mapped = KnowledgeRecord(
        schema_version="1.0",
        knowledge_id=record.knowledge_id,
        content_revision=record.content_revision,
        term=TermInfo(
            canonical_name=record.term.canonical_name,
            english_name=_optional(record.term.english_name),
            aliases=record.term.aliases,
        ),
        classification=Classification(
            term_type="test_item",
            primary_exam_domain=ExamDomain(record.classification.primary_exam_domain.value),
            related_exam_domains=[
                ExamDomain(item.value) for item in record.classification.related_exam_domains
            ],
        ),
        core_facts=CoreFacts(definitions=[_fact(claim) for claim in record.core_facts.definitions]),
        category_content=TestItemCategoryContent(
            template_id="test_item_v1.0",
            test_item=TestItemContent(
                biological_basis=[_fact(claim) for claim in record.core_facts.mechanisms],
                analyte_characteristics=[
                    _fact(claim) for claim in record.core_facts.characteristics
                ],
                purposes=[_fact(claim) for claim in old.purposes],
                specimens=[
                    SpecimenFact(
                        claim_id=item.claim_id,
                        specimen=item.specimen,
                        container_or_anticoagulant=_optional(item.container_or_anticoagulant),
                        handling=item.handling,
                        stability=_optional(item.stability),
                    )
                    for item in old.specimens
                ],
                measurement_methods=[
                    MeasurementMethodFact(
                        claim_id=item.claim_id,
                        method_name=item.method_name,
                        method_family=None,
                        assertion=item.factual_description,
                    )
                    for item in old.measurement_methods
                ],
                measurement_principles=[
                    MeasurementPrincipleFact(
                        claim_id=item.claim_id,
                        related_method_claim_ids=item.related_method_claim_ids,
                        measured_quantity=item.measured_quantity,
                        reaction_sequence=item.reaction_sequence,
                        detection_signal=item.detection_signal,
                        wavelength_or_endpoint=_optional(item.wavelength_or_endpoint),
                        assertion=item.reaction_sequence,
                    )
                    for item in old.measurement_principles
                ],
                standardization_and_traceability=[],
                reporting_systems=[],
                reference_ranges=[
                    ReferenceRangeFact(
                        claim_id=item.claim_id,
                        population=item.population,
                        specimen=item.specimen,
                        related_method_claim_ids=item.related_method_claim_ids,
                        lower_bound=item.lower_bound,
                        upper_bound=item.upper_bound,
                        qualitative_value=_optional(item.qualitative_value),
                        unit=_optional(item.unit),
                        conditions=item.conditions,
                    )
                    for item in old.reference_ranges
                ],
                clinical_decision_limits=[],
                value_associations=ValueAssociations(
                    high=_value_group(old.value_associations.high),
                    low=_value_group(old.value_associations.low),
                ),
                related_test_combinations=[
                    TestCombinationFact(
                        claim_id=item.claim_id,
                        related_test_names=item.related_test_names,
                        related_knowledge_ids=item.related_knowledge_ids,
                        assertion=item.factual_interpretation,
                    )
                    for item in old.related_test_combinations
                ],
                analytical_interferences=[],
                interpretation_cautions=[_fact(claim) for claim in old.interpretation_cautions],
                time_course=[],
                isoenzymes=[],
            ),
        ),
        exam_metadata=_exam_metadata(record),
        evidence=[_evidence(source) for source in record.evidence],
        publish_targets=PublishTargets(
            pdf=_publisher_profile(record.publish_targets.pdf),
            note=_publisher_profile(record.publish_targets.note),
            training_video=_publisher_profile(record.publish_targets.training_video),
            national_exam=_publisher_profile(record.publish_targets.national_exam),
        ),
    )
    try:
        return validate_knowledge_record(mapped)
    except KnowledgeSchemaError as error:
        raise KnowledgeMappingError(
            f"Knowledge JSON v1.0の検証に失敗しました（{error.path}）。{error.detail}"
        ) from error


def _fact(claim: FactClaimV03) -> FactClaim:
    return FactClaim(claim_id=claim.claim_id, assertion=claim.statement)


def _value_group(group: ValueAssociationGroupV03) -> ValueAssociationGroup:
    return ValueAssociationGroup(
        pathophysiologic_states=[
            PathophysiologicStateAssociation(
                claim_id=item.claim_id,
                state_name=item.state_name,
                related_knowledge_id=item.related_knowledge_id,
                assertion=item.factual_relation,
            )
            for item in group.pathophysiologic_states
        ],
        representative_diseases=[
            RepresentativeDiseaseAssociation(
                claim_id=item.claim_id,
                disease_name=item.disease_name,
                disease_knowledge_id=item.disease_knowledge_id,
                assertion=item.factual_relation,
            )
            for item in group.representative_diseases
        ],
        interpretive_notes=[_fact(claim) for claim in group.interpretive_notes],
    )


def _exam_metadata(record: KnowledgeRecordV03) -> ExamMetadata:
    old = record.exam_metadata
    importance = (
        ExamImportanceAssessment(
            level=ExamImportanceLevel(old.importance.level.value),
            score=old.importance.score,
            score_scale_max=old.importance.score_scale_max,
            calculation_method=_optional(old.importance.calculation_method),
        )
        if old.importance is not None
        else None
    )
    frequency = (
        ExamFrequency(
            appearance_count=old.appearance_frequency.appearance_count,
            analyzed_question_count=old.appearance_frequency.analyzed_question_count,
            frequency_rate=old.appearance_frequency.frequency_rate,
            calculation_method=_optional(old.appearance_frequency.calculation_method),
        )
        if old.appearance_frequency is not None
        else None
    )
    return ExamMetadata(
        analysis_batch_id=_optional(old.analysis_batch_id),
        importance=importance,
        first_appearance_session=old.first_appearance_session,
        last_appearance_session=old.last_appearance_session,
        appearance_frequency=frequency,
        blueprint_references=[],
        related_questions=[
            ExamQuestionReference(
                question_id=item.question_id,
                exam_session=item.exam_session,
                question_number=item.question_number,
                tested_claim_ids=item.tested_claim_ids,
            )
            for item in old.related_questions
        ],
        comparison_targets=[
            KnowledgeRelation(knowledge_id=item.knowledge_id, label=item.label)
            for item in old.comparison_targets
        ],
        related_knowledge=[
            KnowledgeRelation(knowledge_id=item.knowledge_id, label=item.label)
            for item in old.related_knowledge
        ],
        priority_claim_ids=old.priority_claim_ids,
        keywords=old.keywords,
    )


def _evidence(source: EvidenceReferenceV03) -> EvidenceReference:
    raw = source.model_dump(mode="json")
    for key in (
        "issuing_organization",
        "edition",
        "chapter",
        "pages",
    ):
        raw[key] = _optional(raw.get(key))
    return EvidenceReference.model_validate(raw)


def _publisher_profile(profile: PublisherUseProfileV03) -> PublisherUseProfile:
    raw = profile.model_dump(mode="json")
    return PublisherUseProfile.model_validate(raw)


def _optional(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
