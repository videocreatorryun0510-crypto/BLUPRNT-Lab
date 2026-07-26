"""Provider-neutral AI boundary used by the application layer."""

from dataclasses import dataclass
from typing import Protocol

from knowledge_workbench.generation_models import GeneratedKnowledgeDraft


@dataclass(frozen=True)
class GenerationResult:
    draft: GeneratedKnowledgeDraft
    provider: str
    model: str
    provider_request_id: str = ""


class KnowledgeProvider(Protocol):
    """Gemini or Claude can be added by implementing this single method."""

    def generate(self, term: str) -> GenerationResult:
        """Generate an unapproved exam-focused knowledge draft."""
