from copy import deepcopy

import pytest
from knowledge_contracts.v10 import (
    KnowledgeRecord,
    KnowledgeSchemaError,
    evaluate_test_item_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)


@pytest.fixture
def ast_v10_record() -> dict[str, object]:
    return _record()


def test_v10_schema_is_versioned_draft_2020_12() -> None:
    schema = knowledge_record_json_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/1.0")


def test_test_item_record_is_valid_v10(ast_v10_record: dict[str, object]) -> None:
    record = validate_knowledge_record(ast_v10_record)

    assert isinstance(record, KnowledgeRecord)
    assert record.schema_version == "1.0"
    assert record.category_content.template_id == "test_item_v1.0"
    assert record.category_content.test_item.biological_basis


def test_v10_rejects_unknown_fields(ast_v10_record: dict[str, object]) -> None:
    raw = deepcopy(ast_v10_record)
    raw["article_body"] = "Publisherで作るべき内容"

    with pytest.raises(KnowledgeSchemaError, match="Additional properties"):
        validate_knowledge_record(raw)


def test_schema_can_pass_while_completeness_is_low(
    ast_v10_record: dict[str, object],
) -> None:
    raw = deepcopy(ast_v10_record)
    content = raw["category_content"]["test_item"]  # type: ignore[index]
    content["measurement_methods"] = []  # type: ignore[index]
    content["measurement_principles"] = []  # type: ignore[index]

    record = validate_knowledge_record(raw)
    assessment = evaluate_test_item_completeness(record)

    assert assessment.validation_status == "completed"
    assert assessment.score <= 49
    assert any(
        item.requirement_id == "test_item.measurement_methods"
        for item in assessment.missing_items
    )


def test_completeness_lists_missing_v10_fields(
    ast_v10_record: dict[str, object],
) -> None:
    assessment = evaluate_test_item_completeness(ast_v10_record)

    assert assessment.score == 66
    assert assessment.profile_id == "knowledge_completeness.test_item"
    labels = {item.label for item in assessment.improvement_candidates}
    assert "基準範囲を追加する" in labels
    assert "標準化・トレーサビリティを追加する" in labels
    assert "干渉物質・分析上の影響を追加する" in labels
    assert "出典を追加する" in labels


def test_v10_rejects_unknown_claim_reference(
    ast_v10_record: dict[str, object],
) -> None:
    raw = deepcopy(ast_v10_record)
    raw["publish_targets"]["pdf"]["priority_claim_ids"] = [  # type: ignore[index]
        "clm_missing_claim"
    ]

    with pytest.raises(KnowledgeSchemaError, match="claim references must exist"):
        validate_knowledge_record(raw)


def _record() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "knowledge_id": "knw_ast_v10_example",
        "content_revision": 1,
        "term": {
            "canonical_name": "AST",
            "english_name": "aspartate aminotransferase",
            "aliases": [],
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
                        "assertion": "組織障害により細胞内ASTが血中へ逸脱する。",
                    }
                ],
                "analyte_characteristics": [
                    {
                        "claim_id": "clm_10000003",
                        "assertion": "ASTは複数の臓器に分布する。",
                    }
                ],
                "purposes": [
                    {
                        "claim_id": "clm_10000004",
                        "assertion": "AST測定は組織障害の評価に用いる。",
                    }
                ],
                "specimens": [
                    {
                        "claim_id": "clm_10000005",
                        "specimen": "血清",
                        "container_or_anticoagulant": None,
                        "handling": "溶血を避ける。",
                        "stability": None,
                    }
                ],
                "measurement_methods": [
                    {
                        "claim_id": "clm_10000006",
                        "method_name": "JSCC標準化対応法",
                        "method_family": None,
                        "assertion": "酵素活性を測定する。",
                    },
                    {
                        "claim_id": "clm_10000007",
                        "method_name": "IFCC法",
                        "method_family": None,
                        "assertion": "酵素活性を測定する。",
                    },
                ],
                "measurement_principles": [
                    {
                        "claim_id": "clm_10000008",
                        "related_method_claim_ids": ["clm_10000006"],
                        "measured_quantity": "AST活性",
                        "reaction_sequence": "共役反応でNADHを消費する。",
                        "detection_signal": "吸光度減少",
                        "wavelength_or_endpoint": "340 nm",
                        "assertion": "NADHの吸光度減少からAST活性を求める。",
                    },
                    {
                        "claim_id": "clm_10000009",
                        "related_method_claim_ids": ["clm_10000007"],
                        "measured_quantity": "AST活性",
                        "reaction_sequence": "共役反応でNADHを消費する。",
                        "detection_signal": "吸光度減少",
                        "wavelength_or_endpoint": "340 nm",
                        "assertion": "NADHの吸光度減少からAST活性を求める。",
                    },
                ],
                "standardization_and_traceability": [],
                "reporting_systems": [],
                "reference_ranges": [],
                "clinical_decision_limits": [],
                "value_associations": {
                    "high": {
                        "pathophysiologic_states": [
                            {
                                "claim_id": "clm_10000010",
                                "state_name": "肝細胞障害",
                                "related_knowledge_id": None,
                                "assertion": "肝細胞障害でASTが高値となる。",
                            }
                        ],
                        "representative_diseases": [
                            {
                                "claim_id": "clm_10000011",
                                "disease_name": "急性肝炎",
                                "disease_knowledge_id": None,
                                "assertion": "急性肝炎でASTが高値となる。",
                            }
                        ],
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
                        "claim_id": "clm_10000012",
                        "related_test_names": ["ALT"],
                        "related_knowledge_ids": [],
                        "assertion": "ASTとALTを組み合わせて解釈する。",
                    }
                ],
                "analytical_interferences": [],
                "interpretation_cautions": [
                    {
                        "claim_id": "clm_10000013",
                        "assertion": "溶血検体では高値となることがある。",
                    }
                ],
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
            name: {
                "priority_claim_ids": [],
                "priority_exam_metadata": [],
            }
            for name in ("pdf", "note", "training_video", "national_exam")
        },
    }
