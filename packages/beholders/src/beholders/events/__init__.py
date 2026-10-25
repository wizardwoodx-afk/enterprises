"""Beholders events system for monitoring and extending agent behavior.

This module provides the event infrastructure that allows users to:
- Monitor agent, task, and crew execution
- Track memory operations and performance
- Build custom logging and analytics
- Extend Beholders with custom event handlers
- Declare handler dependencies for ordered execution

Event type classes are lazy-loaded on first access to avoid importing
~12 Pydantic model modules (and their transitive deps) at package init time.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from beholders.events.base_event_listener import BaseEventListener
from beholders.events.depends import Depends
from beholders.events.event_bus import beholders_event_bus
from beholders.events.handler_graph import CircularDependencyError


if TYPE_CHECKING:
    from beholders.events.types.agent_events import (
        AgentEvaluationCompletedEvent,
        AgentEvaluationFailedEvent,
        AgentEvaluationStartedEvent,
        AgentExecutionCompletedEvent,
        AgentExecutionErrorEvent,
        AgentExecutionStartedEvent,
        LiteAgentExecutionCompletedEvent,
        LiteAgentExecutionErrorEvent,
        LiteAgentExecutionStartedEvent,
    )
    from beholders.events.types.checkpoint_events import (
        CheckpointBaseEvent,
        CheckpointCompletedEvent,
        CheckpointFailedEvent,
        CheckpointForkBaseEvent,
        CheckpointForkCompletedEvent,
        CheckpointForkStartedEvent,
        CheckpointPrunedEvent,
        CheckpointRestoreBaseEvent,
        CheckpointRestoreCompletedEvent,
        CheckpointRestoreFailedEvent,
        CheckpointRestoreStartedEvent,
        CheckpointStartedEvent,
    )
    from beholders.events.types.crew_events import (
        CrewKickoffCompletedEvent,
        CrewKickoffFailedEvent,
        CrewKickoffStartedEvent,
        CrewTestCompletedEvent,
        CrewTestFailedEvent,
        CrewTestResultEvent,
        CrewTestStartedEvent,
        CrewTrainCompletedEvent,
        CrewTrainFailedEvent,
        CrewTrainStartedEvent,
    )
    from beholders.events.types.flow_events import (
        ConversationMessageAddedEvent,
        ConversationRouteSelectedEvent,
        ConversationTurnCompletedEvent,
        ConversationTurnFailedEvent,
        ConversationTurnStartedEvent,
        FlowCreatedEvent,
        FlowEvent,
        FlowFailedEvent,
        FlowFinishedEvent,
        FlowPlotEvent,
        FlowStartedEvent,
        HumanFeedbackReceivedEvent,
        HumanFeedbackRequestedEvent,
        MethodExecutionFailedEvent,
        MethodExecutionFinishedEvent,
        MethodExecutionStartedEvent,
    )
    from beholders.events.types.knowledge_events import (
        KnowledgeQueryCompletedEvent,
        KnowledgeQueryFailedEvent,
        KnowledgeQueryStartedEvent,
        KnowledgeRetrievalCompletedEvent,
        KnowledgeRetrievalStartedEvent,
        KnowledgeSearchQueryFailedEvent,
    )
    from beholders.events.types.llm_events import (
        ContextWindowSummarizationCompletedEvent,
        ContextWindowSummarizationFailedEvent,
        ContextWindowSummarizationStartedEvent,
        LLMCallCompletedEvent,
        LLMCallFailedEvent,
        LLMCallStartedEvent,
        LLMStreamChunkEvent,
    )
    from beholders.events.types.llm_guardrail_events import (
        LLMGuardrailCompletedEvent,
        LLMGuardrailStartedEvent,
    )
    from beholders.events.types.logging_events import (
        AgentLogsExecutionEvent,
        AgentLogsStartedEvent,
    )
    from beholders.events.types.mcp_events import (
        MCPConfigFetchFailedEvent,
        MCPConnectionCompletedEvent,
        MCPConnectionFailedEvent,
        MCPConnectionStartedEvent,
        MCPToolExecutionCompletedEvent,
        MCPToolExecutionFailedEvent,
        MCPToolExecutionStartedEvent,
    )
    from beholders.events.types.memory_events import (
        MemoryQueryCompletedEvent,
        MemoryQueryFailedEvent,
        MemoryQueryStartedEvent,
        MemoryRetrievalCompletedEvent,
        MemoryRetrievalFailedEvent,
        MemoryRetrievalStartedEvent,
        MemorySaveCompletedEvent,
        MemorySaveFailedEvent,
        MemorySaveStartedEvent,
    )
    from beholders.events.types.observation_events import (
        PlanStepCompletedEvent,
        PlanStepEvent,
        PlanStepStartedEvent,
    )
    from beholders.events.types.reasoning_events import (
        AgentReasoningCompletedEvent,
        AgentReasoningFailedEvent,
        AgentReasoningStartedEvent,
        ReasoningEvent,
    )
    from beholders.events.types.skill_events import (
        SkillActivatedEvent,
        SkillDiscoveryCompletedEvent,
        SkillDiscoveryStartedEvent,
        SkillEvent,
        SkillLoadFailedEvent,
        SkillLoadedEvent,
        SkillUsedEvent,
    )
    from beholders.events.types.task_events import (
        TaskCompletedEvent,
        TaskEvaluationEvent,
        TaskFailedEvent,
        TaskStartedEvent,
    )
    from beholders.events.types.tool_usage_events import (
        ToolExecutionErrorEvent,
        ToolFailureDetectedEvent,
        ToolSelectionErrorEvent,
        ToolUsageErrorEvent,
        ToolUsageEvent,
        ToolUsageFinishedEvent,
        ToolUsageStartedEvent,
        ToolValidateInputErrorEvent,
    )

_LAZY_EVENT_MAPPING: dict[str, str] = {
    "AgentEvaluationCompletedEvent": "beholders.events.types.agent_events",
    "AgentEvaluationFailedEvent": "beholders.events.types.agent_events",
    "AgentEvaluationStartedEvent": "beholders.events.types.agent_events",
    "AgentExecutionCompletedEvent": "beholders.events.types.agent_events",
    "AgentExecutionErrorEvent": "beholders.events.types.agent_events",
    "AgentExecutionStartedEvent": "beholders.events.types.agent_events",
    "LiteAgentExecutionCompletedEvent": "beholders.events.types.agent_events",
    "LiteAgentExecutionErrorEvent": "beholders.events.types.agent_events",
    "LiteAgentExecutionStartedEvent": "beholders.events.types.agent_events",
    "CheckpointBaseEvent": "beholders.events.types.checkpoint_events",
    "CheckpointCompletedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointFailedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointForkBaseEvent": "beholders.events.types.checkpoint_events",
    "CheckpointForkCompletedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointForkStartedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointPrunedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointRestoreBaseEvent": "beholders.events.types.checkpoint_events",
    "CheckpointRestoreCompletedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointRestoreFailedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointRestoreStartedEvent": "beholders.events.types.checkpoint_events",
    "CheckpointStartedEvent": "beholders.events.types.checkpoint_events",
    "CrewKickoffCompletedEvent": "beholders.events.types.crew_events",
    "CrewKickoffFailedEvent": "beholders.events.types.crew_events",
    "CrewKickoffStartedEvent": "beholders.events.types.crew_events",
    "CrewTestCompletedEvent": "beholders.events.types.crew_events",
    "CrewTestFailedEvent": "beholders.events.types.crew_events",
    "CrewTestResultEvent": "beholders.events.types.crew_events",
    "CrewTestStartedEvent": "beholders.events.types.crew_events",
    "CrewTrainCompletedEvent": "beholders.events.types.crew_events",
    "CrewTrainFailedEvent": "beholders.events.types.crew_events",
    "CrewTrainStartedEvent": "beholders.events.types.crew_events",
    "ConversationMessageAddedEvent": "beholders.events.types.flow_events",
    "ConversationRouteSelectedEvent": "beholders.events.types.flow_events",
    "ConversationTurnCompletedEvent": "beholders.events.types.flow_events",
    "ConversationTurnFailedEvent": "beholders.events.types.flow_events",
    "ConversationTurnStartedEvent": "beholders.events.types.flow_events",
    "FlowCreatedEvent": "beholders.events.types.flow_events",
    "FlowEvent": "beholders.events.types.flow_events",
    "FlowFailedEvent": "beholders.events.types.flow_events",
    "FlowFinishedEvent": "beholders.events.types.flow_events",
    "FlowPlotEvent": "beholders.events.types.flow_events",
    "FlowStartedEvent": "beholders.events.types.flow_events",
    "HumanFeedbackReceivedEvent": "beholders.events.types.flow_events",
    "HumanFeedbackRequestedEvent": "beholders.events.types.flow_events",
    "MethodExecutionFailedEvent": "beholders.events.types.flow_events",
    "MethodExecutionFinishedEvent": "beholders.events.types.flow_events",
    "MethodExecutionStartedEvent": "beholders.events.types.flow_events",
    "KnowledgeQueryCompletedEvent": "beholders.events.types.knowledge_events",
    "KnowledgeQueryFailedEvent": "beholders.events.types.knowledge_events",
    "KnowledgeQueryStartedEvent": "beholders.events.types.knowledge_events",
    "KnowledgeRetrievalCompletedEvent": "beholders.events.types.knowledge_events",
    "KnowledgeRetrievalStartedEvent": "beholders.events.types.knowledge_events",
    "KnowledgeSearchQueryFailedEvent": "beholders.events.types.knowledge_events",
    "ContextWindowSummarizationCompletedEvent": "beholders.events.types.llm_events",
    "ContextWindowSummarizationFailedEvent": "beholders.events.types.llm_events",
    "ContextWindowSummarizationStartedEvent": "beholders.events.types.llm_events",
    "LLMCallCompletedEvent": "beholders.events.types.llm_events",
    "LLMCallFailedEvent": "beholders.events.types.llm_events",
    "LLMCallStartedEvent": "beholders.events.types.llm_events",
    "LLMStreamChunkEvent": "beholders.events.types.llm_events",
    "LLMGuardrailCompletedEvent": "beholders.events.types.llm_guardrail_events",
    "LLMGuardrailStartedEvent": "beholders.events.types.llm_guardrail_events",
    "AgentLogsExecutionEvent": "beholders.events.types.logging_events",
    "AgentLogsStartedEvent": "beholders.events.types.logging_events",
    "MCPConfigFetchFailedEvent": "beholders.events.types.mcp_events",
    "MCPConnectionCompletedEvent": "beholders.events.types.mcp_events",
    "MCPConnectionFailedEvent": "beholders.events.types.mcp_events",
    "MCPConnectionStartedEvent": "beholders.events.types.mcp_events",
    "MCPToolExecutionCompletedEvent": "beholders.events.types.mcp_events",
    "MCPToolExecutionFailedEvent": "beholders.events.types.mcp_events",
    "MCPToolExecutionStartedEvent": "beholders.events.types.mcp_events",
    "MemoryQueryCompletedEvent": "beholders.events.types.memory_events",
    "MemoryQueryFailedEvent": "beholders.events.types.memory_events",
    "MemoryQueryStartedEvent": "beholders.events.types.memory_events",
    "MemoryRetrievalCompletedEvent": "beholders.events.types.memory_events",
    "MemoryRetrievalFailedEvent": "beholders.events.types.memory_events",
    "MemoryRetrievalStartedEvent": "beholders.events.types.memory_events",
    "MemorySaveCompletedEvent": "beholders.events.types.memory_events",
    "MemorySaveFailedEvent": "beholders.events.types.memory_events",
    "MemorySaveStartedEvent": "beholders.events.types.memory_events",
    "PlanStepCompletedEvent": "beholders.events.types.observation_events",
    "PlanStepEvent": "beholders.events.types.observation_events",
    "PlanStepStartedEvent": "beholders.events.types.observation_events",
    "AgentReasoningCompletedEvent": "beholders.events.types.reasoning_events",
    "AgentReasoningFailedEvent": "beholders.events.types.reasoning_events",
    "AgentReasoningStartedEvent": "beholders.events.types.reasoning_events",
    "ReasoningEvent": "beholders.events.types.reasoning_events",
    "SkillActivatedEvent": "beholders.events.types.skill_events",
    "SkillDiscoveryCompletedEvent": "beholders.events.types.skill_events",
    "SkillDiscoveryStartedEvent": "beholders.events.types.skill_events",
    "SkillEvent": "beholders.events.types.skill_events",
    "SkillLoadFailedEvent": "beholders.events.types.skill_events",
    "SkillLoadedEvent": "beholders.events.types.skill_events",
    "SkillUsedEvent": "beholders.events.types.skill_events",
    "TaskCompletedEvent": "beholders.events.types.task_events",
    "TaskEvaluationEvent": "beholders.events.types.task_events",
    "TaskFailedEvent": "beholders.events.types.task_events",
    "TaskStartedEvent": "beholders.events.types.task_events",
    "ToolExecutionErrorEvent": "beholders.events.types.tool_usage_events",
    "ToolFailureDetectedEvent": "beholders.events.types.tool_usage_events",
    "ToolSelectionErrorEvent": "beholders.events.types.tool_usage_events",
    "ToolUsageErrorEvent": "beholders.events.types.tool_usage_events",
    "ToolUsageEvent": "beholders.events.types.tool_usage_events",
    "ToolUsageFinishedEvent": "beholders.events.types.tool_usage_events",
    "ToolUsageStartedEvent": "beholders.events.types.tool_usage_events",
    "ToolValidateInputErrorEvent": "beholders.events.types.tool_usage_events",
}

_extension_exports: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """Lazy import for event types and registered extensions."""
    if name in _LAZY_EVENT_MAPPING:
        module_path = _LAZY_EVENT_MAPPING[name]
        module = importlib.import_module(module_path)
        val = getattr(module, name)
        globals()[name] = val  # cache for subsequent access
        return val

    if name in _extension_exports:
        value = _extension_exports[name]
        if isinstance(value, str):
            module_path, _, attr_name = value.rpartition(".")
            if module_path:
                module = importlib.import_module(module_path)
                return getattr(module, attr_name)
            return importlib.import_module(value)
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "AgentEvaluationCompletedEvent",
    "AgentEvaluationFailedEvent",
    "AgentEvaluationStartedEvent",
    "AgentExecutionCompletedEvent",
    "AgentExecutionErrorEvent",
    "AgentExecutionStartedEvent",
    "AgentLogsExecutionEvent",
    "AgentLogsStartedEvent",
    "AgentReasoningCompletedEvent",
    "AgentReasoningFailedEvent",
    "AgentReasoningStartedEvent",
    "BaseEventListener",
    "CheckpointBaseEvent",
    "CheckpointCompletedEvent",
    "CheckpointFailedEvent",
    "CheckpointForkBaseEvent",
    "CheckpointForkCompletedEvent",
    "CheckpointForkStartedEvent",
    "CheckpointPrunedEvent",
    "CheckpointRestoreBaseEvent",
    "CheckpointRestoreCompletedEvent",
    "CheckpointRestoreFailedEvent",
    "CheckpointRestoreStartedEvent",
    "CheckpointStartedEvent",
    "CircularDependencyError",
    "ContextWindowSummarizationCompletedEvent",
    "ContextWindowSummarizationFailedEvent",
    "ContextWindowSummarizationStartedEvent",
    "ConversationMessageAddedEvent",
    "ConversationRouteSelectedEvent",
    "ConversationTurnCompletedEvent",
    "ConversationTurnFailedEvent",
    "ConversationTurnStartedEvent",
    "CrewKickoffCompletedEvent",
    "CrewKickoffFailedEvent",
    "CrewKickoffStartedEvent",
    "CrewTestCompletedEvent",
    "CrewTestFailedEvent",
    "CrewTestResultEvent",
    "CrewTestStartedEvent",
    "CrewTrainCompletedEvent",
    "CrewTrainFailedEvent",
    "CrewTrainStartedEvent",
    "Depends",
    "FlowCreatedEvent",
    "FlowEvent",
    "FlowFailedEvent",
    "FlowFinishedEvent",
    "FlowPlotEvent",
    "FlowStartedEvent",
    "HumanFeedbackReceivedEvent",
    "HumanFeedbackRequestedEvent",
    "KnowledgeQueryCompletedEvent",
    "KnowledgeQueryFailedEvent",
    "KnowledgeQueryStartedEvent",
    "KnowledgeRetrievalCompletedEvent",
    "KnowledgeRetrievalStartedEvent",
    "KnowledgeSearchQueryFailedEvent",
    "LLMCallCompletedEvent",
    "LLMCallFailedEvent",
    "LLMCallStartedEvent",
    "LLMGuardrailCompletedEvent",
    "LLMGuardrailStartedEvent",
    "LLMStreamChunkEvent",
    "LiteAgentExecutionCompletedEvent",
    "LiteAgentExecutionErrorEvent",
    "LiteAgentExecutionStartedEvent",
    "MCPConfigFetchFailedEvent",
    "MCPConnectionCompletedEvent",
    "MCPConnectionFailedEvent",
    "MCPConnectionStartedEvent",
    "MCPToolExecutionCompletedEvent",
    "MCPToolExecutionFailedEvent",
    "MCPToolExecutionStartedEvent",
    "MemoryQueryCompletedEvent",
    "MemoryQueryFailedEvent",
    "MemoryQueryStartedEvent",
    "MemoryRetrievalCompletedEvent",
    "MemoryRetrievalFailedEvent",
    "MemoryRetrievalStartedEvent",
    "MemorySaveCompletedEvent",
    "MemorySaveFailedEvent",
    "MemorySaveStartedEvent",
    "MethodExecutionFailedEvent",
    "MethodExecutionFinishedEvent",
    "MethodExecutionStartedEvent",
    "PlanStepCompletedEvent",
    "PlanStepEvent",
    "PlanStepStartedEvent",
    "ReasoningEvent",
    "SkillActivatedEvent",
    "SkillDiscoveryCompletedEvent",
    "SkillDiscoveryStartedEvent",
    "SkillEvent",
    "SkillLoadFailedEvent",
    "SkillLoadedEvent",
    "SkillUsedEvent",
    "TaskCompletedEvent",
    "TaskEvaluationEvent",
    "TaskFailedEvent",
    "TaskStartedEvent",
    "ToolExecutionErrorEvent",
    "ToolFailureDetectedEvent",
    "ToolSelectionErrorEvent",
    "ToolUsageErrorEvent",
    "ToolUsageEvent",
    "ToolUsageFinishedEvent",
    "ToolUsageStartedEvent",
    "ToolValidateInputErrorEvent",
    "_extension_exports",
    "beholders_event_bus",
]
