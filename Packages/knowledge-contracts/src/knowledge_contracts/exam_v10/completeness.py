"""Exam Completeness evaluation kept separate from medical completeness."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from knowledge_contracts.exam_v10.models import (
    ExamDataSourceType,
    ExamMetadataRecord,
)
from knowledge_contracts.exam_v10.validation import validate_exam_metadata_for_knowledge
from knowledge_contracts.v10.models import KnowledgeRecord, StrictModel


class ExamRequirementSeverity(StrEnum):
    CRITICAL_REQUIRED = "critical_required"
    REQUIRED = "required"
    RECOMMENDED_OPTIONAL = "recommended_optional"


class ExamRequirementStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ExamCompletenessLevel(StrEnum):
    READY_FOR_PUBLISHER = "ready_for_publisher"
    MOSTLY_COMPLETE = "mostly_complete"
    INCOMPLETE = "incomplete"
    CRITICALLY_INCOMPLETE = "critically_incomplete"


class ExamRequirementResult(StrictModel):
    requirement_id: str
    json_path: str
    label: str
    severity: ExamRequirementSeverity
    weight: float = Field(ge=0)
    earned_points: float = Field(ge=0)
    status: ExamRequirementStatus
    target_count: int = Field(ge=1)
    actual_valid_count: int = Field(ge=0)


class ExamImprovementCandidate(StrictModel):
    priority: Literal["critical", "high", "medium", "low"]
    requirement_id: str
    label: str
    action: str
    suggested_owner: Literal["csv_importer", "product_owner", "exam_reviewer"]


class ExamCompletenessAssessment(StrictModel):
    assessment_version: Literal["1.0"]
    metadata_id: str
    metadata_revision: int = Field(ge=1)
    knowledge_id: str
    profile_id: Literal["exam_completeness.clinical_laboratory_technologist"]
    profile_version: Literal["1.0"]
    evaluated_at: datetime
    validation_status: Literal["completed"]
    score: int = Field(ge=0, le=100)
    level: ExamCompletenessLevel
    is_ready_for_publisher: bool
    requirement_results: list[ExamRequirementResult]
    improvement_candidates: list[ExamImprovementCandidate]


@dataclass(frozen=True)
class _ExamRequirement:
    requirement_id: str
    json_path: str
    label: str
    severity: ExamRequirementSeverity
    weight: float
    target_count: int
    actual_count: int
    action: str
    owner: Literal["csv_importer", "product_owner", "exam_reviewer"]


def evaluate_exam_completeness(
    metadata: ExamMetadataRecord | dict[str, object],
    knowledge: KnowledgeRecord | dict[str, object],
) -> ExamCompletenessAssessment:
    record = validate_exam_metadata_for_knowledge(metadata, knowledge)
    provenance_count = int(
        record.source_dataset.source_type == ExamDataSourceType.CSV_ANALYSIS
        and record.source_dataset.is_production_data
        and all(item.source_row_id for item in record.history)
    )
    requirements = [
        _requirement(
            "exam.provenance",
            "/source_dataset",
            "CSV解析元データ",
            ExamRequirementSeverity.REQUIRED,
            10,
            provenance_count,
            1,
            "12年分CSVのdataset_id、batch_id、source_row_idを保持して再取込可能にする。",
            "csv_importer",
        ),
        _requirement(
            "exam.history",
            "/history",
            "出題履歴",
            ExamRequirementSeverity.CRITICAL_REQUIRED,
            25,
            len(record.history),
            3,
            "CSVの1行を1件の出題履歴へ変換して追加する。",
            "csv_importer",
        ),
        _requirement(
            "exam.importance",
            "/importance",
            "出題重要度",
            ExamRequirementSeverity.REQUIRED,
            10,
            int(record.importance is not None),
            1,
            "出題頻度と出題形式から0〜100のimportance_scoreを計算する。",
            "product_owner",
        ),
        _requirement(
            "exam.priority_claims",
            "/priority_claims",
            "国家試験重要claim",
            ExamRequirementSeverity.CRITICAL_REQUIRED,
            25,
            len(record.priority_claims),
            3,
            "過去問が実際に確認した医学的事実へclaim_idを結び付ける。",
            "exam_reviewer",
        ),
        _requirement(
            "exam.question_patterns",
            "/question_patterns",
            "出題パターン",
            ExamRequirementSeverity.REQUIRED,
            10,
            len(record.question_patterns),
            2,
            "各出題履歴を定義済みの出題パターンへ分類する。",
            "csv_importer",
        ),
        _requirement(
            "exam.related_terms",
            "/related_terms",
            "関連用語",
            ExamRequirementSeverity.RECOMMENDED_OPTIONAL,
            10,
            len(record.related_terms),
            3,
            "比較、鑑別、組み合わせで同時に問われる用語を追加する。",
            "exam_reviewer",
        ),
        _requirement(
            "exam.common_errors",
            "/common_errors",
            "よくある誤答",
            ExamRequirementSeverity.RECOMMENDED_OPTIONAL,
            10,
            len(record.common_errors),
            2,
            "誤答パターンを正しいclaim_idと組み合わせて追加する。",
            "exam_reviewer",
        ),
    ]
    results = [_score(item) for item in requirements]
    raw_score = round(sum(item.earned_points for item in results))
    missing_required = [
        item
        for item in results
        if item.status == ExamRequirementStatus.MISSING
        and item.severity
        in {
            ExamRequirementSeverity.CRITICAL_REQUIRED,
            ExamRequirementSeverity.REQUIRED,
        }
    ]
    if any(
        item.severity == ExamRequirementSeverity.CRITICAL_REQUIRED
        for item in missing_required
    ):
        score = min(raw_score, 49)
    elif missing_required:
        score = min(raw_score, 79)
    else:
        score = raw_score

    improvements = [
        _improvement(result, configured)
        for result, configured in zip(results, requirements, strict=True)
        if result.status != ExamRequirementStatus.COMPLETE
    ]
    ready = (
        score >= 90
        and record.source_dataset.is_production_data
        and not missing_required
    )
    return ExamCompletenessAssessment(
        assessment_version="1.0",
        metadata_id=record.metadata_id,
        metadata_revision=record.metadata_revision,
        knowledge_id=record.knowledge_id,
        profile_id="exam_completeness.clinical_laboratory_technologist",
        profile_version="1.0",
        evaluated_at=datetime.now(UTC),
        validation_status="completed",
        score=score,
        level=_level(score, ready),
        is_ready_for_publisher=ready,
        requirement_results=results,
        improvement_candidates=improvements,
    )


def _requirement(
    requirement_id: str,
    path: str,
    label: str,
    severity: ExamRequirementSeverity,
    weight: float,
    actual: int,
    target: int,
    action: str,
    owner: Literal["csv_importer", "product_owner", "exam_reviewer"],
) -> _ExamRequirement:
    return _ExamRequirement(
        requirement_id,
        path,
        label,
        severity,
        weight,
        target,
        actual,
        action,
        owner,
    )


def _score(requirement: _ExamRequirement) -> ExamRequirementResult:
    coverage = min(requirement.actual_count / requirement.target_count, 1.0)
    earned = round(requirement.weight * coverage, 2)
    if requirement.actual_count == 0:
        status = ExamRequirementStatus.MISSING
    elif requirement.actual_count < requirement.target_count:
        status = ExamRequirementStatus.PARTIAL
    else:
        status = ExamRequirementStatus.COMPLETE
    return ExamRequirementResult(
        requirement_id=requirement.requirement_id,
        json_path=requirement.json_path,
        label=requirement.label,
        severity=requirement.severity,
        weight=requirement.weight,
        earned_points=earned,
        status=status,
        target_count=requirement.target_count,
        actual_valid_count=requirement.actual_count,
    )


def _improvement(
    result: ExamRequirementResult, requirement: _ExamRequirement
) -> ExamImprovementCandidate:
    if result.severity == ExamRequirementSeverity.CRITICAL_REQUIRED:
        priority: Literal["critical", "high", "medium", "low"] = "critical"
    elif result.severity == ExamRequirementSeverity.REQUIRED:
        priority = "high"
    elif result.weight >= 10:
        priority = "medium"
    else:
        priority = "low"
    suffix = (
        "を追加する" if result.status == ExamRequirementStatus.MISSING else "を補完する"
    )
    return ExamImprovementCandidate(
        priority=priority,
        requirement_id=result.requirement_id,
        label=result.label + suffix,
        action=requirement.action,
        suggested_owner=requirement.owner,
    )


def _level(score: int, ready: bool) -> ExamCompletenessLevel:
    if ready:
        return ExamCompletenessLevel.READY_FOR_PUBLISHER
    if score >= 75:
        return ExamCompletenessLevel.MOSTLY_COMPLETE
    if score >= 50:
        return ExamCompletenessLevel.INCOMPLETE
    return ExamCompletenessLevel.CRITICALLY_INCOMPLETE
