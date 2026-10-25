"""Instructor embedding providers."""

from beholders.rag.embeddings.providers.instructor.instructor_provider import (
    InstructorProvider,
)
from beholders.rag.embeddings.providers.instructor.types import (
    InstructorProviderConfig,
    InstructorProviderSpec,
)


__all__ = [
    "InstructorProvider",
    "InstructorProviderConfig",
    "InstructorProviderSpec",
]
