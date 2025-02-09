import json
from typing import List

from ..llm.types import (
    ContentType,
    Message,
    TextContent,
    ToolCall,
    ToolResult,
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
        # Use h1 for user and h2 for assistant
        heading = "#" if role.lower() == "user" else "##"
        # Calculate padding for centering the text portion only
        text_width = len(role_upper)
        padding_size = len(heading) + 1  # account for heading and space
        padding = (self.window_width - text_width - padding_size) // 2
        centered_line = f"{heading} {' ' * padding}{role_upper}"
        return ["---", centered_line, "---", ""]

    def _format_content(self, content: ContentType | List[ContentType]) -> List[str]:
        """Format a single content item into displayable lines."""
        if isinstance(content, str):
            return self._format_text(content)
        elif isinstance(content, TextContent):
            return self._format_text(content.text)
        elif isinstance(content, ToolCall):
            return self._format_tool_call(content)
        elif isinstance(content, ToolResult):
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
            "### TOOL CALL",
            "",
            f"Name: `{tool_call.name}`",
            "Input:",
            "```",
        ]
        lines.extend(json.dumps(tool_call.input, indent=2).splitlines())
        lines.extend(["```", ""])
        return lines

    def _format_tool_result(self, result: ToolResult) -> List[str]:
        """Format a tool result with proper markdown formatting."""
        lines = ["### TOOL RESULT", "", f"> Error: {result.is_error}", ""]
        lines.extend(self._format_text(result.content))
        return lines
