"""Metadata-only JSONL audit log for Presentation Engine execution."""

import json
from pathlib import Path

from presentation_engine_adapter.models import PresentationEngineAuditRecord


class JsonlPresentationEngineAuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path.resolve()

    def write(self, record: PresentationEngineAuditRecord) -> Path:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self.output_path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
        return self.output_path
