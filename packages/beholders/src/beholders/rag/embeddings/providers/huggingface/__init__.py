"""HuggingFace embedding providers."""

from beholders.rag.embeddings.providers.huggingface.huggingface_provider import (
    HuggingFaceProvider,
)
from beholders.rag.embeddings.providers.huggingface.types import (
    HuggingFaceProviderConfig,
    HuggingFaceProviderSpec,
)


__all__ = [
    "HuggingFaceProvider",
    "HuggingFaceProviderConfig",
    "HuggingFaceProviderSpec",
]
