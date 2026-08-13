"""Phase 5.30 Knowledge Draft-only Preview and Promotion workflow."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from knowledge_contracts.registry_v10 import RegistryStatus
from knowledge_contracts.v10 import KnowledgeRecord, KnowledgeSchemaError, validate_knowledge_record
from pydantic import ValidationError

from knowledge_workbench.claim_key_resolver import (
    ClaimCandidate,
    extract_claim_candidates,
    registry_key_for_record,
)
from knowledge_workbench.knowledge_assembler import KnowledgeDraftService
from knowledge_workbench.knowledge_draft_models import KnowledgeDraft
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.promotion_log import JsonlPromotionLog
from knowledge_workbench.promotion_mapping import CATEGORY_SLOTS, SLOT_PATHS
from knowledge_workbench.promotion_models import (
    CommitKnowledgeDraftPromotionRequest,
    KnowledgeDraftPromotionPreview,
    KnowledgeDraftPromotionResult,
    KnowledgeDraftPromotionValidationReport,
    KnowledgeDraftRegistryDiff,
    PromotionCheck,
    PromotionLogEvent,
    PromotionOperation,
)


class KnowledgeDraftPromotionError(RuntimeError):
    """Raised when a Knowledge Draft cannot be promoted safely."""


@dataclass(frozen=True)
class _PreparedPromotion:
    preview: KnowledgeDraftPromotionPreview
    record: KnowledgeRecord


class KnowledgeDraftPromotionService:
    """Promote only a validated Knowledge Draft, never an Authoring Draft."""

    def __init__(
        self,
        drafts: KnowledgeDraftService,
        registry: KnowledgeRegistry,
        audit_log: JsonlPromotionLog,
    ) -> None:
        self.drafts = drafts
        self.registry = registry
        self.audit_log = audit_log
        self._pending: dict[str, _PreparedPromotion] = {}

    def preview(
        self,
        knowledge_draft_id: str,
        *,
        actor: str = "knowledge_author",
    ) -> KnowledgeDraftPromotionPreview:
        prepared = self._prepare(knowledge_draft_id)
        self._pending[prepared.preview.preview_id] = prepared
        self._log_preview(prepared.preview, actor)
        return prepared.preview

    def commit(
        self,
        request: CommitKnowledgeDraftPromotionRequest,
    ) -> KnowledgeDraftPromotionResult:
        prepared = self._pending.get(request.preview_id)
        if prepared is None:
            raise KnowledgeDraftPromotionError(
                "Promotion Previewが見つかりません。再度Previewしてください。"
            )
        preview = prepared.preview
        try:
            current = self._prepare(preview.knowledge_draft_id)
            self._require_unchanged(preview, current.preview)
            if not current.preview.validation.promotion_allowed:
                raise KnowledgeDraftPromotionError(
                    "Promotion Validationに失敗しています。"
                )

            reconciliation = self.registry.reconcile(
                current.record,
                actor=request.actor,
                note=(
                    request.comment
                    or f"Knowledge Draft {preview.knowledge_draft_id}からPromotion"
                ),
            )
            view = reconciliation.view
            if view.knowledge.status != RegistryStatus.DRAFT:
                raise KnowledgeDraftPromotionError(
                    "Promotion後のApproval Stateがdraftではありません。"
                )
            if view.knowledge.knowledge_version != preview.target_version:
                raise KnowledgeDraftPromotionError(
                    "Promotion後のKnowledge VersionがPreviewと一致しません。"
                )

            result = KnowledgeDraftPromotionResult(
                promotion_id=f"prm_{uuid4().hex[:16]}",
                preview_id=preview.preview_id,
                knowledge_draft_id=preview.knowledge_draft_id,
                promoted_at=datetime.now(UTC),
                operation=preview.operation,
                registry_key=view.knowledge.registry_key,
                knowledge_id=view.knowledge.knowledge_id,
                knowledge_version=view.knowledge.knowledge_version,
                fingerprint=_fingerprint(reconciliation.record.model_dump(mode="json")),
            )
            self.audit_log.append(
                PromotionLogEvent(
                    event_id=f"plg_{uuid4().hex[:16]}",
                    occurred_at=result.promoted_at,
                    event_type="promotion",
                    status="success",
                    draft_id=preview.knowledge_draft_id,
                    preview_id=preview.preview_id,
                    promotion_id=result.promotion_id,
                    registry_key=result.registry_key,
                    operation=result.operation,
                    knowledge_id=result.knowledge_id,
                    knowledge_version=result.knowledge_version,
                    approval_state="draft",
                    actor=request.actor,
                )
            )
            self._pending.pop(request.preview_id, None)
            return result
        except Exception as error:
            self.audit_log.append(
                PromotionLogEvent(
                    event_id=f"plg_{uuid4().hex[:16]}",
                    occurred_at=datetime.now(UTC),
                    event_type="promotion",
                    status="failed",
                    draft_id=preview.knowledge_draft_id,
                    preview_id=preview.preview_id,
                    promotion_id=None,
                    registry_key=preview.registry_key,
                    operation=preview.operation,
                    knowledge_id=preview.target_knowledge_id,
                    knowledge_version=preview.target_version,
                    approval_state=None,
                    actor=request.actor,
                    reason_codes=[error.__class__.__name__],
                )
            )
            raise

    def logs(self, *, limit: int = 100) -> list[PromotionLogEvent]:
        return self.audit_log.list(limit=limit)

    def _prepare(self, knowledge_draft_id: str) -> _PreparedPromotion:
        draft, source, draft_validation = self.drafts.get_with_source(
            knowledge_draft_id
        )
        snapshot = self.registry.snapshot()
        source_raw = source.knowledge.model_dump(mode="json")
        registry_key = registry_key_for_record(source_raw)
        existing = next(
            (item for item in snapshot.knowledge if item.registry_key == registry_key),
            None,
        )
        operation = (
            PromotionOperation.VERSION_UPDATE if existing else PromotionOperation.CREATE
        )
        current_version = existing.knowledge_version if existing else 0
        target_version = current_version + 1
        target_knowledge_id = (
            existing.knowledge_id if existing else source.knowledge.knowledge_id
        )
        existing_record = self.registry.record(existing.knowledge_id) if existing else None

        raw, mapped_ids = self._map_formal_record(
            draft,
            source_raw,
            knowledge_id=target_knowledge_id,
            content_revision=target_version,
        )
        checks: list[PromotionCheck] = []
        schema_valid = True
        try:
            record = validate_knowledge_record(raw)
        except (KnowledgeSchemaError, ValidationError, ValueError) as error:
            schema_valid = False
            record = source.knowledge.model_copy(
                update={
                    "knowledge_id": target_knowledge_id,
                    "content_revision": target_version,
                }
            )
            checks.append(_check("schema", False, f"Knowledge Schema: {error}"))
        else:
            checks.append(_check("schema", True, "Knowledge Schema 1.0に適合しています。"))

        draft_valid = draft_validation.save_allowed
        checks.append(
            _check(
                "draft_validation",
                draft_valid,
                "Knowledge Draft ValidationはOKです。"
                if draft_valid
                else "Knowledge Draftが生成元と一致しないためPromotionできません。",
            )
        )
        claim_text_valid = draft_validation.lossless_claims_valid
        claim_ids = {item.claim_id for item in draft.claims}
        linked_ids = {
            claim_id
            for reference in draft.references
            for claim_id in reference.supported_claim_ids
        }
        invalid_slots = [
            item.claim_id
            for item in draft.claims
            if item.semantic_slot not in CATEGORY_SLOTS[draft.category]
        ]
        unsupported_claims = sorted(claim_ids - linked_ids)
        claim_text_valid = (
            claim_text_valid
            and bool(draft.claims)
            and not invalid_slots
            and not unsupported_claims
        )
        checks.append(
            _check(
                "claim_text",
                claim_text_valid,
                "Claim本文はAuthoringで承認された内容と一致します。"
                if claim_text_valid
                else "Claim本文、保存先、またはReference対応が一致しません。",
            )
        )

        summary_valid = draft_validation.summary_traceable
        checks.append(
            _check(
                "summary",
                summary_valid,
                "Summaryは既存Claim本文の完全一致コピーです。"
                if summary_valid
                else "Summaryが元Claim本文と一致しません。",
            )
        )
        bad_references = [
            item.source_id
            for item in draft.references
            if item.source_priority_rank is None
            or not item.supported_claim_ids
            or not set(item.supported_claim_ids).issubset(mapped_ids)
        ]
        reference_valid = (
            draft_validation.references_unchanged
            and draft_validation.reference_integrity_valid
            and bool(draft.references)
            and not bad_references
        )
        checks.append(
            _check(
                "references",
                reference_valid,
                "Reference本文とClaim対応は一致します。"
                if reference_valid
                else "Reference本文、優先順位、またはClaim対応が一致しません。",
            )
        )
        category_valid = (
            draft_validation.category_valid
            and not invalid_slots
            and (
                existing_record is None
                or existing_record.classification.term_type == draft.category.value
            )
        )
        checks.append(
            _check(
                "category",
                category_valid,
                "CategoryとClaim保存先は一致します。"
                if category_valid
                else "CategoryまたはClaim保存先がRegistryと一致しません。",
            )
        )

        fingerprint_valid = (
            draft_validation.fingerprint_valid
            and bool(re.fullmatch(r"[0-9a-f]{64}", draft.fingerprint))
        )
        checks.append(
            _check(
                "fingerprint",
                fingerprint_valid,
                "Knowledge Draft Fingerprintは一致します。"
                if fingerprint_valid
                else "Knowledge Draft Fingerprintが一致しません。",
            )
        )
        review_state_valid = (
            draft.review.approval_state == "draft"
            and not draft.review.promotion_performed
            and not draft.review.registry_mutated
        )
        checks.append(
            _check(
                "review_state",
                review_state_valid,
                "Review状態はdraftです。"
                if review_state_valid
                else "Knowledge DraftのReview状態がdraftではありません。",
            )
        )

        id_collision = next(
            (
                item
                for item in snapshot.knowledge
                if item.knowledge_id == source.knowledge.knowledge_id
                and item.registry_key != registry_key
            ),
            None,
        )
        incoming_names = {
            _normalized(source.metadata.title),
            *(_normalized(alias) for alias in source.metadata.aliases),
        }
        alias_collisions = [
            item.alias
            for item in snapshot.alias_bindings
            if _normalized(item.alias) in incoming_names and item.target != registry_key
        ]
        target_version_valid = (
            target_version == current_version + 1
            and target_version >= 1
            and id_collision is None
            and not alias_collisions
        )
        checks.append(
            _check(
                "target_version",
                target_version_valid,
                f"Promotion後のVersionは{target_version}です。"
                if target_version_valid
                else "Version、Knowledge ID、またはAliasがRegistryと競合します。",
            )
        )

        diff = self._registry_diff(
            draft,
            record,
            registry_key,
            existing_record,
            snapshot.claims,
        )
        registry_diff_valid = diff.has_changes and not diff.removed_claim_keys
        checks.append(
            _check(
                "registry_diff",
                registry_diff_valid,
                "Registryとの差分を確認できます。"
                if registry_diff_valid
                else (
                    "Claim削除はこのMVPでは安全のためPromotionできません。"
                    if diff.removed_claim_keys
                    else "Registryとの差分がありません。"
                ),
            )
        )

        promotion_allowed = all(
            (
                draft_valid,
                claim_text_valid,
                summary_valid,
                reference_valid,
                category_valid,
                fingerprint_valid,
                review_state_valid,
                target_version_valid,
                registry_diff_valid,
                schema_valid,
            )
        )
        validation = KnowledgeDraftPromotionValidationReport(
            draft_validation_valid=draft_valid,
            claim_text_valid=claim_text_valid,
            summary_valid=summary_valid,
            reference_valid=reference_valid,
            category_valid=category_valid,
            fingerprint_valid=fingerprint_valid,
            review_state_valid=review_state_valid,
            target_version_valid=target_version_valid,
            registry_diff_valid=registry_diff_valid,
            schema_valid=schema_valid,
            promotion_allowed=promotion_allowed,
            checks=checks,
        )
        preview = KnowledgeDraftPromotionPreview(
            preview_id=f"ppv_{uuid4().hex[:16]}",
            knowledge_draft_id=draft.knowledge_draft_id,
            source_authoring_draft_id=draft.metadata.source_authoring_draft_id,
            created_at=datetime.now(UTC),
            title=draft.title,
            category=draft.category.value,
            summary=draft.summary,
            claims=draft.claims,
            references=draft.references,
            completeness_score=draft.completeness.score,
            validation=validation,
            registry_diff=diff,
            registry_key=registry_key,
            operation=operation,
            target_knowledge_id=target_knowledge_id,
            current_version=current_version,
            target_version=target_version,
            draft_fingerprint=draft.fingerprint,
            registry_fingerprint=_fingerprint(snapshot.model_dump(mode="json")),
            knowledge_fingerprint=_fingerprint(record.model_dump(mode="json")),
        )
        return _PreparedPromotion(preview=preview, record=record)

    @staticmethod
    def _map_formal_record(
        draft: KnowledgeDraft,
        source_raw: dict[str, Any],
        *,
        knowledge_id: str,
        content_revision: int,
    ) -> tuple[dict[str, Any], set[str]]:
        raw = json.loads(json.dumps(source_raw, ensure_ascii=False))
        raw["knowledge_id"] = knowledge_id
        raw["content_revision"] = content_revision
        mapped_ids: set[str] = set()
        for claim in draft.claims:
            path = SLOT_PATHS.get((draft.category, claim.semantic_slot))
            if path is None:
                continue
            target: Any = raw
            for key in path:
                target = target[key]
            target.append({"claim_id": claim.claim_id, "assertion": claim.assertion})
            mapped_ids.add(claim.claim_id)
        raw["evidence"] = [
            {
                **reference.model_dump(mode="json"),
                "evidence_role": reference.evidence_role.value,
            }
            for reference in draft.references
            if reference.source_priority_rank is not None
            and reference.supported_claim_ids
            and set(reference.supported_claim_ids).issubset(mapped_ids)
        ]
        for reference in raw["evidence"]:
            reference.pop("evidence_level", None)
        return raw, mapped_ids

    @staticmethod
    def _registry_diff(
        draft: KnowledgeDraft,
        record: KnowledgeRecord,
        registry_key: str,
        existing_record: KnowledgeRecord | None,
        registry_claims: list[Any],
    ) -> KnowledgeDraftRegistryDiff:
        incoming_candidates = extract_claim_candidates(
            record.model_dump(mode="json"), registry_key
        )
        incoming = {item.claim_key: item.assertion for item in incoming_candidates}
        incoming_claim_key_by_id = {
            claim_id: item.claim_key
            for item in incoming_candidates
            for claim_id in item.old_claim_ids
        }
        existing_claims = {
            item.claim_key: item.assertion
            for item in registry_claims
            if existing_record is not None
            and item.knowledge_id == existing_record.knowledge_id
            and item.status != RegistryStatus.DEPRECATED
            and not item.is_deleted
        }
        added_claims = sorted(set(incoming) - set(existing_claims))
        removed_claims = sorted(set(existing_claims) - set(incoming))
        updated_claims = sorted(
            key
            for key in set(incoming) & set(existing_claims)
            if incoming[key] != existing_claims[key]
        )

        current_claim_key_by_id = {
            item.claim_id: item.claim_key
            for item in registry_claims
            if existing_record is not None and item.knowledge_id == existing_record.knowledge_id
        }
        incoming_references = _reference_map(
            record.model_dump(mode="json").get("evidence", []),
            incoming_claim_key_by_id,
        )
        existing_references = _reference_map(
            existing_record.model_dump(mode="json").get("evidence", [])
            if existing_record is not None
            else [],
            current_claim_key_by_id,
        )
        added_references = sorted(set(incoming_references) - set(existing_references))
        removed_references = sorted(set(existing_references) - set(incoming_references))
        updated_references = sorted(
            key
            for key in set(incoming_references) & set(existing_references)
            if incoming_references[key] != existing_references[key]
        )
        is_new = existing_record is None
        title_changed = bool(
            existing_record is not None
            and existing_record.term.canonical_name != draft.title
        )
        category_changed = bool(
            existing_record is not None
            and existing_record.classification.term_type != draft.category.value
        )
        summary_changed = bool(
            existing_record is not None
            and _record_summary(existing_record) != draft.summary
        )
        has_changes = is_new or any(
            (
                title_changed,
                category_changed,
                summary_changed,
                added_claims,
                removed_claims,
                updated_claims,
                added_references,
                removed_references,
                updated_references,
            )
        )
        return KnowledgeDraftRegistryDiff(
            is_new=is_new,
            has_changes=has_changes,
            title_changed=title_changed,
            category_changed=category_changed,
            summary_changed=summary_changed,
            added_claim_keys=added_claims,
            updated_claim_keys=updated_claims,
            removed_claim_keys=removed_claims,
            added_reference_keys=added_references,
            updated_reference_keys=updated_references,
            removed_reference_keys=removed_references,
        )

    @staticmethod
    def _require_unchanged(
        expected: KnowledgeDraftPromotionPreview,
        current: KnowledgeDraftPromotionPreview,
    ) -> None:
        comparisons = (
            (expected.draft_fingerprint, current.draft_fingerprint, "Knowledge Draft"),
            (expected.registry_fingerprint, current.registry_fingerprint, "Registry"),
            (expected.knowledge_fingerprint, current.knowledge_fingerprint, "Knowledge"),
            (expected.target_version, current.target_version, "Promotion対象Version"),
        )
        for before, after, label in comparisons:
            if before != after:
                raise KnowledgeDraftPromotionError(
                    f"{label}がPreview後に変更されました。再度Previewしてください。"
                )

    def _log_preview(
        self,
        preview: KnowledgeDraftPromotionPreview,
        actor: str,
    ) -> None:
        failed = [item.code for item in preview.validation.checks if not item.passed]
        self.audit_log.append(
            PromotionLogEvent(
                event_id=f"plg_{uuid4().hex[:16]}",
                occurred_at=preview.created_at,
                event_type="preview",
                status="ready" if preview.validation.promotion_allowed else "blocked",
                draft_id=preview.knowledge_draft_id,
                preview_id=preview.preview_id,
                promotion_id=None,
                registry_key=preview.registry_key,
                operation=preview.operation,
                knowledge_id=preview.target_knowledge_id,
                knowledge_version=preview.target_version,
                approval_state=None,
                actor=actor,
                reason_codes=failed,
            )
        )


def _check(code: str, passed: bool, message: str) -> PromotionCheck:
    return PromotionCheck(code=code, passed=passed, message=message)


def _fingerprint(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).lower()
        if character.isalnum()
    )


def _reference_key(reference: dict[str, Any]) -> str:
    if reference.get("doi"):
        return f"doi:{str(reference['doi']).lower()}"
    if reference.get("pmid"):
        return f"pmid:{reference['pmid']}"
    if reference.get("url"):
        return f"url:{str(reference['url']).rstrip('/').lower()}"
    return "title:" + _normalized(
        "|".join(
            str(reference.get(key) or "")
            for key in ("title", "issuing_organization", "publication_year")
        )
    )


def _reference_map(
    references: list[dict[str, Any]],
    claim_key_by_id: dict[str, str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for reference in references:
        payload = dict(reference)
        payload.pop("source_id", None)
        payload["supported_claim_keys"] = sorted(
            claim_key_by_id.get(item, f"unmapped:{item}")
            for item in payload.pop("supported_claim_ids", [])
        )
        result[_reference_key(reference)] = _fingerprint(payload)
    return result


def _record_summary(record: KnowledgeRecord) -> str:
    candidates: list[ClaimCandidate] = extract_claim_candidates(
        record.model_dump(mode="json"),
        registry_key_for_record(record.model_dump(mode="json")),
    )
    if not candidates:
        return record.term.canonical_name
    definitions = [item for item in candidates if item.field_path == "core_facts.definitions"]
    return (definitions or candidates)[0].assertion
