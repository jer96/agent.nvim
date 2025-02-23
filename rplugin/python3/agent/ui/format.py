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

    def wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit within a specified width.

        Args:
            text: The text to wrap
            width: The maximum width for each line

        Returns:
            List[str]: The wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            # Check if adding this word would exceed the width
            word_length = len(word)
            if current_length + word_length + len(current_line) <= width:
                current_line.append(word)
                current_length += word_length
            else:
                # Line is full, start a new one
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length

        # Don't forget the last line
        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text]

    def ensure_content_spacing(self, lines: List[str]) -> List[str]:
        """Ensures proper spacing for any formatted content.
        Args:
            lines: The formatted lines to check
        Returns:
            List[str]: Lines with proper spacing
        """
        if not lines:
            return lines

        # Ensure content starts with a non-empty line
        while lines and not lines[0]:
            lines.pop(0)

        # Ensure content ends with exactly one empty line
        while lines and not lines[-1]:
            lines.pop()
        lines.append("")

        return lines

    def format_message(self, message: Message) -> List[str]:
        """Format a complete message including role header and content."""
        lines = []
        lines.extend(self._format_role_header(message.role))
        lines.extend(self.format_content(message.content))
        return self.ensure_content_spacing(lines)

    def _format_role_header(self, role: str) -> List[str]:
        """Format the role header with proper padding and styling."""
        role_upper = role.upper()
        # Use different emojis for different roles
        emoji = "💬" if role.lower() == "user" else "🤖"
        # Left align with single emoji
        line = f"{emoji} {role_upper}"
        return [line, ""]

    def format_content(self, content: ContentType | List[ContentType]) -> List[str]:
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
                list_content.extend(self.format_content(c))
            return list_content
        return self._format_text(str(content))

    def _format_text(self, text: str) -> List[str]:
        """Format plain text content."""
        return text.strip().splitlines()

    def _format_tool_call(self, tool_call: ToolCall) -> List[str]:
        """Format a tool call with proper markdown formatting."""
        lines = [
            "🛠️ TOOL CALL 🛠️",
            "",
            f"Name: `{tool_call.name}`",
            "Input:",
        ]
        lines.extend(json.dumps(tool_call.input, indent=2).splitlines())
        return self.ensure_content_spacing(lines)

    def _format_tool_result(self, result: TextToolResult) -> List[str]:
        """Format a tool result with proper markdown formatting."""
        lines = [
            "📋 Tool Result:",
            "",
        ]
        lines.extend(self._format_text(result.content))
        return self.ensure_content_spacing(lines)

    def format_stream_content(self, text: str, window_width: int) -> List[str]:
        """Format streaming content with proper role prefix."""
        # Start with the role header
        formatted_lines = ["", "🤖 Assistant", ""]

        # Split into lines and add directly
        content_lines = text.strip().splitlines()
        formatted_lines.extend(content_lines)

        return self.ensure_content_spacing(formatted_lines)

    def format_chat_tool_call(self, tool_call: ToolCall) -> List[str]:
        """Format a tool call for chat display."""
        lines = [
            "🔧 Tool Call:",
            "",
            f"  Name: {tool_call.name}",
            "  Parameters:",
        ]
        # Format parameters as YAML-style indented list
        for name, value in tool_call.input.items():
            lines.append(f"    {name}: {value}")
        return self.ensure_content_spacing(lines)
