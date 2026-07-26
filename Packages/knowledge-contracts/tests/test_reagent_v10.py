import copy
import json
from pathlib import Path

from knowledge_contracts.v10 import (
    evaluate_reagent_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

SAMPLE_DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "Docs"
    / "examples"
    / "knowledge-json-v1.0"
    / "reagents"
)
SAMPLE_PATHS = sorted(SAMPLE_DIRECTORY.glob("*.example.json"))


def _raw(path: Path = SAMPLE_PATHS[0]) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_category_union_schema_contains_reagent() -> None:
    schema = knowledge_record_json_schema()

    assert "ReagentCategoryContent" in schema["$defs"]
    assert len(SAMPLE_PATHS) == 4
    for path in SAMPLE_PATHS:
        record = validate_knowledge_record(_raw(path))
        assert record.classification.term_type == "reagent"
        assert record.category_content.template_id == "reagent_v1.0"


def test_four_gram_reagents_are_complete_for_owner_review() -> None:
    expected_kinds = {"primary_stain", "mordant", "decolorizer", "counterstain"}
    actual_kinds: set[str] = set()

    for path in SAMPLE_PATHS:
        record = validate_knowledge_record(_raw(path))
        assessment = evaluate_reagent_completeness(record)
        actual_kinds.add(str(record.category_content.reagent.reagent_kind))
        assert assessment.score == 100
        assert assessment.is_complete_for_review is True
        assert {item.label for item in assessment.requirement_results} >= {
            "定義",
            "用途",
            "使用対象",
            "使用工程",
            "注意事項",
            "保管条件",
            "出典",
        }

    assert actual_kinds == expected_kinds


def test_missing_critical_reagent_fields_cannot_look_complete() -> None:
    raw = copy.deepcopy(_raw())
    content = raw["category_content"]["reagent"]
    content["usage_steps"] = []
    content["cautions"] = []
    raw["evidence"] = []

    assessment = evaluate_reagent_completeness(raw)

    assert assessment.score <= 49
    assert assessment.is_complete_for_review is False
    assert {item.label for item in assessment.missing_items} >= {
        "使用工程",
        "注意事項",
        "出典",
    }
