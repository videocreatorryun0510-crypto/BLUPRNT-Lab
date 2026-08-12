"""Provider-neutral prompt construction for evidence-grounded Claim extraction."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from knowledge_workbench.claim_candidate_models import ClaimGenerationRequest

Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ClaimGenerationPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: Literal["1.0"] = "1.0"
    knowledge_term: str = Field(min_length=1, max_length=300)
    evidence_bundle_id: str
    selected_evidence_ids: tuple[str, ...]
    prompt_text: str = Field(min_length=1, max_length=100_000)
    prompt_fingerprint: Fingerprint


class EvidenceGroundedClaimPromptBuilder:
    builder_id = "evidence_grounded_claim_prompt_builder"
    builder_version = "1.0"
    maximum_evidence_items = 10

    def build(self, request: ClaimGenerationRequest) -> ClaimGenerationPrompt:
        selection = request.evidence_selection
        if len(selection.evidence) > self.maximum_evidence_items:
            raise ValueError(
                f"Claim生成へ渡せるEvidenceは最大{self.maximum_evidence_items}件です。"
            )
        evidence_payload = [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "abstract_or_snippet": item.abstract_or_snippet,
                "citation": item.citation,
                "pmid": item.pmid,
                "doi": item.doi,
            }
            for item in selection.evidence
        ]
        prompt_text = (
            "You extract candidate medical facts only from the supplied Formal Evidence.\n"
            "Do not use memory, general medical knowledge, web search, or unstated facts.\n"
            "Each candidate must contain one independent fact and must not be stronger than "
            "the evidence. Do not resolve contradictions.\n"
            "For every candidate, copy only a necessary short excerpt of at most 20 words "
            "from the supplied abstract_or_snippet and identify its exact evidence_id.\n"
            "Use support_level direct only when the excerpt directly supports the whole claim. "
            "Use partial, indirect, unsupported, or conflicting conservatively.\n"
            "support_scope must correspond to the support level. supporting_evidence_ids, "
            "assessment IDs, and locator IDs must use only the IDs below.\n"
            "Return structured JSON only. Do not create references or formal claim IDs.\n\n"
            f"Knowledge term: {selection.knowledge_term}\n"
            f"Maximum candidates: {request.max_candidates}\n"
            "Formal Evidence JSON:\n"
            + json.dumps(evidence_payload, ensure_ascii=False, separators=(",", ":"))
        )
        fingerprint = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        return ClaimGenerationPrompt(
            knowledge_term=selection.knowledge_term,
            evidence_bundle_id=selection.evidence_bundle_id,
            selected_evidence_ids=tuple(item.evidence_id for item in selection.evidence),
            prompt_text=prompt_text,
            prompt_fingerprint=fingerprint,
        )
