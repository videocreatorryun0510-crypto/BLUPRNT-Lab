"""Column-mapped CSV -> normalized rows -> linked Exam Metadata provider."""

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Literal

from knowledge_contracts.exam_import_v10 import (
    ColumnResolution,
    CsvImportReport,
    CsvValidationReport,
    ImportDiff,
    ImportIssue,
    KnowledgeMappingSummary,
    MappedExamRecord,
    NormalizedExamRecord,
)
from knowledge_contracts.exam_v10 import (
    ClaimExamPriority,
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
from knowledge_contracts.v10 import KnowledgeRecord
from pydantic import ValidationError

from knowledge_workbench.errors import ExamMetadataUnavailableError
from knowledge_workbench.exam_asset_resolver import ExamAssetResolver
from knowledge_workbench.exam_import_mapping import ExamCsvMapping
from knowledge_workbench.exam_importance import (
    ImportanceCalculator,
    WeightedImportanceCalculator,
)
from knowledge_workbench.knowledge_registry import KnowledgeRegistry


@dataclass(frozen=True)
class CsvImportOutcome:
    report: CsvImportReport
    normalized_records: list[NormalizedExamRecord]
    mapped_records: list[MappedExamRecord]
    exam_metadata: list[ExamMetadataRecord]


class CsvExamMetadataProvider:
    """Import one CSV batch and expose the standard ExamMetadataProvider API."""

    def __init__(
        self,
        mapping: ExamCsvMapping,
        knowledge_records: list[KnowledgeRecord],
        asset_resolver: ExamAssetResolver,
        claim_dictionary: KnowledgeRegistry,
        *,
        previous_metadata: list[ExamMetadataRecord] | None = None,
        importance_calculator: ImportanceCalculator | None = None,
    ) -> None:
        self._mapping = mapping
        self._knowledge_records = {item.knowledge_id: item for item in knowledge_records}
        self._asset_resolver = asset_resolver
        self._claim_dictionary = claim_dictionary
        self._previous_metadata = {item.knowledge_id: item for item in (previous_metadata or [])}
        self._importance_calculator = importance_calculator or WeightedImportanceCalculator()
        self._imported_metadata: dict[str, ExamMetadataRecord] = {}

    def import_csv(
        self,
        csv_text: str,
        source_file: str,
        *,
        import_mode: Literal["append", "replace"] = "append",
        is_production_data: bool = False,
    ) -> CsvImportOutcome:
        dataset_hash = sha256(csv_text.encode("utf-8")).hexdigest()
        parsed = self._parse_and_normalize(csv_text, source_file)
        if not parsed.report.can_import:
            return CsvImportOutcome(
                report=_import_report(
                    parsed.report,
                    dataset_hash,
                    [],
                    [],
                    [],
                    0,
                    0,
                    _diff([], self._previous_source_row_ids(), import_mode),
                ),
                normalized_records=parsed.records,
                mapped_records=[],
                exam_metadata=[],
            )

        mapped_records, mapping_summaries, mapping_issues = self._map_records(parsed.records)
        issues = [*parsed.report.issues, *mapping_issues]
        if any(item.severity == "error" for item in mapping_issues):
            validation = parsed.report.model_copy(update={"can_import": False, "issues": issues})
            return CsvImportOutcome(
                report=_import_report(
                    validation,
                    dataset_hash,
                    mapping_summaries,
                    parsed.records,
                    mapped_records,
                    sum(len(item.image_assets) for item in mapped_records),
                    sum(item.code == "image_missing" for item in issues),
                    _diff([], self._previous_source_row_ids(), import_mode),
                ),
                normalized_records=parsed.records,
                mapped_records=mapped_records,
                exam_metadata=[],
            )

        metadata = self._build_metadata(
            mapped_records,
            source_file,
            dataset_hash,
            import_mode,
            is_production_data,
        )
        self._imported_metadata = {item.knowledge_id: item for item in metadata}
        current_ids = [item.normalized.source_row_id for item in mapped_records]
        validation = parsed.report.model_copy(update={"issues": issues})
        report = _import_report(
            validation,
            dataset_hash,
            mapping_summaries,
            parsed.records,
            mapped_records,
            sum(len(item.image_assets) for item in mapped_records),
            sum(item.code == "image_missing" for item in issues),
            _diff(current_ids, self._previous_source_row_ids(), import_mode),
            metadata_count=len(metadata),
        )
        return CsvImportOutcome(report, parsed.records, mapped_records, metadata)

    def build(self, term: str, knowledge: KnowledgeRecord) -> ExamMetadataRecord:
        metadata = self._imported_metadata.get(knowledge.knowledge_id)
        if metadata is None:
            raise ExamMetadataUnavailableError(
                f"CSV Import結果に{term}のExam Metadataがありません。"
            )
        return validate_exam_metadata_for_knowledge(metadata, knowledge)

    def _parse_and_normalize(self, csv_text: str, source_file: str) -> "_ParsedCsv":
        rows = list(
            csv.reader(
                StringIO(csv_text.lstrip("\ufeff")),
                delimiter=self._mapping.delimiter,
            )
        )
        if not rows:
            issue = _issue("error", "empty_csv", "CSVが空です。")
            report = _empty_validation(self._mapping, source_file, [issue])
            return _ParsedCsv(report, [])

        headers = [item.strip() for item in rows[0]]
        resolution = _resolve_columns(headers, self._mapping)
        issues = list(resolution.issues)
        records: list[NormalizedExamRecord] = []
        if not any(item.severity == "error" for item in issues):
            for row_number, values in enumerate(rows[1:], start=2):
                if not any(value.strip() for value in values):
                    continue
                if len(values) != len(headers):
                    issues.append(
                        _issue(
                            "error",
                            "column_count_mismatch",
                            f"列数がヘッダーと一致しません（{len(values)}列）。",
                            row_number=row_number,
                        )
                    )
                    continue
                raw = {header: value.strip() for header, value in zip(headers, values, strict=True)}
                try:
                    records.append(
                        _normalize_row(
                            raw,
                            resolution.field_to_column,
                            self._mapping,
                            source_file,
                            row_number,
                        )
                    )
                except (KeyError, ValueError, ValidationError) as error:
                    issues.append(
                        _issue(
                            "error",
                            "invalid_row",
                            str(error),
                            row_number=row_number,
                        )
                    )

        source_ids = [item.source_row_id for item in records]
        duplicates = sorted(value for value, count in Counter(source_ids).items() if count > 1)
        for source_id in duplicates:
            issues.append(
                _issue(
                    "error",
                    "duplicate_source_row_id",
                    f"source_row_idが重複しています: {source_id}",
                )
            )
        can_import = not any(item.severity == "error" for item in issues)
        report = CsvValidationReport(
            mapping_version=self._mapping.mapping_version,
            source_file=source_file,
            can_import=can_import,
            header_columns=headers,
            column_resolutions=resolution.column_resolutions,
            required_columns_missing=resolution.required_missing,
            optional_fields_unmapped=resolution.optional_missing,
            unused_columns=resolution.unused,
            unknown_columns=resolution.unknown,
            duplicate_columns=resolution.duplicates,
            ambiguous_mappings=resolution.ambiguous,
            source_row_count=max(len(rows) - 1, 0),
            valid_row_count=len(records),
            invalid_row_count=len(
                {
                    item.source_row_number
                    for item in issues
                    if item.severity == "error" and item.source_row_number is not None
                }
            ),
            issues=issues,
        )
        return _ParsedCsv(report, records)

    def _map_records(
        self, records: list[NormalizedExamRecord]
    ) -> tuple[list[MappedExamRecord], list[KnowledgeMappingSummary], list[ImportIssue]]:
        alias_map = _knowledge_alias_map(self._mapping)
        knowledge_by_key = _knowledge_records_by_key(
            self._mapping, list(self._knowledge_records.values())
        )
        mapped: list[MappedExamRecord] = []
        summaries: dict[tuple[str, str, str], KnowledgeMappingSummary] = {}
        issues: list[ImportIssue] = []
        for record in records:
            canonical = alias_map.get(_normalized_label(record.theme))
            if canonical is None or canonical not in knowledge_by_key:
                issues.append(
                    _issue(
                        "error",
                        "knowledge_mapping_failed",
                        f"用語をknowledge_idへ変換できません: {record.theme}",
                        row_number=record.source_row_number,
                        column_name="theme",
                    )
                )
                continue
            knowledge = knowledge_by_key[canonical]
            claim_ids, claim_issues = _map_claims(
                record,
                canonical,
                knowledge,
                self._mapping,
                self._claim_dictionary,
            )
            issues.extend(claim_issues)
            if claim_issues:
                continue

            image_resolution = self._asset_resolver.resolve(record)
            image_assets = [image_resolution.asset] if image_resolution.asset is not None else []
            if image_resolution.warning:
                issues.append(
                    _issue(
                        "warning",
                        "image_missing",
                        image_resolution.warning,
                        row_number=record.source_row_number,
                        column_name="image_reference",
                    )
                )
            mapped.append(
                MappedExamRecord(
                    normalized=record,
                    canonical_theme=canonical,
                    knowledge_id=knowledge.knowledge_id,
                    tested_claim_ids=claim_ids,
                    image_assets=image_assets,
                )
            )
            summary = KnowledgeMappingSummary(
                source_theme=record.theme,
                canonical_theme=canonical,
                knowledge_id=knowledge.knowledge_id,
            )
            summaries[(record.theme, canonical, knowledge.knowledge_id)] = summary
        return mapped, list(summaries.values()), issues

    def _build_metadata(
        self,
        mapped_records: list[MappedExamRecord],
        source_file: str,
        dataset_hash: str,
        import_mode: Literal["append", "replace"],
        is_production_data: bool,
    ) -> list[ExamMetadataRecord]:
        grouped: dict[str, list[MappedExamRecord]] = defaultdict(list)
        for item in mapped_records:
            grouped[item.knowledge_id].append(item)

        dataset_latest_year = max(item.normalized.exam_year for item in mapped_records)
        output: list[ExamMetadataRecord] = []
        for knowledge_id, imported in grouped.items():
            knowledge = self._knowledge_records[knowledge_id]
            previous = self._previous_metadata.get(knowledge_id)
            imported_occurrences = [_occurrence(item) for item in imported]
            history = _merge_history(
                previous.history if previous is not None else [],
                imported_occurrences,
                import_mode,
            )
            related_terms = _merge_related_terms(previous, imported)
            common_errors = previous.common_errors if previous is not None else []
            score = self._importance_calculator.calculate(
                history,
                self._mapping.importance_profile,
                dataset_latest_year,
            )
            first = min(history, key=lambda item: (item.exam_year, item.session_number))
            latest = max(history, key=lambda item: (item.exam_year, item.session_number))
            record = ExamMetadataRecord(
                schema_version="1.0",
                metadata_id=_identifier("exm", knowledge_id),
                metadata_revision=(previous.metadata_revision + 1 if previous else 1),
                knowledge_id=knowledge_id,
                knowledge_content_revision=knowledge.content_revision,
                exam_type="clinical_laboratory_technologist_national_exam",
                source_dataset=SourceDataset(
                    source_type=ExamDataSourceType.CSV_ANALYSIS,
                    dataset_id=f"csv-{Path(source_file).stem}",
                    dataset_version=self._mapping.mapping_version,
                    analysis_batch_id=f"batch-{dataset_hash[:16]}",
                    imported_at=datetime.now(UTC),
                    source_row_count=len(history),
                    is_production_data=is_production_data,
                ),
                frequency=ExamFrequencySummary(
                    appearance_count=len(history),
                    first_session_number=first.session_number,
                    first_exam_year=first.exam_year,
                    latest_session_number=latest.session_number,
                    latest_exam_year=latest.exam_year,
                ),
                history=history,
                importance=ImportanceAssessment(
                    importance_score=score,
                    calculation_method="frequency_weighted_v1",
                    calculation_note=(
                        f"{self._mapping.importance_profile.profile_id} "
                        f"v{self._mapping.importance_profile.profile_version}"
                    ),
                ),
                priority_claims=_priority_claims(history),
                question_patterns=_question_patterns(history),
                related_terms=related_terms,
                common_errors=common_errors,
            )
            output.append(validate_exam_metadata_for_knowledge(record, knowledge))
        return output

    def _previous_source_row_ids(self) -> list[str]:
        return [
            occurrence.source_row_id
            for metadata in self._previous_metadata.values()
            for occurrence in metadata.history
        ]


@dataclass(frozen=True)
class _ParsedCsv:
    report: CsvValidationReport
    records: list[NormalizedExamRecord]


@dataclass(frozen=True)
class _ColumnResolutionOutcome:
    field_to_column: dict[str, str]
    column_resolutions: list[ColumnResolution]
    required_missing: list[str]
    optional_missing: list[str]
    unused: list[str]
    unknown: list[str]
    duplicates: list[str]
    ambiguous: list[str]
    issues: list[ImportIssue]


def _resolve_columns(headers: list[str], mapping: ExamCsvMapping) -> _ColumnResolutionOutcome:
    normalized_headers: dict[str, list[str]] = defaultdict(list)
    for header in headers:
        normalized_headers[_normalized_label(header)].append(header)
    duplicates = sorted(values[0] for values in normalized_headers.values() if len(values) > 1)
    field_to_column: dict[str, str] = {}
    resolutions: list[ColumnResolution] = []
    required_missing: list[str] = []
    optional_missing: list[str] = []
    ambiguous: list[str] = []
    issues: list[ImportIssue] = []
    used: set[str] = set()

    for field, aliases in mapping.column_aliases.items():
        matches = [
            header
            for alias in aliases
            for header in normalized_headers.get(_normalized_label(alias), [])
        ]
        matches = list(dict.fromkeys(matches))
        if len(matches) == 1:
            field_to_column[field] = matches[0]
            used.add(matches[0])
            resolutions.append(
                ColumnResolution(
                    internal_field=field,
                    source_column=matches[0],
                    status="mapped",
                )
            )
        elif len(matches) > 1:
            ambiguous.append(field)
            status: Literal["missing_required", "missing_optional"] = (
                "missing_required" if field in mapping.required_fields else "missing_optional"
            )
            resolutions.append(
                ColumnResolution(
                    internal_field=field,
                    source_column=None,
                    status=status,
                )
            )
            issues.append(
                _issue(
                    "error",
                    "ambiguous_mapping",
                    f"{field}に複数列が一致します: {', '.join(matches)}",
                )
            )
        elif field in mapping.required_fields:
            required_missing.append(field)
            resolutions.append(
                ColumnResolution(
                    internal_field=field,
                    source_column=None,
                    status="missing_required",
                )
            )
            issues.append(
                _issue(
                    "error",
                    "required_column_missing",
                    f"必須列をMappingできません: {field}",
                )
            )
        else:
            optional_missing.append(field)
            resolutions.append(
                ColumnResolution(
                    internal_field=field,
                    source_column=None,
                    status="missing_optional",
                )
            )

    ignored_lookup = {_normalized_label(item) for item in mapping.ignored_columns}
    unused = [header for header in headers if _normalized_label(header) in ignored_lookup]
    unknown = [header for header in headers if header not in used and header not in unused]
    for header in duplicates:
        issues.append(
            _issue(
                "error",
                "duplicate_column",
                f"列名が重複しています: {header}",
                column_name=header,
            )
        )
    if unused:
        issues.append(_issue("warning", "unused_columns", "未使用列: " + ", ".join(unused)))
    if unknown:
        issues.append(_issue("warning", "unknown_columns", "Unknown列: " + ", ".join(unknown)))
    if optional_missing:
        issues.append(
            _issue(
                "warning",
                "optional_fields_unmapped",
                "任意項目をMappingできません: " + ", ".join(optional_missing),
            )
        )
    return _ColumnResolutionOutcome(
        field_to_column,
        resolutions,
        required_missing,
        optional_missing,
        unused,
        unknown,
        duplicates,
        ambiguous,
        issues,
    )


def _normalize_row(
    raw: dict[str, str],
    columns: dict[str, str],
    mapping: ExamCsvMapping,
    source_file: str,
    row_number: int,
) -> NormalizedExamRecord:
    def value(field: str) -> str:
        column = columns.get(field)
        return raw.get(column, "").strip() if column else ""

    session_number = int(value("session_number"))
    exam_year = int(value("exam_year"))
    question_number = int(value("question_number"))
    section_raw = value("section")
    section = mapping.section_aliases.get(section_raw)
    if section is None:
        raise ValueError(f"午前午後を変換できません: {section_raw}")
    patterns = _list(value("patterns"), mapping.list_separator)
    unknown_patterns = [item for item in patterns if item not in mapping.pattern_aliases]
    if unknown_patterns:
        raise ValueError("出題パターンを変換できません: " + ", ".join(unknown_patterns))
    theme = value("theme")
    tested_claims = _list(value("tested_claims"), mapping.list_separator)
    if not theme or not tested_claims:
        raise ValueError("themeとtested_claimsは空にできません")
    source_row_id = value("source_row_id") or _derived_source_row_id(
        session_number, section, question_number, theme
    )
    record_seed = f"{source_file}:{source_row_id}"
    return NormalizedExamRecord(
        record_id=_identifier("nrm", record_seed),
        session_number=session_number,
        exam_year=exam_year,
        section=ExamSection(section),
        question_number=question_number,
        theme=theme,
        source_file=Path(source_file).name,
        source_row_number=row_number,
        source_row_id=source_row_id,
        patterns=[QuestionPattern(mapping.pattern_aliases[item]) for item in patterns],
        related_terms=_list(value("related_terms"), mapping.list_separator),
        image_reference=value("image_reference") or None,
        tested_claims=tested_claims,
    )


def _knowledge_alias_map(mapping: ExamCsvMapping) -> dict[str, str]:
    return {
        _normalized_label(alias): canonical
        for canonical, aliases in mapping.knowledge_aliases.items()
        for alias in aliases
    }


def _knowledge_records_by_key(
    mapping: ExamCsvMapping, records: list[KnowledgeRecord]
) -> dict[str, KnowledgeRecord]:
    output: dict[str, KnowledgeRecord] = {}
    for canonical, aliases in mapping.knowledge_aliases.items():
        normalized_aliases = {_normalized_label(item) for item in aliases}
        for record in records:
            names = {
                _normalized_label(record.term.canonical_name),
                *(_normalized_label(item) for item in record.term.aliases),
            }
            if names & normalized_aliases:
                output[canonical] = record
                break
    return output


def _map_claims(
    record: NormalizedExamRecord,
    canonical: str,
    knowledge: KnowledgeRecord,
    mapping: ExamCsvMapping,
    claim_dictionary: KnowledgeRegistry,
) -> tuple[list[str], list[ImportIssue]]:
    claim_ids: list[str] = []
    issues: list[ImportIssue] = []
    selectors = mapping.claim_selectors[canonical]
    for token in record.tested_claims:
        selector = selectors.get(token)
        if selector is None:
            issues.append(
                _issue(
                    "error",
                    "claim_mapping_missing",
                    f"確認知識をclaimへ変換できません: {canonical}/{token}",
                    row_number=record.source_row_number,
                    column_name="tested_claims",
                )
            )
            continue
        for claim_key in selector.claim_keys:
            claim_id = claim_dictionary.resolve_claim_id(knowledge.knowledge_id, claim_key)
            if claim_id is None:
                issues.append(
                    _issue(
                        "error",
                        "claim_not_available",
                        f"Claim Dictionaryに対象claim_keyがありません: {claim_key}",
                        row_number=record.source_row_number,
                        column_name="tested_claims",
                    )
                )
                continue
            claim_ids.append(claim_id)
    return list(dict.fromkeys(claim_ids)), issues


def _occurrence(item: MappedExamRecord) -> ExamOccurrence:
    record = item.normalized
    return ExamOccurrence(
        occurrence_id=_identifier("exo", f"{item.knowledge_id}:{record.source_row_id}"),
        source_row_id=record.source_row_id,
        session_number=record.session_number,
        exam_year=record.exam_year,
        section=record.section,
        question_number=record.question_number,
        patterns=record.patterns,
        tested_claim_ids=item.tested_claim_ids,
        image_assets=item.image_assets,
    )


def _merge_history(
    previous: list[ExamOccurrence],
    imported: list[ExamOccurrence],
    mode: Literal["append", "replace"],
) -> list[ExamOccurrence]:
    by_source = {item.source_row_id: item for item in previous} if mode == "append" else {}
    by_source.update({item.source_row_id: item for item in imported})
    return sorted(
        by_source.values(),
        key=lambda item: (
            item.exam_year,
            item.session_number,
            item.section.value,
            item.question_number,
        ),
    )


def _merge_related_terms(
    previous: ExamMetadataRecord | None,
    imported: list[MappedExamRecord],
) -> list[RelatedExamTerm]:
    terms = {item.term: item for item in (previous.related_terms if previous is not None else [])}
    for item in imported:
        for term in item.normalized.related_terms:
            terms[term] = RelatedExamTerm(
                term=term,
                related_knowledge_id=None,
                relation_type=RelatedTermType.COMBINATION,
            )
    return list(terms.values())


def _priority_claims(history: list[ExamOccurrence]) -> list[ClaimExamPriority]:
    occurrences: dict[str, list[str]] = defaultdict(list)
    for item in history:
        for claim_id in item.tested_claim_ids:
            occurrences[claim_id].append(item.occurrence_id)
    ordered = sorted(occurrences, key=lambda claim_id: (-len(occurrences[claim_id]), claim_id))
    output: list[ClaimExamPriority] = []
    for index, claim_id in enumerate(ordered):
        if index < 2:
            priority = MemorizationPriority.HIGHEST
        elif index < 5:
            priority = MemorizationPriority.IMPORTANT
        else:
            priority = MemorizationPriority.SUPPLEMENTARY
        output.append(
            ClaimExamPriority(
                claim_id=claim_id,
                priority=priority,
                evidence_occurrence_ids=occurrences[claim_id],
            )
        )
    return output


def _question_patterns(history: list[ExamOccurrence]) -> list[QuestionPatternSummary]:
    grouped: dict[QuestionPattern, list[ExamOccurrence]] = defaultdict(list)
    for occurrence in history:
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


def _diff(
    current_ids: list[str],
    previous_ids: list[str],
    mode: Literal["append", "replace"],
) -> ImportDiff:
    current = set(current_ids)
    previous = set(previous_ids)
    return ImportDiff(
        added_source_row_ids=sorted(current - previous),
        removed_source_row_ids=sorted(previous - current) if mode == "replace" else [],
        unchanged_source_row_ids=sorted(current & previous),
    )


def _import_report(
    validation: CsvValidationReport,
    dataset_hash: str,
    mappings: list[KnowledgeMappingSummary],
    normalized: list[NormalizedExamRecord],
    mapped: list[MappedExamRecord],
    image_count: int,
    image_warning_count: int,
    diff: ImportDiff,
    *,
    metadata_count: int = 0,
) -> CsvImportReport:
    return CsvImportReport(
        import_id=f"imp-{dataset_hash[:16]}",
        dataset_hash=dataset_hash,
        validation=validation,
        knowledge_mappings=mappings,
        normalized_record_count=len(normalized),
        mapped_record_count=len(mapped),
        metadata_record_count=metadata_count,
        image_mapped_count=image_count,
        image_warning_count=image_warning_count,
        diff=diff,
    )


def _empty_validation(
    mapping: ExamCsvMapping, source_file: str, issues: list[ImportIssue]
) -> CsvValidationReport:
    return CsvValidationReport(
        mapping_version=mapping.mapping_version,
        source_file=source_file,
        can_import=False,
        header_columns=[],
        column_resolutions=[],
        required_columns_missing=mapping.required_fields,
        optional_fields_unmapped=[],
        unused_columns=[],
        unknown_columns=[],
        duplicate_columns=[],
        ambiguous_mappings=[],
        source_row_count=0,
        valid_row_count=0,
        invalid_row_count=0,
        issues=issues,
    )


def _issue(
    severity: Literal["error", "warning"],
    code: str,
    message: str,
    *,
    row_number: int | None = None,
    column_name: str | None = None,
) -> ImportIssue:
    return ImportIssue(
        severity=severity,
        code=code,
        message=message,
        source_row_number=row_number,
        column_name=column_name,
    )


def _list(value: str, separator: str) -> list[str]:
    return [item.strip() for item in value.split(separator) if item.strip()]


def _normalized_label(value: str) -> str:
    return "".join(value.strip().casefold().split())


def _derived_source_row_id(
    session_number: int,
    section: str,
    question_number: int,
    theme: str,
) -> str:
    # File names commonly change each year, so they must not change row identity.
    seed = (
        f"clinical-lab-exam:{session_number}:{section}:{question_number}:{_normalized_label(theme)}"
    )
    return f"row-{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _identifier(prefix: str, seed: str) -> str:
    return f"{prefix}_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"
