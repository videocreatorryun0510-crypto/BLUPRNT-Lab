"""Knowledge JSON Version 0.3 public contract."""

from knowledge_contracts.v03.models import (
    Classification,
    CoreFacts,
    EvidenceReference,
    ExamMetadata,
    FactClaim,
    GenericCategoryContent,
    KnowledgeRecord,
    PublishTargets,
    TestItemCategoryContent,
    TestItemContent,
    TermInfo,
)
from knowledge_contracts.v03.validation import (
    KnowledgeSchemaError,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

__all__ = [
    "Classification",
    "CoreFacts",
    "EvidenceReference",
    "ExamMetadata",
    "FactClaim",
    "GenericCategoryContent",
    "KnowledgeRecord",
    "KnowledgeSchemaError",
    "PublishTargets",
    "TermInfo",
    "TestItemCategoryContent",
    "TestItemContent",
    "knowledge_record_json_schema",
    "validate_knowledge_record",
]
