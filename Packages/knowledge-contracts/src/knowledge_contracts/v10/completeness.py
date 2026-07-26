"""Medical Knowledge Completeness for Knowledge JSON Version 1.0."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from knowledge_contracts.v10.models import (
    BiologicalStructureCategoryContent,
    DiseaseCategoryContent,
    KnowledgeRecord,
    LaboratoryTestItemCategoryContent,
    ReagentCategoryContent,
    SpecimenCategoryContent,
    StainingMethodCategoryContent,
    StrictModel,
    TestItemCategoryContent,
)
from knowledge_contracts.v10.validation import validate_knowledge_record


class RequirementSeverity(StrEnum):
    CRITICAL_REQUIRED = "critical_required"
    REQUIRED = "required"
    RECOMMENDED_OPTIONAL = "recommended_optional"


class RequirementStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class CompletenessLevel(StrEnum):
    COMPLETE_FOR_REVIEW = "complete_for_review"
    MOSTLY_COMPLETE = "mostly_complete"
    INCOMPLETE = "incomplete"
    CRITICALLY_INCOMPLETE = "critically_incomplete"


class RequirementResult(StrictModel):
    requirement_id: str
    json_path: str
    label: str
    severity: RequirementSeverity
    weight: float = Field(ge=0)
    earned_points: float = Field(ge=0)
    status: RequirementStatus
    minimum_count: int = Field(ge=0)
    target_count: int = Field(ge=1)
    actual_valid_count: int = Field(ge=0)


class MissingItem(StrictModel):
    requirement_id: str
    json_path: str
    label: str
    severity: RequirementSeverity
    points_lost: float = Field(ge=0)


class ImprovementCandidate(StrictModel):
    priority: Literal["critical", "high", "medium", "low"]
    requirement_id: str
    label: str
    action: str
    suggested_owner: Literal[
        "ai_with_approved_evidence",
        "developer",
        "medical_reviewer",
        "product_owner",
    ]


class ScoreBreakdown(StrictModel):
    category_content_points: float = Field(ge=0, le=85)
    evidence_points: float = Field(ge=0, le=15)
    raw_total: float = Field(ge=0, le=100)
    capped_total: int = Field(ge=0, le=100)


class CompletenessAssessment(StrictModel):
    assessment_version: Literal["1.1"]
    knowledge_id: str
    content_revision: int = Field(ge=1)
    profile_id: Literal[
        "knowledge_completeness.test_item",
        "knowledge_completeness.staining_method",
        "knowledge_completeness.specimen",
        "knowledge_completeness.reagent",
        "knowledge_completeness.biological_structure",
        "knowledge_completeness.disease",
        "knowledge_completeness.laboratory_test_item",
    ]
    profile_version: Literal["1.0", "1.1"]
    evaluated_at: datetime
    evaluation_engine_version: Literal["1.1"]
    validation_status: Literal["completed"]
    score: int = Field(ge=0, le=100)
    level: CompletenessLevel
    is_complete_for_review: bool
    score_breakdown: ScoreBreakdown
    requirement_results: list[RequirementResult]
    missing_items: list[MissingItem]
    improvement_candidates: list[ImprovementCandidate]


@dataclass(frozen=True)
class _Requirement:
    requirement_id: str
    json_path: str
    label: str
    severity: RequirementSeverity
    weight: float
    minimum_count: int
    target_count: int
    actual_count: int
    action: str
    owner: Literal[
        "ai_with_approved_evidence",
        "developer",
        "medical_reviewer",
        "product_owner",
    ]


def evaluate_test_item_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score medical facts and evidence without using exam metadata."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, TestItemCategoryContent):
        raise ValueError("test-item completeness requires term_type=test_item")
    content = record.category_content.test_item
    value_count = sum(
        len(group.pathophysiologic_states)
        + len(group.representative_diseases)
        + len(group.interpretive_notes)
        for group in (content.value_associations.high, content.value_associations.low)
    )
    requirements = [
        _requirement(
            "test_item.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            6,
            len(record.core_facts.definitions),
            "承認済み根拠から検査項目の定義を追加する。",
        ),
        _requirement(
            "test_item.biological_basis",
            "/category_content/test_item/biological_basis",
            "生物学的基盤",
            RequirementSeverity.REQUIRED,
            6,
            len(content.biological_basis),
            "検査対象の生物学的機序をclaim単位で追加する。",
        ),
        _requirement(
            "test_item.analyte_characteristics",
            "/category_content/test_item/analyte_characteristics",
            "検査対象の特徴",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            4,
            len(content.analyte_characteristics),
            "検査対象の分布や性質を承認済み根拠から追加する。",
        ),
        _requirement(
            "test_item.purposes",
            "/category_content/test_item/purposes",
            "検査の目的",
            RequirementSeverity.REQUIRED,
            7,
            len(content.purposes),
            "検査目的を追加する。",
        ),
        _requirement(
            "test_item.specimens",
            "/category_content/test_item/specimens",
            "検体",
            RequirementSeverity.CRITICAL_REQUIRED,
            8,
            len(content.specimens),
            "検体、取扱い、必要な抗凝固剤を確認して追加する。",
        ),
        _requirement(
            "test_item.measurement_methods",
            "/category_content/test_item/measurement_methods",
            "測定法",
            RequirementSeverity.CRITICAL_REQUIRED,
            12,
            len(content.measurement_methods),
            "国家試験で扱う代表的な測定法を追加する。",
            target_count=2,
        ),
        _requirement(
            "test_item.measurement_principles",
            "/category_content/test_item/measurement_principles",
            "測定原理",
            RequirementSeverity.CRITICAL_REQUIRED,
            12,
            len(content.measurement_principles),
            "各測定法に対応する測定原理を追加する。",
            target_count=2,
        ),
        _requirement(
            "test_item.standardization_and_traceability",
            "/category_content/test_item/standardization_and_traceability",
            "標準化・トレーサビリティ",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            4,
            len(content.standardization_and_traceability),
            "標準化体系と測定法の関係を出典付きで追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "test_item.reporting_systems",
            "/category_content/test_item/reporting_systems",
            "報告単位・報告方式",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            4,
            len(content.reporting_systems),
            "報告単位と報告方式を出典付きで追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "test_item.reference_ranges",
            "/category_content/test_item/reference_ranges",
            "基準範囲",
            RequirementSeverity.REQUIRED,
            8,
            len(content.reference_ranges),
            "対象集団、検体、測定法、単位を伴う基準範囲を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "test_item.value_associations",
            "/category_content/test_item/value_associations",
            "高値・低値との関連",
            RequirementSeverity.REQUIRED,
            5,
            value_count,
            "高値・低値に関連する病態と代表疾患を追加する。",
            target_count=2,
        ),
        _requirement(
            "test_item.related_test_combinations",
            "/category_content/test_item/related_test_combinations",
            "他検査との組み合わせ",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            3,
            len(content.related_test_combinations),
            "組み合わせて解釈する代表検査を追加する。",
        ),
        _requirement(
            "test_item.analytical_interferences",
            "/category_content/test_item/analytical_interferences",
            "干渉物質・分析上の影響",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            3,
            len(content.analytical_interferences),
            "溶血、乳び、黄疸などの方法依存の影響を構造化する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "test_item.interpretation_cautions",
            "/category_content/test_item/interpretation_cautions",
            "解釈時の注意点",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            3,
            len(content.interpretation_cautions),
            "解釈時に必要な注意点を追加する。",
        ),
    ]

    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.test_item",
        profile_version="1.1",
    )


def evaluate_staining_method_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score the facts required to operate a staining-method record."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, StainingMethodCategoryContent):
        raise ValueError(
            "staining-method completeness requires term_type=staining_method"
        )
    content = record.category_content.staining_method
    requirements = [
        _requirement(
            "staining_method.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            7,
            len(record.core_facts.definitions),
            "染色法が何を区別・観察する方法かを出典付きで追加する。",
        ),
        _requirement(
            "staining_method.purposes",
            "/category_content/staining_method/purposes",
            "目的",
            RequirementSeverity.REQUIRED,
            7,
            len(content.purposes),
            "検査・観察における染色目的を追加する。",
        ),
        _requirement(
            "staining_method.target_structures",
            "/category_content/staining_method/target_structures",
            "対象構造",
            RequirementSeverity.REQUIRED,
            8,
            len(content.target_structures),
            "染色性を決める細胞・組織構造を追加する。",
        ),
        _requirement(
            "staining_method.fixation_requirements",
            "/category_content/staining_method/fixation_requirements",
            "固定法",
            RequirementSeverity.CRITICAL_REQUIRED,
            8,
            len(content.fixation_requirements),
            "標本の固定方法と条件を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.reagents",
            "/category_content/staining_method/reagents",
            "試薬",
            RequirementSeverity.CRITICAL_REQUIRED,
            10,
            len(content.reagents),
            "主要試薬と各試薬の役割を追加する。",
            target_count=4,
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.procedure_steps",
            "/category_content/staining_method/procedure_steps",
            "工程",
            RequirementSeverity.CRITICAL_REQUIRED,
            12,
            len(content.procedure_steps),
            "順序と使用試薬を持つ染色工程を追加する。",
            target_count=4,
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.result_interpretations",
            "/category_content/staining_method/result_interpretations",
            "判定",
            RequirementSeverity.CRITICAL_REQUIRED,
            10,
            len(content.result_interpretations),
            "観察色・パターンと判定の対応を追加する。",
            target_count=2,
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.quality_controls",
            "/category_content/staining_method/quality_controls",
            "精度管理",
            RequirementSeverity.CRITICAL_REQUIRED,
            9,
            len(content.quality_controls),
            "陽性・陰性対照と期待結果を追加する。",
            target_count=2,
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.limitations",
            "/category_content/staining_method/limitations",
            "限界",
            RequirementSeverity.REQUIRED,
            9,
            len(content.limitations),
            "適用できない対象や誤判定につながる限界を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "staining_method.staining_principles",
            "/category_content/staining_method/staining_principles",
            "染色原理",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            5,
            len(content.staining_principles),
            "構造差と染色結果を結ぶ原理を追加する。",
            target_count=2,
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.staining_method",
        profile_version="1.0",
    )


def evaluate_specimen_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score the facts required to operate a specimen record."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, SpecimenCategoryContent):
        raise ValueError("specimen completeness requires term_type=specimen")
    content = record.category_content.specimen
    requirements = [
        _requirement(
            "specimen.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            12,
            len(record.core_facts.definitions),
            "検体・標本が何を指すかを出典付きで追加する。",
        ),
        _requirement(
            "specimen.overview",
            "/category_content/specimen/overview",
            "概要",
            RequirementSeverity.REQUIRED,
            13,
            len(content.overview),
            "検体・標本の性質と検査上の位置付けを追加する。",
        ),
        _requirement(
            "specimen.uses",
            "/category_content/specimen/uses",
            "使用用途",
            RequirementSeverity.REQUIRED,
            15,
            len(content.uses),
            "代表的な検査・観察用途を追加する。",
        ),
        _requirement(
            "specimen.collection_methods",
            "/category_content/specimen/collection_methods",
            "採取・作製方法",
            RequirementSeverity.CRITICAL_REQUIRED,
            18,
            len(content.collection_methods),
            "採取元、容器、作製手順を標準作業書と出典から追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "specimen.storage_conditions",
            "/category_content/specimen/storage_conditions",
            "保存条件",
            RequirementSeverity.CRITICAL_REQUIRED,
            17,
            len(content.storage_conditions),
            "温度、時間、前処理を含む保存条件を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "specimen.cautions",
            "/category_content/specimen/cautions",
            "注意事項",
            RequirementSeverity.REQUIRED,
            10,
            len(content.cautions),
            "検体品質、安全、結果への影響に関する注意を追加する。",
            owner="medical_reviewer",
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.specimen",
        profile_version="1.0",
    )


def evaluate_reagent_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score the facts required to review and operate a reagent record."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, ReagentCategoryContent):
        raise ValueError("reagent completeness requires term_type=reagent")
    content = record.category_content.reagent
    requirements = [
        _requirement(
            "reagent.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            15,
            len(record.core_facts.definitions),
            "試薬の役割と適用範囲を出典付きで追加する。",
        ),
        _requirement(
            "reagent.purposes",
            "/category_content/reagent/purposes",
            "用途",
            RequirementSeverity.REQUIRED,
            15,
            len(content.purposes),
            "検査・染色での用途を追加する。",
        ),
        _requirement(
            "reagent.targets",
            "/category_content/reagent/targets",
            "使用対象",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            10,
            len(content.targets),
            "使用する標本や対象構造を追加する。",
        ),
        _requirement(
            "reagent.usage_steps",
            "/category_content/reagent/usage_steps",
            "使用工程",
            RequirementSeverity.CRITICAL_REQUIRED,
            20,
            len(content.usage_steps),
            "工程上の役割、使用方法、条件を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "reagent.cautions",
            "/category_content/reagent/cautions",
            "注意事項",
            RequirementSeverity.CRITICAL_REQUIRED,
            15,
            len(content.cautions),
            "品質、安全、判定への影響に関する注意を追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "reagent.storage_conditions",
            "/category_content/reagent/storage_conditions",
            "保管条件",
            RequirementSeverity.RECOMMENDED_OPTIONAL,
            10,
            len(content.storage_conditions),
            "製品添付文書または標準作業書に基づく保管条件を追加する。",
            owner="medical_reviewer",
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.reagent",
        profile_version="1.0",
    )


def evaluate_biological_structure_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score only the approved Phase 5.8 biological-structure MVP fields."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, BiologicalStructureCategoryContent):
        raise ValueError(
            "biological-structure completeness requires term_type=biological_structure"
        )
    content = record.category_content.biological_structure
    requirements = [
        _requirement(
            "biological_structure.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            40,
            len(record.core_facts.definitions),
            "生体構造が何を指すかを出典付きで追加する。",
        ),
        _requirement(
            "biological_structure.main_functions",
            "/category_content/biological_structure/main_functions",
            "主な機能",
            RequirementSeverity.REQUIRED,
            45,
            len(content.main_functions),
            "生体構造の主要な機能を出典付きで追加する。",
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.biological_structure",
        profile_version="1.0",
    )


def evaluate_disease_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score only the approved Phase 5.10 Disease MVP requirements."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, DiseaseCategoryContent):
        raise ValueError("disease completeness requires term_type=disease")
    content = record.category_content.disease
    requirements = [
        _requirement(
            "disease.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            25,
            len(record.core_facts.definitions),
            "疾患が何を指すかを出典付きで追加する。",
        ),
        _requirement(
            "disease.pathophysiology",
            "/category_content/disease/pathophysiology",
            "病態",
            RequirementSeverity.CRITICAL_REQUIRED,
            30,
            len(content.pathophysiology),
            "疾患が成立する主要な病態を出典付きで追加する。",
        ),
        _requirement(
            "disease.main_laboratory_findings",
            "/category_content/disease/main_laboratory_findings",
            "主な検査所見",
            RequirementSeverity.CRITICAL_REQUIRED,
            30,
            len(content.main_laboratory_findings),
            "国家試験で識別に必要な代表検査所見を追加する。",
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.disease",
        profile_version="1.0",
    )


def evaluate_laboratory_test_item_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Score only the approved Phase 5.11 laboratory-test-item MVP fields."""

    record = validate_knowledge_record(value)
    if not isinstance(record.category_content, LaboratoryTestItemCategoryContent):
        raise ValueError(
            "laboratory-test-item completeness requires "
            "term_type=laboratory_test_item"
        )
    content = record.category_content.laboratory_test_item
    requirements = [
        _requirement(
            "laboratory_test_item.definitions",
            "/core_facts/definitions",
            "定義",
            RequirementSeverity.REQUIRED,
            20,
            len(record.core_facts.definitions),
            "検査項目が何を測るかを出典付きで定義する。",
        ),
        _requirement(
            "laboratory_test_item.clinical_significance",
            "/category_content/laboratory_test_item/clinical_significance",
            "臨床的意義",
            RequirementSeverity.CRITICAL_REQUIRED,
            30,
            len(content.clinical_significance),
            "結果を何の評価に使うかを出典付きで追加する。",
            owner="medical_reviewer",
        ),
        _requirement(
            "laboratory_test_item.measured_targets",
            "/category_content/laboratory_test_item/measured_targets",
            "測定対象",
            RequirementSeverity.CRITICAL_REQUIRED,
            35,
            len(content.measured_targets),
            "測定する分析対象と代表検体を出典付きで追加する。",
            owner="medical_reviewer",
        ),
    ]
    return _evaluate_requirements(
        record,
        requirements,
        profile_id="knowledge_completeness.laboratory_test_item",
        profile_version="1.0",
    )


def evaluate_knowledge_completeness(
    value: KnowledgeRecord | dict[str, object],
) -> CompletenessAssessment:
    """Dispatch completeness evaluation by the validated Category Union."""

    record = validate_knowledge_record(value)
    if record.classification.term_type == "test_item":
        return evaluate_test_item_completeness(record)
    if record.classification.term_type == "staining_method":
        return evaluate_staining_method_completeness(record)
    if record.classification.term_type == "specimen":
        return evaluate_specimen_completeness(record)
    if record.classification.term_type == "reagent":
        return evaluate_reagent_completeness(record)
    if record.classification.term_type == "biological_structure":
        return evaluate_biological_structure_completeness(record)
    if record.classification.term_type == "disease":
        return evaluate_disease_completeness(record)
    if record.classification.term_type == "laboratory_test_item":
        return evaluate_laboratory_test_item_completeness(record)
    raise ValueError(
        f"unsupported completeness category: {record.classification.term_type}"
    )


def _evaluate_requirements(
    record: KnowledgeRecord,
    requirements: list[_Requirement],
    *,
    profile_id: Literal[
        "knowledge_completeness.test_item",
        "knowledge_completeness.staining_method",
        "knowledge_completeness.specimen",
        "knowledge_completeness.reagent",
        "knowledge_completeness.biological_structure",
        "knowledge_completeness.disease",
        "knowledge_completeness.laboratory_test_item",
    ],
    profile_version: Literal["1.0", "1.1"],
) -> CompletenessAssessment:
    category_results = [_score_requirement(item) for item in requirements]
    claim_ids = _collect_claim_ids(record.model_dump(mode="json"))
    supported_claim_ids = {
        claim_id
        for source in record.evidence
        for claim_id in source.supported_claim_ids
    }
    supported_count = len(set(claim_ids) & supported_claim_ids)
    evidence_points = 15 * supported_count / len(set(claim_ids)) if claim_ids else 0.0
    evidence_result = _external_result(
        requirement_id="common.evidence",
        json_path="/evidence",
        label="出典",
        weight=15,
        earned=evidence_points,
        actual=supported_count,
        target=max(len(set(claim_ids)), 1),
    )

    all_results = [*category_results, evidence_result]
    category_points = sum(item.earned_points for item in category_results)
    raw_total = category_points + evidence_points

    incomplete_required = [
        result
        for result in category_results
        if result.status != RequirementStatus.COMPLETE
        and result.severity
        in {
            RequirementSeverity.CRITICAL_REQUIRED,
            RequirementSeverity.REQUIRED,
        }
    ]
    blocking_missing = [
        result
        for result in incomplete_required
        if result.status == RequirementStatus.MISSING
    ]
    if any(
        item.severity == RequirementSeverity.CRITICAL_REQUIRED
        for item in blocking_missing
    ):
        capped_score = min(round(raw_total), 49)
    elif blocking_missing:
        capped_score = min(round(raw_total), 79)
    else:
        capped_score = round(raw_total)

    missing_items = [
        MissingItem(
            requirement_id=result.requirement_id,
            json_path=result.json_path,
            label=result.label,
            severity=result.severity,
            points_lost=round(result.weight - result.earned_points, 2),
        )
        for result in all_results
        if result.status != RequirementStatus.COMPLETE
    ]
    requirement_index = {item.requirement_id: item for item in requirements}
    improvements = [
        _improvement_for(result, requirement_index)
        for result in all_results
        if result.status != RequirementStatus.COMPLETE
    ]
    level = _level_for(capped_score)
    complete_for_review = (
        capped_score >= 90
        and not incomplete_required
        and evidence_result.status == RequirementStatus.COMPLETE
    )

    return CompletenessAssessment(
        assessment_version="1.1",
        knowledge_id=record.knowledge_id,
        content_revision=record.content_revision,
        profile_id=profile_id,
        profile_version=profile_version,
        evaluated_at=datetime.now(UTC),
        evaluation_engine_version="1.1",
        validation_status="completed",
        score=capped_score,
        level=level,
        is_complete_for_review=complete_for_review,
        score_breakdown=ScoreBreakdown(
            category_content_points=round(category_points, 2),
            evidence_points=round(evidence_points, 2),
            raw_total=round(raw_total, 2),
            capped_total=capped_score,
        ),
        requirement_results=all_results,
        missing_items=missing_items,
        improvement_candidates=improvements,
    )


def _requirement(
    requirement_id: str,
    path: str,
    label: str,
    severity: RequirementSeverity,
    weight: float,
    actual_count: int,
    action: str,
    *,
    target_count: int = 1,
    owner: Literal[
        "ai_with_approved_evidence",
        "developer",
        "medical_reviewer",
        "product_owner",
    ] = "ai_with_approved_evidence",
) -> _Requirement:
    return _Requirement(
        requirement_id=requirement_id,
        json_path=path,
        label=label,
        severity=severity,
        weight=weight,
        minimum_count=1,
        target_count=target_count,
        actual_count=actual_count,
        action=action,
        owner=owner,
    )


def _score_requirement(requirement: _Requirement) -> RequirementResult:
    coverage = min(requirement.actual_count / requirement.target_count, 1.0)
    earned = round(requirement.weight * coverage, 2)
    if requirement.actual_count < requirement.minimum_count:
        status = RequirementStatus.MISSING
    elif requirement.actual_count < requirement.target_count:
        status = RequirementStatus.PARTIAL
    else:
        status = RequirementStatus.COMPLETE
    return RequirementResult(
        requirement_id=requirement.requirement_id,
        json_path=requirement.json_path,
        label=requirement.label,
        severity=requirement.severity,
        weight=requirement.weight,
        earned_points=earned,
        status=status,
        minimum_count=requirement.minimum_count,
        target_count=requirement.target_count,
        actual_valid_count=requirement.actual_count,
    )


def _external_result(
    requirement_id: str,
    json_path: str,
    label: str,
    weight: float,
    earned: float,
    actual: int,
    target: int,
) -> RequirementResult:
    if earned >= weight:
        status = RequirementStatus.COMPLETE
    elif earned > 0:
        status = RequirementStatus.PARTIAL
    else:
        status = RequirementStatus.MISSING
    return RequirementResult(
        requirement_id=requirement_id,
        json_path=json_path,
        label=label,
        severity=RequirementSeverity.RECOMMENDED_OPTIONAL,
        weight=weight,
        earned_points=round(earned, 2),
        status=status,
        minimum_count=0,
        target_count=target,
        actual_valid_count=actual,
    )


def _collect_claim_ids(value: object) -> list[str]:
    claim_ids: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "claim_id" and isinstance(child, str):
                    claim_ids.append(child)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return claim_ids


def _improvement_for(
    result: RequirementResult,
    requirement_index: dict[str, _Requirement],
) -> ImprovementCandidate:
    configured = requirement_index.get(result.requirement_id)
    if configured is not None:
        action = configured.action
        owner = configured.owner
    elif result.requirement_id == "common.evidence":
        action = "各claimを承認可能な主根拠または補助根拠へ結び付ける。"
        owner = "medical_reviewer"
    else:
        action = "不足している医学的事実を承認済み根拠から追加する。"
        owner = "medical_reviewer"

    priority: Literal["critical", "high", "medium", "low"]
    if result.severity == RequirementSeverity.CRITICAL_REQUIRED:
        priority = "critical"
    elif result.severity == RequirementSeverity.REQUIRED:
        priority = "high"
    elif result.weight >= 10:
        priority = "high"
    elif result.weight >= 4:
        priority = "medium"
    else:
        priority = "low"

    suffix = (
        "を追加する" if result.status == RequirementStatus.MISSING else "を補完する"
    )
    return ImprovementCandidate(
        priority=priority,
        requirement_id=result.requirement_id,
        label=f"{result.label}{suffix}",
        action=action,
        suggested_owner=owner,
    )


def _level_for(score: int) -> CompletenessLevel:
    if score >= 90:
        return CompletenessLevel.COMPLETE_FOR_REVIEW
    if score >= 75:
        return CompletenessLevel.MOSTLY_COMPLETE
    if score >= 50:
        return CompletenessLevel.INCOMPLETE
    return CompletenessLevel.CRITICALLY_INCOMPLETE
