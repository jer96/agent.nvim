import logging
from typing import Callable, Dict, List, Optional

from ..context import AgentContext
from ..llm.types import Message, TextToolResult, ToolCall
from .handlers import EditFileHandler, ToolHandler

logger = logging.getLogger(__name__)


HandlerFactory = Callable[[AgentContext], ToolHandler]

DEFAULT_HANDLER_FACTORIES: List[HandlerFactory] = [
    lambda context: EditFileHandler(context),
]


class ToolRegistry:
    """Registry for tool handlers"""

    def __init__(self, context: AgentContext):
        self._context = context
        self._handlers: Dict[str, ToolHandler] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register the default set of tool handlers"""
        for handler_factory in DEFAULT_HANDLER_FACTORIES:
            self.register_handler(handler_factory(self._context))

    def register_handler(self, handler: ToolHandler):
        """Register a new tool handler"""
        if not isinstance(handler, ToolHandler):
            raise TypeError(f"Handler must be an instance of ToolHandler, got {type(handler)}")

        self._handlers[handler.name] = handler
        logger.debug(f"Registered handler for tool: {handler.name}")

    def reset_tool_handlers(self):
        for handler in self._handlers.values():
            handler.reset_handler_state()

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        """Get a handler for a given tool name"""
        return self._handlers.get(name)

    def handle_messages(self, messages: List[Message]):
        def handle_tool_content(content):
            if isinstance(content, ToolCall):
                self._handle_tool_call(content)
            elif isinstance(content, TextToolResult):
                self._handle_tool_result(content)
            elif isinstance(content, List):
                for c in content:
                    handle_tool_content(c)

        for msg in messages:
            handle_tool_content(msg.content)

        self.reset_tool_handlers()

    def _handle_tool_call(self, tool_call: ToolCall) -> Optional[Dict]:
        """Process a tool call using the appropriate handler"""
        handler = self.get_handler(tool_call.name)
        if handler and handler.can_handle_call(tool_call):
            return handler.handle_call(tool_call)
        return None

    def _handle_tool_result(self, tool_result: TextToolResult) -> Optional[Dict]:
        """Process a tool result using the appropriate handler"""
        # Find handler that can handle this result
        for handler in self._handlers.values():
            if handler.can_handle_result(tool_result):
                return handler.handle_result(tool_result)
        return None
