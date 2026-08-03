"""Canonical Presentation Request fingerprint."""

import hashlib
import json

from presentation_request_builder import PresentationRequest


def presentation_request_fingerprint(request: PresentationRequest) -> str:
    serialized = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
