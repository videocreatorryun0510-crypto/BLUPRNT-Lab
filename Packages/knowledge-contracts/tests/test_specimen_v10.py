import copy
import json
from pathlib import Path

from knowledge_contracts.v10 import (
    evaluate_specimen_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

SAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "specimen.example.json"
)


def _raw() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_category_union_schema_contains_specimen() -> None:
    schema = knowledge_record_json_schema()
    record = validate_knowledge_record(_raw())

    assert "SpecimenCategoryContent" in schema["$defs"]
    assert record.classification.term_type == "specimen"
    assert record.category_content.template_id == "specimen_v1.0"


def test_specimen_kind_supports_national_exam_specimen_families() -> None:
    supported = {
        "serum",
        "plasma",
        "whole_blood",
        "urine",
        "stool",
        "sputum",
        "cerebrospinal_fluid",
        "smear_specimen",
    }
    for specimen_kind in supported:
        raw = copy.deepcopy(_raw())
        raw["category_content"]["specimen"]["specimen_kind"] = specimen_kind
        assert (
            validate_knowledge_record(raw).category_content.specimen.specimen_kind
            == specimen_kind
        )


def test_specimen_completeness_covers_production_requirements() -> None:
    assessment = evaluate_specimen_completeness(_raw())

    assert assessment.score == 100
    assert assessment.is_complete_for_review is True
    assert {item.label for item in assessment.requirement_results} >= {
        "定義",
        "概要",
        "使用用途",
        "採取・作製方法",
        "保存条件",
        "注意事項",
        "出典",
    }


def test_missing_critical_specimen_fields_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    raw["category_content"]["specimen"]["collection_methods"] = []
    raw["category_content"]["specimen"]["storage_conditions"] = []
    raw["evidence"] = []

    assessment = evaluate_specimen_completeness(raw)

    assert assessment.score <= 49
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} >= {
        "採取・作製方法",
        "保存条件",
    }
