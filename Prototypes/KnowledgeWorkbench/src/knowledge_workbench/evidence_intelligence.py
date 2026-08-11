"""Provider-neutral Evidence deduplication, ranking, bundling, and audit."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from pydantic import ValidationError

from knowledge_workbench.knowledge_pipeline_models import (
    BundledEvidence,
    DeduplicationReason,
    EvidenceBundle,
    EvidenceDeduplicationDecision,
    EvidenceDeduplicationResult,
    EvidenceNormalizationResult,
    EvidenceRankingResult,
    EvidenceSearchAuditEntry,
    NormalizedEvidence,
    PipelineEvidenceLevel,
    RankedEvidence,
    RawEvidenceSearchResult,
    SearchAuditProviderCount,
)


class EvidenceIntelligenceError(RuntimeError):
    """Raised when Evidence cannot be safely standardized or audited."""


class DefaultEvidenceDeduplicator:
    deduplicator_version = "1.0"
    title_similarity_threshold = 0.94

    def deduplicate(
        self,
        result: EvidenceNormalizationResult,
    ) -> EvidenceDeduplicationResult:
        retained: list[BundledEvidence] = []
        decisions: list[EvidenceDeduplicationDecision] = []
        excluded: list[str] = []
        ordered = sorted(result.evidence, key=_evidence_quality_key)

        for candidate in ordered:
            match_index: int | None = None
            match_reasons: list[DeduplicationReason] = []
            for index, existing in enumerate(retained):
                reasons = _duplicate_reasons(existing, candidate)
                if reasons:
                    match_index = index
                    match_reasons = reasons
                    break
            if match_index is None:
                retained.append(_as_bundled(candidate))
                continue

            existing = retained[match_index]
            retained[match_index] = _merge_evidence(existing, candidate)
            excluded.append(candidate.provider.provider_record_id)
            decisions.append(
                EvidenceDeduplicationDecision(
                    retained_evidence_id=existing.evidence_id,
                    merged_provider_record_ids=[candidate.provider.provider_record_id],
                    reasons=match_reasons,
                )
            )

        return EvidenceDeduplicationResult(
            evidence=retained,
            input_count=len(result.evidence),
            unique_count=len(retained),
            excluded_count=len(excluded),
            excluded_provider_record_ids=excluded,
            decisions=decisions,
        )


class DefaultEvidenceRanker:
    ranking_version = "1.0"

    def rank(self, result: EvidenceDeduplicationResult) -> EvidenceRankingResult:
        level_order = {
            PipelineEvidenceLevel.A: 1,
            PipelineEvidenceLevel.B: 2,
            PipelineEvidenceLevel.C: 3,
        }
        ordered = sorted(
            result.evidence,
            key=lambda item: (
                level_order[item.evidence_level],
                item.information_priority_rank,
                -(item.publication_date.toordinal() if item.publication_date else 0),
                item.evidence_id,
            ),
        )
        ranked = [
            RankedEvidence(
                evidence=item,
                rank=index,
                evidence_level_order=level_order[item.evidence_level],
                information_priority_rank=item.information_priority_rank,
                ranking_reasons=[
                    f"Evidence Level {item.evidence_level.value}（第一基準）",
                    (
                        "Information Priority "
                        f"{item.information_priority_rank}（同Level内の補助基準）"
                    ),
                ],
            )
            for index, item in enumerate(ordered, start=1)
        ]
        return EvidenceRankingResult(ranked_evidence=ranked)


class EvidenceBundleBuilder:
    builder_version = "1.0"

    def build(
        self,
        normalization: EvidenceNormalizationResult,
        deduplication: EvidenceDeduplicationResult,
        ranking: EvidenceRankingResult,
    ) -> EvidenceBundle:
        providers = sorted(
            {
                provider.provider_name
                for ranked in ranking.ranked_evidence
                for provider in ranked.evidence.providers
            }
        )
        excluded_ids = [
            *normalization.rejected_provider_record_ids,
            *deduplication.excluded_provider_record_ids,
        ]
        semantic_payload = {
            "query": normalization.query.model_dump(mode="json"),
            "subject": normalization.subject.model_dump(mode="json"),
            "providers": providers,
            "evidence": [_semantic_evidence(item) for item in ranking.ranked_evidence],
            "excluded_provider_record_ids": sorted(excluded_ids),
        }
        fingerprint = _fingerprint(semantic_payload)
        return EvidenceBundle(
            bundle_id=f"evb_{fingerprint[:20]}",
            query=normalization.query,
            subject=normalization.subject,
            created_at=datetime.now(UTC),
            providers=providers,
            evidence=ranking.ranked_evidence,
            input_record_count=(
                len(normalization.evidence)
                + len(normalization.rejected_provider_record_ids)
            ),
            normalized_evidence_count=len(normalization.evidence),
            accepted_evidence_count=len(ranking.ranked_evidence),
            excluded_evidence_count=len(excluded_ids),
            excluded_provider_record_ids=excluded_ids,
            deduplication_decisions=deduplication.decisions,
            external_search_performed=normalization.external_search_performed,
            search_duration_ms=normalization.search_duration_ms,
            warnings=normalization.warnings,
            fingerprint=fingerprint,
        )


class JsonlEvidenceSearchAuditLog:
    """Append-only search metadata; Evidence and Claim bodies are never written."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        raw: RawEvidenceSearchResult,
        bundle: EvidenceBundle,
    ) -> EvidenceSearchAuditEntry:
        provider_counts = Counter(item.provider_name for item in raw.records)
        entry = EvidenceSearchAuditEntry(
            event_id=f"esa_{uuid4().hex[:16]}",
            bundle_id=bundle.bundle_id,
            search_query=raw.query.theme,
            providers=[
                SearchAuditProviderCount(provider=name, retrieved_count=count)
                for name, count in sorted(provider_counts.items())
            ],
            retrieved_count=len(raw.records),
            accepted_evidence_ids=[
                item.evidence.evidence_id for item in bundle.evidence
            ],
            excluded_provider_record_ids=bundle.excluded_provider_record_ids,
            searched_at=raw.searched_at,
            duration_ms=raw.duration_ms,
            status="success",
        )
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise EvidenceIntelligenceError("Search Auditを保存できません。") from error
        return entry

    def list(self, *, limit: int = 100) -> list[EvidenceSearchAuditEntry]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            events = [
                EvidenceSearchAuditEntry.model_validate_json(line)
                for line in lines
                if line
            ]
        except (OSError, ValidationError) as error:
            raise EvidenceIntelligenceError("Search Auditを読み込めません。") from error
        return list(reversed(events[-limit:]))

    def record_failure(
        self,
        *,
        query: str,
        provider: str,
        searched_at: datetime,
        duration_ms: int,
    ) -> EvidenceSearchAuditEntry:
        failure_id = hashlib.sha256(
            f"{query}:{searched_at.isoformat()}".encode()
        ).hexdigest()[:20]
        entry = EvidenceSearchAuditEntry(
            event_id=f"esa_{uuid4().hex[:16]}",
            bundle_id=f"evb_failed_{failure_id}",
            search_query=query,
            providers=[SearchAuditProviderCount(provider=provider, retrieved_count=0)],
            retrieved_count=0,
            accepted_evidence_ids=[],
            excluded_provider_record_ids=[],
            searched_at=searched_at,
            duration_ms=duration_ms,
            status="failed",
        )
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise EvidenceIntelligenceError("Search Auditを保存できません。") from error
        return entry


def stable_evidence_id(
    *,
    doi: str | None,
    pmid: str | None,
    url: str | None,
    title: str,
    publisher: str,
    publication_date: str | None,
) -> str:
    identity = (
        f"doi:{_canonical_doi(doi)}"
        if _canonical_doi(doi)
        else f"pmid:{_canonical_pmid(pmid)}"
        if _canonical_pmid(pmid)
        else f"url:{_canonical_url(url)}"
        if _canonical_url(url)
        else "title:"
        + "|".join(
            (_normalized_text(title), _normalized_text(publisher), publication_date or "")
        )
    )
    return f"evd_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def _evidence_quality_key(evidence: NormalizedEvidence) -> tuple[int, int, str, str]:
    level_order = {
        PipelineEvidenceLevel.A: 1,
        PipelineEvidenceLevel.B: 2,
        PipelineEvidenceLevel.C: 3,
    }
    return (
        level_order[evidence.evidence_level],
        evidence.information_priority_rank,
        evidence.provider.provider_name,
        evidence.provider.provider_record_id,
    )


def _as_bundled(item: NormalizedEvidence) -> BundledEvidence:
    return BundledEvidence(
        evidence_id=item.evidence_id,
        title=item.title,
        publisher=item.publisher,
        evidence_type=item.evidence_type,
        evidence_level=item.evidence_level,
        publication_date=item.publication_date,
        url=item.url,
        doi=item.doi,
        pmid=item.pmid,
        language=item.language,
        abstract_or_snippet=item.abstract_or_snippet,
        retrieved_at=item.retrieved_at,
        providers=[item.provider],
        information_priority_rank=item.information_priority_rank,
        citation=item.citation,
    )


def _merge_evidence(
    existing: BundledEvidence,
    candidate: NormalizedEvidence,
) -> BundledEvidence:
    provider_by_key = {
        (
            item.provider_name,
            item.provider_version,
            item.provider_record_id,
        ): item
        for item in [*existing.providers, candidate.provider]
    }
    return BundledEvidence(
        evidence_id=existing.evidence_id,
        title=existing.title,
        publisher=existing.publisher,
        evidence_type=existing.evidence_type,
        evidence_level=existing.evidence_level,
        publication_date=existing.publication_date or candidate.publication_date,
        url=existing.url or candidate.url,
        doi=existing.doi or candidate.doi,
        pmid=existing.pmid or candidate.pmid,
        language=existing.language,
        abstract_or_snippet=existing.abstract_or_snippet,
        retrieved_at=max(existing.retrieved_at, candidate.retrieved_at),
        providers=[provider_by_key[key] for key in sorted(provider_by_key)],
        information_priority_rank=min(
            existing.information_priority_rank,
            candidate.information_priority_rank,
        ),
        citation=existing.citation,
    )


def _duplicate_reasons(
    existing: BundledEvidence,
    candidate: NormalizedEvidence,
) -> list[DeduplicationReason]:
    reasons: list[DeduplicationReason] = []
    if _canonical_doi(existing.doi) and _canonical_doi(existing.doi) == _canonical_doi(
        candidate.doi
    ):
        reasons.append("doi")
    if _canonical_pmid(existing.pmid) and _canonical_pmid(
        existing.pmid
    ) == _canonical_pmid(candidate.pmid):
        reasons.append("pmid")
    if _canonical_url(str(existing.url) if existing.url else None) and _canonical_url(
        str(existing.url) if existing.url else None
    ) == _canonical_url(str(candidate.url) if candidate.url else None):
        reasons.append("url")
    left = _normalized_text(existing.title)
    right = _normalized_text(candidate.title)
    if left == right or (
        min(len(left), len(right)) >= 12
        and SequenceMatcher(None, left, right).ratio()
        >= DefaultEvidenceDeduplicator.title_similarity_threshold
    ):
        reasons.append("title_similarity")
    return reasons


def _canonical_doi(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized


def _canonical_pmid(value: str | None) -> str:
    if not value:
        return ""
    return "".join(character for character in value if character.isdigit())


def _canonical_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _normalized_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).lower()
        if character.isalnum()
    )


def _semantic_evidence(item: RankedEvidence) -> dict[str, object]:
    evidence = item.evidence
    return {
        "rank": item.rank,
        "evidence_id": evidence.evidence_id,
        "title": evidence.title,
        "publisher": evidence.publisher,
        "evidence_type": evidence.evidence_type.value,
        "evidence_level": evidence.evidence_level.value,
        "publication_date": (
            evidence.publication_date.isoformat() if evidence.publication_date else None
        ),
        "url": str(evidence.url) if evidence.url else None,
        "doi": evidence.doi,
        "pmid": evidence.pmid,
        "language": evidence.language.value,
        "abstract_or_snippet": evidence.abstract_or_snippet,
        "providers": sorted(
            (
                provider.provider_name,
                provider.provider_version,
                provider.provider_record_id,
            )
            for provider in evidence.providers
        ),
        "information_priority_rank": evidence.information_priority_rank,
    }


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
