"""Versioned, human-readable definitions for Disease Relation Types."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from knowledge_contracts.relation_v10.models import LongText, ShortText, StrictModel
from knowledge_contracts.relation_v12.models import RelationType

DiseaseRelationType = Literal[
    RelationType.HAS_HIGH_TEST_ITEM,
    RelationType.HAS_LOW_TEST_ITEM,
    RelationType.DIAGNOSED_BY,
    RelationType.CAUSED_BY,
    RelationType.RELATED_DISEASE,
    RelationType.AFFECTS_STRUCTURE,
    RelationType.HAS_PATHOPHYSIOLOGY,
]


class RelationDirection(StrictModel):
    value: Literal["source_to_target", "symmetric"]
    source_role: ShortText
    target_role: ShortText


class RelationVocabularyExample(StrictModel):
    source_label: ShortText
    target_label: ShortText
    reading: ShortText


class RelationVocabularyEntry(StrictModel):
    relation_type: DiseaseRelationType
    domain: Literal["disease"]
    meaning: LongText
    direction: RelationDirection
    source_categories: list[ShortText] = Field(min_length=1, max_length=10)
    target_categories: list[ShortText] = Field(min_length=1, max_length=20)
    example: RelationVocabularyExample

    @model_validator(mode="after")
    def validate_categories(self) -> Self:
        if self.source_categories != ["disease"]:
            raise ValueError("Disease vocabulary must use disease as its source category")
        if len(self.target_categories) != len(set(self.target_categories)):
            raise ValueError("target_categories must be unique")
        return self


class RelationVocabularyCatalog(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    vocabulary_id: Literal["relation_vocabulary.disease"] = (
        "relation_vocabulary.disease"
    )
    relation_contract_version: Literal["1.2"] = "1.2"
    domain: Literal["disease"] = "disease"
    entries: list[RelationVocabularyEntry] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        expected = {
            RelationType.HAS_HIGH_TEST_ITEM,
            RelationType.HAS_LOW_TEST_ITEM,
            RelationType.DIAGNOSED_BY,
            RelationType.CAUSED_BY,
            RelationType.RELATED_DISEASE,
            RelationType.AFFECTS_STRUCTURE,
            RelationType.HAS_PATHOPHYSIOLOGY,
        }
        actual = [item.relation_type for item in self.entries]
        if len(actual) != len(set(actual)):
            raise ValueError("relation_type values must be unique within a catalog")
        if set(actual) != expected:
            raise ValueError("Disease vocabulary must define the seven approved types")
        return self


_OUTBOUND = RelationDirection(
    value="source_to_target",
    source_role="疾患Knowledge",
    target_role="関係先Knowledge",
)


def _entry(
    relation_type: DiseaseRelationType,
    meaning: str,
    target_categories: list[str],
    source_label: str,
    target_label: str,
    reading: str,
    *,
    direction: RelationDirection = _OUTBOUND,
) -> RelationVocabularyEntry:
    return RelationVocabularyEntry(
        relation_type=relation_type,
        domain="disease",
        meaning=meaning,
        direction=direction,
        source_categories=["disease"],
        target_categories=target_categories,
        example=RelationVocabularyExample(
            source_label=source_label,
            target_label=target_label,
            reading=reading,
        ),
    )


DISEASE_RELATION_VOCABULARY = RelationVocabularyCatalog(
    entries=[
        _entry(
            RelationType.HAS_HIGH_TEST_ITEM,
            "疾患・病態で、対象の臨床検査項目が代表的に高値を示すという検査所見を表す。基準範囲や患者測定値そのものは表さない。",
            ["laboratory_test_item"],
            "鉄過剰症",
            "フェリチン",
            "鉄過剰症ではフェリチンが高値となる",
        ),
        _entry(
            RelationType.HAS_LOW_TEST_ITEM,
            "疾患・病態で、対象の臨床検査項目が代表的に低値を示すという検査所見を表す。基準範囲や患者測定値そのものは表さない。",
            ["laboratory_test_item"],
            "鉄欠乏性貧血",
            "フェリチン",
            "鉄欠乏性貧血ではフェリチンが低値となる",
        ),
        _entry(
            RelationType.DIAGNOSED_BY,
            "疾患の診断、確定、または診断基準上の評価に直接利用される検査項目・検査法を表す。単なる関連所見には使用しない。",
            [
                "laboratory_test_item",
                "examination_method",
                "physiological_examination",
                "morphologic_finding",
            ],
            "糖尿病",
            "HbA1c",
            "糖尿病の診断評価にHbA1cを用いる",
        ),
        _entry(
            RelationType.CAUSED_BY,
            "疾患の成立に直接関与する病因・原因Knowledgeを表す。危険因子や単なる併存関係には使用しない。",
            [
                "disease",
                "microorganism",
                "parasite",
                "substance",
                "genomic_entity",
                "biological_process",
            ],
            "巨赤芽球性貧血",
            "ビタミンB12欠乏",
            "巨赤芽球性貧血はビタミンB12欠乏により生じ得る",
        ),
        _entry(
            RelationType.RELATED_DISEASE,
            "鑑別、併存、または学習上の比較対象となる疾患同士の関連を表す。因果関係は表さず、意味は対称として扱う。",
            ["disease"],
            "鉄欠乏性貧血",
            "慢性疾患に伴う貧血",
            "両疾患は鑑別・比較対象となる",
            direction=RelationDirection(
                value="symmetric",
                source_role="疾患Knowledge",
                target_role="関連する疾患Knowledge",
            ),
        ),
        _entry(
            RelationType.AFFECTS_STRUCTURE,
            "疾患が主として障害、変化、または機能低下を及ぼす生体構造を表す。症状が現れる部位という理由だけでは使用しない。",
            ["biological_structure"],
            "心筋梗塞",
            "心筋",
            "心筋梗塞は心筋を障害する",
        ),
        _entry(
            RelationType.HAS_PATHOPHYSIOLOGY,
            "疾患を成立させる病態生理上の過程を表す。疾患本文の説明文ではなく、独立した過程Knowledgeを参照する。",
            ["biological_process"],
            "鉄欠乏性貧血",
            "ヘモグロビン合成低下",
            "鉄欠乏性貧血はヘモグロビン合成低下という病態を持つ",
        ),
    ]
)


def disease_relation_vocabulary() -> RelationVocabularyCatalog:
    return DISEASE_RELATION_VOCABULARY.model_copy(deep=True)


def disease_relation_vocabulary_json_schema() -> dict[str, Any]:
    schema = RelationVocabularyCatalog.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        "https://bluprnt-lab.local/schemas/relation-vocabulary/disease/1.0"
    )
    schema["title"] = "BLUPRNT Lab Disease Relation Vocabulary Version 1.0"
    return schema


__all__ = [
    "DISEASE_RELATION_VOCABULARY",
    "DiseaseRelationType",
    "RelationDirection",
    "RelationVocabularyCatalog",
    "RelationVocabularyEntry",
    "RelationVocabularyExample",
    "disease_relation_vocabulary",
    "disease_relation_vocabulary_json_schema",
]
