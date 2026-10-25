"""Backwards-compatible re-export surface for the Flow framework.

The implementation now lives in three modules, split by concern:

- ``beholders.flow.dsl`` -- authoring decorators (``@start`` / ``@listen`` /
  ``@router``, ``or_`` / ``and_``) and Python Flow class projection
- ``beholders.flow.flow_definition`` -- the serializable Flow Definition contract
- ``beholders.flow.runtime`` -- the Flow execution engine and state
- ``beholders.flow.conversational_mixin`` -- conversational
  runtime extension composed onto the public ``Flow`` class

Prefer importing from those modules in new code; this module preserves the
historical ``beholders.flow.flow`` import path.
"""

from typing import Any, TypeVar

from pydantic import BaseModel

from beholders.flow.conversational_mixin import _ConversationalMixin
from beholders.flow.dsl import and_, listen, or_, router, start
from beholders.flow.runtime import (
    _INITIAL_STATE_CLASS_MARKER,
    Flow as RuntimeFlow,
    FlowMeta,
    FlowState,
)


T = TypeVar("T", bound=dict[str, Any] | BaseModel)


class Flow(_ConversationalMixin, RuntimeFlow[T]):
    """Public Flow class with conversational extension behavior."""


__all__ = [
    "_INITIAL_STATE_CLASS_MARKER",
    "Flow",
    "FlowMeta",
    "FlowState",
    "and_",
    "listen",
    "or_",
    "router",
    "start",
]
