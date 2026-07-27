"""Atomic writer for derived Presentation Request artifacts."""

import json
import os
from pathlib import Path
from uuid import uuid4

from presentation_request_builder.models import PresentationRequest


class PresentationRequestJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory.resolve()

    def write(self, request: PresentationRequest) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{request.source.knowledge_id}_v{request.source.knowledge_version}."
            f"{request.request_mode.value}.presentation-request.json"
        )
        destination = self.output_directory / filename
        temporary = self.output_directory / f".{filename}.{uuid4().hex}.tmp"
        payload = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
