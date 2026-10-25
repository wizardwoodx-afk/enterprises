from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from beholders.tools.agent_tools.ask_question_tool import AskQuestionTool
from beholders.tools.agent_tools.delegate_work_tool import DelegateWorkTool
from beholders.utilities.i18n import I18N_DEFAULT


if TYPE_CHECKING:
    from beholders.agents.agent_builder.base_agent import BaseAgent
    from beholders.tools.base_tool import BaseTool


class AgentTools:
    """Manager class for agent-related tools"""

    def __init__(self, agents: Sequence[BaseAgent]) -> None:
        self.agents = agents

    def tools(self) -> list[BaseTool]:
        """Get all available agent tools"""
        coworkers = ", ".join([f"{agent.role}" for agent in self.agents])

        delegate_tool = DelegateWorkTool(
            agents=self.agents,
            description=I18N_DEFAULT.tools("delegate_work").format(coworkers=coworkers),  # type: ignore
        )

        ask_tool = AskQuestionTool(
            agents=self.agents,
            description=I18N_DEFAULT.tools("ask_question").format(coworkers=coworkers),  # type: ignore
        )

        return [delegate_tool, ask_tool]
