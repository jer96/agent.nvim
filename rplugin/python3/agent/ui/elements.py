import json
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from ..llm.types import TextToolResult, ToolCall
from .constants import FAIL_ICON, MESSAGE_ICON, SUCCESS_ICON, TOOL_ICON


class MarkType(str, Enum):
    MESSAGE_USER = "MessageUser"
    MESSAGE_ASSISTANT = "MessageAssistant"
    MESSAGE_SYSTEM = "MessageSystem"
    TOOL_CALL = "MessageToolCall"
    TOOL_SUCCESS = "MessageToolSuccess"
    TOOL_ERROR = "MessageToolError"


class UIMarkData(BaseModel):
    """Data for creating extmarks in the buffer"""

    highlight_group: MarkType
    sign_text: str
    start: int
    end: int


class UIFoldData(BaseModel):
    """Data for creating folds in the buffer"""

    start_line: int
    end_line: int
    fold_level: int
    manual_fold: bool


class UIElement(BaseModel, ABC):
    """Base class for UI elements that can be formatted with marks and folds"""

    start_line: int = 0

    @property
    @abstractmethod
    def lines(self) -> list[str]:
        """Get the formatted lines for this element"""
        pass

    @property
    @abstractmethod
    def marks(self) -> list[UIMarkData] | None:
        """Get mark data for this element"""
        pass

    @property
    @abstractmethod
    def folds(self) -> list[UIFoldData] | None:
        """Get fold data for this element"""
        pass


class ToolCallElement(UIElement):
    tool_call: ToolCall

    @property
    def lines(self) -> list[str]:
        param_names = ",".join(self.tool_call.input.keys()) if self.tool_call.input else ""
        lines = ["Tool Call", f"Name: `{self.tool_call.name}`", f"Parameters: {param_names}", "{{{1"]
        input_lines = json.dumps(self.tool_call.input, indent=2).splitlines()
        lines.extend(input_lines)
        lines.append("}}}1")
        lines.append("")  # Ensure exactly one space after content
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        return [
            UIMarkData(
                highlight_group=MarkType.TOOL_CALL,
                sign_text=TOOL_ICON,
                start=self.start_line,
                end=self.start_line,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class ToolResultElement(UIElement):
    result: TextToolResult

    @property
    def lines(self) -> list[str]:
        status = "Error" if self.result.is_error else "Success"
        lines = [f"Tool {status}", "{{{1"]
        result_lines = self.result.content.strip().splitlines()
        lines.extend(result_lines)
        lines.append("}}}1")
        lines.append("")  # Ensure exactly one space after content
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        sign_text = FAIL_ICON if self.result.is_error else SUCCESS_ICON
        return [
            UIMarkData(
                highlight_group=MarkType.TOOL_ERROR if self.result.is_error else MarkType.TOOL_SUCCESS,
                start=self.start_line,
                end=self.start_line,
                sign_text=sign_text,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class TextElement(UIElement):
    text: str

    @property
    def lines(self) -> list[str]:
        lines = self.text.strip().splitlines()
        lines.append("")
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        return None

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class StreamElement(UIElement):
    text: str

    @property
    def lines(self) -> list[str]:
        lines = self.text.strip().splitlines()
        lines.append("")
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        return None

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class MessageElement(UIElement):
    role: str

    @property
    def lines(self) -> list[str]:
        # No extra newline after the heading
        if self.role == "assistant":
            return ["Agent"]
        return [self.role.capitalize()]

    @property
    def marks(self) -> list[UIMarkData] | None:
        return [
            UIMarkData(
                highlight_group={
                    "user": MarkType.MESSAGE_USER,
                    "assistant": MarkType.MESSAGE_ASSISTANT,
                    "system": MarkType.MESSAGE_SYSTEM,
                }[self.role],
                start=self.start_line,
                end=self.start_line,
                sign_text=MESSAGE_ICON,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None
