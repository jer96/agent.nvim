import json
from typing import List

from ..llm.types import (
    ContentType,
    Message,
    TextContent,
    TextToolResult,
    ToolCall,
)


class MessageFormatter:
    """Handles formatting of different message types into displayable text."""

    def __init__(self, window_width: int = 80):
        self.window_width = window_width

    def format_message(self, message: Message) -> List[str]:
        """Format a complete message including role header and content."""
        lines = []
        lines.extend(self._format_role_header(message.role))
        lines.extend(self._format_content(message.content))
        if not lines[-1] == "":
            lines.append("")
        return lines

    def _format_role_header(self, role: str) -> List[str]:
        """Format the role header with proper padding and styling."""
        role_upper = role.upper()
        # Use different emojis for different roles
        emoji = "💬" if role.lower() == "user" else "🤖"
        # Left align with single emoji
        line = f"{emoji} {role_upper}"
        return [line, ""]

    def _format_content(self, content: ContentType | List[ContentType]) -> List[str]:
        """Format a single content item into displayable lines."""
        if isinstance(content, str):
            return self._format_text(content)
        elif isinstance(content, TextContent):
            return self._format_text(content.text)
        elif isinstance(content, ToolCall):
            return self._format_tool_call(content)
        elif isinstance(content, TextToolResult):
            return self._format_tool_result(content)
        elif isinstance(content, List):
            list_content = []
            for c in content:
                list_content.extend(self._format_content(c))
            return list_content
        return self._format_text(str(content))

    def _format_text(self, text: str) -> List[str]:
        """Format plain text content."""
        return text.strip().split("\n")

    def _format_tool_call(self, tool_call: ToolCall) -> List[str]:
        """Format a tool call with proper markdown formatting."""
        lines = [
            "🛠️ TOOL CALL 🛠️",
            "",
            f"Name: `{tool_call.name}`",
            "Input:",
            "```",
        ]
        lines.extend(json.dumps(tool_call.input, indent=2).splitlines())
        lines.extend(["```", ""])
        return lines

    def _format_tool_result(self, result: TextToolResult) -> List[str]:
        """Format a tool result with proper markdown formatting."""
        status_emoji = "❌" if result.is_error else "✅"
        lines = ["⚡ TOOL RESULT ⚡", "", f"{status_emoji} Status: {'Error' if result.is_error else 'Success'}", ""]
        lines.extend(self._format_text(result.content))
        return lines
