"""Metadata-only audit for Gemini Sandbox executions."""

import json
from pathlib import Path

from presentation_engine_adapter.gemini_models import GeminiSandboxAuditRecord


class JsonlGeminiSandboxAuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def write(self, record: GeminiSandboxAuditRecord) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n"
            )
