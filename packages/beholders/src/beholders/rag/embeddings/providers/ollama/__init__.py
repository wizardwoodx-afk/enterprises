"""Ollama embedding providers."""

from beholders.rag.embeddings.providers.ollama.ollama_provider import (
    OllamaProvider,
)
from beholders.rag.embeddings.providers.ollama.types import (
    OllamaProviderConfig,
    OllamaProviderSpec,
)


__all__ = [
    "OllamaProvider",
    "OllamaProviderConfig",
    "OllamaProviderSpec",
]
