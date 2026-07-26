import copy
import json
from pathlib import Path

from knowledge_contracts.v10 import (
    evaluate_biological_structure_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

SAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "biological-structure.example.json"
)


def _raw() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_category_union_schema_contains_biological_structure() -> None:
    schema = knowledge_record_json_schema()
    record = validate_knowledge_record(_raw())

    assert "BiologicalStructureCategoryContent" in schema["$defs"]
    assert record.classification.term_type == "biological_structure"
    assert record.category_content.template_id == "biological_structure_v1.0"


def test_biological_structure_mvp_completeness_uses_only_approved_requirements() -> None:
    assessment = evaluate_biological_structure_completeness(_raw())

    assert assessment.score == 100
    assert assessment.is_complete_for_review is True
    assert [item.label for item in assessment.requirement_results] == [
        "定義",
        "主な機能",
        "出典",
    ]


def test_missing_required_structure_fact_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    raw["category_content"]["biological_structure"]["main_functions"] = []
    raw["evidence"][0]["supported_claim_ids"].remove("clm_bwall_function")

    assessment = evaluate_biological_structure_completeness(raw)

    assert assessment.score <= 79
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} == {"主な機能"}
