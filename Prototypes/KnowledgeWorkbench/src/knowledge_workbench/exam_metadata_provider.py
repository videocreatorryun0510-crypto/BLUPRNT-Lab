"""Exam metadata provider boundary and explicit vertical-slice fixtures."""

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from knowledge_contracts.exam_v10 import (
    ClaimExamPriority,
    CommonExamError,
    ExamDataSourceType,
    ExamFrequencySummary,
    ExamMetadataRecord,
    ExamOccurrence,
    ExamSection,
    ImportanceAssessment,
    MemorizationPriority,
    QuestionPattern,
    QuestionPatternSummary,
    RelatedExamTerm,
    RelatedTermType,
    SourceDataset,
    validate_exam_metadata_for_knowledge,
)
from knowledge_contracts.v10 import (
    BiologicalStructureCategoryContent,
    DiseaseCategoryContent,
    KnowledgeRecord,
    LaboratoryTestItemCategoryContent,
    ReagentCategoryContent,
    SpecimenCategoryContent,
    StainingMethodCategoryContent,
    TestItemCategoryContent,
)

from knowledge_workbench.errors import ExamMetadataUnavailableError


class ExamMetadataProvider(Protocol):
    """Exchangeable source boundary for Dummy, CSV, and future Database providers."""

    def build(self, term: str, knowledge: KnowledgeRecord) -> ExamMetadataRecord:
        """Return exam metadata linked to the supplied medical knowledge."""


class DummyExamMetadataProvider:
    """Manual dummy data for vertical-slice tests; never production exam evidence."""

    def build(self, term: str, knowledge: KnowledgeRecord) -> ExamMetadataRecord:
        if isinstance(
            knowledge.category_content,
            (
                SpecimenCategoryContent,
                ReagentCategoryContent,
                BiologicalStructureCategoryContent,
                DiseaseCategoryContent,
                LaboratoryTestItemCategoryContent,
            ),
        ):
            return _empty_exam_metadata(knowledge)
        key = _theme_key(term, knowledge)
        if isinstance(knowledge.category_content, StainingMethodCategoryContent) and not key:
            return _empty_exam_metadata(knowledge)
        config = _CONFIG.get(key)
        if config is None:
            raise ExamMetadataUnavailableError(
                "Exam Metadata Version 1.0 Dummy Providerは"
                "AST、HbA1c、Gram染色だけに対応しています。"
            )

        claim_ids = _select_priority_claims(knowledge)
        if len(claim_ids) < 4:
            raise ExamMetadataUnavailableError(
                "国家試験メタデータへ結び付けるclaimが不足しています。"
            )

        occurrences = _occurrences(key, config, claim_ids)
        occurrence_ids_by_claim: dict[str, list[str]] = defaultdict(list)
        for occurrence in occurrences:
            for claim_id in occurrence.tested_claim_ids:
                occurrence_ids_by_claim[claim_id].append(occurrence.occurrence_id)

        priorities = [
            MemorizationPriority.HIGHEST,
            MemorizationPriority.HIGHEST,
            MemorizationPriority.IMPORTANT,
            MemorizationPriority.SUPPLEMENTARY,
        ]
        priority_claims = [
            ClaimExamPriority(
                claim_id=claim_id,
                priority=priority,
                evidence_occurrence_ids=occurrence_ids_by_claim[claim_id],
            )
            for claim_id, priority in zip(claim_ids[:4], priorities, strict=True)
        ]
        record = ExamMetadataRecord(
            schema_version="1.0",
            metadata_id=_identifier("exm", knowledge.knowledge_id),
            metadata_revision=1,
            knowledge_id=knowledge.knowledge_id,
            knowledge_content_revision=knowledge.content_revision,
            exam_type="clinical_laboratory_technologist_national_exam",
            source_dataset=SourceDataset(
                source_type=ExamDataSourceType.MANUAL_DUMMY,
                dataset_id="prototype-exam-metadata-v1",
                dataset_version="1.0",
                analysis_batch_id="prototype-manual-dummy-v1",
                imported_at=None,
                source_row_count=len(occurrences),
                is_production_data=False,
            ),
            frequency=ExamFrequencySummary(
                appearance_count=len(occurrences),
                first_session_number=occurrences[0].session_number,
                first_exam_year=occurrences[0].exam_year,
                latest_session_number=occurrences[-1].session_number,
                latest_exam_year=occurrences[-1].exam_year,
            ),
            history=occurrences,
            importance=ImportanceAssessment(
                importance_score=config.importance_score,
                calculation_method="manual_dummy",
                calculation_note="Workbench動作確認用の仮スコア。CSV取込後に再計算する。",
            ),
            priority_claims=priority_claims,
            question_patterns=_pattern_summaries(occurrences),
            related_terms=[
                RelatedExamTerm(
                    term=item[0],
                    related_knowledge_id=None,
                    relation_type=RelatedTermType(item[1]),
                )
                for item in config.related_terms
            ],
            common_errors=[
                CommonExamError(
                    error_id=_identifier("err", f"{key}:{index}"),
                    misconception=misconception,
                    correction_claim_ids=[claim_ids[claim_index]],
                    observed_occurrence_ids=[occurrences[occurrence_index].occurrence_id],
                )
                for index, (misconception, claim_index, occurrence_index) in enumerate(
                    config.common_errors, start=1
                )
            ],
        )
        return validate_exam_metadata_for_knowledge(record, knowledge)


# Compatibility name kept for code written before the provider family was formalized.
PrototypeExamMetadataProvider = DummyExamMetadataProvider


def _empty_exam_metadata(knowledge: KnowledgeRecord) -> ExamMetadataRecord:
    """Return an explicit no-data record until CSV exam evidence is imported."""

    record = ExamMetadataRecord(
        schema_version="1.0",
        metadata_id=_identifier("exm", knowledge.knowledge_id),
        metadata_revision=1,
        knowledge_id=knowledge.knowledge_id,
        knowledge_content_revision=knowledge.content_revision,
        exam_type="clinical_laboratory_technologist_national_exam",
        source_dataset=SourceDataset(
            source_type=ExamDataSourceType.MANUAL_DUMMY,
            dataset_id="prototype-exam-metadata-empty-v1",
            dataset_version="1.0",
            analysis_batch_id="not_imported",
            imported_at=None,
            source_row_count=0,
            is_production_data=False,
        ),
        frequency=ExamFrequencySummary(
            appearance_count=0,
            first_session_number=None,
            first_exam_year=None,
            latest_session_number=None,
            latest_exam_year=None,
        ),
        history=[],
        importance=None,
        priority_claims=[],
        question_patterns=[],
        related_terms=[],
        common_errors=[],
    )
    return validate_exam_metadata_for_knowledge(record, knowledge)


def _theme_key(term: str, knowledge: KnowledgeRecord) -> str:
    candidates = {
        term.casefold().replace(" ", ""),
        knowledge.term.canonical_name.casefold().replace(" ", ""),
        *(item.casefold().replace(" ", "") for item in knowledge.term.aliases),
    }
    if "ast" in candidates:
        return "ast"
    if "hba1c" in candidates or "ヘモグロビンa1c" in candidates:
        return "hba1c"
    if {"gram染色", "グラム染色", "gramstain"}.intersection(candidates):
        return "gram_stain"
    return ""


def _select_priority_claims(knowledge: KnowledgeRecord) -> list[str]:
    if isinstance(knowledge.category_content, TestItemCategoryContent):
        content = knowledge.category_content.test_item
        candidates = [
            *(item.claim_id for item in content.measurement_principles),
            *(item.claim_id for item in content.measurement_methods),
            *(item.claim_id for item in content.interpretation_cautions),
            *(item.claim_id for item in content.related_test_combinations),
            *(item.claim_id for item in knowledge.core_facts.definitions),
            *(item.claim_id for item in content.purposes),
        ]
    elif isinstance(knowledge.category_content, StainingMethodCategoryContent):
        staining_content = knowledge.category_content.staining_method
        candidates = [
            *(item.claim_id for item in staining_content.staining_principles),
            *(item.claim_id for item in staining_content.procedure_steps),
            *(item.claim_id for item in staining_content.error_causes),
            *(item.claim_id for item in staining_content.limitations),
            *(item.claim_id for item in knowledge.core_facts.definitions),
            *(item.claim_id for item in staining_content.purposes),
        ]
    else:
        raise ExamMetadataUnavailableError("未対応のKnowledge Categoryです。")
    return list(dict.fromkeys(candidates))


def _occurrences(key: str, config: "_ThemeConfig", claim_ids: list[str]) -> list[ExamOccurrence]:
    occurrences: list[ExamOccurrence] = []
    for row in config.history:
        occurrences.append(
            ExamOccurrence(
                occurrence_id=_identifier(
                    "exo", f"{key}:{row.session}:{row.section}:{row.question_number}"
                ),
                source_row_id=(f"dummy:{key}:{row.session}:{row.section}:{row.question_number}"),
                session_number=row.session,
                exam_year=row.year,
                section=ExamSection(row.section),
                question_number=row.question_number,
                patterns=[QuestionPattern(item) for item in row.patterns],
                tested_claim_ids=[claim_ids[item] for item in row.claim_indexes],
                image_assets=[],
            )
        )
    return occurrences


def _pattern_summaries(
    occurrences: list[ExamOccurrence],
) -> list[QuestionPatternSummary]:
    grouped: dict[QuestionPattern, list[ExamOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        for pattern in occurrence.patterns:
            grouped[pattern].append(occurrence)
    return [
        QuestionPatternSummary(
            pattern=pattern,
            appearance_count=len(items),
            occurrence_ids=[item.occurrence_id for item in items],
            related_claim_ids=list(
                dict.fromkeys(claim_id for item in items for claim_id in item.tested_claim_ids)
            ),
        )
        for pattern, items in grouped.items()
    ]


def _identifier(prefix: str, seed: str) -> str:
    return f"{prefix}_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True)
class _HistoryRow:
    session: int
    year: int
    section: str
    question_number: int
    patterns: tuple[str, ...]
    claim_indexes: tuple[int, ...]


@dataclass(frozen=True)
class _ThemeConfig:
    importance_score: int
    history: tuple[_HistoryRow, ...]
    related_terms: tuple[tuple[str, str], ...]
    common_errors: tuple[tuple[str, int, int], ...]


_CONFIG: dict[str, _ThemeConfig] = {
    "ast": _ThemeConfig(
        importance_score=86,
        history=(
            _HistoryRow(
                61,
                2015,
                "morning",
                12,
                ("standalone_knowledge", "combination"),
                (0, 1),
            ),
            _HistoryRow(
                72,
                2026,
                "afternoon",
                38,
                ("differential", "combination"),
                (0, 2, 3),
            ),
        ),
        related_terms=(
            ("ALT", "comparison"),
            ("LD", "combination"),
            ("CK", "differential"),
            ("De Ritis比", "calculation_context"),
        ),
        common_errors=(
            ("ASTは肝臓だけに存在する検査項目であると判断する。", 2, 0),
            ("測定法が異なっても同一条件の値として比較できると判断する。", 0, 1),
        ),
    ),
    "hba1c": _ThemeConfig(
        importance_score=84,
        history=(
            _HistoryRow(
                61,
                2015,
                "afternoon",
                22,
                ("standalone_knowledge", "combination"),
                (0, 1),
            ),
            _HistoryRow(
                72,
                2026,
                "morning",
                44,
                ("differential", "elimination"),
                (0, 2, 3),
            ),
        ),
        related_terms=(
            ("血糖", "combination"),
            ("グリコアルブミン", "comparison"),
            ("1,5-AG", "comparison"),
            ("貧血", "differential"),
        ),
        common_errors=(
            ("HbA1cは採血直前の血糖変化だけを反映すると判断する。", 2, 0),
            ("赤血球寿命の変化はHbA1cの解釈に影響しないと判断する。", 3, 1),
        ),
    ),
    "gram_stain": _ThemeConfig(
        importance_score=82,
        history=(
            _HistoryRow(
                68,
                2022,
                "morning",
                23,
                ("standalone_knowledge", "combination"),
                (0, 1),
            ),
            _HistoryRow(
                72,
                2026,
                "afternoon",
                18,
                ("differential", "elimination"),
                (0, 2, 3),
            ),
        ),
        related_terms=(
            ("Gram陽性菌", "comparison"),
            ("Gram陰性菌", "comparison"),
            ("抗酸菌染色", "differential"),
            ("マイコプラズマ", "differential"),
        ),
        common_errors=(
            ("脱色時間はGram反応へ影響しないと判断する。", 2, 0),
            ("マイコプラズマをGram反応で分類できると判断する。", 3, 1),
        ),
    ),
}
