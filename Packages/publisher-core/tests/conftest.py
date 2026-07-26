from datetime import UTC, datetime
from pathlib import Path

import pytest
from knowledge_contracts.exam_v10 import ExamMetadataRecord
from knowledge_contracts.registry_v10 import (
    ClaimRegistryEntry,
    KnowledgeRegistryEntry,
    RegistryKnowledgeView,
    RegistryStatus,
    RegistryValidationReport,
)
from knowledge_contracts.v10 import KnowledgeRecord

from publisher_core import PublicationSourceBundle, TemplateRegistry


@pytest.fixture
def profile_root() -> Path:
    return Path(__file__).resolve().parents[1] / "profiles"


@pytest.fixture
def template_registry(profile_root: Path) -> TemplateRegistry:
    return TemplateRegistry.from_directory(profile_root)


@pytest.fixture
def publication_source() -> PublicationSourceBundle:
    knowledge = KnowledgeRecord.model_validate(_knowledge_record())
    registry = _registry_view()
    exam_metadata = ExamMetadataRecord.model_validate(_exam_metadata())
    return PublicationSourceBundle(
        knowledge=knowledge,
        exam_metadata=exam_metadata,
        registry=registry,
    )


def _knowledge_record() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "knowledge_id": "knw_ast_v10_example",
        "content_revision": 1,
        "term": {
            "canonical_name": "AST",
            "english_name": "aspartate aminotransferase",
            "aliases": ["GOT"],
        },
        "classification": {
            "term_type": "test_item",
            "primary_exam_domain": "clinical_chemistry",
            "related_exam_domains": [],
        },
        "core_facts": {
            "definitions": [
                {
                    "claim_id": "clm_10000001",
                    "assertion": "ASTはアミノ基転移反応を触媒する酵素である。",
                }
            ]
        },
        "category_content": {
            "template_id": "test_item_v1.0",
            "test_item": {
                "biological_basis": [
                    {
                        "claim_id": "clm_10000002",
                        "assertion": "ASTは細胞障害時に血中へ逸脱する。",
                    }
                ],
                "analyte_characteristics": [],
                "purposes": [],
                "specimens": [],
                "measurement_methods": [
                    {
                        "claim_id": "clm_10000003",
                        "method_name": "JSCC標準化対応法",
                        "method_family": None,
                        "assertion": "AST活性を測定する方法である。",
                    }
                ],
                "measurement_principles": [
                    {
                        "claim_id": "clm_10000004",
                        "related_method_claim_ids": ["clm_10000003"],
                        "measured_quantity": "AST活性",
                        "reaction_sequence": "共役反応でNADHを消費する。",
                        "detection_signal": "吸光度減少",
                        "wavelength_or_endpoint": "340 nm",
                        "assertion": "340 nmの吸光度減少からAST活性を求める。",
                    }
                ],
                "standardization_and_traceability": [],
                "reporting_systems": [],
                "reference_ranges": [],
                "clinical_decision_limits": [],
                "value_associations": {
                    "high": {
                        "pathophysiologic_states": [],
                        "representative_diseases": [],
                        "interpretive_notes": [],
                    },
                    "low": {
                        "pathophysiologic_states": [],
                        "representative_diseases": [],
                        "interpretive_notes": [],
                    },
                },
                "related_test_combinations": [
                    {
                        "claim_id": "clm_10000005",
                        "related_test_names": ["ALT"],
                        "related_knowledge_ids": [],
                        "assertion": "ASTとALTを組み合わせて解釈する。",
                    }
                ],
                "analytical_interferences": [],
                "interpretation_cautions": [],
                "time_course": [],
                "isoenzymes": [],
            },
        },
        "exam_metadata": {
            "analysis_batch_id": None,
            "importance": None,
            "first_appearance_session": None,
            "last_appearance_session": None,
            "appearance_frequency": None,
            "blueprint_references": [],
            "related_questions": [],
            "comparison_targets": [],
            "related_knowledge": [],
            "priority_claim_ids": [],
            "keywords": [],
        },
        "evidence": [],
        "publish_targets": {
            name: {"priority_claim_ids": [], "priority_exam_metadata": []}
            for name in ("pdf", "note", "training_video", "national_exam")
        },
    }


def _registry_view() -> RegistryKnowledgeView:
    now = datetime(2026, 7, 17, 0, 0, tzinfo=UTC)
    claims = (
        (
            "clm_10000001",
            "ast.definition.aminotransferase_enzyme",
            "core_facts.definitions",
            "ASTはアミノ基転移反応を触媒する酵素である。",
        ),
        (
            "clm_10000002",
            "ast.is_leakage_enzyme",
            "category_content.test_item.biological_basis",
            "ASTは細胞障害時に血中へ逸脱する。",
        ),
        (
            "clm_10000003",
            "ast.jscc",
            "category_content.test_item.measurement_methods",
            "AST活性を測定する方法である。",
        ),
        (
            "clm_10000004",
            "ast.measurement.340nm",
            "category_content.test_item.measurement_principles",
            "340 nmの吸光度減少からAST活性を求める。",
        ),
        (
            "clm_10000005",
            "ast.combination.alt",
            "category_content.test_item.related_test_combinations",
            "ASTとALTを組み合わせて解釈する。",
        ),
    )
    entries = [
        ClaimRegistryEntry(
            knowledge_id="knw_ast_v10_example",
            claim_id=claim_id,
            claim_key=claim_key,
            claim_version=1,
            field_path=field_path,
            assertion=assertion,
            status=RegistryStatus.APPROVED,
            created_at=now,
            updated_at=now,
            aliases=[],
            approval=[],
            fact_payload={"claim_id": claim_id, "assertion": assertion},
            is_deleted=False,
        )
        for claim_id, claim_key, field_path, assertion in claims
    ]
    return RegistryKnowledgeView(
        knowledge=KnowledgeRegistryEntry(
            knowledge_id="knw_ast_v10_example",
            registry_key="ast",
            canonical_name="AST",
            knowledge_version=1,
            status=RegistryStatus.APPROVED,
            created_at=now,
            updated_at=now,
            aliases=["GOT"],
            approval=[],
        ),
        claims=entries,
        merge_redirects=[],
        merge_candidates=[],
        history=[],
        validation=RegistryValidationReport(
            is_valid=True,
            knowledge_count=1,
            claim_count=len(entries),
            alias_count=1,
            merge_redirect_count=0,
            history_count=0,
            errors=[],
        ),
    )


def _exam_metadata() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata_id": "exm_ast_v10_example",
        "metadata_revision": 1,
        "knowledge_id": "knw_ast_v10_example",
        "knowledge_content_revision": 1,
        "exam_type": "clinical_laboratory_technologist_national_exam",
        "source_dataset": {
            "source_type": "manual_verified",
            "dataset_id": "dataset.ast_exam",
            "dataset_version": "1.0",
            "analysis_batch_id": "batch.publisher_test",
            "imported_at": "2026-07-17T00:00:00Z",
            "source_row_count": 1,
            "is_production_data": False,
        },
        "frequency": {
            "appearance_count": 1,
            "first_session_number": 73,
            "first_exam_year": 2027,
            "latest_session_number": 73,
            "latest_exam_year": 2027,
        },
        "history": [
            {
                "occurrence_id": "exo_ast_73am01",
                "source_row_id": "row.ast.73am01",
                "session_number": 73,
                "exam_year": 2027,
                "section": "morning",
                "question_number": 1,
                "patterns": ["standalone_knowledge"],
                "tested_claim_ids": ["clm_10000001"],
                "image_assets": [],
            }
        ],
        "importance": {
            "importance_score": 90,
            "calculation_method": "manual_verified",
            "calculation_note": "Publisher Coreの契約テスト用",
        },
        "priority_claims": [
            {
                "claim_id": "clm_10000001",
                "priority": "highest",
                "evidence_occurrence_ids": ["exo_ast_73am01"],
            }
        ],
        "question_patterns": [
            {
                "pattern": "standalone_knowledge",
                "appearance_count": 1,
                "occurrence_ids": ["exo_ast_73am01"],
                "related_claim_ids": ["clm_10000001"],
            }
        ],
        "related_terms": [],
        "common_errors": [
            {
                "error_id": "err_ast_00000001",
                "misconception": "ASTを肝臓だけに存在する酵素と誤認する。",
                "correction_claim_ids": ["clm_10000002"],
                "observed_occurrence_ids": ["exo_ast_73am01"],
            }
        ],
    }
