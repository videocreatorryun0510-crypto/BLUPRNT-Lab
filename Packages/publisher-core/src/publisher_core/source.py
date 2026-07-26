"""Read-only connection to the current Knowledge, Exam and Registry contracts."""

import hashlib
import json
from typing import Self

from knowledge_contracts.exam_v10 import ExamMetadataRecord
from knowledge_contracts.registry_v10 import RegistryKnowledgeView, RegistryStatus
from knowledge_contracts.v10 import KnowledgeRecord
from pydantic import model_validator

from publisher_core.models import FrozenModel


class PublicationSourceBundle(FrozenModel):
    knowledge: KnowledgeRecord
    exam_metadata: ExamMetadataRecord | None
    registry: RegistryKnowledgeView

    @model_validator(mode="after")
    def validate_single_source_of_truth(self) -> Self:
        knowledge_id = self.knowledge.knowledge_id
        if self.registry.knowledge.knowledge_id != knowledge_id:
            raise ValueError("Registry and Knowledge JSON knowledge_id must match")
        if self.exam_metadata is not None:
            if self.exam_metadata.knowledge_id != knowledge_id:
                raise ValueError("Exam Metadata and Knowledge JSON knowledge_id must match")
            if self.exam_metadata.knowledge_content_revision != self.knowledge.content_revision:
                raise ValueError("Exam Metadata points to a different Knowledge revision")
        if not self.registry.validation.is_valid:
            raise ValueError("Publisher cannot consume an invalid Knowledge Registry")
        if self.registry.knowledge.status != RegistryStatus.APPROVED:
            raise ValueError("Publisher can only consume approved Knowledge")
        return self


def publication_source_fingerprint(source: PublicationSourceBundle) -> str:
    """Return the stable fingerprint embedded in a Publication Plan."""

    payload = source.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
