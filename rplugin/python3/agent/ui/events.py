from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from ..llm.types import Message, TextToolResult, ToolCall


class UIEventType(Enum):
    MESSAGES_EVENT = auto()  # For complete messages
    MESSAGE_STREAM_START = auto()  # Start of streaming content
    MESSAGE_STREAM_EVENT = auto()  # For streaming content chunks
    MESSAGE_STREAM_STOP = auto()  # End of streaming content
    CLEAR_INPUT = auto()
    CLOSE = auto()
    DELETE_BUFFERS = auto()
    REFRESH_BUFFERS = auto()
    SHOW = auto()
    RESIZE = auto()
    FOCUS_CHAT = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    TOOL_BATCH = auto()  # For batched tool calls and results


ToolContent = ToolCall | TextToolResult


@dataclass
class UIEvent:
    type: UIEventType
    # TODO: refactor
    messages: Optional[List[Message]] = None
    text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[TextToolResult] = None
    tool_batch: Optional[List[ToolContent]] = None
