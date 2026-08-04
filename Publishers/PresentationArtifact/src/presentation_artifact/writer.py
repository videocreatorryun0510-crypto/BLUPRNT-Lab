"""Atomic writer for validated Presentation Artifact JSON."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from presentation_artifact.models import PresentationArtifact


class PresentationArtifactJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory

    def write(self, artifact: PresentationArtifact) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{artifact.source.knowledge_id}_v{artifact.source.knowledge_version}."
            f"{artifact.identity.artifact_id}.presentation-artifact.json"
        )
        output_path = self.output_directory / filename
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.output_directory,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(artifact.model_dump_json(indent=2))
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
        return output_path
