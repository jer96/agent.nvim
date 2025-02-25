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

    def format_message(self, message: Message, start_line: int) -> List[UIElement]:
        """Format a complete message including role header and content."""
        elements = []

        # Add role header element with proper spacing
        header_element = MessageElement(role=message.role, start_line=start_line)
        elements.append(header_element)

        # For user messages, add an empty line after the header for consistent spacing
        if message.role == "user":
            elements.append(TextElement(text="", start_line=start_line + len(header_element.lines)))
            next_line = start_line + len(header_element.lines) + 1
        else:
            next_line = start_line + len(header_element.lines)

        # Add content elements
        content_elements = self.format_content(message.content, next_line)
        elements.extend(content_elements)

        return elements

    def format_content(self, content: ContentType | List[ContentType], start_line: int) -> List[UIElement]:
        """Format a single content item into UI elements."""
        elements = []

        if isinstance(content, (str, TextContent)):
            text = content if isinstance(content, str) else content.text
            elements.append(TextElement(text=text, start_line=start_line))
        elif isinstance(content, ToolCall):
            elements.append(ToolCallElement(tool_call=content, start_line=start_line))
        elif isinstance(content, TextToolResult):
            elements.append(ToolResultElement(result=content, start_line=start_line))
        elif isinstance(content, list):
            current_line = start_line
            for c in content:
                content_elements = self.format_content(c, current_line)
                elements.extend(content_elements)
                current_line += sum(len(elem.lines) for elem in content_elements)
        else:
            elements.append(TextElement(text=str(content), start_line=start_line))

        return elements

    def format_stream_content(self, text: str, start_line: int) -> List[UIElement]:
        """Format streaming content with proper role prefix."""
        return [StreamElement(text=text, start_line=start_line)]
