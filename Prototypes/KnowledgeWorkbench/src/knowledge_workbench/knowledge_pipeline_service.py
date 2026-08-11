"""Orchestrates Theme -> Evidence -> Claims -> Authoring Draft without Promotion."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.evidence_intelligence import (
    EvidenceBundleBuilder,
    JsonlEvidenceSearchAuditLog,
)
from knowledge_workbench.knowledge_pipeline_builders import (
    AuthoringKnowledgeBuilder,
    AuthoringReferenceBuilder,
)
from knowledge_workbench.knowledge_pipeline_interfaces import (
    ClaimBuilder,
    EvidenceDeduplicator,
    EvidenceNormalizer,
    EvidenceRanker,
    EvidenceSearchProvider,
)
from knowledge_workbench.knowledge_pipeline_models import (
    EvidenceSearchRequest,
    KnowledgePipelinePreview,
    SavePipelineDraftResult,
)


class KnowledgePipelineError(RuntimeError):
    """Raised when a safe Draft Preview cannot be produced or saved."""


class KnowledgePipelineService:
    def __init__(
        self,
        *,
        search_provider: EvidenceSearchProvider,
        evidence_normalizer: EvidenceNormalizer,
        evidence_deduplicator: EvidenceDeduplicator,
        evidence_ranker: EvidenceRanker,
        evidence_bundle_builder: EvidenceBundleBuilder,
        search_audit: JsonlEvidenceSearchAuditLog,
        claim_builder: ClaimBuilder,
        reference_builder: AuthoringReferenceBuilder,
        knowledge_builder: AuthoringKnowledgeBuilder,
        authoring: KnowledgeAuthoringService,
    ) -> None:
        self.search_provider = search_provider
        self.evidence_normalizer = evidence_normalizer
        self.evidence_deduplicator = evidence_deduplicator
        self.evidence_ranker = evidence_ranker
        self.evidence_bundle_builder = evidence_bundle_builder
        self.search_audit = search_audit
        self.claim_builder = claim_builder
        self.reference_builder = reference_builder
        self.knowledge_builder = knowledge_builder
        self.authoring = authoring
        self._pending: dict[str, KnowledgePipelinePreview] = {}

    def preview(self, theme: str) -> KnowledgePipelinePreview:
        normalized = " ".join(theme.strip().split())
        if not normalized:
            raise KnowledgePipelineError("テーマまたは医療用語を入力してください。")
        if len(normalized) > 300:
            raise KnowledgePipelineError("テーマは300文字以内で入力してください。")

        request = EvidenceSearchRequest(theme=normalized)
        search_started_at = datetime.now(UTC)
        search_timer = perf_counter()
        try:
            raw = self.search_provider.search(request)
        except Exception:
            self.search_audit.record_failure(
                query=normalized,
                provider=self.search_provider.provider_name,
                searched_at=search_started_at,
                duration_ms=max(0, round((perf_counter() - search_timer) * 1000)),
            )
            raise
        if not raw.records:
            raise KnowledgePipelineError("Evidenceが見つからないためDraftを生成できません。")
        normalization = self.evidence_normalizer.normalize(raw)
        if not normalization.evidence:
            raise KnowledgePipelineError(
                "標準化できるEvidenceがないためDraftを生成できません。"
            )
        deduplication = self.evidence_deduplicator.deduplicate(normalization)
        ranking = self.evidence_ranker.rank(deduplication)
        bundle = self.evidence_bundle_builder.build(
            normalization,
            deduplication,
            ranking,
        )
        self.search_audit.record(raw, bundle)
        claim_build = self.claim_builder.build(normalized, bundle)
        if not claim_build.claims:
            raise KnowledgePipelineError("Evidenceに対応するClaim候補がありません。")
        references = self.reference_builder.build(bundle, claim_build)
        draft = self.knowledge_builder.build(bundle, claim_build, references)
        pipeline_id = f"kpp_{uuid4().hex[:16]}"
        fingerprint = _fingerprint(draft.model_dump(mode="json"))
        preview = KnowledgePipelinePreview(
            pipeline_id=pipeline_id,
            theme=normalized,
            created_at=datetime.now(UTC),
            evidence_bundle=bundle,
            claim_build=claim_build,
            references=references,
            authoring_draft=draft,
            fingerprint=fingerprint,
            external_ai_called=claim_build.llm_called,
            search_audit_recorded=True,
            external_search_called=bundle.external_search_performed,
        )
        self._pending[pipeline_id] = preview
        return preview

    def save(self, pipeline_id: str) -> SavePipelineDraftResult:
        preview = self._pending.get(pipeline_id)
        if preview is None:
            raise KnowledgePipelineError(
                "Draft Previewが見つかりません。もう一度生成してください。"
            )
        current_fingerprint = _fingerprint(preview.authoring_draft.model_dump(mode="json"))
        if current_fingerprint != preview.fingerprint:
            raise KnowledgePipelineError("Draft PreviewのFingerprintが一致しません。")
        saved = self.authoring.save_generated_draft(preview.authoring_draft)
        self._pending.pop(pipeline_id, None)
        return SavePipelineDraftResult(
            pipeline_id=pipeline_id,
            saved_at=datetime.now(UTC),
            draft=saved,
            fingerprint=current_fingerprint,
        )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
