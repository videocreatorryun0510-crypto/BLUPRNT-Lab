"""Public Knowledge JSON contracts shared by BLUPRNT Lab clients."""

from knowledge_contracts.models import (
    Classification,
    EvidenceReference,
    ExamDomain,
    ExamEssential,
    KnowledgeDraft,
    KnowledgeRecord,
    MedicalReview,
    MeasurementMethod,
    MeasurementPrinciple,
    Provenance,
    ReferenceRange,
    SpecimenInfo,
    StudyContent,
    TestCombination,
    TestItemContent,
    TermInfo,
    TermType,
    VisualHook,
    WarningItem,
)
from knowledge_contracts.validation import (
    KnowledgeSchemaError,
    knowledge_record_json_schema,
    validate_knowledge_record,
)
from knowledge_contracts.exam_v10 import (
    ExamCompletenessAssessment,
    ExamMetadataRecord,
    ExamMetadataSchemaError,
    evaluate_exam_completeness,
    exam_metadata_json_schema,
    validate_exam_metadata,
    validate_exam_metadata_for_knowledge,
)
from knowledge_contracts.v03 import (
    KnowledgeRecord as KnowledgeRecordV03,
)
from knowledge_contracts.v03 import (
    KnowledgeSchemaError as KnowledgeSchemaErrorV03,
)
from knowledge_contracts.v03 import (
    knowledge_record_json_schema as knowledge_record_v03_json_schema,
)
from knowledge_contracts.v03 import (
    validate_knowledge_record as validate_knowledge_record_v03,
)
from knowledge_contracts.v10 import (
    CompletenessAssessment as CompletenessAssessmentV10,
)
from knowledge_contracts.v10 import (
    KnowledgeRecord as KnowledgeRecordV10,
)
from knowledge_contracts.v10 import (
    KnowledgeSchemaError as KnowledgeSchemaErrorV10,
)
from knowledge_contracts.v10 import (
    evaluate_biological_structure_completeness as evaluate_biological_structure_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_disease_completeness as evaluate_disease_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_knowledge_completeness as evaluate_knowledge_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_laboratory_test_item_completeness as evaluate_laboratory_test_item_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_reagent_completeness as evaluate_reagent_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_specimen_completeness as evaluate_specimen_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_staining_method_completeness as evaluate_staining_method_completeness_v10,
)
from knowledge_contracts.v10 import (
    evaluate_test_item_completeness as evaluate_test_item_completeness_v10,
)
from knowledge_contracts.v10 import (
    knowledge_record_json_schema as knowledge_record_v10_json_schema,
)
from knowledge_contracts.v10 import (
    validate_knowledge_record as validate_knowledge_record_v10,
)
from knowledge_contracts.relation_v10 import (
    KnowledgeRelationRecord,
    KnowledgeRelationSnapshot,
    KnowledgeRelationView,
    RelationResolutionStatus,
    RelationStatus,
    RelationType,
    knowledge_relation_json_schema,
    validate_knowledge_relation_snapshot,
)
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationRecord as KnowledgeRelationRecordV11,
)
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationSnapshot as KnowledgeRelationSnapshotV11,
)
from knowledge_contracts.relation_v11 import (
    KnowledgeRelationView as KnowledgeRelationViewV11,
)
from knowledge_contracts.relation_v11 import (
    RelationContext,
    knowledge_relation_json_schema as knowledge_relation_v11_json_schema,
    validate_knowledge_relation_snapshot as validate_knowledge_relation_snapshot_v11,
)
from knowledge_contracts.relation_v12 import (
    DISEASE_RELATION_VOCABULARY,
    DiseaseRelationType,
    KnowledgeRelationRecord as KnowledgeRelationRecordV12,
    KnowledgeRelationSnapshot as KnowledgeRelationSnapshotV12,
    KnowledgeRelationView as KnowledgeRelationViewV12,
    RelationDirection,
    RelationType as RelationTypeV12,
    RelationVocabularyCatalog,
    RelationVocabularyEntry,
    RelationVocabularyExample,
    disease_relation_vocabulary,
    disease_relation_vocabulary_json_schema,
    knowledge_relation_json_schema as knowledge_relation_v12_json_schema,
    validate_knowledge_relation_snapshot as validate_knowledge_relation_snapshot_v12,
)
from knowledge_contracts.relation_growth_v10 import NetworkSummary, ResolutionReport

__all__ = [
    "Classification",
    "CompletenessAssessmentV10",
    "EvidenceReference",
    "ExamDomain",
    "ExamEssential",
    "ExamCompletenessAssessment",
    "ExamMetadataRecord",
    "ExamMetadataSchemaError",
    "KnowledgeDraft",
    "KnowledgeRecord",
    "KnowledgeRecordV03",
    "KnowledgeRecordV10",
    "KnowledgeRelationRecord",
    "KnowledgeRelationSnapshot",
    "KnowledgeRelationView",
    "KnowledgeRelationRecordV11",
    "KnowledgeRelationSnapshotV11",
    "KnowledgeRelationViewV11",
    "KnowledgeRelationRecordV12",
    "KnowledgeRelationSnapshotV12",
    "KnowledgeRelationViewV12",
    "DISEASE_RELATION_VOCABULARY",
    "DiseaseRelationType",
    "KnowledgeSchemaError",
    "KnowledgeSchemaErrorV03",
    "KnowledgeSchemaErrorV10",
    "MedicalReview",
    "MeasurementMethod",
    "MeasurementPrinciple",
    "NetworkSummary",
    "Provenance",
    "RelationResolutionStatus",
    "ResolutionReport",
    "RelationContext",
    "RelationDirection",
    "RelationStatus",
    "RelationType",
    "RelationTypeV12",
    "RelationVocabularyCatalog",
    "RelationVocabularyEntry",
    "RelationVocabularyExample",
    "ReferenceRange",
    "SpecimenInfo",
    "StudyContent",
    "TestCombination",
    "TestItemContent",
    "TermInfo",
    "TermType",
    "VisualHook",
    "WarningItem",
    "knowledge_record_json_schema",
    "knowledge_relation_json_schema",
    "disease_relation_vocabulary",
    "disease_relation_vocabulary_json_schema",
    "knowledge_relation_v11_json_schema",
    "knowledge_relation_v12_json_schema",
    "knowledge_record_v03_json_schema",
    "knowledge_record_v10_json_schema",
    "evaluate_test_item_completeness_v10",
    "evaluate_biological_structure_completeness_v10",
    "evaluate_disease_completeness_v10",
    "evaluate_knowledge_completeness_v10",
    "evaluate_laboratory_test_item_completeness_v10",
    "evaluate_reagent_completeness_v10",
    "evaluate_specimen_completeness_v10",
    "evaluate_staining_method_completeness_v10",
    "evaluate_exam_completeness",
    "exam_metadata_json_schema",
    "validate_knowledge_record",
    "validate_knowledge_record_v03",
    "validate_knowledge_record_v10",
    "validate_knowledge_relation_snapshot",
    "validate_knowledge_relation_snapshot_v11",
    "validate_knowledge_relation_snapshot_v12",
    "validate_exam_metadata",
    "validate_exam_metadata_for_knowledge",
]
