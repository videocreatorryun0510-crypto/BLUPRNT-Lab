"""Deterministic fingerprints for requests and provider payloads."""

import hashlib
import json
from typing import Any

from presentation_request_builder import PresentationRequest

from provider_payload_resolver.models import PresentationPayload


def presentation_request_fingerprint(request: PresentationRequest) -> str:
    return _sha256(request.model_dump(mode="json"))


def presentation_payload_fingerprint(payload: PresentationPayload) -> str:
    """Hash stable inputs while excluding generated identity and timestamps."""

    raw = payload.model_dump(mode="json")
    raw["identity"].pop("payload_id", None)
    raw["identity"].pop("created_at", None)
    raw["metadata"].pop("payload_fingerprint", None)
    return _sha256(raw)


def _sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
