"""Safe Preview-then-Commit workflow from Authoring Draft to Knowledge Registry."""

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
from knowledge_contracts.v10 import (
    KnowledgeRecord,
    KnowledgeSchemaError,
    validate_knowledge_record,
)
from pydantic import ValidationError

from knowledge_workbench.authoring_models import (
    AuthoringDraftState,
    KnowledgeAuthoringDraft,
)
from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.claim_key_resolver import (
    extract_claim_candidates,
    registry_key_for_record,
)
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.promotion_log import JsonlPromotionLog
from knowledge_workbench.promotion_mapping import (
    CATEGORY_SLOTS as _CATEGORY_SLOTS,
)
from knowledge_workbench.promotion_mapping import (
    SLOT_PATHS as _SLOT_PATHS,
)
from knowledge_workbench.promotion_models import (
    CommitPromotionRequest,
    DraftDisposition,
    PromotionCheck,
    PromotionLogEvent,
    PromotionOperation,
    PromotionPreview,
    PromotionResult,
    PromotionValidationReport,
)


class PromotionError(RuntimeError):
    """Raised when a preview is stale or a commit cannot be completed safely."""


@dataclass(frozen=True)
class _PreparedPromotion:
    preview: PromotionPreview
    record: KnowledgeRecord


class KnowledgePromotionService:
    """Deprecated Phase 5.23 implementation retained for import compatibility.

    The HTTP compatibility endpoints return 410 and this service also rejects
    direct use.  KnowledgeDraftPromotionService is the sole writable path.
    """

    def __init__(
        self,
        authoring: KnowledgeAuthoringService,
        registry: KnowledgeRegistry,
        audit_log: JsonlPromotionLog,
    ) -> None:
        self.authoring = authoring
        self.registry = registry
        self.audit_log = audit_log
        self._pending: dict[str, _PreparedPromotion] = {}

    def preview(self, draft_id: str, *, actor: str = "knowledge_author") -> PromotionPreview:
        raise PromotionError(
            "Authoring Draftから直接Promotionできません。Knowledge Draftを使用してください。"
        )

    def _deprecated_preview_reference(
        self, draft_id: str, *, actor: str = "knowledge_author"
    ) -> PromotionPreview:
        """Historical implementation kept temporarily to make migration reviewable."""

        prepared = self._prepare(draft_id)
        self._pending[prepared.preview.preview_id] = prepared
        self._log_preview(prepared.preview, actor)
        return prepared.preview

    def commit(self, request: CommitPromotionRequest) -> PromotionResult:
        raise PromotionError(
            "Authoring Draft用PromotionはDeprecatedです。Knowledge Draftを使用してください。"
        )

    def _deprecated_commit_reference(
        self, request: CommitPromotionRequest
    ) -> PromotionResult:
        """Historical implementation kept temporarily to make migration reviewable."""

        prepared = self._pending.get(request.preview_id)
        if prepared is None:
            raise PromotionError("Promotion Previewが見つかりません。再度Previewしてください。")
        preview = prepared.preview
        try:
            current = self._prepare(preview.draft_id)
            if current.preview.draft_fingerprint != preview.draft_fingerprint:
                raise PromotionError("下書きがPreview後に変更されました。再度Previewしてください。")
            if current.preview.registry_fingerprint != preview.registry_fingerprint:
                raise PromotionError(
                    "RegistryがPreview後に変更されました。再度Previewしてください。"
                )
            if current.preview.knowledge_fingerprint != preview.knowledge_fingerprint:
                raise PromotionError("正式KnowledgeのFingerprintが一致しません。")
            if not preview.validation.promotion_allowed:
                raise PromotionError("Promotion Validationに失敗しています。")

            reconciliation = self.registry.reconcile(
                prepared.record,
                actor=request.actor,
                note=request.comment or f"Authoring Draft {preview.draft_id}からPromotion",
            )
            view = reconciliation.view
            if view.knowledge.status != RegistryStatus.DRAFT:
                raise PromotionError("Promotion後のApproval Stateがdraftではありません。")
            if view.knowledge.knowledge_version != preview.target_version:
                raise PromotionError("Promotion後のKnowledge VersionがPreviewと一致しません。")

            warnings: list[str] = []
            draft_state = AuthoringDraftState.ACTIVE
            if request.draft_disposition == DraftDisposition.ARCHIVE:
                try:
                    draft_state = self.authoring.archive(preview.draft_id).lifecycle_state
                except Exception:  # Registry commit must not be reported as rolled back.
                    warnings.append(
                        "Registry保存は成功しましたが、DraftをArchivedへ変更できませんでした。"
                    )

            result = PromotionResult(
                promotion_id=f"prm_{uuid4().hex[:16]}",
                preview_id=preview.preview_id,
                draft_id=preview.draft_id,
                promoted_at=datetime.now(UTC),
                operation=preview.operation,
                registry_key=view.knowledge.registry_key,
                knowledge_id=view.knowledge.knowledge_id,
                knowledge_version=view.knowledge.knowledge_version,
                draft_disposition_requested=request.draft_disposition,
                draft_lifecycle_state=draft_state.value,
                fingerprint=_fingerprint(reconciliation.record.model_dump(mode="json")),
                warnings=warnings,
            )
            self.audit_log.append(
                PromotionLogEvent(
                    event_id=f"plg_{uuid4().hex[:16]}",
                    occurred_at=result.promoted_at,
                    event_type="promotion",
                    status="success",
                    draft_id=preview.draft_id,
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
                    draft_id=preview.draft_id,
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

    def _prepare(self, draft_id: str) -> _PreparedPromotion:
        draft = self.authoring.get(draft_id)
        authoring_validation = self.authoring.validate(draft)
        snapshot = self.registry.snapshot()
        draft_raw = draft.knowledge.model_dump(mode="json")
        registry_key = registry_key_for_record(draft_raw)
        existing = next(
            (entry for entry in snapshot.knowledge if entry.registry_key == registry_key),
            None,
        )
        operation = (
            PromotionOperation.VERSION_UPDATE if existing else PromotionOperation.CREATE
        )
        target_knowledge_id = (
            existing.knowledge_id if existing else draft.knowledge.knowledge_id
        )
        target_version = existing.knowledge_version + 1 if existing else 1
        existing_record = self.registry.record(existing.knowledge_id) if existing else None

        mapped_raw, mapped_ids = self._map_formal_record(
            draft,
            knowledge_id=target_knowledge_id,
            content_revision=target_version,
        )
        checks: list[PromotionCheck] = []

        schema_valid = True
        try:
            record = validate_knowledge_record(mapped_raw)
        except (KnowledgeSchemaError, ValidationError, ValueError) as error:
            schema_valid = False
            record = draft.knowledge.model_copy(
                update={
                    "knowledge_id": target_knowledge_id,
                    "content_revision": target_version,
                }
            )
            checks.append(_check("schema", False, f"Knowledge Schema: {error}"))
        else:
            checks.append(_check("schema", True, "Knowledge Schema 1.0に適合しています。"))

        allowed_slots = _CATEGORY_SLOTS[draft.metadata.category]
        invalid_slots = [
            claim.claim_id
            for claim in draft.claims
            if claim.semantic_slot not in allowed_slots
        ]
        category_mismatch = bool(
            existing_record is not None
            and existing_record.classification.term_type != draft.metadata.category.value
        )
        category_valid = not invalid_slots and not category_mismatch
        checks.append(
            _check(
                "category",
                category_valid,
                "すべてのClaimがCategory対応の保存先を持ちます。"
                if category_valid
                else (
                    "既存RegistryとCategoryが一致しません。"
                    if category_mismatch
                    else "保存先が未指定またはCategory非対応のClaimがあります: "
                    + ", ".join(invalid_slots)
                ),
            )
        )

        claim_ids = {claim.claim_id for claim in draft.claims}
        linked_claim_ids = {
            claim_id
            for reference in draft.references
            for claim_id in reference.supported_claim_ids
        }
        unsupported_claims = sorted(claim_ids - linked_claim_ids)
        claim_valid = bool(draft.claims) and not invalid_slots and not unsupported_claims
        checks.append(
            _check(
                "claims",
                claim_valid,
                "Claim ID、保存先、出典接続が有効です。"
                if claim_valid
                else (
                    "Claimが必要です。" if not draft.claims else
                    "Referenceで支えられていないClaimがあります: "
                    + ", ".join(unsupported_claims or invalid_slots)
                ),
            )
        )

        bad_references = [
            reference.source_id
            for reference in draft.references
            if reference.source_priority_rank is None
            or not reference.supported_claim_ids
            or not set(reference.supported_claim_ids).issubset(mapped_ids)
        ]
        reference_valid = bool(draft.references) and not bad_references
        checks.append(
            _check(
                "references",
                reference_valid,
                "Reference IDとClaim対応が有効です。"
                if reference_valid
                else (
                    "Referenceが必要です。" if not draft.references else
                    "優先順位未指定、未接続、または無効なReferenceがあります: "
                    + ", ".join(bad_references)
                ),
            )
        )

        id_collision = next(
            (
                entry
                for entry in snapshot.knowledge
                if entry.knowledge_id == draft.knowledge.knowledge_id
                and entry.registry_key != registry_key
            ),
            None,
        )
        incoming_names = {
            _normalized(draft.metadata.title),
            *(_normalized(alias) for alias in draft.metadata.aliases),
        }
        alias_collisions = [
            binding.alias
            for binding in snapshot.alias_bindings
            if _normalized(binding.alias) in incoming_names
            and binding.target != registry_key
        ]
        no_claim_change = False
        if existing is not None and schema_valid:
            incoming = {
                item.claim_key: item.assertion
                for item in extract_claim_candidates(
                    record.model_dump(mode="json"), registry_key
                )
            }
            current = {
                item.claim_key: item.assertion
                for item in snapshot.claims
                if item.knowledge_id == existing.knowledge_id
                and item.status != RegistryStatus.DEPRECATED
                and not item.is_deleted
            }
            no_claim_change = not any(
                current.get(key) != assertion for key, assertion in incoming.items()
            )
        registry_valid = id_collision is None and not alias_collisions and not no_claim_change
        registry_message = "Registry KeyとKnowledge IDの競合はありません。"
        if id_collision is not None:
            registry_message = "Knowledge IDが別のRegistry Keyで使用されています。"
        elif alias_collisions:
            registry_message = "Aliasが別Knowledgeで使用されています: " + ", ".join(
                alias_collisions
            )
        elif no_claim_change:
            registry_message = (
                "既存Knowledgeに新しいClaim変更がありません。"
                "根拠だけの版更新は現在のRegistry契約では安全に行えません。"
            )
        checks.append(_check("registry", registry_valid, registry_message))

        knowledge_id_valid = bool(
            re.fullmatch(r"knw_[a-z0-9][a-z0-9_-]{7,63}", target_knowledge_id)
        )
        checks.append(
            _check(
                "knowledge_id",
                knowledge_id_valid,
                "Knowledge ID形式は有効です。"
                if knowledge_id_valid
                else "Knowledge ID形式が無効です。",
            )
        )

        knowledge_fingerprint = _fingerprint(record.model_dump(mode="json"))
        fingerprint_valid = knowledge_fingerprint == _fingerprint(
            record.model_dump(mode="json")
        ) and bool(re.fullmatch(r"[0-9a-f]{64}", knowledge_fingerprint))
        checks.append(
            _check(
                "fingerprint",
                fingerprint_valid,
                "Fingerprintは決定的に再計算できました。"
                if fingerprint_valid
                else "Fingerprint検証に失敗しました。",
            )
        )

        lifecycle_valid = draft.lifecycle_state == AuthoringDraftState.ACTIVE
        checks.append(
            _check(
                "draft_state",
                lifecycle_valid,
                "Active Draftです。"
                if lifecycle_valid
                else "Archived Draftは再Promotionできません。",
            )
        )

        promotion_allowed = all(
            (
                schema_valid,
                category_valid,
                claim_valid,
                reference_valid,
                registry_valid,
                fingerprint_valid,
                knowledge_id_valid,
                lifecycle_valid,
                authoring_validation.save_allowed,
            )
        )
        validation = PromotionValidationReport(
            schema_valid=schema_valid,
            category_valid=category_valid,
            claim_valid=claim_valid,
            reference_valid=reference_valid,
            registry_valid=registry_valid,
            fingerprint_valid=fingerprint_valid,
            knowledge_id_valid=knowledge_id_valid,
            promotion_allowed=promotion_allowed,
            checks=checks,
        )
        preview = PromotionPreview(
            preview_id=f"ppv_{uuid4().hex[:16]}",
            draft_id=draft.draft_id,
            created_at=datetime.now(UTC),
            knowledge_name=draft.metadata.title,
            category=draft.metadata.category.value,
            claim_count=len(draft.claims),
            reference_count=len(draft.references),
            completeness_score=authoring_validation.completeness_score,
            validation=validation,
            registry_key=registry_key,
            operation=operation,
            target_knowledge_id=target_knowledge_id,
            target_version=target_version,
            draft_fingerprint=_fingerprint(draft.model_dump(mode="json")),
            registry_fingerprint=_fingerprint(snapshot.model_dump(mode="json")),
            knowledge_fingerprint=knowledge_fingerprint,
        )
        return _PreparedPromotion(preview=preview, record=record)

    @staticmethod
    def _map_formal_record(
        draft: KnowledgeAuthoringDraft,
        *,
        knowledge_id: str,
        content_revision: int,
    ) -> tuple[dict[str, Any], set[str]]:
        raw = draft.knowledge.model_dump(mode="json")
        raw["knowledge_id"] = knowledge_id
        raw["content_revision"] = content_revision
        mapped_ids: set[str] = set()
        for claim in draft.claims:
            path = _SLOT_PATHS.get((draft.metadata.category, claim.semantic_slot))
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

    def _log_preview(self, preview: PromotionPreview, actor: str) -> None:
        failed = [check.code for check in preview.validation.checks if not check.passed]
        self.audit_log.append(
            PromotionLogEvent(
                event_id=f"plg_{uuid4().hex[:16]}",
                occurred_at=preview.created_at,
                event_type="preview",
                status="ready" if preview.validation.promotion_allowed else "blocked",
                draft_id=preview.draft_id,
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
