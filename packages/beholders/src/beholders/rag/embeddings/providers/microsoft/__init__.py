"""Microsoft embedding providers."""

from beholders.rag.embeddings.providers.microsoft.azure import (
    AzureProvider,
)
from beholders.rag.embeddings.providers.microsoft.types import (
    AzureProviderConfig,
    AzureProviderSpec,
)


__all__ = [
    "AzureProvider",
    "AzureProviderConfig",
    "AzureProviderSpec",
]
