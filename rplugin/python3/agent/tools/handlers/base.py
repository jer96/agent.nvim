from abc import ABC, abstractmethod
from typing import Dict

from ...context import AgentContext
from ...llm.types import TextToolResult, ToolCall


class ToolHandler(ABC):
    """Base class for tool handlers"""

    tool_use_map: Dict[str, ToolCall]

    def __init__(self, context: AgentContext):
        self._tool_use_map = {}
        self._context = context

    def reset_handler_state(self):
        self._tool_use_map = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool this handler manages"""
        pass

    def can_handle_call(self, tool_call: ToolCall) -> bool:
        """Check if this handler can process the given tool call"""
        return tool_call.name == self.name

    def can_handle_result(self, tool_result: TextToolResult) -> bool:
        """Check if this handler can process the given tool result"""
        return tool_result.tool_use_id in self._tool_use_map

    def handle_call(self, tool_call: ToolCall) -> None:
        """Handle the tool call"""
        self._tool_use_map[tool_call.id] = tool_call

    @abstractmethod
    def handle_result(self, tool_result: TextToolResult) -> None:
        """Handle the tool result

        Returns:
            Dict containing handler-specific data and any required UI actions
        """
        pass
