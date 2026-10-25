from beholders.events.types.a2a_events import (
    A2AAgentCardFetchedEvent,
    A2AArtifactReceivedEvent,
    A2AAuthenticationFailedEvent,
    A2AConnectionErrorEvent,
    A2AConversationCompletedEvent,
    A2AConversationStartedEvent,
    A2ADelegationCompletedEvent,
    A2ADelegationStartedEvent,
    A2AMessageSentEvent,
    A2AParallelDelegationCompletedEvent,
    A2AParallelDelegationStartedEvent,
    A2APollingStartedEvent,
    A2APollingStatusEvent,
    A2APushNotificationReceivedEvent,
    A2APushNotificationRegisteredEvent,
    A2APushNotificationSentEvent,
    A2APushNotificationTimeoutEvent,
    A2AResponseReceivedEvent,
    A2AServerTaskCanceledEvent,
    A2AServerTaskCompletedEvent,
    A2AServerTaskFailedEvent,
    A2AServerTaskStartedEvent,
    A2AStreamingChunkEvent,
    A2AStreamingStartedEvent,
)
from beholders.events.types.agent_events import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    LiteAgentExecutionCompletedEvent,
)
from beholders.events.types.checkpoint_events import (
    CheckpointCompletedEvent,
    CheckpointFailedEvent,
    CheckpointForkCompletedEvent,
    CheckpointForkStartedEvent,
    CheckpointPrunedEvent,
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
    FlowFailedEvent,
    FlowFinishedEvent,
    FlowStartedEvent,
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
    PlanStepStartedEvent,
)
from beholders.events.types.reasoning_events import (
    AgentReasoningCompletedEvent,
    AgentReasoningFailedEvent,
    AgentReasoningStartedEvent,
)
from beholders.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from beholders.events.types.tool_usage_events import (
    ToolFailureDetectedEvent,
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)


EventTypes = (
    A2AAgentCardFetchedEvent
    | A2AArtifactReceivedEvent
    | A2AAuthenticationFailedEvent
    | A2AConnectionErrorEvent
    | A2AConversationCompletedEvent
    | A2AConversationStartedEvent
    | A2ADelegationCompletedEvent
    | A2ADelegationStartedEvent
    | A2AMessageSentEvent
    | A2APollingStartedEvent
    | A2APollingStatusEvent
    | A2APushNotificationReceivedEvent
    | A2APushNotificationRegisteredEvent
    | A2APushNotificationSentEvent
    | A2APushNotificationTimeoutEvent
    | A2AResponseReceivedEvent
    | A2AServerTaskCanceledEvent
    | A2AServerTaskCompletedEvent
    | A2AServerTaskFailedEvent
    | A2AServerTaskStartedEvent
    | A2AStreamingChunkEvent
    | A2AStreamingStartedEvent
    | A2AParallelDelegationStartedEvent
    | A2AParallelDelegationCompletedEvent
    | CrewKickoffStartedEvent
    | CrewKickoffCompletedEvent
    | CrewKickoffFailedEvent
    | CrewTestStartedEvent
    | CrewTestCompletedEvent
    | CrewTestFailedEvent
    | CrewTrainStartedEvent
    | CrewTrainCompletedEvent
    | CrewTrainFailedEvent
    | AgentExecutionStartedEvent
    | AgentExecutionCompletedEvent
    | LiteAgentExecutionCompletedEvent
    | TaskStartedEvent
    | TaskCompletedEvent
    | TaskFailedEvent
    | ConversationMessageAddedEvent
    | ConversationRouteSelectedEvent
    | ConversationTurnCompletedEvent
    | ConversationTurnFailedEvent
    | ConversationTurnStartedEvent
    | FlowStartedEvent
    | FlowFinishedEvent
    | FlowFailedEvent
    | MethodExecutionStartedEvent
    | MethodExecutionFinishedEvent
    | MethodExecutionFailedEvent
    | AgentExecutionErrorEvent
    | ToolUsageFinishedEvent
    | ToolUsageErrorEvent
    | ToolFailureDetectedEvent
    | ToolUsageStartedEvent
    | ContextWindowSummarizationStartedEvent
    | ContextWindowSummarizationCompletedEvent
    | ContextWindowSummarizationFailedEvent
    | LLMCallStartedEvent
    | LLMCallCompletedEvent
    | LLMCallFailedEvent
    | LLMStreamChunkEvent
    | LLMGuardrailStartedEvent
    | LLMGuardrailCompletedEvent
    | AgentReasoningStartedEvent
    | AgentReasoningCompletedEvent
    | AgentReasoningFailedEvent
    | KnowledgeRetrievalStartedEvent
    | KnowledgeRetrievalCompletedEvent
    | KnowledgeQueryStartedEvent
    | KnowledgeQueryCompletedEvent
    | KnowledgeQueryFailedEvent
    | KnowledgeSearchQueryFailedEvent
    | MemorySaveStartedEvent
    | MemorySaveCompletedEvent
    | MemorySaveFailedEvent
    | MemoryQueryStartedEvent
    | MemoryQueryCompletedEvent
    | MemoryQueryFailedEvent
    | MemoryRetrievalStartedEvent
    | MemoryRetrievalCompletedEvent
    | MemoryRetrievalFailedEvent
    | PlanStepStartedEvent
    | PlanStepCompletedEvent
    | MCPConnectionStartedEvent
    | MCPConnectionCompletedEvent
    | MCPConnectionFailedEvent
    | MCPToolExecutionStartedEvent
    | MCPToolExecutionCompletedEvent
    | MCPToolExecutionFailedEvent
    | MCPConfigFetchFailedEvent
    | CheckpointStartedEvent
    | CheckpointCompletedEvent
    | CheckpointFailedEvent
    | CheckpointForkStartedEvent
    | CheckpointForkCompletedEvent
    | CheckpointRestoreStartedEvent
    | CheckpointRestoreCompletedEvent
    | CheckpointRestoreFailedEvent
    | CheckpointPrunedEvent
)
