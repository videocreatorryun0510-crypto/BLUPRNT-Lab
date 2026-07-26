"""Application service for the CSV Import MVP."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from knowledge_contracts.exam_v10 import (
    ExamCompletenessAssessment,
    ExamMetadataRecord,
    evaluate_exam_completeness,
)
from knowledge_contracts.v10 import KnowledgeRecord

from knowledge_workbench.csv_exam_metadata_provider import (
    CsvExamMetadataProvider,
    CsvImportOutcome,
)
from knowledge_workbench.exam_asset_resolver import (
    CompositeExamAssetResolver,
    EmbeddedAssetIndexResolver,
    FolderExamAssetResolver,
)
from knowledge_workbench.exam_import_mapping import load_exam_csv_mapping
from knowledge_workbench.exam_importance import ImportanceCalculator
from knowledge_workbench.knowledge_mapper import map_to_knowledge_record
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.knowledge_v10_mapper import map_v03_to_v10
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.sqlite_knowledge_registry import SQLiteKnowledgeRegistry

WORKBENCH_DIR = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE_DIR = WORKBENCH_DIR / "ExamImages"
SAMPLE_CSV_PATH = WORKBENCH_DIR / "fixtures" / "exam_import_sample.csv"


@dataclass(frozen=True)
class ExamImportExecutionResult:
    outcome: CsvImportOutcome
    exam_completeness: list[ExamCompletenessAssessment]


def import_exam_csv(
    csv_text: str,
    source_file: str,
    *,
    image_directory: Path = DEFAULT_IMAGE_DIR,
    embedded_asset_index: dict[str, Path] | None = None,
    previous_metadata: list[ExamMetadataRecord] | None = None,
    importance_calculator: ImportanceCalculator | None = None,
    registry: KnowledgeRegistry | None = None,
    import_mode: Literal["append", "replace"] = "replace",
    is_production_data: bool = False,
) -> ExamImportExecutionResult:
    """Run the complete import pipeline without calling OpenAI."""

    if registry is None:
        with TemporaryDirectory(prefix="bluprnt-registry-test-") as directory:
            temporary_registry = SQLiteKnowledgeRegistry(
                Path(directory) / "knowledge_registry.sqlite3"
            )
            return import_exam_csv(
                csv_text,
                source_file,
                image_directory=image_directory,
                embedded_asset_index=embedded_asset_index,
                previous_metadata=previous_metadata,
                importance_calculator=importance_calculator,
                registry=temporary_registry,
                import_mode=import_mode,
                is_production_data=is_production_data,
            )

    mapping = load_exam_csv_mapping()
    knowledge_records = build_prototype_knowledge_catalog(registry)
    resolver = CompositeExamAssetResolver(
        [
            EmbeddedAssetIndexResolver(
                embedded_asset_index or {},
                WORKBENCH_DIR,
            ),
            FolderExamAssetResolver(
                image_directory,
                WORKBENCH_DIR,
                mapping.image_mapping,
            ),
        ]
    )
    provider = CsvExamMetadataProvider(
        mapping,
        knowledge_records,
        resolver,
        registry,
        previous_metadata=previous_metadata,
        importance_calculator=importance_calculator,
    )
    outcome = provider.import_csv(
        csv_text,
        Path(source_file).name,
        import_mode=import_mode,
        is_production_data=is_production_data,
    )
    knowledge_by_id = {item.knowledge_id: item for item in knowledge_records}
    assessments = [
        evaluate_exam_completeness(item, knowledge_by_id[item.knowledge_id])
        for item in outcome.exam_metadata
    ]
    return ExamImportExecutionResult(outcome, assessments)


def import_sample_exam_csv(
    *,
    previous_metadata: list[ExamMetadataRecord] | None = None,
    registry: KnowledgeRegistry | None = None,
) -> ExamImportExecutionResult:
    return import_exam_csv(
        SAMPLE_CSV_PATH.read_text(encoding="utf-8-sig"),
        SAMPLE_CSV_PATH.name,
        previous_metadata=previous_metadata,
        registry=registry,
    )


def build_prototype_knowledge_catalog(
    registry: KnowledgeRegistry | None = None,
) -> list[KnowledgeRecord]:
    provider = FixtureKnowledgeProvider()
    records = [
        map_v03_to_v10(map_to_knowledge_record(provider.generate(term).draft))
        for term in ("AST", "HbA1c")
    ]
    if registry is None:
        return records
    return [registry.reconcile(record).record for record in records]
