"""Map provider output into the system-owned Knowledge JSON Version 0.3."""

import hashlib
import unicodedata
from collections import Counter

from knowledge_contracts.v03 import KnowledgeSchemaError, validate_knowledge_record
from knowledge_contracts.v03.models import (
    Classification,
    CoreFacts,
    ExamMetadata,
    FactClaim,
    GenericCategoryContent,
    KnowledgeRecord,
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
from knowledge_workbench.generation_models import (
    GeneratedFact,
    GeneratedKnowledgeDraft,
    GeneratedMeasurementMethod,
    GeneratedValueAssociationGroup,
)


def map_to_knowledge_record(draft: GeneratedKnowledgeDraft) -> KnowledgeRecord:
    """Add stable IDs and empty system-owned sections, then validate Version 0.3."""

    knowledge_id = _knowledge_id(draft)
    claim_ids = _ClaimIdFactory(knowledge_id)
    core_facts = CoreFacts(
        definitions=_map_claims(claim_ids, "core_definition", draft.core_facts.definitions),
        mechanisms=_map_claims(claim_ids, "core_mechanism", draft.core_facts.mechanisms),
        characteristics=_map_claims(
            claim_ids, "core_characteristic", draft.core_facts.characteristics
        ),
    )

    category_content: GenericCategoryContent | TestItemCategoryContent
    if draft.test_item_content is None:
        category_content = GenericCategoryContent(template_id="generic_facts_v0.3")
    else:
        category_content = _map_test_item(claim_ids, draft.test_item_content)

    record = KnowledgeRecord(
        schema_version="0.3",
        knowledge_id=knowledge_id,
        content_revision=1,
        term=TermInfo(**draft.term.model_dump()),
        classification=Classification(**draft.classification.model_dump()),
        core_facts=core_facts,
        category_content=category_content,
        exam_metadata=ExamMetadata(
            analysis_batch_id="",
            importance=None,
            first_appearance_session=None,
            last_appearance_session=None,
            appearance_frequency=None,
            related_questions=[],
            comparison_targets=[],
            related_knowledge=[],
            priority_claim_ids=[],
            keywords=[],
        ),
        evidence=[],
        publish_targets=PublishTargets(
            pdf=_empty_publisher_profile(),
            note=_empty_publisher_profile(),
            training_video=_empty_publisher_profile(),
            national_exam=_empty_publisher_profile(),
        ),
    )
    try:
        return validate_knowledge_record(record)
    except KnowledgeSchemaError as error:
        raise KnowledgeMappingError(
            f"Knowledge JSON v0.3の検証に失敗しました（{error.path}）。{error.detail}"
        ) from error


def _map_test_item(claim_ids: "_ClaimIdFactory", content: object) -> TestItemCategoryContent:
    from knowledge_workbench.generation_models import GeneratedTestItemContent

    if not isinstance(content, GeneratedTestItemContent):
        raise KnowledgeMappingError("検査項目データをVersion 0.3へ変換できませんでした。")

    method_pairs = [
        (
            item,
            MeasurementMethodFact(
                claim_id=claim_ids.make("measurement_method", item.method_name),
                method_name=item.method_name,
                standardizing_body=item.standardizing_body,
                factual_description=item.factual_description,
            ),
        )
        for item in content.measurement_methods
    ]
    method_index = _method_claim_index(method_pairs)

    test_item = TestItemContent(
        purposes=_map_claims(claim_ids, "purpose", content.purposes),
        specimens=[
            SpecimenFact(
                claim_id=claim_ids.make("specimen", item.specimen),
                specimen=item.specimen,
                container_or_anticoagulant=item.container_or_anticoagulant,
                handling=item.handling,
                stability=item.stability,
            )
            for item in content.specimens
        ],
        measurement_methods=[mapped for _, mapped in method_pairs],
        measurement_principles=[
            MeasurementPrincipleFact(
                claim_id=claim_ids.make(
                    "measurement_principle",
                    f"{item.measured_quantity}:{item.detection_signal}",
                ),
                related_method_claim_ids=_resolve_method_names(
                    method_index, item.related_method_names
                ),
                measured_quantity=item.measured_quantity,
                reaction_sequence=item.reaction_sequence,
                detection_signal=item.detection_signal,
                wavelength_or_endpoint=item.wavelength_or_endpoint,
            )
            for item in content.measurement_principles
        ],
        reference_ranges=[
            ReferenceRangeFact(
                claim_id=claim_ids.make(
                    "reference_range",
                    f"{item.population}:{item.specimen}:{item.unit}:{item.qualitative_value}",
                ),
                population=item.population,
                specimen=item.specimen,
                related_method_claim_ids=_resolve_method_names(
                    method_index, item.related_method_names
                ),
                lower_bound=item.lower_bound,
                upper_bound=item.upper_bound,
                qualitative_value=item.qualitative_value,
                unit=item.unit,
                conditions=item.conditions,
            )
            for item in content.reference_ranges
        ],
        value_associations=ValueAssociations(
            high=_map_value_group(claim_ids, "high", content.value_associations.high),
            low=_map_value_group(claim_ids, "low", content.value_associations.low),
        ),
        related_test_combinations=[
            TestCombinationFact(
                claim_id=claim_ids.make("test_combination", ":".join(item.related_test_names)),
                related_test_names=item.related_test_names,
                related_knowledge_ids=[],
                factual_interpretation=item.factual_interpretation,
            )
            for item in content.related_test_combinations
        ],
        interpretation_cautions=_map_claims(
            claim_ids, "interpretation_caution", content.interpretation_cautions
        ),
    )
    return TestItemCategoryContent(template_id="test_item_v0.3", test_item=test_item)


def _map_value_group(
    claim_ids: "_ClaimIdFactory",
    direction: str,
    group: GeneratedValueAssociationGroup,
) -> ValueAssociationGroup:
    return ValueAssociationGroup(
        pathophysiologic_states=[
            PathophysiologicStateAssociation(
                claim_id=claim_ids.make(f"{direction}_state", item.state_name),
                state_name=item.state_name,
                related_knowledge_id=None,
                factual_relation=item.factual_relation,
            )
            for item in group.pathophysiologic_states
        ],
        representative_diseases=[
            RepresentativeDiseaseAssociation(
                claim_id=claim_ids.make(f"{direction}_disease", item.disease_name),
                disease_name=item.disease_name,
                disease_knowledge_id=None,
                factual_relation=item.factual_relation,
            )
            for item in group.representative_diseases
        ],
        interpretive_notes=_map_claims(claim_ids, f"{direction}_note", group.interpretive_notes),
    )


def _map_claims(
    claim_ids: "_ClaimIdFactory", scope: str, facts: list[GeneratedFact]
) -> list[FactClaim]:
    return [
        FactClaim(claim_id=claim_ids.make(scope, item.statement), statement=item.statement)
        for item in facts
    ]


def _method_claim_index(
    method_pairs: list[tuple[GeneratedMeasurementMethod, MeasurementMethodFact]],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for source, mapped in method_pairs:
        key = _normalize_seed(source.method_name)
        if key in index:
            raise KnowledgeMappingError("同じ測定方法名が重複して生成されました。")
        index[key] = mapped.claim_id
    return index


def _resolve_method_names(index: dict[str, str], names: list[str]) -> list[str]:
    resolved: list[str] = []
    for name in names:
        claim_id = index.get(_normalize_seed(name))
        if claim_id is None:
            raise KnowledgeMappingError(
                f"測定方法「{name}」に対応する測定原理・基準範囲を結び付けられませんでした。"
            )
        resolved.append(claim_id)
    return resolved


def _knowledge_id(draft: GeneratedKnowledgeDraft) -> str:
    seed = f"{draft.classification.term_type.value}:{_normalize_seed(draft.term.canonical_name)}"
    return f"knw_{_digest(seed)}"


def _empty_publisher_profile() -> PublisherUseProfile:
    return PublisherUseProfile(priority_claim_ids=[], priority_exam_metadata=[])


def _normalize_seed(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().lower().split())


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


class _ClaimIdFactory:
    def __init__(self, knowledge_id: str) -> None:
        self._knowledge_id = knowledge_id
        self._seen: Counter[tuple[str, str]] = Counter()

    def make(self, scope: str, identity: str) -> str:
        normalized_identity = _normalize_seed(identity)
        key = (scope, normalized_identity)
        occurrence = self._seen[key]
        self._seen[key] += 1
        seed = f"{self._knowledge_id}:{scope}:{normalized_identity}:{occurrence}"
        return f"clm_{_digest(seed)}"
