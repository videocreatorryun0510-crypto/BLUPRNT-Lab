import copy
import json
from pathlib import Path

from knowledge_contracts.v10 import (
    evaluate_laboratory_test_item_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

SAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "laboratory-test-item.example.json"
)


def _raw() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_category_union_schema_contains_laboratory_test_item() -> None:
    schema = knowledge_record_json_schema()
    record = validate_knowledge_record(_raw())

    assert "LaboratoryTestItemCategoryContent" in schema["$defs"]
    assert record.classification.term_type == "laboratory_test_item"
    assert record.category_content.template_id == "laboratory_test_item_v1.0"


def test_laboratory_test_item_completeness_uses_only_mvp_requirements() -> None:
    assessment = evaluate_laboratory_test_item_completeness(_raw())

    assert assessment.score == 100
    assert assessment.is_complete_for_review is True
    assert [item.label for item in assessment.requirement_results] == [
        "定義",
        "臨床的意義",
        "測定対象",
        "出典",
    ]


def test_missing_critical_clinical_significance_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    category = raw["category_content"]["laboratory_test_item"]
    removed_claim_ids = {
        item["claim_id"] for item in category["clinical_significance"]
    }
    category["clinical_significance"] = []
    for source in raw["evidence"]:
        source["supported_claim_ids"] = [
            claim_id
            for claim_id in source["supported_claim_ids"]
            if claim_id not in removed_claim_ids
        ]

    assessment = evaluate_laboratory_test_item_completeness(raw)

    assert assessment.score <= 49
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} == {"臨床的意義"}
