"""Local writers for derived Payload and Response JSON artifacts."""

from pathlib import Path

from provider_payload_resolver.models import (
    PresentationPayload,
    TraceablePresentationResponse,
)


class PresentationPayloadJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory.resolve()

    def write(self, payload: PresentationPayload) -> Path:
        path = self.output_directory / (
            f"{payload.source.knowledge_id}_v{payload.source.knowledge_version}."
            f"{payload.request.request_mode.value}.provider-payload.json"
        )
        return _write(path, payload.model_dump_json(indent=2))


class TraceableResponseJsonWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory.resolve()

    def write(self, response: TraceablePresentationResponse) -> Path:
        path = self.output_directory / f"{response.identity.response_id}.response.json"
        return _write(path, response.model_dump_json(indent=2))


def _write(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
