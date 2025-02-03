from abc import ABC, abstractmethod
from typing import Dict

from ...context import AgentContext
from ...llm.types import ToolCall, ToolResult


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

    @abstractmethod
    def can_handle_call(self, tool_call: ToolCall) -> bool:
        """Check if this handler can process the given tool call"""
        pass

    @abstractmethod
    def can_handle_result(self, tool_result: ToolResult) -> bool:
        """Check if this handler can process the given tool result"""
        pass

    @abstractmethod
    def handle_call(self, tool_call: ToolCall) -> None:
        """Handle the tool call

        Returns:
            Dict containing handler-specific data and any required UI actions
        """
        pass

    @abstractmethod
    def handle_result(self, tool_result: ToolResult) -> None:
        """Handle the tool result

        Returns:
            Dict containing handler-specific data and any required UI actions
        """
        pass
