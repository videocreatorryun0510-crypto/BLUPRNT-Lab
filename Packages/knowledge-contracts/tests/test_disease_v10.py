import copy
import json
from pathlib import Path

from knowledge_contracts.v10 import (
    evaluate_disease_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

SAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "disease.example.json"
)


def _raw() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_category_union_schema_contains_disease() -> None:
    schema = knowledge_record_json_schema()
    record = validate_knowledge_record(_raw())

    assert "DiseaseCategoryContent" in schema["$defs"]
    assert record.classification.term_type == "disease"
    assert record.category_content.template_id == "disease_v1.0"


def test_disease_mvp_completeness_uses_only_approved_requirements() -> None:
    assessment = evaluate_disease_completeness(_raw())

    assert assessment.score == 100
    assert assessment.is_complete_for_review is True
    assert [item.label for item in assessment.requirement_results] == [
        "定義",
        "病態",
        "主な検査所見",
        "出典",
    ]


def test_missing_critical_laboratory_findings_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    removed_claim_ids = {
        item["claim_id"]
        for item in raw["category_content"]["disease"]["main_laboratory_findings"]
    }
    raw["category_content"]["disease"]["main_laboratory_findings"] = []
    raw["category_content"]["disease"]["national_exam_point_claim_ids"] = []
    for source in raw["evidence"]:
        source["supported_claim_ids"] = [
            claim_id
            for claim_id in source["supported_claim_ids"]
            if claim_id not in removed_claim_ids
        ]

    assessment = evaluate_disease_completeness(raw)

    assert assessment.score <= 49
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} == {"主な検査所見"}
