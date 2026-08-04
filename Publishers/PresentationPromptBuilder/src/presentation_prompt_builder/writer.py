"""Atomic local writer for derived Presentation Prompt JSON."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from presentation_prompt_builder.models import PresentationPrompt


class PresentationPromptJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory

    def write(self, prompt: PresentationPrompt) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        output_path = self.output_directory / (
            f"{prompt.source.knowledge_id}_v{prompt.source.knowledge_version}."
            f"{prompt.source.request_mode.value}.presentation-prompt.json"
        )
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.output_directory,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(prompt.model_dump_json(indent=2))
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
        return output_path
