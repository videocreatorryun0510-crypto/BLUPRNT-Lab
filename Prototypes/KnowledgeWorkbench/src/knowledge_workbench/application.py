"""The provider-neutral AI -> Knowledge JSON use case."""

import re
from dataclasses import dataclass

from knowledge_contracts.exam_v10 import (
    ExamCompletenessAssessment,
    ExamMetadataRecord,
    evaluate_exam_completeness,
)
from knowledge_contracts.registry_v10 import RegistryKnowledgeView
from knowledge_contracts.v10 import (
    CompletenessAssessment,
    KnowledgeRecord,
    evaluate_test_item_completeness,
)

from knowledge_workbench.errors import InvalidTermError
from knowledge_workbench.exam_metadata_provider import (
    DummyExamMetadataProvider,
    ExamMetadataProvider,
)
from knowledge_workbench.knowledge_mapper import map_to_knowledge_record
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.knowledge_v10_mapper import map_v03_to_v10
from knowledge_workbench.providers.base import KnowledgeProvider

CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class KnowledgeGenerationOutcome:
    record: KnowledgeRecord
    knowledge_completeness: CompletenessAssessment
    exam_metadata: ExamMetadataRecord
    exam_completeness: ExamCompletenessAssessment
    registry: RegistryKnowledgeView | None

    @property
    def completeness(self) -> CompletenessAssessment:
        """Compatibility alias for clients written before the score split."""

        return self.knowledge_completeness


class GenerateKnowledge:
    def __init__(
        self,
        provider: KnowledgeProvider,
        exam_metadata_provider: ExamMetadataProvider | None = None,
        registry: KnowledgeRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._exam_metadata_provider = exam_metadata_provider or DummyExamMetadataProvider()
        self._registry = registry

    def execute(self, term: str) -> KnowledgeGenerationOutcome:
        normalized_term = _normalize_term(term)
        result = self._provider.generate(normalized_term)
        record_v03 = map_to_knowledge_record(result.draft)
        record_v10 = map_v03_to_v10(record_v03)
        registry_view = None
        if self._registry is not None:
            reconciliation = self._registry.reconcile(record_v10)
            record_v10 = reconciliation.record
            registry_view = reconciliation.view
        knowledge_completeness = evaluate_test_item_completeness(record_v10)
        exam_metadata = self._exam_metadata_provider.build(normalized_term, record_v10)
        exam_completeness = evaluate_exam_completeness(exam_metadata, record_v10)
        return KnowledgeGenerationOutcome(
            record=record_v10,
            knowledge_completeness=knowledge_completeness,
            exam_metadata=exam_metadata,
            exam_completeness=exam_completeness,
            registry=registry_view,
        )


def _normalize_term(term: str) -> str:
    normalized = " ".join(term.strip().split())
    if not normalized:
        raise InvalidTermError("医療用語を1つ入力してください。")
    if len(normalized) > 80:
        raise InvalidTermError("入力は80文字以内にしてください。")
    if CONTROL_CHARACTER_PATTERN.search(normalized):
        raise InvalidTermError("入力に使用できない文字が含まれています。")
    return normalized
