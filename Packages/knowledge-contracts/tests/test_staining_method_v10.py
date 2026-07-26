import copy
import json
from pathlib import Path

import pytest
from knowledge_contracts.v10 import (
    KnowledgeSchemaError,
    evaluate_staining_method_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)


SAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "staining-method.example.json"
)


def _raw() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_category_union_schema_contains_staining_method() -> None:
    schema = knowledge_record_json_schema()
    record = validate_knowledge_record(_raw())

    assert "StainingMethodCategoryContent" in schema["$defs"]
    assert record.classification.term_type == "staining_method"
    assert record.category_content.template_id == "staining_method_v1.0"


def test_staining_method_completeness_covers_production_requirements() -> None:
    assessment = evaluate_staining_method_completeness(_raw())

    assert assessment.score == 100
    assert assessment.is_complete_for_review is True
    assert {item.label for item in assessment.requirement_results} >= {
        "定義",
        "目的",
        "対象構造",
        "固定法",
        "工程",
        "試薬",
        "判定",
        "精度管理",
        "限界",
        "出典",
    }


def test_missing_critical_staining_fields_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    category = raw["category_content"]["staining_method"]
    category["reagents"] = []
    category["procedure_steps"] = []
    category["quality_controls"] = []
    raw["evidence"] = []

    assessment = evaluate_staining_method_completeness(raw)

    assert assessment.score <= 49
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} >= {
        "試薬",
        "工程",
        "精度管理",
    }


def test_procedure_step_order_must_be_unique() -> None:
    raw = copy.deepcopy(_raw())
    steps = raw["category_content"]["staining_method"]["procedure_steps"]
    steps[1]["step_order"] = steps[0]["step_order"]

    with pytest.raises(KnowledgeSchemaError) as error:
        validate_knowledge_record(raw)

    assert "step_order values must be unique" in error.value.detail


def test_procedure_reagent_reference_must_exist_in_same_record() -> None:
    raw = copy.deepcopy(_raw())
    steps = raw["category_content"]["staining_method"]["procedure_steps"]
    steps[0]["reagent_claim_ids"] = ["clm_missing_reagent"]

    with pytest.raises(KnowledgeSchemaError) as error:
        validate_knowledge_record(raw)

    assert "claim references must exist" in error.value.detail
