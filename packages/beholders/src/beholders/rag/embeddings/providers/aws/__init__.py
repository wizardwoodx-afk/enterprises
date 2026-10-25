"""AWS embedding providers."""

from beholders.rag.embeddings.providers.aws.bedrock import BedrockProvider
from beholders.rag.embeddings.providers.aws.types import (
    BedrockProviderConfig,
    BedrockProviderSpec,
)


__all__ = [
    "BedrockProvider",
    "BedrockProviderConfig",
    "BedrockProviderSpec",
]
