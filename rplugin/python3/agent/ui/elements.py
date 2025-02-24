import json
from abc import ABC, abstractmethod

from pydantic import BaseModel

from ..llm.types import TextToolResult, ToolCall


class UIMarkData(BaseModel):
    """Data for creating extmarks in the buffer"""

    mark_type: str
    mark_role: str
    sign_text: str
    start_line: int
    end_line: int


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
        lines = ["Tool Call", "", f"Name: `{self.tool_call.name}`", f"Parameters: {param_names}", "{{{1"]
        input_lines = json.dumps(self.tool_call.input, indent=2).splitlines()
        lines.extend(input_lines)
        lines.append("}}}1")
        lines.append("")  # Ensure spacing
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        return [
            UIMarkData(
                mark_type="tool",
                mark_role="pending",
                sign_text="",
                start_line=self.start_line,
                end_line=self.start_line,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class ToolResultElement(UIElement):
    result: TextToolResult

    @property
    def lines(self) -> list[str]:
        status = "❌" if self.result.is_error else "✅"
        lines = [f"Tool Result: {status}", "", "Result:", "{{{1"]
        result_lines = self.result.content.strip().splitlines()
        lines.extend(result_lines)
        lines.append("}}}1")
        lines.append("")  # Ensure spacing
        return lines

    @property
    def marks(self) -> list[UIMarkData] | None:
        return [
            UIMarkData(
                mark_type="tool",
                mark_role="result",
                sign_text="",
                start_line=self.start_line,
                end_line=self.start_line,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None


class TextElement(UIElement):
    text: str

    @property
    def lines(self) -> list[str]:
        return self.text.strip().splitlines()

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
        return self.text.strip().splitlines()

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
        return [self.role.capitalize(), ""]

    @property
    def marks(self) -> list[UIMarkData] | None:
        return [
            UIMarkData(
                mark_type="message",
                mark_role=self.role,
                sign_text="󰍪",
                start_line=self.start_line,
                end_line=self.start_line,
            )
        ]

    @property
    def folds(self) -> list[UIFoldData] | None:
        return None
