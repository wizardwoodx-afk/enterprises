"""Custom embedding providers."""

from beholders.rag.embeddings.providers.custom.custom_provider import CustomProvider
from beholders.rag.embeddings.providers.custom.types import (
    CustomProviderConfig,
    CustomProviderSpec,
)


__all__ = [
    "CustomProvider",
    "CustomProviderConfig",
    "CustomProviderSpec",
]
