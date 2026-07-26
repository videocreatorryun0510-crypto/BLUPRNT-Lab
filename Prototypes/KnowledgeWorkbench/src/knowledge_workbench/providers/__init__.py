"""AI provider adapters and their provider-neutral contract."""

from knowledge_workbench.providers.base import GenerationResult, KnowledgeProvider
from knowledge_workbench.providers.openai_provider import OpenAIKnowledgeProvider

__all__ = ["GenerationResult", "KnowledgeProvider", "OpenAIKnowledgeProvider"]
