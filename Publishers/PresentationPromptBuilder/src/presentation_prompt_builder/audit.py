"""Metadata-only JSONL audit for Presentation Prompt builds."""

import json
from pathlib import Path

from presentation_prompt_builder.models import PromptAuditRecord


class JsonlPromptAuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def write(self, record: PromptAuditRecord) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n"
            )
