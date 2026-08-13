"""Human-only medical review orchestration and derived approval eligibility."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from knowledge_contracts.registry_v10 import (
    ClaimRegistryEntry,
    RegistryKnowledgeView,
    RegistryStatus,
)
from knowledge_contracts.v10 import (
    EvidenceReference,
    KnowledgeRecord,
    evaluate_knowledge_completeness,
    validate_knowledge_record,
)

from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.medical_review_checklist import (
    CHECKLIST_ID,
    CHECKLIST_VERSION,
    EVIDENCE_POLICY_VERSION,
    checklist_by_id,
    checklist_for_category,
)
from knowledge_workbench.medical_review_models import (
    ApprovalEligibilityCheck,
    ChecklistItemReview,
    ChecklistResultValue,
    ChecklistSeverity,
    ClaimReview,
    ClaimReviewDecision,
    CreateMedicalReviewRequest,
    EvidenceAssessment,
    EvidenceSupport,
    KnowledgeReviewSnapshot,
    MedicalApprovalEligibility,
    MedicalReviewKnowledgeContext,
    MedicalReviewQueueEntry,
    MedicalReviewRecord,
    ReviewDecision,
    ReviewerProfile,
    ReviewValidity,
)
from knowledge_workbench.medical_review_registry import (
    MedicalReviewRegistry,
    MedicalReviewRegistryError,
    ReviewerRegistry,
)


class MedicalReviewServiceError(RuntimeError):
    """A human review request cannot be safely recorded."""


class MedicalReviewService:
    """Build immutable review records without modifying medical Knowledge."""

    def __init__(
        self,
        knowledge_registry: KnowledgeRegistry,
        review_registry: MedicalReviewRegistry,
        reviewer_registry: ReviewerRegistry,
        *,
        checklist_version: str = CHECKLIST_VERSION,
        evidence_policy_version: str = EVIDENCE_POLICY_VERSION,
        allow_fixture_identity_for_approval: bool = False,
    ) -> None:
        self.knowledge_registry = knowledge_registry
        self.review_registry = review_registry
        self.reviewer_registry = reviewer_registry
        self.checklist_version = checklist_version
        self.evidence_policy_version = evidence_policy_version
        self.allow_fixture_identity_for_approval = allow_fixture_identity_for_approval

    def create_review(self, request: CreateMedicalReviewRequest) -> MedicalReviewRecord:
        now = _utc_now()
        valid_until = _as_utc(request.valid_until)
        if valid_until <= now:
            raise MedicalReviewServiceError("Review期限は現在より後を指定してください。")
        record, view, active_claims = self._current(request.knowledge_id)
        reviewer = self._require_reviewer(request, record)
        claim_inputs = {item.claim_id: item for item in request.claim_reviews}
        if len(claim_inputs) != len(request.claim_reviews):
            raise MedicalReviewServiceError("Claim Reviewのclaim_idが重複しています。")
        unknown_claims = sorted(set(claim_inputs) - {item.claim_id for item in active_claims})
        if unknown_claims:
            raise MedicalReviewServiceError(
                "現行active Claimではありません: " + ", ".join(unknown_claims)
            )

        evidence_by_id = {item.source_id: item for item in record.evidence}
        claim_reviews = [
            self._build_claim_review(
                claim,
                claim_inputs[claim.claim_id],
                evidence_by_id,
                reviewer,
                now,
            )
            for claim in active_claims
            if claim.claim_id in claim_inputs
        ]
        checklist_catalog = checklist_by_id(record.classification.term_type)
        checklist_inputs = {item.item_id: item for item in request.checklist_results}
        if len(checklist_inputs) != len(request.checklist_results):
            raise MedicalReviewServiceError("Checklist item_idが重複しています。")
        unknown_items = sorted(set(checklist_inputs) - set(checklist_catalog))
        if unknown_items:
            raise MedicalReviewServiceError(
                "対象CategoryのChecklistではありません: " + ", ".join(unknown_items)
            )
        checklist_results = [
            ChecklistItemReview(
                item_id=item_id,
                severity=checklist_catalog[item_id].severity,
                result=value.result,
                reason=value.reason,
                reviewed_by=reviewer.reviewer_id,
                reviewed_at=now,
            )
            for item_id, value in checklist_inputs.items()
        ]
        completeness = evaluate_knowledge_completeness(record)
        knowledge_review = KnowledgeReviewSnapshot(
            category=record.classification.term_type,
            definition_present=_definition_present(active_claims),
            schema_valid=True,
            completeness_score=completeness.score,
            completeness_threshold_met=completeness.is_complete_for_review,
            completeness_profile_id=completeness.profile_id,
            active_claim_count=len(active_claims),
            reviewed_claim_count=len(claim_reviews),
            approved_claim_count=sum(
                item.decision == ClaimReviewDecision.APPROVED for item in claim_reviews
            ),
            evidence_supported_claim_count=sum(
                _claim_has_direct_support(item) for item in claim_reviews
            ),
        )
        review_version = self.review_registry.next_version(request.knowledge_id)
        values: dict[str, Any] = {
            "review_id": f"mrv_{uuid4().hex[:20]}",
            "review_version": review_version,
            "knowledge_id": request.knowledge_id,
            "knowledge_version": view.knowledge.knowledge_version,
            "knowledge_fingerprint": _fingerprint(record.model_dump(mode="json")),
            "reviewer_id": reviewer.reviewer_id,
            "reviewer_role": request.reviewer_role,
            "review_scope": request.review_scope,
            "checklist_id": CHECKLIST_ID,
            "checklist_version": self.checklist_version,
            "evidence_policy_version": self.evidence_policy_version,
            "claim_reviews": claim_reviews,
            "checklist_results": checklist_results,
            "knowledge_review": knowledge_review,
            "decision": request.decision,
            "comments": request.comments,
            "reviewed_at": now,
            "valid_until": valid_until,
            "record_fingerprint": "pending",
        }
        values["record_fingerprint"] = _fingerprint(
            {key: value for key, value in _jsonable(values).items() if key != "record_fingerprint"}
        )
        review = MedicalReviewRecord.model_validate(values)
        try:
            self.review_registry.append(review)
        except MedicalReviewRegistryError as error:
            raise MedicalReviewServiceError(str(error)) from error
        return review

    def queue(self) -> list[MedicalReviewQueueEntry]:
        result: list[MedicalReviewQueueEntry] = []
        for entry in self.knowledge_registry.snapshot().knowledge:
            record = self.knowledge_registry.record(entry.knowledge_id)
            if record is not None:
                result.append(self._queue_entry(record))
        return sorted(result, key=lambda item: (item.category, item.knowledge_name))

    def knowledge_context(self, knowledge_id: str) -> MedicalReviewKnowledgeContext:
        record, view, active_claims = self._current(knowledge_id)
        evidence_by_claim = _evidence_by_claim(record.evidence)
        claims: list[dict[str, object]] = []
        for claim in active_claims:
            claims.append(
                {
                    "claim_id": claim.claim_id,
                    "claim_key": claim.claim_key,
                    "claim_version": claim.claim_version,
                    "assertion": claim.assertion,
                    "field_path": claim.field_path,
                    "fingerprint": _claim_fingerprint(claim),
                    "evidence": [
                        item.model_dump(mode="json")
                        for item in evidence_by_claim.get(claim.claim_id, [])
                    ],
                }
            )
        latest = self.review_registry.latest_for_knowledge(knowledge_id)
        return MedicalReviewKnowledgeContext(
            queue_entry=self._queue_entry(record),
            claims=claims,
            checklist=checklist_for_category(record.classification.term_type),
            reviewers=[
                item
                for item in self.reviewer_registry.list_active()
                if record.classification.term_type in item.specialty_categories
            ],
            latest_review=latest,
            eligibility=self.evaluate_eligibility(knowledge_id, latest),
        )

    def evaluate_eligibility(
        self,
        knowledge_id: str,
        review: MedicalReviewRecord | None = None,
        *,
        now: datetime | None = None,
    ) -> MedicalApprovalEligibility:
        evaluated_at = _as_utc(now or _utc_now())
        record, view, active_claims = self._current(knowledge_id)
        selected = review or self.review_registry.latest_for_knowledge(knowledge_id)
        if selected is None:
            return MedicalApprovalEligibility(
                knowledge_id=knowledge_id,
                review_id=None,
                review_version=None,
                validity=None,
                eligible_for_final_approval=False,
                reasons=["review_missing"],
                checks=[
                    ApprovalEligibilityCheck(
                        code="review_exists", passed=False, message="Medical Reviewがありません。"
                    )
                ],
                evaluated_at=evaluated_at,
            )

        latest = self.review_registry.latest_for_knowledge(knowledge_id)
        latest_ok = latest is not None and latest.review_id == selected.review_id
        checks: list[ApprovalEligibilityCheck] = []

        def check(code: str, passed: bool, message: str) -> None:
            checks.append(ApprovalEligibilityCheck(code=code, passed=passed, message=message))

        current_knowledge_fingerprint = _fingerprint(record.model_dump(mode="json"))
        knowledge_version_ok = selected.knowledge_version == view.knowledge.knowledge_version
        knowledge_fingerprint_ok = selected.knowledge_fingerprint == current_knowledge_fingerprint
        checklist_version_ok = selected.checklist_version == self.checklist_version
        evidence_policy_ok = selected.evidence_policy_version == self.evidence_policy_version
        deadline_ok = selected.valid_until > evaluated_at
        decision_ok = selected.decision == ReviewDecision.APPROVED
        schema_ok = selected.knowledge_review.schema_valid
        completeness = evaluate_knowledge_completeness(record)
        completeness_ok = completeness.is_complete_for_review
        reviewer = self.reviewer_registry.get(selected.reviewer_id)
        reviewer_ok = (
            reviewer is not None
            and reviewer.active
            and selected.reviewer_role in reviewer.roles
            and record.classification.term_type in reviewer.specialty_categories
            and (
                reviewer.identity_assurance == "verified_identity_provider"
                or self.allow_fixture_identity_for_approval
            )
        )

        current_claims = {item.claim_id: item for item in active_claims}
        reviewed_claims = {item.claim_id: item for item in selected.claim_reviews}
        claim_set_ok = set(current_claims) == set(reviewed_claims)
        claim_versions_ok = claim_set_ok and all(
            reviewed_claims[claim_id].claim_version == claim.claim_version
            and reviewed_claims[claim_id].claim_fingerprint == _claim_fingerprint(claim)
            for claim_id, claim in current_claims.items()
        )
        claims_approved = claim_set_ok and all(
            item.decision == ClaimReviewDecision.APPROVED for item in reviewed_claims.values()
        )
        current_evidence = {item.source_id: item for item in record.evidence}
        evidence_ok = claim_set_ok and all(
            _review_evidence_is_current_and_supportive(
                reviewed_claims[claim_id], current_evidence, claim_id
            )
            for claim_id in current_claims
        )
        catalog = checklist_by_id(record.classification.term_type)
        results = {item.item_id: item for item in selected.checklist_results}
        checklist_ok = all(
            item.severity == ChecklistSeverity.ADVISORY
            or (
                item.item_id in results
                and results[item.item_id].result == ChecklistResultValue.PASS
            )
            for item in catalog.values()
        )

        check("schema_valid", schema_ok, "現行Knowledge Schemaの検証結果")
        check("completeness_threshold", completeness_ok, "Category Completeness基準")
        check("latest_review", latest_ok, "最新Review Version")
        check("knowledge_version", knowledge_version_ok, "Knowledge Version一致")
        check("knowledge_fingerprint", knowledge_fingerprint_ok, "Knowledge Fingerprint一致")
        check("claim_set", claim_set_ok, "全active ClaimをReview")
        check("claim_versions", claim_versions_ok, "Claim Version/Fingerprint一致")
        check("claims_approved", claims_approved, "全active Claimがapproved")
        check("evidence_assessed", evidence_ok, "必須Evidenceを直接支持として確認")
        check("checklist_complete", checklist_ok, "blocker/required Checklistがpass")
        check("checklist_version", checklist_version_ok, "Checklist Version一致")
        check("evidence_policy_version", evidence_policy_ok, "Evidence Policy Version一致")
        check("reviewer_identity", reviewer_ok, "Reviewer RegistryのID・Role・専門領域一致")
        check("review_deadline", deadline_ok, "Review期限内")
        check("final_decision", decision_ok, "Final Decisionがapproved")

        stale_codes = {
            "latest_review",
            "knowledge_version",
            "knowledge_fingerprint",
            "claim_set",
            "claim_versions",
            "checklist_version",
            "evidence_policy_version",
        }
        failed = [item for item in checks if not item.passed]
        if not deadline_ok:
            validity = ReviewValidity.EXPIRED
        elif any(item.code in stale_codes for item in failed):
            validity = ReviewValidity.STALE
        else:
            validity = ReviewValidity.CURRENT
        return MedicalApprovalEligibility(
            knowledge_id=knowledge_id,
            review_id=selected.review_id,
            review_version=selected.review_version,
            validity=validity,
            eligible_for_final_approval=not failed,
            reasons=[item.code for item in failed],
            checks=checks,
            evaluated_at=evaluated_at,
        )

    def reviews_for_knowledge(self, knowledge_id: str) -> list[MedicalReviewRecord]:
        self._current(knowledge_id)
        return self.review_registry.list_for_knowledge(knowledge_id)

    def _queue_entry(self, record: KnowledgeRecord) -> MedicalReviewQueueEntry:
        view = self.knowledge_registry.view(record.knowledge_id)
        active_claims = _active_claims(view.claims)
        latest = self.review_registry.latest_for_knowledge(record.knowledge_id)
        reviewed = 0 if latest is None else len(latest.claim_reviews)
        evidence_by_claim = _evidence_by_claim(record.evidence)
        evidence_covered = sum(bool(evidence_by_claim.get(item.claim_id)) for item in active_claims)
        completeness = evaluate_knowledge_completeness(record)
        eligibility = self.evaluate_eligibility(record.knowledge_id, latest)
        claim_count = len(active_claims)
        return MedicalReviewQueueEntry(
            knowledge_id=record.knowledge_id,
            knowledge_name=record.term.canonical_name,
            category=record.classification.term_type,
            knowledge_version=view.knowledge.knowledge_version,
            review_version=0 if latest is None else latest.review_version,
            claim_count=claim_count,
            reviewed_claim_count=reviewed,
            unreviewed_claim_count=max(0, claim_count - reviewed),
            evidence_coverage=(round(evidence_covered * 100 / claim_count) if claim_count else 0),
            completeness=completeness.score,
            current_decision=None if latest is None else latest.decision,
            review_deadline=None if latest is None else latest.valid_until,
            review_validity=eligibility.validity,
            eligible_for_final_approval=eligibility.eligible_for_final_approval,
        )

    def _current(
        self, knowledge_id: str
    ) -> tuple[KnowledgeRecord, RegistryKnowledgeView, list[ClaimRegistryEntry]]:
        record = self.knowledge_registry.record(knowledge_id)
        if record is None:
            raise MedicalReviewServiceError(f"Knowledgeが見つかりません: {knowledge_id}")
        validate_knowledge_record(record)
        view = self.knowledge_registry.view(knowledge_id)
        return record, view, _active_claims(view.claims)

    def _require_reviewer(
        self,
        request: CreateMedicalReviewRequest,
        record: KnowledgeRecord,
    ) -> ReviewerProfile:
        reviewer = self.reviewer_registry.get(request.reviewer_id)
        if reviewer is None or not reviewer.active:
            raise MedicalReviewServiceError("Reviewer Registryに有効なreviewer_idがありません。")
        if request.reviewer_role not in reviewer.roles:
            raise MedicalReviewServiceError("Reviewer RoleがReviewer Registryと一致しません。")
        if record.classification.term_type not in reviewer.specialty_categories:
            raise MedicalReviewServiceError("Reviewerの専門Category範囲外です。")
        return reviewer

    def _build_claim_review(
        self,
        claim: ClaimRegistryEntry,
        request: Any,
        evidence_by_id: dict[str, EvidenceReference],
        reviewer: ReviewerProfile,
        now: datetime,
    ) -> ClaimReview:
        linked = {
            item.source_id: item
            for item in evidence_by_id.values()
            if claim.claim_id in item.supported_claim_ids
        }
        assessment_ids = [item.evidence_id for item in request.evidence_assessments]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise MedicalReviewServiceError(
                f"Evidence Assessmentが重複しています: {claim.claim_id}"
            )
        unknown = sorted(set(assessment_ids) - set(linked))
        if unknown:
            raise MedicalReviewServiceError(
                f"Claimに紐付かないEvidenceです: {claim.claim_id} / {', '.join(unknown)}"
            )
        assessments = []
        for value in request.evidence_assessments:
            evidence = linked[value.evidence_id]
            assessments.append(
                EvidenceAssessment(
                    assessment_id=f"eva_{uuid4().hex[:20]}",
                    evidence_id=evidence.source_id,
                    evidence_fingerprint=_evidence_fingerprint(evidence),
                    exists_confirmed=value.exists_confirmed,
                    current_confirmed=value.current_confirmed,
                    directly_supports=value.directly_supports,
                    evidence_level=value.evidence_level,
                    evidence_source=evidence.issuing_organization or evidence.title,
                    support=value.support,
                    locator=value.locator,
                    pmid=evidence.pmid,
                    doi=evidence.doi,
                    reviewed_by=reviewer.reviewer_id,
                    reviewed_at=now,
                    comment=value.comment,
                )
            )
        return ClaimReview(
            claim_id=claim.claim_id,
            claim_key=claim.claim_key,
            claim_version=claim.claim_version,
            claim_fingerprint=_claim_fingerprint(claim),
            evidence_ids=sorted(linked),
            evidence_assessments=assessments,
            decision=request.decision,
            comment=request.comment,
            reviewed_by=reviewer.reviewer_id,
            reviewed_at=now,
        )


def _active_claims(claims: list[ClaimRegistryEntry]) -> list[ClaimRegistryEntry]:
    return sorted(
        (
            item
            for item in claims
            if item.status != RegistryStatus.DEPRECATED and not item.is_deleted
        ),
        key=lambda item: item.field_path,
    )


def _definition_present(claims: list[ClaimRegistryEntry]) -> bool:
    return any(
        "definition" in item.field_path.lower() and bool(item.assertion.strip())
        for item in claims
    )


def _evidence_by_claim(
    evidence: list[EvidenceReference],
) -> dict[str, list[EvidenceReference]]:
    result: dict[str, list[EvidenceReference]] = {}
    for item in evidence:
        for claim_id in item.supported_claim_ids:
            result.setdefault(claim_id, []).append(item)
    return result


def _claim_has_direct_support(review: ClaimReview) -> bool:
    return any(
        item.exists_confirmed
        and item.current_confirmed
        and item.directly_supports
        and item.support == EvidenceSupport.SUPPORTS
        for item in review.evidence_assessments
    )


def _review_evidence_is_current_and_supportive(
    review: ClaimReview,
    current_evidence: dict[str, EvidenceReference],
    claim_id: str,
) -> bool:
    for assessment in review.evidence_assessments:
        evidence = current_evidence.get(assessment.evidence_id)
        if evidence is None or claim_id not in evidence.supported_claim_ids:
            continue
        if assessment.evidence_fingerprint != _evidence_fingerprint(evidence):
            continue
        if (
            assessment.exists_confirmed
            and assessment.current_confirmed
            and assessment.directly_supports
            and assessment.support == EvidenceSupport.SUPPORTS
        ):
            return True
    return False


def _claim_fingerprint(claim: ClaimRegistryEntry) -> str:
    return _fingerprint(
        {
            "claim_id": claim.claim_id,
            "claim_key": claim.claim_key,
            "claim_version": claim.claim_version,
            "assertion": claim.assertion,
            "fact_payload": claim.fact_payload,
        }
    )


def _evidence_fingerprint(evidence: EvidenceReference) -> str:
    return _fingerprint(evidence.model_dump(mode="json"))


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _jsonable(value: object) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
