import json
from copy import deepcopy
from pathlib import Path

import pytest
from knowledge_contracts.v03 import (
    KnowledgeRecord,
    KnowledgeSchemaError,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATH = PACKAGE_DIR / "examples" / "ast-test-item-v0.3.json"


@pytest.fixture
def ast_record() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_v03_schema_is_versioned_draft_2020_12() -> None:
    schema = knowledge_record_json_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/0.3")


def test_ast_example_is_a_valid_v03_record(ast_record: dict[str, object]) -> None:
    record = validate_knowledge_record(ast_record)

    assert isinstance(record, KnowledgeRecord)
    assert record.schema_version == "0.3"
    assert record.category_content.template_id == "test_item_v0.3"


def test_v03_excludes_publisher_body_and_presentation_fields(
    ast_record: dict[str, object],
) -> None:
    forbidden_fields = {
        "quick_summary",
        "visual_hooks",
        "mnemonics",
        "article_body",
        "video_script",
        "exam_questions",
    }

    assert forbidden_fields.isdisjoint(_collect_keys(ast_record))
    raw = deepcopy(ast_record)
    raw["mnemonics"] = ["must not be stored"]
    with pytest.raises(KnowledgeSchemaError, match="Additional properties"):
        validate_knowledge_record(raw)


def test_high_and_low_values_separate_states_from_diseases(
    ast_record: dict[str, object],
) -> None:
    record = validate_knowledge_record(ast_record)
    test_item = record.category_content.test_item

    assert test_item.value_associations.high.pathophysiologic_states
    assert test_item.value_associations.high.representative_diseases
    assert isinstance(test_item.value_associations.low.pathophysiologic_states, list)
    assert isinstance(test_item.value_associations.low.representative_diseases, list)


def test_exam_metadata_has_empty_csv_destinations(
    ast_record: dict[str, object],
) -> None:
    record = validate_knowledge_record(ast_record)

    assert record.exam_metadata.analysis_batch_id == ""
    assert record.exam_metadata.importance is None
    assert record.exam_metadata.first_appearance_session is None
    assert record.exam_metadata.last_appearance_session is None
    assert record.exam_metadata.appearance_frequency is None
    assert record.exam_metadata.related_questions == []
    assert record.exam_metadata.comparison_targets == []
    assert record.exam_metadata.related_knowledge == []


def test_exam_metadata_can_receive_future_csv_analysis(
    ast_record: dict[str, object],
) -> None:
    raw = deepcopy(ast_record)
    raw["exam_metadata"] = {
        "analysis_batch_id": "exam_csv_batch_2026_01",
        "importance": {
            "level": "high",
            "score": 82.5,
            "score_scale_max": 100,
            "calculation_method": "構造検証用スコア",
        },
        "first_appearance_session": 70,
        "last_appearance_session": 75,
        "appearance_frequency": {
            "appearance_count": 2,
            "analyzed_question_count": 100,
            "frequency_rate": 0.02,
            "calculation_method": "構造検証用集計",
        },
        "related_questions": [
            {
                "question_id": "qst_session75_no12",
                "exam_session": 75,
                "question_number": 12,
                "tested_claim_ids": ["clm_ast_principle_uv"],
            }
        ],
        "comparison_targets": [{"knowledge_id": "knw_alt_testitem", "label": "ALT"}],
        "related_knowledge": [
            {"knowledge_id": "knw_liver_injury", "label": "肝細胞障害"}
        ],
        "priority_claim_ids": ["clm_ast_principle_uv"],
        "keywords": ["JSCC", "IFCC"],
    }

    record = validate_knowledge_record(raw)

    assert record.exam_metadata.analysis_batch_id == "exam_csv_batch_2026_01"
    assert record.exam_metadata.related_questions[0].exam_session == 75


def test_publish_targets_store_references_but_no_body(
    ast_record: dict[str, object],
) -> None:
    raw = deepcopy(ast_record)
    raw["publish_targets"]["pdf"] = {
        "priority_claim_ids": ["clm_ast_definition", "clm_ast_principle_uv"],
        "priority_exam_metadata": ["importance", "comparison_targets"],
    }

    record = validate_knowledge_record(raw)

    assert record.publish_targets.pdf.priority_claim_ids == [
        "clm_ast_definition",
        "clm_ast_principle_uv",
    ]
    assert not hasattr(record.publish_targets.pdf, "body")


def test_evidence_can_hold_full_bibliography_and_support_claims(
    ast_record: dict[str, object],
) -> None:
    raw = deepcopy(ast_record)
    raw["evidence"] = [
        {
            "source_id": "src_guideline_example",
            "source_priority_rank": 3,
            "title": "構造検証用ガイドライン",
            "issuing_organization": "構造検証用学会",
            "edition": "第1版",
            "publication_year": 2026,
            "url": "https://example.org/guideline",
            "doi": "10.1234/example.2026",
            "pmid": "12345678",
            "accessed_at": "2026-07-15",
            "chapter": "第2章",
            "pages": "10-12",
            "supported_claim_ids": ["clm_ast_definition"],
            "evidence_role": "primary",
        }
    ]

    record = validate_knowledge_record(raw)

    assert record.evidence[0].supported_claim_ids == ["clm_ast_definition"]


def test_unknown_claim_reference_is_rejected(ast_record: dict[str, object]) -> None:
    raw = deepcopy(ast_record)
    raw["publish_targets"]["pdf"]["priority_claim_ids"] = ["clm_missing_claim"]

    with pytest.raises(KnowledgeSchemaError, match="claim references must exist"):
        validate_knowledge_record(raw)


def test_duplicate_claim_id_is_rejected(ast_record: dict[str, object]) -> None:
    raw = deepcopy(ast_record)
    raw["core_facts"]["mechanisms"][0]["claim_id"] = "clm_ast_definition"

    with pytest.raises(KnowledgeSchemaError, match="claim_id values must be unique"):
        validate_knowledge_record(raw)


@pytest.mark.parametrize(
    "term_type",
    [
        "disease",
        "microorganism",
        "parasite",
        "staining_method",
        "pathology",
        "transfusion",
        "immunology",
    ],
)
def test_shared_metadata_is_category_independent(
    ast_record: dict[str, object], term_type: str
) -> None:
    raw = deepcopy(ast_record)
    raw["knowledge_id"] = f"knw_{term_type}_example"
    raw["classification"]["term_type"] = term_type
    raw["category_content"] = {"template_id": "generic_facts_v0.3"}

    record = validate_knowledge_record(raw)

    assert record.category_content.template_id == "generic_facts_v0.3"
    assert record.exam_metadata.related_questions == []
    assert record.evidence == []
    assert record.publish_targets.pdf.priority_claim_ids == []


def test_test_item_cannot_use_generic_template(ast_record: dict[str, object]) -> None:
    raw = deepcopy(ast_record)
    raw["category_content"] = {"template_id": "generic_facts_v0.3"}

    with pytest.raises(KnowledgeSchemaError):
        validate_knowledge_record(raw)


def _collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_collect_keys(child))
    return keys
