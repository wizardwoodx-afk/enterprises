"""OpenCLIP embedding providers."""

from beholders.rag.embeddings.providers.openclip.openclip_provider import (
    OpenCLIPProvider,
)
from beholders.rag.embeddings.providers.openclip.types import (
    OpenCLIPProviderConfig,
    OpenCLIPProviderSpec,
)


__all__ = [
    "OpenCLIPProvider",
    "OpenCLIPProviderConfig",
    "OpenCLIPProviderSpec",
]
