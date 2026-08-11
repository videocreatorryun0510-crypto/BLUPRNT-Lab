"""Append-only, content-free audit log for Knowledge Promotion."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from knowledge_workbench.promotion_models import PromotionLogEvent


class PromotionLogError(RuntimeError):
    """Raised when a Promotion audit event cannot be persisted safely."""


class JsonlPromotionLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: PromotionLogEvent) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(event.model_dump_json())
                stream.write("\n")
                stream.flush()
        except OSError as error:
            raise PromotionLogError("Promotion Logを保存できません。") from error

    def list(self, *, limit: int = 100) -> list[PromotionLogEvent]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            events = [PromotionLogEvent.model_validate_json(line) for line in lines if line]
        except (OSError, ValidationError) as error:
            raise PromotionLogError("Promotion Logを読み込めません。") from error
        return list(reversed(events[-limit:]))
