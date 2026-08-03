"""Metadata-only JSONL audit logs for Payload and Response processing."""

import json
from pathlib import Path

from provider_payload_resolver.models import PayloadAuditRecord, ResponseAuditRecord


class JsonlPayloadAuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path.resolve()

    def write(self, record: PayloadAuditRecord) -> Path:
        return _append(self.output_path, record.model_dump(mode="json"))


class JsonlResponseAuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path.resolve()

    def write(self, record: ResponseAuditRecord) -> Path:
        return _append(self.output_path, record.model_dump(mode="json"))


def _append(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(serialized + "\n")
        stream.flush()
    return path
