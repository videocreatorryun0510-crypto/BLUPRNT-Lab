"""Lossless Authoring Draft to Knowledge Draft assembly boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, Protocol
from uuid import uuid4

from knowledge_workbench.authoring_models import (
    AuthoringSemanticSlot,
    KnowledgeAuthoringDraft,
)
from knowledge_workbench.knowledge_draft_models import (
    KnowledgeDraft,
    KnowledgeDraftClaim,
    KnowledgeDraftCompleteness,
    KnowledgeDraftMetadata,
    KnowledgeDraftReference,
    KnowledgeDraftReview,
    KnowledgeDraftSection,
    KnowledgeDraftSummary,
    KnowledgeDraftValidationIssue,
    KnowledgeDraftValidationReport,
    knowledge_draft_fingerprint,
)
from knowledge_workbench.knowledge_draft_repository import KnowledgeDraftRepository


class KnowledgeDraftValidationError(ValueError):
    """Raised before persistence when an assembled Draft is not structurally safe."""

    def __init__(self, report: KnowledgeDraftValidationReport) -> None:
        super().__init__("Knowledge Draft validation failed; Draft was not saved")
        self.report = report


class KnowledgeAssembler:
    """Arrange human-reviewed inputs without inventing or rewriting medical content."""

    assembler_id: ClassVar[Literal["deterministic_knowledge_assembler"]] = (
        "deterministic_knowledge_assembler"
    )
    assembler_version: ClassVar[Literal["1.0.0"]] = "1.0.0"

    def assemble(self, source: KnowledgeAuthoringDraft) -> KnowledgeDraft:
        now = datetime.now(UTC)
        source_fingerprint = _canonical_fingerprint(source.model_dump(mode="json"))
        summary_claim = next(
            (
                claim
                for slot in (
                    AuthoringSemanticSlot.DEFINITION,
                    AuthoringSemanticSlot.OVERVIEW,
                )
                for claim in source.claims
                if claim.semantic_slot == slot
            ),
            source.claims[0] if source.claims else None,
        )
        summary = summary_claim.assertion if summary_claim is not None else source.metadata.title
        claim_reference_ids = {
            claim.claim_id: tuple(
                reference.source_id
                for reference in source.references
                if claim.claim_id in reference.supported_claim_ids
            )
            for claim in source.claims
        }
        claims = tuple(
            KnowledgeDraftClaim(
                claim_id=claim.claim_id,
                assertion=claim.assertion,
                position=claim.position,
                semantic_slot=claim.semantic_slot,
                reference_ids=claim_reference_ids[claim.claim_id],
            )
            for claim in source.claims
        )
        references = tuple(
            KnowledgeDraftReference.model_validate(reference.model_dump(mode="json"))
            for reference in source.references
        )
        sections = self._sections(claims)
        completeness = self._completeness(claims, references)
        raw: dict[str, Any] = {
            "knowledge_draft_version": "1.0",
            "knowledge_draft_id": f"kdr_{uuid4().hex[:16]}",
            "temporary_knowledge_id": f"tmp_knw_{uuid4().hex[:16]}",
            "category": source.metadata.category.value,
            "title": source.metadata.title,
            "summary": summary,
            "summary_source_claim_id": (
                summary_claim.claim_id if summary_claim is not None else None
            ),
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "references": [reference.model_dump(mode="json") for reference in references],
            "category_structure": [section.model_dump(mode="json") for section in sections],
            "metadata": KnowledgeDraftMetadata(
                source_authoring_draft_id=source.draft_id,
                source_authoring_fingerprint=source_fingerprint,
                difficulty=source.metadata.difficulty,
                exam_importance=source.metadata.exam_importance,
                assembler_id=self.assembler_id,
                assembler_version=self.assembler_version,
                assembled_at=now,
            ).model_dump(mode="json"),
            "review": KnowledgeDraftReview().model_dump(mode="json"),
            "completeness": completeness.model_dump(mode="json"),
        }
        raw["fingerprint"] = knowledge_draft_fingerprint(raw)
        return KnowledgeDraft.model_validate(raw)

    @staticmethod
    def _sections(
        claims: tuple[KnowledgeDraftClaim, ...],
    ) -> tuple[KnowledgeDraftSection, ...]:
        order: list[AuthoringSemanticSlot] = []
        grouped: dict[AuthoringSemanticSlot, list[str]] = {}
        for claim in claims:
            if claim.semantic_slot not in grouped:
                order.append(claim.semantic_slot)
                grouped[claim.semantic_slot] = []
            grouped[claim.semantic_slot].append(claim.claim_id)
        return tuple(
            KnowledgeDraftSection(section_key=slot, claim_ids=tuple(grouped[slot]))
            for slot in order
        )

    @staticmethod
    def _completeness(
        claims: tuple[KnowledgeDraftClaim, ...],
        references: tuple[KnowledgeDraftReference, ...],
    ) -> KnowledgeDraftCompleteness:
        linked = {claim_id for item in references for claim_id in item.supported_claim_ids}
        unassigned = sum(
            claim.semantic_slot == AuthoringSemanticSlot.UNASSIGNED for claim in claims
        )
        missing: list[str] = []
        score = 35
        if claims:
            score += 25
        else:
            missing.append("claims")
        if references:
            score += 20
        else:
            missing.append("references")
        if claims and all(claim.claim_id in linked for claim in claims):
            score += 15
        else:
            missing.append("claim_reference_mapping")
        if unassigned == 0 and claims:
            score += 5
        elif unassigned:
            missing.append("category_section_assignment")
        return KnowledgeDraftCompleteness(
            score=min(score, 100),
            missing_items=tuple(missing),
            claim_count=len(claims),
            reference_count=len(references),
            linked_claim_count=sum(claim.claim_id in linked for claim in claims),
            unassigned_claim_count=unassigned,
        )


class KnowledgeDraftValidator:
    """Validate structural integrity and losslessness before saving a Draft."""

    def validate(
        self,
        draft: KnowledgeDraft,
        source: KnowledgeAuthoringDraft,
    ) -> KnowledgeDraftValidationReport:
        issues: list[KnowledgeDraftValidationIssue] = []

        positions = [claim.position for claim in draft.claims]
        claim_order_valid = positions == list(range(1, len(draft.claims) + 1))
        self._issue_if_false(
            issues,
            claim_order_valid,
            "claim_order_invalid",
            "claims.position",
            "Claim順は1からの連番である必要があります。",
        )
        claim_ids = [claim.claim_id for claim in draft.claims]
        unique_claim_ids_valid = len(claim_ids) == len(set(claim_ids))
        self._issue_if_false(
            issues,
            unique_claim_ids_valid,
            "claim_id_duplicate",
            "claims.claim_id",
            "Claim IDが重複しています。",
        )
        source_ids = [reference.source_id for reference in draft.references]
        linked_claim_ids = {
            claim_id for item in draft.references for claim_id in item.supported_claim_ids
        }
        known_claim_ids = set(claim_ids)
        reference_integrity_valid = bool(draft.references) and bool(draft.claims)
        reference_integrity_valid = reference_integrity_valid and len(source_ids) == len(
            set(source_ids)
        )
        reference_integrity_valid = reference_integrity_valid and all(
            set(item.supported_claim_ids).issubset(known_claim_ids)
            for item in draft.references
        )
        reference_integrity_valid = reference_integrity_valid and all(
            claim_id in linked_claim_ids for claim_id in claim_ids
        )
        reference_integrity_valid = reference_integrity_valid and all(
            claim.reference_ids
            == tuple(
                reference.source_id
                for reference in draft.references
                if claim.claim_id in reference.supported_claim_ids
            )
            for claim in draft.claims
        )
        self._issue_if_false(
            issues,
            reference_integrity_valid,
            "reference_integrity_invalid",
            "references",
            "すべてのClaimに存在するReferenceの対応が必要です。",
        )
        category_valid = (
            draft.category == source.metadata.category
            and source.knowledge.classification.term_type == draft.category.value
            and draft.title == source.metadata.title
            and draft.category_structure == KnowledgeAssembler._sections(draft.claims)
        )
        self._issue_if_false(
            issues,
            category_valid,
            "category_mismatch",
            "category",
            "Authoring DraftとCategoryまたはTitleが一致しません。",
        )
        fingerprint_valid = draft.fingerprint == knowledge_draft_fingerprint(draft)
        self._issue_if_false(
            issues,
            fingerprint_valid,
            "fingerprint_mismatch",
            "fingerprint",
            "Knowledge DraftのFingerprintが一致しません。",
        )
        source_fingerprint = _canonical_fingerprint(source.model_dump(mode="json"))
        metadata_valid = (
            draft.metadata.source_authoring_draft_id == source.draft_id
            and draft.metadata.source_authoring_fingerprint == source_fingerprint
            and draft.metadata.assembler_id == "deterministic_knowledge_assembler"
            and draft.metadata.assembler_version == "1.0.0"
            and draft.completeness
            == KnowledgeAssembler._completeness(draft.claims, draft.references)
        )
        self._issue_if_false(
            issues,
            metadata_valid,
            "metadata_invalid",
            "metadata",
            "入力DraftまたはAssemblerのMetadataが一致しません。",
        )
        lossless_claims_valid = [
            (
                item.claim_id,
                item.assertion,
                item.position,
                item.semantic_slot,
            )
            for item in draft.claims
        ] == [
            (
                item.claim_id,
                item.assertion,
                item.position,
                item.semantic_slot,
            )
            for item in source.claims
        ]
        self._issue_if_false(
            issues,
            lossless_claims_valid,
            "claims_changed",
            "claims",
            "AssemblerがAuthoring Claimを追加・削除・変更しています。",
        )
        references_unchanged = [
            item.model_dump(mode="json", exclude={"reference_ids"})
            for item in draft.references
        ] == [item.model_dump(mode="json") for item in source.references]
        self._issue_if_false(
            issues,
            references_unchanged,
            "references_changed",
            "references",
            "Assemblerが選択済みReferenceを変更しています。",
        )
        source_claim = next(
            (
                item
                for item in source.claims
                if item.claim_id == draft.summary_source_claim_id
            ),
            None,
        )
        summary_traceable = (
            source_claim is not None and draft.summary == source_claim.assertion
        )
        self._issue_if_false(
            issues,
            summary_traceable,
            "summary_not_traceable",
            "summary",
            "Summaryは既存Claim本文の完全一致コピーである必要があります。",
        )
        save_allowed = all(
            (
                claim_order_valid,
                unique_claim_ids_valid,
                reference_integrity_valid,
                category_valid,
                fingerprint_valid,
                metadata_valid,
                lossless_claims_valid,
                references_unchanged,
                summary_traceable,
                draft.review.approval_state == "draft",
                not draft.review.promotion_performed,
                not draft.review.registry_mutated,
            )
        )
        return KnowledgeDraftValidationReport(
            schema_valid=True,
            claim_order_valid=claim_order_valid,
            unique_claim_ids_valid=unique_claim_ids_valid,
            reference_integrity_valid=reference_integrity_valid,
            category_valid=category_valid,
            fingerprint_valid=fingerprint_valid,
            metadata_valid=metadata_valid,
            lossless_claims_valid=lossless_claims_valid,
            references_unchanged=references_unchanged,
            summary_traceable=summary_traceable,
            save_allowed=save_allowed,
            issues=tuple(issues),
        )

    @staticmethod
    def _issue_if_false(
        issues: list[KnowledgeDraftValidationIssue],
        passed: bool,
        code: str,
        path: str,
        message: str,
    ) -> None:
        if not passed:
            issues.append(KnowledgeDraftValidationIssue(code=code, path=path, message=message))


class AuthoringDraftReader(Protocol):
    def get(self, draft_id: str) -> KnowledgeAuthoringDraft: ...


class KnowledgeDraftService:
    """Orchestrate assemble, validate, and save without Registry or Promotion access."""

    def __init__(
        self,
        assembler: KnowledgeAssembler,
        validator: KnowledgeDraftValidator,
        repository: KnowledgeDraftRepository,
        authoring: AuthoringDraftReader,
    ) -> None:
        self.assembler = assembler
        self.validator = validator
        self.repository = repository
        self.authoring = authoring

    def generate(
        self, authoring_draft_id: str
    ) -> tuple[KnowledgeDraft, KnowledgeDraftValidationReport]:
        source: KnowledgeAuthoringDraft = self.authoring.get(authoring_draft_id)
        draft = self.assembler.assemble(source)
        report = self.validator.validate(draft, source)
        if not report.save_allowed:
            raise KnowledgeDraftValidationError(report)
        self.repository.save(draft)
        return draft, report

    def get(
        self, knowledge_draft_id: str
    ) -> tuple[KnowledgeDraft, KnowledgeDraftValidationReport]:
        draft, _, report = self.get_with_source(knowledge_draft_id)
        return draft, report

    def get_with_source(
        self, knowledge_draft_id: str
    ) -> tuple[
        KnowledgeDraft,
        KnowledgeAuthoringDraft,
        KnowledgeDraftValidationReport,
    ]:
        """Load the immutable Draft together with its verified authoring source.

        Promotion receives only a Knowledge Draft ID.  The source is loaded here
        solely to prove that the assembled content is still lossless and to reuse
        the category skeleton that already belongs to the existing contract.
        """

        draft = self.repository.get(knowledge_draft_id)
        source: KnowledgeAuthoringDraft = self.authoring.get(
            draft.metadata.source_authoring_draft_id
        )
        return draft, source, self.validator.validate(draft, source)

    def list(self) -> list[KnowledgeDraftSummary]:
        return [
            KnowledgeDraftSummary(
                knowledge_draft_id=draft.knowledge_draft_id,
                temporary_knowledge_id=draft.temporary_knowledge_id,
                source_authoring_draft_id=draft.metadata.source_authoring_draft_id,
                title=draft.title,
                category=draft.category,
                completeness_score=draft.completeness.score,
                fingerprint=draft.fingerprint,
                assembled_at=draft.metadata.assembled_at,
            )
            for draft in self.repository.list()
        ]

    @staticmethod
    def export_json(draft: KnowledgeDraft) -> str:
        return draft.model_dump_json(indent=2)

    @staticmethod
    def export_markdown(draft: KnowledgeDraft) -> str:
        claim_lines = "\n".join(
            f"{item.position}. `{item.claim_id}` (`{item.semantic_slot.value}`) — "
            f"{item.assertion}"
            for item in draft.claims
        )
        reference_lines = "\n".join(
            f"- `{item.source_id}` [{item.evidence_level.value}] {item.title} "
            f"(Claims: {', '.join(item.supported_claim_ids)})"
            for item in draft.references
        )
        return (
            f"# {draft.title}\n\n"
            f"- Temporary Knowledge ID: `{draft.temporary_knowledge_id}`\n"
            f"- Category: `{draft.category.value}`\n"
            f"- Approval: `draft`\n"
            f"- Completeness: `{draft.completeness.score}%`\n"
            f"- Fingerprint: `{draft.fingerprint}`\n\n"
            "## Summary\n\n"
            f"{draft.summary}\n\n"
            "## Claims\n\n"
            f"{claim_lines}\n\n"
            "## References\n\n"
            f"{reference_lines}\n"
        )


def _canonical_fingerprint(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
