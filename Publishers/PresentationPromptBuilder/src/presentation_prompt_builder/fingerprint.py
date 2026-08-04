"""Deterministic Presentation Prompt fingerprints."""

import hashlib
import json
from typing import Any

from presentation_prompt_builder.models import PresentationPrompt


def presentation_prompt_fingerprint(prompt: PresentationPrompt) -> str:
    raw = prompt.model_dump(mode="json")
    raw["identity"].pop("prompt_id", None)
    raw["identity"].pop("created_at", None)
    raw["metadata"].pop("prompt_fingerprint", None)
    return _sha256(raw)


def _sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
