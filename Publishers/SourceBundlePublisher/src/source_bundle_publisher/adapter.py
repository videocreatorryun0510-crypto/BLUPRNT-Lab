"""Read-only Knowledge to Source Bundle Publisher Adapter."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from knowledge_contracts.approval_v10 import (
    ApprovalGateAction,
    ApprovalGateDecision,
    ApprovalSnapshot,
    approval_snapshot_from_registry,
    evaluate_approval_gate,
)
from knowledge_contracts.exam_v10 import ExamMetadataRecord
from knowledge_contracts.registry_v10 import (
    ClaimRegistryEntry,
    RegistryKnowledgeView,
)
from knowledge_contracts.v10 import KnowledgeRecord

from source_bundle_publisher.approval_gate import JsonlApprovalAuditLogger
from source_bundle_publisher.models import (
    DiagramRequest,
    DiagramRequestProfile,
    ExamPoint,
    SourceBundle,
    SourceBundleClaim,
    SourceBundleMetadata,
    SourceBundleProfile,
)
from source_bundle_publisher.profiles import SourceBundleProfileCatalog
from source_bundle_publisher.writer import SourceBundleJsonWriter


class SourceBundlePublisherError(ValueError):
    """Raised when a read-only Source Bundle cannot be built safely."""


@dataclass(frozen=True)
class SourceBundlePublication:
    bundle: SourceBundle
    output_path: Path


class SourceBundlePublisherAdapter:
    """Project current SSOT data into a provider-neutral presentation source."""

    publisher_version: Literal["1.1.0"] = "1.1.0"

    def __init__(
        self,
        catalog: SourceBundleProfileCatalog,
        writer: SourceBundleJsonWriter,
        audit_logger: JsonlApprovalAuditLogger,
    ) -> None:
        self._catalog = catalog
        self._writer = writer
        self._audit_logger = audit_logger

    @classmethod
    def from_directories(
        cls,
        profile_directory: Path,
        output_directory: Path,
        audit_log_path: Path | None = None,
    ) -> "SourceBundlePublisherAdapter":
        resolved_audit_log = (
            audit_log_path
            if audit_log_path is not None
            else output_directory.parent / "logs" / "approval_gate.jsonl"
        )
        return cls(
            SourceBundleProfileCatalog.from_directory(profile_directory),
            SourceBundleJsonWriter(output_directory),
            JsonlApprovalAuditLogger(resolved_audit_log),
        )

    @property
    def supported_knowledge_ids(self) -> tuple[str, ...]:
        return self._catalog.supported_knowledge_ids

    @property
    def audit_log_path(self) -> Path:
        return self._audit_logger.output_path

    @staticmethod
    def approval_snapshot(registry: RegistryKnowledgeView) -> ApprovalSnapshot:
        return approval_snapshot_from_registry(registry.knowledge)

    def can_publish(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision:
        return self._evaluate_and_audit(
            registry,
            ApprovalGateAction.PUBLISH,
            evaluated_at=evaluated_at,
        )

    def can_send_to_external_ai(
        self,
        registry: RegistryKnowledgeView,
        *,
        evaluated_at: datetime | None = None,
    ) -> ApprovalGateDecision:
        return self._evaluate_and_audit(
            registry,
            ApprovalGateAction.EXTERNAL_AI_SEND,
            evaluated_at=evaluated_at,
        )

    def publish(
        self,
        knowledge: KnowledgeRecord,
        registry: RegistryKnowledgeView,
        exam_metadata: ExamMetadataRecord | None,
        *,
        generated_at: datetime | None = None,
    ) -> SourceBundlePublication:
        profile = self._profile_for(knowledge.knowledge_id)
        self._validate_sources(knowledge, registry, exam_metadata)
        approval = self.approval_snapshot(registry)
        active_claims = tuple(
            item
            for item in registry.claims
            if not item.is_deleted and item.status.value != "deprecated"
        )
        claims_by_key = {item.claim_key: item for item in active_claims}
        claims_by_id = {item.claim_id: item for item in active_claims}
        ordered_claims = self._ordered_claims(knowledge, claims_by_id)
        source_claims = tuple(_claim_snapshot(item) for item in ordered_claims)
        summary = self._required_claim(
            claims_by_key, profile.summary_claim_key, "summary_claim_key"
        ).assertion
        key_messages = tuple(
            _claim_snapshot(
                self._required_claim(claims_by_key, key, "key_claim_keys")
            )
            for key in profile.key_claim_keys
        )
        diagram_requests = tuple(
            self._diagram_request(item, claims_by_key)
            for item in profile.diagram_requests
        )
        exam_points = self._exam_points(exam_metadata, claims_by_id)
        timestamp = generated_at or datetime.now(UTC)
        fingerprint = _source_fingerprint(
            knowledge,
            registry,
            exam_metadata,
            profile,
        )
        bundle = SourceBundle(
            schema_version="1.0",
            title=knowledge.term.canonical_name,
            summary=summary,
            learning_objective=profile.learning_objective,
            target_audience=profile.target_audience,
            claims=source_claims,
            key_messages=key_messages,
            exam_points=exam_points,
            diagram_requests=diagram_requests,
            references=tuple(knowledge.evidence),
            metadata=SourceBundleMetadata(
                source_bundle_schema_version="1.0",
                knowledge_id=knowledge.knowledge_id,
                version=registry.knowledge.knowledge_version,
                category=knowledge.classification.term_type,
                status=registry.knowledge.status,
                publisher_version=self.publisher_version,
                generated_at=timestamp,
                source_fingerprint=fingerprint,
                approval_state=approval.approval_state,
                approved_at=approval.approved_at,
                approved_by=approval.approved_by,
                review_version=approval.review_version,
                review_required=approval.review_required,
            ),
        )
        return SourceBundlePublication(bundle=bundle, output_path=self._writer.write(bundle))

    def _evaluate_and_audit(
        self,
        registry: RegistryKnowledgeView,
        action: ApprovalGateAction,
        *,
        evaluated_at: datetime | None,
    ) -> ApprovalGateDecision:
        decision = evaluate_approval_gate(
            self.approval_snapshot(registry),
            action,
            evaluated_at=evaluated_at,
        )
        self._audit_logger.write(decision)
        return decision

    def _profile_for(self, knowledge_id: str) -> SourceBundleProfile:
        try:
            return self._catalog.resolve(knowledge_id)
        except KeyError as error:
            raise SourceBundlePublisherError(
                "Source Bundle Publisher MVPはフェリチンと鉄欠乏性貧血だけに対応しています。"
            ) from error

    @staticmethod
    def _validate_sources(
        knowledge: KnowledgeRecord,
        registry: RegistryKnowledgeView,
        exam_metadata: ExamMetadataRecord | None,
    ) -> None:
        if registry.knowledge.knowledge_id != knowledge.knowledge_id:
            raise SourceBundlePublisherError(
                "Knowledge JSONとRegistryのknowledge_idが一致しません。"
            )
        if not registry.validation.is_valid:
            raise SourceBundlePublisherError("Registry Validationが成功していません。")
        if exam_metadata is None:
            return
        if exam_metadata.knowledge_id != knowledge.knowledge_id:
            raise SourceBundlePublisherError(
                "Exam MetadataとKnowledge JSONのknowledge_idが一致しません。"
            )
        if exam_metadata.knowledge_content_revision != knowledge.content_revision:
            raise SourceBundlePublisherError(
                "Exam Metadataが異なるKnowledge Revisionを参照しています。"
            )

    @staticmethod
    def _ordered_claims(
        knowledge: KnowledgeRecord,
        claims_by_id: dict[str, ClaimRegistryEntry],
    ) -> tuple[ClaimRegistryEntry, ...]:
        ordered_ids = _claim_id_order(knowledge)
        missing = [claim_id for claim_id in ordered_ids if claim_id not in claims_by_id]
        if missing:
            raise SourceBundlePublisherError(
                "Knowledge JSONのClaimが有効なRegistry Claimへ対応していません: "
                + ", ".join(missing)
            )
        return tuple(claims_by_id[claim_id] for claim_id in ordered_ids)

    @staticmethod
    def _required_claim(
        claims_by_key: dict[str, ClaimRegistryEntry],
        claim_key: str,
        profile_field: str,
    ) -> ClaimRegistryEntry:
        claim = claims_by_key.get(claim_key)
        if claim is None:
            raise SourceBundlePublisherError(
                f"Profileの{profile_field}に対応するClaimがありません: {claim_key}"
            )
        return claim

    def _diagram_request(
        self,
        request: DiagramRequestProfile,
        claims_by_key: dict[str, ClaimRegistryEntry],
    ) -> DiagramRequest:
        source_claims = tuple(
            self._required_claim(
                claims_by_key, claim_key, "diagram_requests.source_claim_keys"
            )
            for claim_key in request.source_claim_keys
        )
        return DiagramRequest(
            request_id=request.request_id,
            diagram_type=request.diagram_type,
            title=request.title,
            learning_goal=request.learning_goal,
            source_claim_ids=tuple(item.claim_id for item in source_claims),
        )

    @staticmethod
    def _exam_points(
        exam_metadata: ExamMetadataRecord | None,
        claims_by_id: dict[str, ClaimRegistryEntry],
    ) -> tuple[ExamPoint, ...]:
        if exam_metadata is None or not exam_metadata.priority_claims:
            return ()
        points: list[ExamPoint] = []
        for item in exam_metadata.priority_claims:
            claim = claims_by_id.get(item.claim_id)
            if claim is None:
                raise SourceBundlePublisherError(
                    "Exam Metadataの重要ClaimがRegistryにありません: "
                    + item.claim_id
                )
            points.append(
                ExamPoint(
                    claim_id=claim.claim_id,
                    claim_key=claim.claim_key,
                    assertion=claim.assertion,
                    priority=item.priority.value,
                    evidence_occurrence_ids=tuple(item.evidence_occurrence_ids),
                )
            )
        return tuple(points)


def _claim_snapshot(claim: ClaimRegistryEntry) -> SourceBundleClaim:
    return SourceBundleClaim(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        field_path=claim.field_path,
        assertion=claim.assertion,
    )


def _claim_id_order(knowledge: KnowledgeRecord) -> tuple[str, ...]:
    ordered: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            claim_id = value.get("claim_id")
            if isinstance(claim_id, str):
                ordered.append(claim_id)
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    raw = knowledge.model_dump(mode="json")
    visit(raw["core_facts"])
    visit(raw["category_content"])
    return tuple(dict.fromkeys(ordered))


def _source_fingerprint(
    knowledge: KnowledgeRecord,
    registry: RegistryKnowledgeView,
    exam_metadata: ExamMetadataRecord | None,
    profile: SourceBundleProfile,
) -> str:
    payload = {
        "knowledge": knowledge.model_dump(mode="json"),
        "registry": registry.model_dump(mode="json"),
        "exam_metadata": (
            exam_metadata.model_dump(mode="json")
            if exam_metadata is not None
            else None
        ),
        "profile": profile.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
