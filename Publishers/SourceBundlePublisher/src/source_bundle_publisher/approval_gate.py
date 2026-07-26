"""Persistent audit boundary for provider-neutral Approval Gate decisions."""

import json
from pathlib import Path

from knowledge_contracts.approval_v10 import ApprovalGateDecision


class JsonlApprovalAuditLogger:
    """Append one immutable JSON record per gate evaluation."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path.resolve()

    def write(self, decision: ApprovalGateDecision) -> Path:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            decision.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self.output_path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
        return self.output_path
