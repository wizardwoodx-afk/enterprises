"""IBM embedding providers."""

from beholders.rag.embeddings.providers.ibm.types import (
    WatsonXProviderConfig,
    WatsonXProviderSpec,
)
from beholders.rag.embeddings.providers.ibm.watsonx import (
    WatsonXProvider,
)


__all__ = [
    "WatsonXProvider",
    "WatsonXProviderConfig",
    "WatsonXProviderSpec",
]
