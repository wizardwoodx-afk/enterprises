"""The Beholders engine.

Public API: ``Agent``, ``Task``, ``Crew``, ``Process``, ``Flow``, ``LLM`` …

Importing this package is cheap on purpose. The engine's own imports (pydantic,
httpx, litellm, …) are deferred into :func:`_bootstrap` and run the first time
an engine name is touched, so the desktop bridge — ``beholders.service`` — can be
imported and served on a machine that only has the standard library. A missing
optional dependency therefore degrades one feature instead of the whole plugin.
"""
import importlib
import sys
from typing import TYPE_CHECKING, Annotated, Any
import warnings

_ENGINE_READY = False


def _bootstrap() -> None:
    """Import the engine and resolve its pydantic forward references. Idempotent."""
    global _ENGINE_READY, RuntimeState, Entity
    global Agent, BaseLLM, Crew, CrewOutput, ExecutionContext, Flow, Knowledge
    global LLM, LLMGuardrail, PlanningConfig, Process, Task
    if _ENGINE_READY:
        return
    _ENGINE_READY = True

    import beholders_core.plus_api  # noqa: F401
    from pydantic import Field, PydanticUserError

    from beholders.agent.core import Agent
    from beholders.agent.planning_config import PlanningConfig
    from beholders.context import ExecutionContext
    from beholders.crew import Crew
    from beholders.crews.crew_output import CrewOutput
    from beholders.flow.flow import Flow
    from beholders.knowledge.knowledge import Knowledge
    from beholders.llm import LLM
    from beholders.llms.base_llm import BaseLLM
    from beholders.process import Process
    from beholders.state.checkpoint_config import CheckpointConfig  # noqa: F401
    from beholders.task import Task
    from beholders.tasks.llm_guardrail import LLMGuardrail
    from beholders.tasks.task_output import TaskOutput


    if TYPE_CHECKING:
        from beholders.memory.unified_memory import Memory


    def _suppress_pydantic_deprecation_warnings() -> None:
        """Suppress Pydantic deprecation warnings using targeted monkey patch."""
        original_warn = warnings.warn

        def filtered_warn(
            message: Any,
            category: type | None = None,
            stacklevel: int = 1,
            source: Any = None,
        ) -> Any:
            if (
                category
                and hasattr(category, "__module__")
                and category.__module__ == "pydantic.warnings"
            ):
                return None
            return original_warn(message, category, stacklevel + 1, source)

        warnings.warn = filtered_warn  # type: ignore[assignment]


    _suppress_pydantic_deprecation_warnings()

    __version__ = "1.15.30"

    try:
        from beholders.agents.agent_builder.base_agent import BaseAgent as _BaseAgent
        from beholders.agents.agent_builder.base_agent_executor import (
            BaseAgentExecutor as _BaseAgentExecutor,
        )
        from beholders.agents.agent_executor import AgentExecutor as _AgentExecutor
        from beholders.agents.tools_handler import ToolsHandler as _ToolsHandler
        from beholders.hooks.llm_hooks import LLMCallHookContext as _LLMCallHookContext
        from beholders.tools.tool_types import ToolResult as _ToolResult
        from beholders.utilities.prompts import (
            StandardPromptResult as _StandardPromptResult,
            SystemPromptResult as _SystemPromptResult,
        )

        _base_namespace: dict[str, type] = {
            "Agent": Agent,
            "BaseAgent": _BaseAgent,
            "Crew": Crew,
            "Flow": Flow,
            "BaseLLM": BaseLLM,
            "Task": Task,
            "BaseAgentExecutor": _BaseAgentExecutor,
            "ExecutionContext": ExecutionContext,
            "StandardPromptResult": _StandardPromptResult,
            "SystemPromptResult": _SystemPromptResult,
        }

        from beholders.tools.base_tool import BaseTool as _BaseTool
        from beholders.tools.structured_tool import CrewStructuredTool as _CrewStructuredTool

        _base_namespace["BaseTool"] = _BaseTool
        _base_namespace["CrewStructuredTool"] = _CrewStructuredTool

        try:
            from beholders.a2a.config import (
                A2AClientConfig as _A2AClientConfig,
                A2AConfig as _A2AConfig,
                A2AServerConfig as _A2AServerConfig,
            )

            _base_namespace.update(
                {
                    "A2AConfig": _A2AConfig,
                    "A2AClientConfig": _A2AClientConfig,
                    "A2AServerConfig": _A2AServerConfig,
                }
            )
        except ImportError:
            pass

        _full_namespace = {
            **_base_namespace,
            "ToolsHandler": _ToolsHandler,
            "StandardPromptResult": _StandardPromptResult,
            "SystemPromptResult": _SystemPromptResult,
            "LLMCallHookContext": _LLMCallHookContext,
            "ToolResult": _ToolResult,
        }

        _resolve_namespace = {
            **_full_namespace,
            **sys.modules[_BaseAgent.__module__].__dict__,
        }

        import beholders.state.runtime as _runtime_state_mod

        for _mod_name in (
            _BaseAgent.__module__,
            Agent.__module__,
            Crew.__module__,
            Flow.__module__,
            Task.__module__,
            _runtime_state_mod.__name__,
            _AgentExecutor.__module__,
        ):
            sys.modules[_mod_name].__dict__.update(_resolve_namespace)

        from beholders.tasks.conditional_task import ConditionalTask as _ConditionalTask

        _BaseAgentExecutor.model_rebuild(force=True, _types_namespace=_full_namespace)
        _BaseAgent.model_rebuild(force=True, _types_namespace=_full_namespace)
        Task.model_rebuild(force=True, _types_namespace=_full_namespace)
        _ConditionalTask.model_rebuild(force=True, _types_namespace=_full_namespace)
        Crew.model_rebuild(force=True, _types_namespace=_full_namespace)
        Flow.model_rebuild(force=True, _types_namespace=_full_namespace)
        _AgentExecutor.model_rebuild(force=True, _types_namespace=_full_namespace)

        from beholders.state.runtime import RuntimeState

        Entity = Annotated[
            Flow | Crew | Agent,  # type: ignore[type-arg]
            Field(discriminator="entity_type"),
        ]

        RuntimeState.model_rebuild(
            force=True,
            _types_namespace={**_full_namespace, "Entity": Entity},
        )

        try:
            Agent.model_rebuild(force=True, _types_namespace=_full_namespace)
        except PydanticUserError:
            pass

    except (ImportError, PydanticUserError):
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "model_rebuild() failed; forward refs may be unresolved.",
            exc_info=True,
        )
        RuntimeState = None  # type: ignore[assignment,misc]




if TYPE_CHECKING:
    from beholders.memory.unified_memory import Memory

# Populated by _bootstrap(); declared here so attribute lookups have a home.
RuntimeState: Any = None
Entity: Any = None


__version__ = "1.15.30"

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "Memory": ("beholders.memory.unified_memory", "Memory"),
}

# Every name the engine bootstrap defines. Touch one and it imports.
_ENGINE_NAMES = frozenset(
    {
        "Agent",
        "BaseAgent",
        "BaseAgentExecutor",
        "BaseLLM",
        "BaseTool",
        "Crew",
        "CrewOutput",
        "CrewStructuredTool",
        "ExecutionContext",
        "LLMCallHookContext",
        "LLM",
        "LLMGuardrail",
        "PlanningConfig",
        "Process",
        "StandardPromptResult",
        "SystemPromptResult",
        "Task",
        "TaskOutput",
        "ToolResult",
        "ToolsHandler",
        "Knowledge",
        "RuntimeState",
        "Entity",
    }
)


def __getattr__(name: str) -> Any:
    """Import an engine name — or a heavy module such as ``Memory`` — on first use."""
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        val = getattr(importlib.import_module(module_path), attr)
        globals()[name] = val
        return val
    if name in _ENGINE_NAMES:
        _bootstrap()
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(
                f"module 'beholders' has no attribute {name!r} "
                "(the engine failed to import; see the warnings above)"
            ) from None
    raise AttributeError(f"module 'beholders' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _ENGINE_NAMES | set(_LAZY_IMPORTS))


__all__ = [
    "LLM",
    "Agent",
    "BaseLLM",
    "Crew",
    "CrewOutput",
    "Entity",
    "ExecutionContext",
    "Flow",
    "Knowledge",
    "LLMGuardrail",
    "Memory",
    "PlanningConfig",
    "Process",
    "RuntimeState",
    "Task",
    "TaskOutput",
    "__version__",
]
