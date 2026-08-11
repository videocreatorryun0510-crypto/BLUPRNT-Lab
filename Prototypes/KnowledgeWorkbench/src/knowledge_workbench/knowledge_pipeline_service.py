"""Orchestrates Theme -> Evidence -> Claims -> Authoring Draft without Promotion."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.knowledge_pipeline_builders import (
    AuthoringKnowledgeBuilder,
    AuthoringReferenceBuilder,
)
from knowledge_workbench.knowledge_pipeline_interfaces import (
    ClaimBuilder,
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
        evidence_ranker: EvidenceRanker,
        claim_builder: ClaimBuilder,
        reference_builder: AuthoringReferenceBuilder,
        knowledge_builder: AuthoringKnowledgeBuilder,
        authoring: KnowledgeAuthoringService,
    ) -> None:
        self.search_provider = search_provider
        self.evidence_ranker = evidence_ranker
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

        search = self.search_provider.search(EvidenceSearchRequest(theme=normalized))
        if not search.evidence:
            raise KnowledgePipelineError("Evidenceが見つからないためDraftを生成できません。")
        ranking = self.evidence_ranker.rank(search)
        claim_build = self.claim_builder.build(normalized, ranking)
        if not claim_build.claims:
            raise KnowledgePipelineError("Evidenceに対応するClaim候補がありません。")
        references = self.reference_builder.build(ranking, claim_build)
        draft = self.knowledge_builder.build(search, claim_build, references)
        pipeline_id = f"kpp_{uuid4().hex[:16]}"
        fingerprint = _fingerprint(draft.model_dump(mode="json"))
        preview = KnowledgePipelinePreview(
            pipeline_id=pipeline_id,
            theme=normalized,
            created_at=datetime.now(UTC),
            evidence_search=search,
            evidence_ranking=ranking,
            claim_build=claim_build,
            references=references,
            authoring_draft=draft,
            fingerprint=fingerprint,
            external_ai_called=claim_build.llm_called,
            external_search_called=search.external_search_performed,
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
