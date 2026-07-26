"""Atomic JSON writer for derived Source Bundle artifacts."""

import json
import os
from pathlib import Path
from uuid import uuid4

from source_bundle_publisher.models import SourceBundle


class SourceBundleJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory.resolve()

    def write(self, bundle: SourceBundle) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{bundle.metadata.knowledge_id}_v{bundle.metadata.version}"
            ".source-bundle.json"
        )
        destination = self.output_directory / filename
        temporary = self.output_directory / f".{filename}.{uuid4().hex}.tmp"
        payload = json.dumps(
            bundle.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
