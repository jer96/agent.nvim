from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from ..llm.types import Message


class UIEventType(Enum):
    UPDATE_MESSAGES = auto()
    CLEAR_INPUT = auto()
    CLOSE = auto()
    DELETE_BUFFERS = auto()
    REFRESH_BUFFERS = auto()
    SHOW = auto()
    RESIZE = auto()
    FOCUS_CHAT = auto()


@dataclass
class UIEvent:
    type: UIEventType
    messages: Optional[List[Message]] = None
    is_stream: bool = False

