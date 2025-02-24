from typing import List

from ..llm.types import (
    ContentType,
    Message,
    TextContent,
    TextToolResult,
    ToolCall,
)
from .elements import (
    MessageElement,
    StreamElement,
    TextElement,
    ToolCallElement,
    ToolResultElement,
    UIElement,
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

        return self.ensure_content_spacing(lines if lines else [text])

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

    def format_message(self, message: Message, start_line: int) -> List[UIElement]:
        """Format a complete message including role header and content."""
        elements = []

        # Add role header element
        header_element = MessageElement(role=message.role, start_line=start_line)
        elements.append(header_element)

        # Add content elements
        content_elements = self.format_content(message.content, start_line + len(header_element.lines))
        elements.extend(content_elements)

        return elements

    def format_role_header(self, role: str) -> List[str]:
        """Format the role header with proper padding and styling."""
        return [role.capitalize(), ""]

    def format_content(self, content: ContentType | List[ContentType], start_line: int) -> List[UIElement]:
        """Format a single content item into UI elements."""
        elements = []

        if isinstance(content, (str, TextContent)):
            text = content if isinstance(content, str) else content.text
            text_lines = self.ensure_content_spacing(self._format_text(text))
            elements.append(TextElement(text="\n".join(text_lines), start_line=start_line))
        elif isinstance(content, ToolCall):
            elements.append(ToolCallElement(tool_call=content, start_line=start_line))
        elif isinstance(content, TextToolResult):
            elements.append(ToolResultElement(result=content, start_line=start_line))
        elif isinstance(content, List):
            current_line = start_line
            for c in content:
                content_elements = self.format_content(c, current_line)
                elements.extend(content_elements)
                # Update current_line based on the added elements
                current_line += sum(len(elem.lines) for elem in content_elements)
        else:
            elements.append(TextElement(text=str(content), start_line=start_line))

        return elements

    def _format_text(self, text: str) -> List[str]:
        """Format plain text content."""
        return text.strip().splitlines()

    def format_stream_content(self, text: str, start_line: int) -> List[UIElement]:
        """Format streaming content with proper role prefix."""
        return [StreamElement(text=text, start_line=start_line)]
