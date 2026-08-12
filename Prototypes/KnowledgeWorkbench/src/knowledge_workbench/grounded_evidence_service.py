"""Discovery-only orchestration for Gemini grounded citation candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from knowledge_workbench.discovery_boundary import validate_discovery_candidate
from knowledge_workbench.discovery_models import (
    DiscoverySearchAuditEntry,
    DiscoverySearchRequest,
    DiscoverySearchUsage,
    GroundedDiscoveryPreview,
)
from knowledge_workbench.gemini_grounded_search import (
    GeminiGroundedDiscoveryResult,
    GeminiGroundedSearchError,
    GeminiGroundedSearchProvider,
)


class DiscoveryAuditError(RuntimeError):
    """Raised when metadata-only Discovery audit cannot be persisted safely."""


class JsonlGroundedDiscoveryAuditLog:
    """Metadata-only audit; no response prose, Evidence, Claim, or headers."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_success(
        self,
        provider_result: GeminiGroundedDiscoveryResult,
    ) -> DiscoverySearchAuditEntry:
        execution = provider_result.execution
        candidate_set = provider_result.candidate_set
        entry = DiscoverySearchAuditEntry(
            search_execution_id=execution.search_execution_id,
            candidate_set_id=candidate_set.candidate_set_id,
            input_term=execution.query_plan.input_term,
            generated_queries=tuple(
                item.query for item in execution.query_plan.queries
            ),
            executed_queries=execution.executed_queries,
            provider=execution.provider,
            model=execution.model,
            search_started_at=execution.search_started_at,
            completed_at=execution.completed_at,
            duration_ms=execution.duration_ms,
            raw_source_count=candidate_set.raw_source_count,
            candidate_count=candidate_set.candidate_count,
            duplicate_count=candidate_set.duplicate_count,
            usage=DiscoverySearchUsage(
                **execution.usage.model_dump(mode="python")
            ),
            status="success",
        )
        self._append(entry)
        return entry

    def record_failure(
        self,
        error: GeminiGroundedSearchError,
    ) -> DiscoverySearchAuditEntry:
        entry = DiscoverySearchAuditEntry(
            search_execution_id=error.search_execution_id,
            input_term=error.query_plan.input_term,
            generated_queries=tuple(item.query for item in error.query_plan.queries),
            executed_queries=error.executed_queries,
            provider="gemini_google_search",
            model=error.model,
            search_started_at=error.started_at,
            completed_at=error.completed_at,
            duration_ms=max(
                0,
                int((error.completed_at - error.started_at).total_seconds() * 1000),
            ),
            raw_source_count=0,
            candidate_count=0,
            duplicate_count=0,
            usage=DiscoverySearchUsage(
                request_count=error.attempt_count,
                attempt_count=error.attempt_count,
                search_grounding_used=False,
                estimated_cost_usd=None,
            ),
            status="failed",
            error_code=error.code.value,
        )
        self._append(entry)
        return entry

    def list(self, *, limit: int = 100) -> list[DiscoverySearchAuditEntry]:
        if not self.path.exists():
            return []
        try:
            events = [
                _parse_audit_line(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValueError, ValidationError) as error:
            raise DiscoveryAuditError(
                "Gemini Discovery Search Auditを読み込めません。"
            ) from error
        return list(reversed(events[-limit:]))

    def _append(self, entry: DiscoverySearchAuditEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise DiscoveryAuditError(
                "Gemini Discovery Search Auditを保存できません。"
            ) from error


class GroundedDiscoveryService:
    """Stops at Discovery Candidate Set; no Evidence component is available here."""

    def __init__(
        self,
        provider: GeminiGroundedSearchProvider,
        audit: JsonlGroundedDiscoveryAuditLog,
    ) -> None:
        self.provider = provider
        self.audit = audit

    def preview(self, term: str) -> GroundedDiscoveryPreview:
        request = DiscoverySearchRequest(medical_term=term)
        try:
            provider_result = self.provider.discover_with_report(request)
        except GeminiGroundedSearchError as error:
            self.audit.record_failure(error)
            raise

        for candidate in provider_result.candidate_set.candidates:
            validate_discovery_candidate(candidate)
        audit = self.audit.record_success(provider_result)
        response_fingerprint = _fingerprint(
            {
                "execution_id": provider_result.execution.search_execution_id,
                "candidate_set_fingerprint": (
                    provider_result.candidate_set.discovery_fingerprint
                ),
                "boundary": {
                    "claim_eligible": False,
                    "evidence_bundle_eligible": False,
                    "promotion_allowed": False,
                    "registry_allowed": False,
                    "approval_allowed": False,
                },
            }
        )
        return GroundedDiscoveryPreview(
            search_execution_id=provider_result.execution.search_execution_id,
            input_term=provider_result.execution.query_plan.input_term,
            provider=provider_result.execution.provider,
            provider_version=provider_result.execution.provider_version,
            model=provider_result.execution.model,
            discovery_candidate_set=provider_result.candidate_set,
            search_audit=audit,
            response_fingerprint=response_fingerprint,
        )


def _parse_audit_line(line: str) -> DiscoverySearchAuditEntry:
    raw = json.loads(line)
    if not isinstance(raw, dict):
        raise ValueError("audit line must be an object")
    if raw.get("audit_version") == "1.1":
        return DiscoverySearchAuditEntry.model_validate(raw)

    # Phase 5.26 audit migration. Old Evidence-named counters are retained only
    # as historical execution metadata and are never restored as Evidence.
    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    return DiscoverySearchAuditEntry(
        search_execution_id=raw["search_execution_id"],
        candidate_set_id=None,
        input_term=raw["input_term"],
        generated_queries=tuple(raw.get("generated_queries", ())),
        executed_queries=tuple(raw.get("executed_queries", ())),
        provider=raw.get("provider", "gemini_google_search"),
        model=raw["model"],
        search_started_at=raw["search_started_at"],
        completed_at=raw["completed_at"],
        duration_ms=raw.get("duration_ms", 0),
        raw_source_count=raw.get("raw_source_count", 0),
        candidate_count=raw.get("accepted_count", 0),
        duplicate_count=raw.get("deduplicated_count", 0),
        usage=DiscoverySearchUsage.model_validate(usage),
        status=raw.get("status", "failed"),
        error_code=raw.get("error_code"),
    )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
