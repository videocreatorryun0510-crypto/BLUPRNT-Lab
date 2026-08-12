"""Evidence-gated Claim generation, validation, review, and Draft adoption."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import ValidationError

from knowledge_workbench.authoring_models import (
    AuthoringClaim,
    AuthoringSemanticSlot,
    CreateAuthoringDraftRequest,
    KnowledgeAuthoringDraft,
)
from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.claim_candidate_models import (
    ClaimAdapterResult,
    ClaimCandidate,
    ClaimCandidateSet,
    ClaimCandidateValidationReport,
    ClaimDuplicateAssessment,
    ClaimDuplicateClassification,
    ClaimDuplicateMatch,
    ClaimGenerationAuditEntry,
    ClaimGenerationErrorCode,
    ClaimGenerationKpi,
    ClaimGenerationRequest,
    ClaimSupportLevel,
    ClaimSupportScopeType,
    ClaimValidationIssue,
    CreateGroundedAuthoringDraftRequest,
    FormalEvidenceSelectionSet,
    GeneratedClaimDraft,
    GroundedAuthoringDraftResult,
    HumanClaimDecision,
    HumanClaimReviewEntry,
    HumanClaimReviewRequest,
    claim_candidate_set_fingerprint,
    generated_claim_fingerprint,
)
from knowledge_workbench.claim_generation_interfaces import (
    ClaimGenerationAdapter,
    ClaimGenerationAdapterError,
)
from knowledge_workbench.knowledge_pipeline_builders import AuthoringReferenceBuilder
from knowledge_workbench.knowledge_pipeline_models import (
    ClaimBuildResult,
    PipelineClaim,
    PipelineClaimType,
)
from knowledge_workbench.knowledge_registry import KnowledgeRegistry
from knowledge_workbench.pubmed_service import (
    PubMedEvidenceServiceError,
    PubMedFormalEvidenceService,
)


class ClaimGenerationServiceError(RuntimeError):
    def __init__(
        self,
        code: ClaimGenerationErrorCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code


class JsonlClaimGenerationAuditLog:
    """Metadata-only generation audit without Evidence or Claim bodies."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: ClaimGenerationAuditEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim Generation Auditを保存できません。",
            ) from error

    def list(self, *, limit: int = 100) -> list[ClaimGenerationAuditEntry]:
        if not self.path.exists():
            return []
        try:
            entries = [
                ClaimGenerationAuditEntry.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValidationError) as error:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim Generation Auditを読み込めません。",
            ) from error
        return list(reversed(entries[-limit:]))


class JsonlHumanClaimReviewRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: HumanClaimReviewEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Human Claim Reviewを保存できません。",
            ) from error

    def list(self, *, limit: int = 500) -> list[HumanClaimReviewEntry]:
        if not self.path.exists():
            return []
        try:
            entries = [
                HumanClaimReviewEntry.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValidationError) as error:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Human Claim Reviewを読み込めません。",
            ) from error
        return list(reversed(entries[-limit:]))

    def latest_for_set(self, candidate_set_id: str) -> dict[str, HumanClaimReviewEntry]:
        latest: dict[str, HumanClaimReviewEntry] = {}
        for entry in self.list(limit=5000):
            is_target_set = entry.candidate_set_id == candidate_set_id
            if is_target_set and entry.candidate_claim_id not in latest:
                latest[entry.candidate_claim_id] = entry
        return latest


class ClaimCandidateValidator:
    validator_version = "1.0"

    def validate(
        self,
        candidates: tuple[ClaimCandidate, ...],
        *,
        accepted_evidence: dict[str, str],
        evidence_metadata: dict[str, tuple[str | None, str | None]],
    ) -> ClaimCandidateValidationReport:
        issues: list[ClaimValidationIssue] = []
        candidate_ids = [item.candidate_claim_id for item in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            issues.append(
                ClaimValidationIssue(
                    code="candidate_id_duplicate",
                    severity="error",
                    path="candidates.candidate_claim_id",
                    message="Candidate IDが重複しています。",
                )
            )
        known_ids = set(accepted_evidence)
        evidence_ids_valid = True
        locators_valid = True
        fingerprints_valid = True
        provider_neutral = True
        scope_by_level = {
            ClaimSupportLevel.DIRECT: ClaimSupportScopeType.FULL_CLAIM,
            ClaimSupportLevel.PARTIAL: ClaimSupportScopeType.CLAIM_PART,
            ClaimSupportLevel.INDIRECT: ClaimSupportScopeType.CONTEXT_ONLY,
            ClaimSupportLevel.UNSUPPORTED: ClaimSupportScopeType.NO_SUPPORT,
            ClaimSupportLevel.CONFLICTING: ClaimSupportScopeType.CONFLICTING_EVIDENCE,
        }
        for candidate in candidates:
            forbidden_keys = _provider_specific_keys(
                candidate.model_dump(mode="json")
            )
            if forbidden_keys:
                provider_neutral = False
                issues.append(
                    ClaimValidationIssue(
                        code="provider_specific_contract_field",
                        severity="error",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="candidate",
                        message=(
                            "Provider固有情報をClaim Candidate Contractで検出しました: "
                            + ", ".join(sorted(forbidden_keys))
                        ),
                    )
                )
            unknown = sorted(set(candidate.supporting_evidence_ids) - known_ids)
            if unknown:
                evidence_ids_valid = False
                issues.append(
                    ClaimValidationIssue(
                        code="evidence_id_hallucination",
                        severity="error",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="supporting_evidence_ids",
                        message="選択されていないEvidence IDを参照しています。",
                    )
                )
            if candidate.support_scope.scope_type is not scope_by_level[candidate.support_level]:
                issues.append(
                    ClaimValidationIssue(
                        code="support_scope_mismatch",
                        severity="error",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="support_scope.scope_type",
                        message="Support LevelとSupport Scopeが一致しません。",
                    )
                )
            for locator in candidate.source_locators:
                source = accepted_evidence.get(locator.evidence_id)
                expected_pmid, expected_doi = evidence_metadata.get(
                    locator.evidence_id,
                    (None, None),
                )
                if source is None or _normalized(locator.quote_excerpt) not in _normalized(source):
                    locators_valid = False
                    issues.append(
                        ClaimValidationIssue(
                            code="locator_mismatch",
                            severity="error",
                            candidate_claim_id=candidate.candidate_claim_id,
                            path="source_locators.quote_excerpt",
                            message="Evidence抜粋を選択済みEvidence内で確認できません。",
                        )
                    )
                if locator.pmid and locator.pmid != expected_pmid:
                    locators_valid = False
                    issues.append(
                        ClaimValidationIssue(
                            code="locator_pmid_mismatch",
                            severity="error",
                            candidate_claim_id=candidate.candidate_claim_id,
                            path="source_locators.pmid",
                            message="Source LocatorのPMIDがEvidenceと一致しません。",
                        )
                    )
                if locator.doi and _canonical_doi(locator.doi) != _canonical_doi(expected_doi):
                    locators_valid = False
                    issues.append(
                        ClaimValidationIssue(
                            code="locator_doi_mismatch",
                            severity="error",
                            candidate_claim_id=candidate.candidate_claim_id,
                            path="source_locators.doi",
                            message="Source LocatorのDOIがEvidenceと一致しません。",
                        )
                    )
            if candidate.candidate_fingerprint != generated_claim_fingerprint(
                candidate.knowledge_term,
                _as_generated(candidate),
            ):
                fingerprints_valid = False
                issues.append(
                    ClaimValidationIssue(
                        code="fingerprint_mismatch",
                        severity="error",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="candidate_fingerprint",
                        message="Candidate Fingerprintが一致しません。",
                    )
                )
            if candidate.support_level is ClaimSupportLevel.UNSUPPORTED:
                issues.append(
                    ClaimValidationIssue(
                        code="unsupported_claim_isolated",
                        severity="warning",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="support_level",
                        message="Unsupported ClaimはAuthoring Draftへ採用できません。",
                    )
                )
            if candidate.support_level is ClaimSupportLevel.CONFLICTING:
                issues.append(
                    ClaimValidationIssue(
                        code="conflicting_claim_requires_human_review",
                        severity="warning",
                        candidate_claim_id=candidate.candidate_claim_id,
                        path="support_assessment.conflicts",
                        message="Evidence間の相違を人が確認してください。自動解決しません。",
                    )
                )
        counts = Counter(item.support_level for item in candidates)
        error_exists = any(item.severity == "error" for item in issues)
        return ClaimCandidateValidationReport(
            schema_valid=True,
            evidence_ids_valid=evidence_ids_valid,
            accepted_evidence_only=evidence_ids_valid,
            locators_valid=locators_valid,
            fingerprints_valid=fingerprints_valid,
            provider_neutral=provider_neutral,
            candidate_count=len(candidates),
            direct_count=counts[ClaimSupportLevel.DIRECT],
            partial_count=counts[ClaimSupportLevel.PARTIAL],
            indirect_count=counts[ClaimSupportLevel.INDIRECT],
            unsupported_count=counts[ClaimSupportLevel.UNSUPPORTED],
            conflicting_count=counts[ClaimSupportLevel.CONFLICTING],
            authoring_eligible_count=counts[ClaimSupportLevel.DIRECT],
            validation_passed=not error_exists,
            issues=tuple(issues),
        )


class ClaimDuplicateDetector:
    detector_version = "1.0"
    possible_threshold = 0.86

    def __init__(self, registry: KnowledgeRegistry) -> None:
        self.registry = registry

    def assess(
        self,
        knowledge_term: str,
        candidate_id: str,
        claim_text: str,
        peers: list[tuple[str, str]],
    ) -> ClaimDuplicateAssessment:
        comparisons: list[tuple[str, str, Literal["candidate", "registry"]]] = [
            *((matched_id, matched_text, "candidate") for matched_id, matched_text in peers),
            *self._registry_claims(knowledge_term),
        ]
        matches: list[ClaimDuplicateMatch] = []
        for matched_id, matched_text, source in comparisons:
            if matched_id == candidate_id:
                continue
            similarity = _claim_similarity(claim_text, matched_text)
            if similarity == 1:
                classification: Literal[
                    "exact_duplicate", "possible_duplicate"
                ] = "exact_duplicate"
            elif similarity >= self.possible_threshold:
                classification = "possible_duplicate"
            else:
                continue
            matches.append(
                ClaimDuplicateMatch(
                    matched_id=matched_id,
                    matched_source=source,
                    classification=classification,
                    similarity=similarity,
                )
            )
        overall = (
            ClaimDuplicateClassification.EXACT
            if any(item.classification == "exact_duplicate" for item in matches)
            else ClaimDuplicateClassification.POSSIBLE
            if matches
            else ClaimDuplicateClassification.DISTINCT
        )
        return ClaimDuplicateAssessment(
            classification=overall,
            matches=tuple(matches),
        )

    def _registry_claims(
        self,
        knowledge_term: str,
    ) -> list[tuple[str, str, Literal["registry"]]]:
        normalized_term = _normalized(knowledge_term)
        snapshot = self.registry.snapshot()
        knowledge_ids = {
            item.knowledge_id
            for item in snapshot.knowledge
            if normalized_term
            in {_normalized(item.canonical_name), *(_normalized(alias) for alias in item.aliases)}
        }
        return [
            (item.claim_id, item.assertion, "registry")
            for item in snapshot.claims
            if item.knowledge_id in knowledge_ids and not item.is_deleted
        ]


class EvidenceGroundedClaimService:
    service_version = "1.0"

    def __init__(
        self,
        *,
        pubmed: PubMedFormalEvidenceService,
        adapter: ClaimGenerationAdapter,
        registry: KnowledgeRegistry,
        authoring: KnowledgeAuthoringService,
        generation_audit: JsonlClaimGenerationAuditLog,
        human_reviews: JsonlHumanClaimReviewRepository,
        validator: ClaimCandidateValidator | None = None,
    ) -> None:
        self.pubmed = pubmed
        self.adapter = adapter
        self.registry = registry
        self.authoring = authoring
        self.generation_audit = generation_audit
        self.human_reviews = human_reviews
        self.validator = validator or ClaimCandidateValidator()
        self.duplicates = ClaimDuplicateDetector(registry)
        self.references = AuthoringReferenceBuilder()
        self._pending: dict[str, ClaimCandidateSet] = {}

    def generate(
        self,
        *,
        knowledge_term: str,
        evidence_bundle_id: str,
        max_candidates: int = 10,
    ) -> ClaimCandidateSet:
        execution_id = f"cge_{uuid4().hex}"
        try:
            selection = self.pubmed.accepted_evidence_selection(
                evidence_bundle_id,
                knowledge_term=knowledge_term,
            )
        except PubMedEvidenceServiceError as error:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                str(error),
            ) from error
        request = ClaimGenerationRequest(
            evidence_selection=selection,
            max_candidates=max_candidates,
        )
        try:
            result = self.adapter.generate(request)
        except ClaimGenerationAdapterError as error:
            self._record_failure(execution_id, selection, error.code)
            raise ClaimGenerationServiceError(error.code, str(error)) from error
        generated_at = datetime.now(UTC)
        peer_values = [
            (
                _candidate_id(generated_claim_fingerprint(knowledge_term, item), index),
                item.claim_text,
            )
            for index, item in enumerate(result.response.candidates, start=1)
        ]
        try:
            candidates = tuple(
                self._candidate(
                    knowledge_term,
                    generated,
                    generated_at=generated_at,
                    generator_id=result.generator_id,
                    generator_version=result.generator_version,
                    ordinal=index,
                    peers=peer_values,
                )
                for index, generated in enumerate(
                    result.response.candidates,
                    start=1,
                )
            )
        except (ValidationError, ValueError) as error:
            self._record_failure(
                execution_id,
                selection,
                ClaimGenerationErrorCode.INVALID_RESPONSE,
            )
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.INVALID_RESPONSE,
                "Claim候補のContract整合性を確認できませんでした。",
            ) from error
        accepted_evidence = {
            item.evidence_id: item.abstract_or_snippet for item in selection.evidence
        }
        evidence_metadata = {
            item.evidence_id: (item.pmid, item.doi) for item in selection.evidence
        }
        validation = self.validator.validate(
            candidates,
            accepted_evidence=accepted_evidence,
            evidence_metadata=evidence_metadata,
        )
        if not validation.validation_passed:
            code = _validation_error_code(validation)
            self._record_result(
                execution_id,
                selection,
                result,
                validation,
                status="validation_failed",
                error_code=code,
            )
            raise ClaimGenerationServiceError(
                code,
                "Claim候補がEvidence Validationを通過しませんでした。",
            )
        count = len(candidates)
        pubmed_preview = self.pubmed.pending_preview(evidence_bundle_id)
        kpi = ClaimGenerationKpi(
            evidence_search_duration_ms=(
                pubmed_preview.evidence_bundle.search_duration_ms
                if pubmed_preview is not None
                else 0
            ),
            claim_generation_duration_ms=result.duration_ms,
            candidate_count=count,
            direct_rate=validation.direct_count / count if count else 0,
            unsupported_rate=validation.unsupported_count / count if count else 0,
        )
        set_fingerprint = claim_candidate_set_fingerprint(
            selection.selection_set_id,
            [item.candidate_fingerprint for item in candidates],
        )
        candidate_set = ClaimCandidateSet(
            candidate_set_id=f"ccs_{set_fingerprint[:20]}",
            knowledge_term=knowledge_term,
            evidence_selection=selection,
            candidates=candidates,
            validation=validation,
            kpi=kpi,
            generator_id=result.generator_id,
            generator_version=result.generator_version,
            generated_at=generated_at,
            candidate_set_fingerprint=set_fingerprint,
        )
        self._pending[candidate_set.candidate_set_id] = candidate_set
        self._record_result(
            execution_id,
            selection,
            result,
            validation,
            status="success",
        )
        return candidate_set

    def review(self, request: HumanClaimReviewRequest) -> HumanClaimReviewEntry:
        candidate_set = self._pending.get(request.candidate_set_id)
        if candidate_set is None:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim Candidate Setが見つかりません。もう一度生成してください。",
            )
        candidate = next(
            (
                item
                for item in candidate_set.candidates
                if item.candidate_claim_id == request.candidate_claim_id
            ),
            None,
        )
        if candidate is None:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim CandidateがCandidate Setにありません。",
            )
        timestamp = datetime.now(UTC)
        review_fingerprint = _fingerprint(
            {
                "candidate": candidate.candidate_claim_id,
                "timestamp": timestamp.isoformat(),
                "operator": request.operator,
            }
        )
        review_id = f"hcr_{review_fingerprint[:20]}"
        entry = HumanClaimReviewEntry(
            review_id=review_id,
            candidate_set_id=request.candidate_set_id,
            candidate_claim_id=request.candidate_claim_id,
            decision=request.decision,
            operator=request.operator,
            timestamp=timestamp,
            comment=request.comment,
            original_claim_text=candidate.claim_text,
            revised_claim_text=request.revised_claim_text,
            support_level=candidate.support_level,
            review_duration_ms=request.review_duration_ms,
        )
        self.human_reviews.append(entry)
        return entry

    def review_kpi(self, candidate_set_id: str) -> ClaimGenerationKpi:
        candidate_set = self._pending.get(candidate_set_id)
        if candidate_set is None:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim Candidate Setが見つかりません。もう一度生成してください。",
            )
        latest = self.human_reviews.latest_for_set(candidate_set_id)
        reviewed = list(latest.values())
        reviewed_count = len(reviewed)
        durations = [
            item.review_duration_ms
            for item in reviewed
            if item.review_duration_ms is not None
        ]
        return candidate_set.kpi.model_copy(
            update={
                "human_revision_rate": (
                    sum(
                        item.decision is HumanClaimDecision.REVISED
                        for item in reviewed
                    )
                    / reviewed_count
                    if reviewed_count
                    else None
                ),
                "human_exclusion_rate": (
                    sum(
                        item.decision is HumanClaimDecision.EXCLUDED
                        for item in reviewed
                    )
                    / reviewed_count
                    if reviewed_count
                    else None
                ),
                "claim_review_duration_ms": max(durations) if durations else None,
            }
        )

    def create_authoring_draft(
        self,
        request: CreateGroundedAuthoringDraftRequest,
    ) -> GroundedAuthoringDraftResult:
        candidate_set = self._pending.get(request.candidate_set_id)
        if candidate_set is None:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "Claim Candidate Setが見つかりません。もう一度生成してください。",
            )
        latest = self.human_reviews.latest_for_set(request.candidate_set_id)
        adopted = [
            item
            for item in candidate_set.candidates
            if item.support_level is ClaimSupportLevel.DIRECT
            and latest.get(item.candidate_claim_id) is not None
            and latest[item.candidate_claim_id].decision is HumanClaimDecision.ACCEPTED
        ]
        if not adopted:
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.REQUEST,
                "採用済みかつDirectのClaim Candidateがありません。",
            )
        pipeline_claims = [
            PipelineClaim(
                claim_id=f"clm_ground_{_fingerprint(item.candidate_claim_id)[:16]}",
                assertion=item.claim_text,
                claim_type=PipelineClaimType(item.claim_type.value),
                semantic_slot=_semantic_slot(item.claim_type.value),
                evidence_ids=list(item.supporting_evidence_ids),
                confidence=item.confidence,
            )
            for item in adopted
        ]
        claim_build = ClaimBuildResult(
            builder_name="evidence_grounded_claim_builder",
            builder_version="1.0",
            claims=pipeline_claims,
            llm_called=True,
            warnings=[
                "Human accepted + direct candidates only; Promotion and Approval were not run."
            ],
        )
        pubmed_preview = self.pubmed.pending_preview(
            candidate_set.evidence_selection.evidence_bundle_id
        )
        if pubmed_preview is None or (
            pubmed_preview.evidence_bundle.fingerprint
            != candidate_set.evidence_selection.evidence_bundle_fingerprint
        ):
            raise ClaimGenerationServiceError(
                ClaimGenerationErrorCode.FINGERPRINT,
                "Evidence Bundle Fingerprintが一致しません。",
            )
        references = self.references.build(pubmed_preview.evidence_bundle, claim_build)
        skeleton = self.authoring.build_skeleton(
            CreateAuthoringDraftRequest(
                category=request.category,
                title=candidate_set.knowledge_term,
                aliases=[],
                difficulty=request.difficulty,
                exam_importance=request.exam_importance,
            )
        )
        authoring_claims = [
            AuthoringClaim(
                claim_id=item.claim_id,
                assertion=item.assertion,
                position=index,
                semantic_slot=item.semantic_slot,
            )
            for index, item in enumerate(pipeline_claims, start=1)
        ]
        draft = KnowledgeAuthoringDraft.model_validate(
            skeleton.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "claims": authoring_claims,
                    "references": references,
                }
            )
        )
        saved = self.authoring.save_generated_draft(draft)
        mapping = {
            candidate.candidate_claim_id: pipeline.claim_id
            for candidate, pipeline in zip(adopted, pipeline_claims, strict=True)
        }
        adopted_ids = tuple(mapping)
        rejected_ids = tuple(
            item.candidate_claim_id
            for item in candidate_set.candidates
            if item.candidate_claim_id not in mapping
        )
        return GroundedAuthoringDraftResult(
            candidate_set_id=request.candidate_set_id,
            draft=saved,
            candidate_to_claim_id=mapping,
            adopted_candidate_ids=adopted_ids,
            rejected_candidate_ids=rejected_ids,
            saved_at=datetime.now(UTC),
        )

    def pending(self, candidate_set_id: str) -> ClaimCandidateSet | None:
        return self._pending.get(candidate_set_id)

    def _candidate(
        self,
        knowledge_term: str,
        generated: GeneratedClaimDraft,
        *,
        generated_at: datetime,
        generator_id: str,
        generator_version: str,
        ordinal: int,
        peers: list[tuple[str, str]],
    ) -> ClaimCandidate:
        fingerprint = generated_claim_fingerprint(knowledge_term, generated)
        candidate_id = _candidate_id(fingerprint, ordinal)
        duplicate = self.duplicates.assess(
            knowledge_term,
            candidate_id,
            generated.claim_text,
            [(peer_id, peer_text) for peer_id, peer_text in peers],
        )
        return ClaimCandidate(
            candidate_claim_id=candidate_id,
            knowledge_term=knowledge_term,
            claim_text=generated.claim_text,
            claim_type=generated.claim_type,
            supporting_evidence_ids=generated.supporting_evidence_ids,
            source_locators=generated.source_locators,
            support_level=generated.support_level,
            support_scope=generated.support_scope,
            support_assessment=generated.support_assessment,
            confidence=generated.confidence,
            generator_id=generator_id,
            generator_version=generator_version,
            generated_at=generated_at,
            candidate_fingerprint=fingerprint,
            duplicate_assessment=duplicate,
        )

    def _record_failure(
        self,
        execution_id: str,
        selection: FormalEvidenceSelectionSet,
        code: ClaimGenerationErrorCode,
    ) -> None:
        self.generation_audit.append(
            ClaimGenerationAuditEntry(
                execution_id=execution_id,
                knowledge_term=selection.knowledge_term,
                evidence_bundle_id=selection.evidence_bundle_id,
                selected_evidence_ids=tuple(
                    item.evidence_id for item in selection.evidence
                ),
                provider=self.adapter.provider_name,
                model=self.adapter.model,
                candidate_count=0,
                direct_count=0,
                unsupported_count=0,
                conflicting_count=0,
                duration_ms=0,
                status="failed",
                error_code=code,
                generated_at=datetime.now(UTC),
            )
        )

    def _record_result(
        self,
        execution_id: str,
        selection: FormalEvidenceSelectionSet,
        result: ClaimAdapterResult,
        validation: ClaimCandidateValidationReport,
        *,
        status: Literal["success", "validation_failed", "failed"],
        error_code: ClaimGenerationErrorCode | None = None,
    ) -> None:
        self.generation_audit.append(
            ClaimGenerationAuditEntry(
                execution_id=execution_id,
                knowledge_term=selection.knowledge_term,
                evidence_bundle_id=selection.evidence_bundle_id,
                selected_evidence_ids=tuple(
                    item.evidence_id for item in selection.evidence
                ),
                provider=result.provider,
                model=result.model,
                candidate_count=validation.candidate_count,
                direct_count=validation.direct_count,
                unsupported_count=validation.unsupported_count,
                conflicting_count=validation.conflicting_count,
                duration_ms=result.duration_ms,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                status=status,
                error_code=error_code,
                generated_at=datetime.now(UTC),
            )
        )


def _candidate_id(fingerprint: str, ordinal: int) -> str:
    return f"ccl_{_fingerprint(f'{fingerprint}:{ordinal}')[:20]}"


def _as_generated(candidate: ClaimCandidate) -> GeneratedClaimDraft:
    return GeneratedClaimDraft(
        claim_text=candidate.claim_text,
        claim_type=candidate.claim_type,
        supporting_evidence_ids=candidate.supporting_evidence_ids,
        source_locators=candidate.source_locators,
        support_level=candidate.support_level,
        support_scope=candidate.support_scope,
        support_assessment=candidate.support_assessment,
        confidence=candidate.confidence,
    )


def _validation_error_code(
    report: ClaimCandidateValidationReport,
) -> ClaimGenerationErrorCode:
    codes = {item.code for item in report.issues if item.severity == "error"}
    if "evidence_id_hallucination" in codes:
        return ClaimGenerationErrorCode.EVIDENCE_ID_HALLUCINATION
    if any(item.startswith("locator_") for item in codes):
        return ClaimGenerationErrorCode.LOCATOR_MISMATCH
    if "fingerprint_mismatch" in codes:
        return ClaimGenerationErrorCode.FINGERPRINT
    return ClaimGenerationErrorCode.INVALID_RESPONSE


def _semantic_slot(claim_type: str) -> AuthoringSemanticSlot:
    return {
        "definition": AuthoringSemanticSlot.DEFINITION,
        "overview": AuthoringSemanticSlot.OVERVIEW,
        "caution": AuthoringSemanticSlot.CAUTION,
    }.get(claim_type, AuthoringSemanticSlot.UNASSIGNED)


def _claim_similarity(left: str, right: str) -> float:
    normalized_left = _normalized(left)
    normalized_right = _normalized(right)
    if not normalized_left or not normalized_right:
        return 0
    if normalized_left == normalized_right:
        return 1
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _canonical_doi(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _provider_specific_keys(payload: object) -> set[str]:
    forbidden = {
        "api_key",
        "api_request",
        "model",
        "provider",
        "provider_request",
        "provider_response",
        "structured_output_config",
        "token_usage",
    }
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.casefold() in forbidden:
                found.add(key)
            found.update(_provider_specific_keys(value))
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found.update(_provider_specific_keys(value))
    return found
