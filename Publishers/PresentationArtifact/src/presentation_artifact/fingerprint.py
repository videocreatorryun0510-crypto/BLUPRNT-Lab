"""Stable fingerprints for Presentation Artifacts."""

import hashlib
import json
from typing import Any

from presentation_artifact.models import PresentationArtifact


def artifact_fingerprint(artifact: PresentationArtifact) -> str:
    """Hash meaningful educational content, excluding identity and wall-clock data."""

    payload = artifact.model_dump(mode="json")
    payload["identity"].pop("artifact_id", None)
    payload["metadata"].pop("fingerprint", None)
    payload["metadata"].pop("created_at", None)
    return _sha256(payload)


def source_bundle_id(source_fingerprint: str) -> str:
    return f"sbn_{source_fingerprint[:32]}"


def stable_block_id(*parts: str) -> str:
    return f"blk_{hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:16]}"


def _sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
