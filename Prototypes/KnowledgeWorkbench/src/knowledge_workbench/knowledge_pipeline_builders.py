"""Provider-independent Evidence ranking, Reference building and Draft assembly."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from knowledge_workbench.authoring_models import (
    AuthoringClaim,
    AuthoringExamImportance,
    AuthoringReference,
    CreateAuthoringDraftRequest,
    DifficultyLevel,
    EvidenceLevel,
    KnowledgeAuthoringDraft,
    ReferenceRole,
)
from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    EvidenceRankingResult,
    EvidenceSearchResult,
    PipelineEvidenceLevel,
    RankedEvidence,
)


class DefaultEvidenceRanker:
    ranking_version = "1.0"

    def rank(self, result: EvidenceSearchResult) -> EvidenceRankingResult:
        level_bonus = {
            PipelineEvidenceLevel.A: 12,
            PipelineEvidenceLevel.B: 6,
            PipelineEvidenceLevel.C: 0,
        }
        ordered = sorted(
            result.evidence,
            key=lambda item: (
                item.source_priority_rank,
                -level_bonus[item.evidence_level],
                item.title,
            ),
        )
        ranked = [
            RankedEvidence(
                evidence=item,
                rank=index,
                rank_score=max(
                    0,
                    min(
                        100,
                        100
                        - ((item.source_priority_rank - 1) * 12)
                        + level_bonus[item.evidence_level],
                    ),
                ),
                ranking_reasons=[
                    f"情報源優先順位 {item.source_priority_rank}",
                    f"Evidence Level {item.evidence_level.value}",
                ],
            )
            for index, item in enumerate(ordered, start=1)
        ]
        return EvidenceRankingResult(ranked_evidence=ranked)


class AuthoringReferenceBuilder:
    builder_version = "1.0"

    def build(
        self,
        ranking: EvidenceRankingResult,
        claims: ClaimBuildResult,
    ) -> list[AuthoringReference]:
        references: list[AuthoringReference] = []
        for ranked in ranking.ranked_evidence:
            evidence = ranked.evidence
            supported_claim_ids = [
                claim.claim_id
                for claim in claims.claims
                if evidence.evidence_id in claim.evidence_ids
            ]
            if not supported_claim_ids:
                continue
            references.append(
                AuthoringReference(
                    source_id=f"src_pipe_{_digest(evidence.evidence_id)[:16]}",
                    evidence_level=EvidenceLevel(evidence.evidence_level.value),
                    evidence_role=(
                        ReferenceRole.PRIMARY
                        if evidence.source_priority_rank <= 3
                        else ReferenceRole.SUPPORTING
                    ),
                    source_priority_rank=evidence.source_priority_rank,
                    title=evidence.title,
                    issuing_organization=evidence.publisher,
                    edition=evidence.citation.edition,
                    publication_year=(
                        evidence.publication_date.year
                        if evidence.publication_date is not None
                        else None
                    ),
                    url=evidence.url,
                    doi=evidence.citation.doi,
                    pmid=evidence.citation.pmid,
                    accessed_at=None,
                    chapter=evidence.citation.chapter,
                    pages=evidence.citation.pages,
                    supported_claim_ids=supported_claim_ids,
                )
            )
        return references


class AuthoringKnowledgeBuilder:
    builder_version = "1.0"

    def __init__(self, authoring: KnowledgeAuthoringService) -> None:
        self.authoring = authoring

    def build(
        self,
        search: EvidenceSearchResult,
        claims: ClaimBuildResult,
        references: list[AuthoringReference],
    ) -> KnowledgeAuthoringDraft:
        skeleton = self.authoring.build_skeleton(
            CreateAuthoringDraftRequest(
                category=search.subject.category,
                title=search.subject.canonical_name,
                aliases=search.subject.aliases,
                difficulty=DifficultyLevel.STANDARD,
                exam_importance=AuthoringExamImportance.MEDIUM,
            )
        )
        authoring_claims = [
            AuthoringClaim(
                claim_id=claim.claim_id,
                assertion=claim.assertion,
                position=index,
                semantic_slot=claim.semantic_slot,
            )
            for index, claim in enumerate(claims.claims, start=1)
        ]
        updated = skeleton.model_copy(
            update={
                "updated_at": datetime.now(UTC),
                "claims": authoring_claims,
                "references": references,
            }
        )
        return KnowledgeAuthoringDraft.model_validate(updated)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
