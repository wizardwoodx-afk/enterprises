"""Type definitions for the embeddings module."""

from typing import Any, Literal, TypeAlias

from beholders.rag.core.base_embeddings_provider import BaseEmbeddingsProvider
from beholders.rag.embeddings.providers.aws.types import BedrockProviderSpec
from beholders.rag.embeddings.providers.cohere.types import CohereProviderSpec
from beholders.rag.embeddings.providers.custom.types import CustomProviderSpec
from beholders.rag.embeddings.providers.google.types import (
    GenerativeAiProviderSpec,
    VertexAIProviderSpec,
)
from beholders.rag.embeddings.providers.huggingface.types import HuggingFaceProviderSpec
from beholders.rag.embeddings.providers.ibm.types import (
    WatsonXProviderSpec,
)
from beholders.rag.embeddings.providers.instructor.types import InstructorProviderSpec
from beholders.rag.embeddings.providers.jina.types import JinaProviderSpec
from beholders.rag.embeddings.providers.microsoft.types import AzureProviderSpec
from beholders.rag.embeddings.providers.ollama.types import OllamaProviderSpec
from beholders.rag.embeddings.providers.onnx.types import ONNXProviderSpec
from beholders.rag.embeddings.providers.openai.types import OpenAIProviderSpec
from beholders.rag.embeddings.providers.openclip.types import OpenCLIPProviderSpec
from beholders.rag.embeddings.providers.openrouter.types import OpenRouterProviderSpec
from beholders.rag.embeddings.providers.oracle.types import OracleProviderSpec
from beholders.rag.embeddings.providers.roboflow.types import RoboflowProviderSpec
from beholders.rag.embeddings.providers.sentence_transformer.types import (
    SentenceTransformerProviderSpec,
)
from beholders.rag.embeddings.providers.text2vec.types import Text2VecProviderSpec
from beholders.rag.embeddings.providers.voyageai.types import VoyageAIProviderSpec


ProviderSpec: TypeAlias = (
    AzureProviderSpec
    | BedrockProviderSpec
    | CohereProviderSpec
    | CustomProviderSpec
    | GenerativeAiProviderSpec
    | HuggingFaceProviderSpec
    | InstructorProviderSpec
    | JinaProviderSpec
    | OllamaProviderSpec
    | ONNXProviderSpec
    | OpenAIProviderSpec
    | OpenCLIPProviderSpec
    | OpenRouterProviderSpec
    | OracleProviderSpec
    | RoboflowProviderSpec
    | SentenceTransformerProviderSpec
    | Text2VecProviderSpec
    | VertexAIProviderSpec
    | VoyageAIProviderSpec
    | WatsonXProviderSpec
)

AllowedEmbeddingProviders = Literal[
    "azure",
    "amazon-bedrock",
    "cohere",
    "custom",
    "google-generativeai",
    "google-vertex",
    "huggingface",
    "instructor",
    "jina",
    "ollama",
    "onnx",
    "openai",
    "openclip",
    "openrouter",
    "oracle",
    "roboflow",
    "sentence-transformer",
    "text2vec",
    "voyageai",
    "watsonx",
]

EmbedderConfig: TypeAlias = (
    ProviderSpec | BaseEmbeddingsProvider[Any] | type[BaseEmbeddingsProvider[Any]]
)
