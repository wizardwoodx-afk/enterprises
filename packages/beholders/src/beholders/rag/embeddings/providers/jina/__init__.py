"""Jina embedding providers."""

from beholders.rag.embeddings.providers.jina.jina_provider import JinaProvider
from beholders.rag.embeddings.providers.jina.types import (
    JinaProviderConfig,
    JinaProviderSpec,
)


__all__ = [
    "JinaProvider",
    "JinaProviderConfig",
    "JinaProviderSpec",
]
