"""Application service for fast, non-AI Knowledge authoring."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from knowledge_contracts.v10 import KnowledgeRecord
from pydantic import ValidationError

from knowledge_workbench.authoring_models import (
    AddAuthoringClaimRequest,
    AddAuthoringReferenceRequest,
    AuthoringClaim,
    AuthoringDraftState,
    AuthoringDraftSummary,
    AuthoringMetadata,
    AuthoringReference,
    AuthoringValidationIssue,
    AuthoringValidationReport,
    CreateAuthoringDraftRequest,
    ImportAuthoringDraftRequest,
    KnowledgeAuthoringDraft,
    ReorderAuthoringClaimsRequest,
    UpdateAuthoringClaimRequest,
    UpdateAuthoringReferenceRequest,
    ValidationSeverity,
)
from knowledge_workbench.authoring_repository import AuthoringDraftRepository


class KnowledgeAuthoringService:
    """Owns draft authoring without writing incomplete data to Registry."""

    def __init__(self, repository: AuthoringDraftRepository) -> None:
        self.repository = repository

    def list_drafts(self) -> list[AuthoringDraftSummary]:
        return [self._summary(draft) for draft in self.repository.list()]

    def get(self, draft_id: str) -> KnowledgeAuthoringDraft:
        return self.repository.get(draft_id)

    def create(self, request: CreateAuthoringDraftRequest) -> KnowledgeAuthoringDraft:
        return self.save_generated_draft(self.build_skeleton(request))

    def build_skeleton(
        self, request: CreateAuthoringDraftRequest
    ) -> KnowledgeAuthoringDraft:
        """Build a contract-valid draft without persisting it."""

        now = datetime.now(UTC)
        knowledge_id = self._new_id("knw")
        knowledge = KnowledgeRecord.model_validate(
            self._empty_knowledge(
                knowledge_id=knowledge_id,
                category=request.category.value,
                title=request.title,
                aliases=request.aliases,
            )
        )
        draft = KnowledgeAuthoringDraft(
            draft_id=self._new_id("kad"),
            created_at=now,
            updated_at=now,
            metadata=AuthoringMetadata.model_validate(request.model_dump()),
            knowledge=knowledge,
        )
        return draft

    def save_generated_draft(
        self, draft: KnowledgeAuthoringDraft
    ) -> KnowledgeAuthoringDraft:
        """Persist a Pipeline draft only after the user confirms its Preview."""

        validated = KnowledgeAuthoringDraft.model_validate(draft)
        if not self.validate(validated).save_allowed:
            raise ValueError("Authoring validation failed")
        return self.repository.save(validated)

    def add_claim(
        self, draft_id: str, request: AddAuthoringClaimRequest
    ) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        claims = [
            *draft.claims,
            AuthoringClaim(
                claim_id=self._new_id("clm"),
                assertion=request.assertion,
                position=len(draft.claims) + 1,
                semantic_slot=request.semantic_slot,
            ),
        ]
        return self._save_update(draft, claims=claims)

    def update_claim(
        self,
        draft_id: str,
        claim_id: str,
        request: UpdateAuthoringClaimRequest,
    ) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        found = False
        claims = []
        for claim in draft.claims:
            if claim.claim_id == claim_id:
                found = True
                claim = claim.model_copy(
                    update={
                        "assertion": request.assertion,
                        "semantic_slot": request.semantic_slot,
                    }
                )
            claims.append(claim)
        if not found:
            raise ValueError(f"Claim not found: {claim_id}")
        return self._save_update(draft, claims=claims)

    def delete_claim(self, draft_id: str, claim_id: str) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        if claim_id not in {claim.claim_id for claim in draft.claims}:
            raise ValueError(f"Claim not found: {claim_id}")
        claims = [claim for claim in draft.claims if claim.claim_id != claim_id]
        claims = [
            claim.model_copy(update={"position": position})
            for position, claim in enumerate(claims, start=1)
        ]
        references = [
            reference.model_copy(
                update={
                    "supported_claim_ids": [
                        item for item in reference.supported_claim_ids if item != claim_id
                    ]
                }
            )
            for reference in draft.references
        ]
        return self._save_update(draft, claims=claims, references=references)

    def reorder_claims(
        self, draft_id: str, request: ReorderAuthoringClaimsRequest
    ) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        existing = {claim.claim_id: claim for claim in draft.claims}
        if len(request.claim_ids) != len(set(request.claim_ids)):
            raise ValueError("claim_ids must not contain duplicates")
        if set(request.claim_ids) != set(existing):
            raise ValueError("claim_ids must contain every current Claim exactly once")
        claims = [
            existing[claim_id].model_copy(update={"position": position})
            for position, claim_id in enumerate(request.claim_ids, start=1)
        ]
        return self._save_update(draft, claims=claims)

    def add_reference(
        self, draft_id: str, request: AddAuthoringReferenceRequest
    ) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        reference = AuthoringReference(
            source_id=self._new_id("src"),
            **request.model_dump(),
        )
        return self._save_update(
            draft,
            references=[*draft.references, reference],
        )

    def update_reference(
        self,
        draft_id: str,
        source_id: str,
        request: UpdateAuthoringReferenceRequest,
    ) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        found = False
        references = []
        for reference in draft.references:
            if reference.source_id == source_id:
                found = True
                reference = AuthoringReference(
                    source_id=source_id,
                    **request.model_dump(),
                )
            references.append(reference)
        if not found:
            raise ValueError(f"Reference not found: {source_id}")
        return self._save_update(draft, references=references)

    def delete_reference(self, draft_id: str, source_id: str) -> KnowledgeAuthoringDraft:
        draft = self.get(draft_id)
        if source_id not in {reference.source_id for reference in draft.references}:
            raise ValueError(f"Reference not found: {source_id}")
        references = [
            reference for reference in draft.references if reference.source_id != source_id
        ]
        return self._save_update(draft, references=references)

    def import_json(self, request: ImportAuthoringDraftRequest) -> KnowledgeAuthoringDraft:
        imported = KnowledgeAuthoringDraft.model_validate(request.draft)
        now = datetime.now(UTC)
        cloned = imported.model_copy(
            update={
                "draft_id": self._new_id("kad"),
                "created_at": now,
                "updated_at": now,
            }
        )
        return self.repository.save(KnowledgeAuthoringDraft.model_validate(cloned))

    def validate(self, draft: KnowledgeAuthoringDraft) -> AuthoringValidationReport:
        issues: list[AuthoringValidationIssue] = []
        knowledge_schema_valid = True
        try:
            KnowledgeRecord.model_validate(draft.knowledge.model_dump(mode="json"))
        except ValidationError as error:
            knowledge_schema_valid = False
            issues.append(
                AuthoringValidationIssue(
                    code="knowledge_schema_invalid",
                    severity=ValidationSeverity.ERROR,
                    path="knowledge",
                    message=str(error),
                )
            )

        required_fields_valid = bool(
            draft.metadata.title.strip()
            and draft.metadata.category.value
            and draft.metadata.difficulty.value
            and draft.metadata.exam_importance.value
        )
        if not required_fields_valid:
            issues.append(
                AuthoringValidationIssue(
                    code="required_fields_missing",
                    severity=ValidationSeverity.ERROR,
                    path="metadata",
                    message="Category、Title、Difficulty、Exam Importanceは必須です。",
                )
            )

        claim_ids = {claim.claim_id for claim in draft.claims}
        broken_references = [
            reference.source_id
            for reference in draft.references
            if not set(reference.supported_claim_ids).issubset(claim_ids)
        ]
        reference_integrity_valid = not broken_references
        if broken_references:
            issues.append(
                AuthoringValidationIssue(
                    code="reference_claim_mismatch",
                    severity=ValidationSeverity.ERROR,
                    path="references",
                    message="存在しないClaimを参照するReferenceがあります。",
                )
            )

        if not draft.claims:
            issues.append(
                AuthoringValidationIssue(
                    code="claim_empty",
                    severity=ValidationSeverity.WARNING,
                    path="claims",
                    message="Claimが未入力です。Skeletonとしては保存できます。",
                )
            )
        if not draft.references:
            issues.append(
                AuthoringValidationIssue(
                    code="reference_empty",
                    severity=ValidationSeverity.WARNING,
                    path="references",
                    message="Referenceが未入力です。医学レビュー前に追加してください。",
                )
            )
        elif any(not item.supported_claim_ids for item in draft.references):
            issues.append(
                AuthoringValidationIssue(
                    code="reference_unlinked",
                    severity=ValidationSeverity.WARNING,
                    path="references.supported_claim_ids",
                    message="Claimへ未接続のReferenceがあります。",
                )
            )
        if draft.references and any(
            item.source_priority_rank is None for item in draft.references
        ):
            issues.append(
                AuthoringValidationIssue(
                    code="source_priority_unassigned",
                    severity=ValidationSeverity.WARNING,
                    path="references.source_priority_rank",
                    message="Promotion前に情報源の優先順位を選択してください。",
                )
            )

        completeness = 40
        completeness += min(len(draft.claims), 3) * 10
        completeness += min(len(draft.references), 2) * 10
        if draft.references and all(item.supported_claim_ids for item in draft.references):
            completeness += 10
        completeness = min(completeness, 100)
        save_allowed = (
            knowledge_schema_valid and required_fields_valid and reference_integrity_valid
        )
        return AuthoringValidationReport(
            schema_valid=True,
            knowledge_schema_valid=knowledge_schema_valid,
            required_fields_valid=required_fields_valid,
            reference_integrity_valid=reference_integrity_valid,
            claim_count=len(draft.claims),
            reference_count=len(draft.references),
            relation_count=len(draft.relations),
            completeness_score=completeness,
            save_allowed=save_allowed,
            issues=issues,
        )

    def export_json(self, draft: KnowledgeAuthoringDraft) -> str:
        return draft.model_dump_json(indent=2)

    def export_markdown(self, draft: KnowledgeAuthoringDraft) -> str:
        aliases = "、".join(draft.metadata.aliases) or "なし"
        claim_lines = (
            "\n".join(
                f"{claim.position}. `{claim.claim_id}` "
                f"(`{claim.semantic_slot.value}`) — {claim.assertion}"
                for claim in draft.claims
            )
            or "（未入力）"
        )
        reference_lines = (
            "\n".join(
                f"- `{item.source_id}` [{item.evidence_level.value}] {item.title}"
                for item in draft.references
            )
            or "（未入力）"
        )
        return (
            f"# {draft.metadata.title}\n\n"
            f"- Knowledge ID: `{draft.knowledge.knowledge_id}`\n"
            f"- Category: `{draft.metadata.category.value}`\n"
            f"- Alias: {aliases}\n"
            f"- Difficulty: `{draft.metadata.difficulty.value}`\n"
            f"- Exam Importance: `{draft.metadata.exam_importance.value}`\n"
            f"- Review: `draft`\n\n"
            "## Claims\n\n"
            f"{claim_lines}\n\n"
            "## References\n\n"
            f"{reference_lines}\n\n"
            "## Relations\n\n（未入力）\n"
        )

    def archive(self, draft_id: str) -> KnowledgeAuthoringDraft:
        """Archive a promoted draft without deleting its authoring history."""

        draft = self.get(draft_id)
        return self._save_update(draft, lifecycle_state=AuthoringDraftState.ARCHIVED)

    def _save_update(
        self, draft: KnowledgeAuthoringDraft, **updates: Any
    ) -> KnowledgeAuthoringDraft:
        updated = draft.model_copy(update={"updated_at": datetime.now(UTC), **updates})
        validated = KnowledgeAuthoringDraft.model_validate(updated)
        report = self.validate(validated)
        if not report.save_allowed:
            raise ValueError("Authoring validation failed")
        return self.repository.save(validated)

    @staticmethod
    def _summary(draft: KnowledgeAuthoringDraft) -> AuthoringDraftSummary:
        return AuthoringDraftSummary(
            draft_id=draft.draft_id,
            knowledge_id=draft.knowledge.knowledge_id,
            title=draft.metadata.title,
            category=draft.metadata.category,
            difficulty=draft.metadata.difficulty,
            exam_importance=draft.metadata.exam_importance,
            claim_count=len(draft.claims),
            reference_count=len(draft.references),
            review_state=draft.review.state,
            lifecycle_state=draft.lifecycle_state,
            updated_at=draft.updated_at,
        )

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:16]}"

    @staticmethod
    def _empty_knowledge(
        *, knowledge_id: str, category: str, title: str, aliases: list[str]
    ) -> dict[str, Any]:
        empty_groups: dict[str, list[Any]] = {
            "pathophysiologic_states": [],
            "representative_diseases": [],
            "interpretive_notes": [],
        }
        category_content: dict[str, Any]
        if category == "test_item":
            category_content = {
                "template_id": "test_item_v1.0",
                "test_item": {
                    "biological_basis": [],
                    "analyte_characteristics": [],
                    "purposes": [],
                    "specimens": [],
                    "measurement_methods": [],
                    "measurement_principles": [],
                    "standardization_and_traceability": [],
                    "reporting_systems": [],
                    "reference_ranges": [],
                    "clinical_decision_limits": [],
                    "value_associations": {
                        "high": empty_groups,
                        "low": json.loads(json.dumps(empty_groups)),
                    },
                    "related_test_combinations": [],
                    "analytical_interferences": [],
                    "interpretation_cautions": [],
                    "time_course": [],
                    "isoenzymes": [],
                },
            }
        else:
            empty_by_category = {
                "staining_method": {
                    "purposes": [],
                    "target_structures": [],
                    "applicable_specimens": [],
                    "fixation_requirements": [],
                    "staining_principles": [],
                    "reagents": [],
                    "procedure_steps": [],
                    "result_interpretations": [],
                    "quality_controls": [],
                    "error_causes": [],
                    "limitations": [],
                    "safety_considerations": [],
                    "related_methods": [],
                },
                "specimen": {
                    "specimen_kind": "other",
                    "overview": [],
                    "uses": [],
                    "collection_methods": [],
                    "storage_conditions": [],
                    "cautions": [],
                },
                "reagent": {
                    "reagent_kind": "other",
                    "purposes": [],
                    "targets": [],
                    "usage_steps": [],
                    "cautions": [],
                    "storage_conditions": [],
                },
                "biological_structure": {
                    "overview": [],
                    "main_functions": [],
                    "main_components": [],
                    "organisms_present": [],
                },
                "disease": {
                    "overview": [],
                    "pathophysiology": [],
                    "causes": [],
                    "main_symptoms": [],
                    "main_laboratory_findings": [],
                    "differential_points": [],
                    "national_exam_point_claim_ids": [],
                },
                "laboratory_test_item": {
                    "overview": [],
                    "measured_targets": [],
                    "clinical_significance": [],
                    "high_conditions": [],
                    "low_conditions": [],
                    "measurement_methods": [],
                },
            }
            category_content = {
                "template_id": f"{category}_v1.0",
                category: empty_by_category[category],
            }
        empty_publisher: dict[str, list[Any]] = {
            "priority_claim_ids": [],
            "priority_exam_metadata": [],
        }
        return {
            "schema_version": "1.0",
            "knowledge_id": knowledge_id,
            "content_revision": 1,
            "term": {
                "canonical_name": title,
                "english_name": None,
                "aliases": aliases,
            },
            "classification": {
                "term_type": category,
                "primary_exam_domain": "other",
                "related_exam_domains": [],
            },
            "core_facts": {"definitions": []},
            "category_content": category_content,
            "exam_metadata": {
                "analysis_batch_id": None,
                "importance": None,
                "first_appearance_session": None,
                "last_appearance_session": None,
                "appearance_frequency": None,
                "blueprint_references": [],
                "related_questions": [],
                "comparison_targets": [],
                "related_knowledge": [],
                "priority_claim_ids": [],
                "keywords": [],
            },
            "evidence": [],
            "publish_targets": {
                "pdf": empty_publisher,
                "note": dict(empty_publisher),
                "training_video": dict(empty_publisher),
                "national_exam": dict(empty_publisher),
            },
        }
