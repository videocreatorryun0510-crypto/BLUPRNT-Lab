from pathlib import Path

from knowledge_contracts.exam_v10 import ImageAssetSourceType

from knowledge_workbench.exam_asset_resolver import (
    CompositeExamAssetResolver,
    EmbeddedAssetIndexResolver,
    FolderExamAssetResolver,
)
from knowledge_workbench.exam_import_mapping import load_exam_csv_mapping
from knowledge_workbench.exam_import_service import (
    SAMPLE_CSV_PATH,
    build_prototype_knowledge_catalog,
    import_exam_csv,
    import_sample_exam_csv,
)
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry


class _FixedImportanceCalculator:
    def calculate(self, history: object, profile: object, dataset_latest_year: int) -> int:
        return 42


def _sample_text() -> str:
    return SAMPLE_CSV_PATH.read_text(encoding="utf-8-sig")


def test_sample_csv_imports_ast_hba1c_and_normalizes_before_mapping() -> None:
    result = import_sample_exam_csv()
    outcome = result.outcome

    assert outcome.report.validation.can_import is True
    assert outcome.report.normalized_record_count == 4
    assert outcome.report.mapped_record_count == 4
    assert outcome.report.metadata_record_count == 2
    assert {record.normalized.theme for record in outcome.mapped_records} == {
        "GOT",
        "AST",
        "HbA1c",
        "ヘモグロビンA1c",
    }
    assert {record.canonical_theme for record in outcome.mapped_records} == {
        "AST",
        "HbA1c",
    }
    assert all(record.normalized.source_row_id for record in outcome.mapped_records)
    assert all(record.tested_claim_ids for record in outcome.mapped_records)


def test_claim_mapping_only_references_existing_knowledge_claims(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    result = import_sample_exam_csv(registry=registry)
    knowledge_records = {
        record.knowledge_id: record for record in build_prototype_knowledge_catalog(registry)
    }

    for mapped in result.outcome.mapped_records:
        knowledge_json = knowledge_records[mapped.knowledge_id].model_dump(mode="json")
        serialized = str(knowledge_json)
        assert all(claim_id in serialized for claim_id in mapped.tested_claim_ids)


def test_csv_claim_mapping_uses_semantic_keys_not_ai_list_position(
    tmp_path: Path,
) -> None:
    registry = SQLiteKnowledgeRegistry(tmp_path / "registry.sqlite3")
    outcome = import_sample_exam_csv(registry=registry).outcome
    ast_record = next(
        item for item in outcome.mapped_records if item.normalized.source_row_id == "dummy-73-pm-15"
    )
    ifcc_id = registry.resolve_claim_id(ast_record.knowledge_id, "ast.ifcc")
    jscc_id = registry.resolve_claim_id(ast_record.knowledge_id, "ast.jscc")

    assert ifcc_id is not None
    assert jscc_id is not None
    assert {ifcc_id, jscc_id} <= set(ast_record.tested_claim_ids)


def test_importance_score_is_recalculated_when_history_changes() -> None:
    original = import_sample_exam_csv().outcome.exam_metadata
    extra_ast_row = "73,2027,午後,99,AST,dummy-73-pm-99,単独知識,ALT,,測定原理,追加行\n"
    updated = import_exam_csv(
        _sample_text() + extra_ast_row,
        "exam_import_updated.csv",
    ).outcome.exam_metadata

    original_ast = next(item for item in original if item.frequency.appearance_count == 2)
    updated_ast = next(item for item in updated if item.frequency.appearance_count == 3)
    assert updated_ast.importance.importance_score > original_ast.importance.importance_score
    assert updated_ast.importance.calculation_note == "frequency-recency-pattern-v1 v1.0"


def test_importance_formula_can_be_replaced_without_changing_csv_provider() -> None:
    outcome = import_exam_csv(
        _sample_text(),
        "custom_formula.csv",
        importance_calculator=_FixedImportanceCalculator(),
    ).outcome

    assert {item.importance.importance_score for item in outcome.exam_metadata} == {42}


def test_image_assets_are_linked_by_reference_without_storing_bytes() -> None:
    outcome = import_sample_exam_csv().outcome
    image_assets = [
        asset
        for metadata in outcome.exam_metadata
        for item in metadata.history
        for asset in item.image_assets
    ]

    assert outcome.report.image_mapped_count == 2
    assert outcome.report.image_warning_count == 0
    assert {asset.image_filename for asset in image_assets} == {
        "73-AM-06.svg",
        "73-PM-22.svg",
    }
    assert all(asset.image_path.startswith("ExamImages/") for asset in image_assets)
    assert all(len(asset.image_hash or "") == 64 for asset in image_assets)


def test_missing_image_is_warning_and_does_not_stop_import(tmp_path: Path) -> None:
    result = import_exam_csv(
        _sample_text(),
        "missing_images.csv",
        image_directory=tmp_path,
    )

    assert result.outcome.report.validation.can_import is True
    assert result.outcome.report.image_mapped_count == 0
    assert result.outcome.report.image_warning_count == 2
    assert {
        issue.code
        for issue in result.outcome.report.validation.issues
        if issue.severity == "warning"
    } >= {"image_missing"}


def test_image_filename_is_derived_when_csv_reference_is_empty() -> None:
    text = _sample_text().replace(
        ",73-AM-06,測定原理|測定法",
        ",,測定原理|測定法",
        1,
    )

    outcome = import_exam_csv(text, "derived_image_name.csv").outcome

    assert outcome.report.validation.can_import is True
    assert outcome.report.image_mapped_count == 2
    filenames = {
        asset.image_filename
        for metadata in outcome.exam_metadata
        for occurrence in metadata.history
        for asset in occurrence.image_assets
    }
    assert "73-AM-06.svg" in filenames


def test_embedded_asset_index_has_priority_over_external_image_folder(
    tmp_path: Path,
) -> None:
    embedded = tmp_path / "embedded" / "sheet-image.svg"
    external_folder = tmp_path / "ExamImages"
    embedded.parent.mkdir()
    external_folder.mkdir()
    embedded.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    (external_folder / "73-AM-06.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        encoding="utf-8",
    )
    record = import_sample_exam_csv().outcome.normalized_records[0]
    mapping = load_exam_csv_mapping()
    resolver = CompositeExamAssetResolver(
        [
            EmbeddedAssetIndexResolver({"73-AM-06": embedded}, tmp_path),
            FolderExamAssetResolver(external_folder, tmp_path, mapping.image_mapping),
        ]
    )

    resolution = resolver.resolve(record)

    assert resolution.asset is not None
    assert resolution.asset.source_type == ImageAssetSourceType.EMBEDDED_SPREADSHEET
    assert resolution.asset.image_filename == "sheet-image.svg"


def test_header_alias_can_change_without_changing_import_code() -> None:
    text = _sample_text().replace("試験回,年度", "回,年度", 1)

    outcome = import_exam_csv(text, "alias_header.csv").outcome

    assert outcome.report.validation.can_import is True
    resolution = next(
        item
        for item in outcome.report.validation.column_resolutions
        if item.internal_field == "session_number"
    )
    assert resolution.source_column == "回"


def test_derived_row_id_does_not_change_when_csv_filename_changes() -> None:
    text = _sample_text()
    for source_row_id in (
        "dummy-73-am-06",
        "dummy-73-pm-15",
        "dummy-73-am-18",
        "dummy-73-pm-22",
    ):
        text = text.replace(source_row_id, "")

    first = import_exam_csv(text, "exam-73-original.csv").outcome.normalized_records
    renamed = import_exam_csv(text, "exam-73-renamed.csv").outcome.normalized_records

    assert [item.source_row_id for item in first] == [item.source_row_id for item in renamed]


def test_validation_reports_missing_unknown_unused_and_duplicate_columns() -> None:
    missing = _sample_text().replace("試験回,", "", 1)
    missing_outcome = import_exam_csv(missing, "missing.csv").outcome
    assert missing_outcome.report.validation.can_import is False
    assert "session_number" in missing_outcome.report.validation.required_columns_missing

    unknown = _sample_text().replace("備考", "将来列", 1)
    unknown_outcome = import_exam_csv(unknown, "unknown.csv").outcome
    assert unknown_outcome.report.validation.can_import is True
    assert unknown_outcome.report.validation.unknown_columns == ["将来列"]

    sample_outcome = import_sample_exam_csv().outcome
    assert sample_outcome.report.validation.unused_columns == ["備考"]

    duplicate = _sample_text().replace("試験回,年度", "試験回,試験回,年度", 1)
    duplicate_rows = "\n".join(
        line.replace(",", ",73,", 1) if index else line
        for index, line in enumerate(duplicate.splitlines())
    )
    duplicate_outcome = import_exam_csv(duplicate_rows, "duplicate.csv").outcome
    assert duplicate_outcome.report.validation.can_import is False
    assert duplicate_outcome.report.validation.duplicate_columns == ["試験回"]
