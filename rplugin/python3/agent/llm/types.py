import uuid
from abc import ABC
from datetime import datetime
from typing import Any, Dict, List, Literal, Union

from pydantic import BaseModel, Field

from .constants import (
    FILE_CONTEXT_PROMPT,
    MAX_TOKENS,
    SYSTEM_PROMPT,
    TEMPERATURE,
    create_file_context_prompt,
)


class Tool(BaseModel):
    """Definition of a tool that can be used by the LLM."""

    name: str
    description: str
    input_schema: dict[str, Any]


class InferenceConfig(BaseModel):
    """Configuration for LLM completion requests."""

    temperature: float = Field(default=TEMPERATURE, ge=0, le=1)
    max_tokens: int = Field(default=MAX_TOKENS, gt=0)
    system_prompt: str | None = SYSTEM_PROMPT
    model: str | None = None


class ToolCall(BaseModel):
    """Represents a tool call made by the LLM."""

    type: str = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class ToolResult(BaseModel, ABC):
    """Represents the result of a tool call."""

    type: str = "tool_result"
    tool_use_id: str
    is_error: bool = False
    content: str


class TextContent(BaseModel):
    """Represents a text response from the LLM."""

    type: str = "text"
    text: str


ContentType = Union[str, TextContent, ToolCall, ToolResult]


class CompletionResponse(BaseModel):
    """Complete response from an LLM, including both text and tool interactions."""

    content: List[ContentType]


MessageRole = Literal["system", "user", "assistant"]


class Message(BaseModel):
    """Base message model for all LLM interactions."""

    role: MessageRole
    content: Union[ContentType, List[ContentType]]


class Conversation(BaseModel):
    """Model representing a stored conversation."""

    id: str
    timestamp: datetime
    messages: List[Message]


class ConversationMetadata(BaseModel):
    """Model for conversation listing."""

    id: str
    timestamp: datetime
    message_count: int


class FileContext(BaseModel):
    active_buffers: List[str]
    files: List[str]

    def get_prompt(self):
        buf_prompts = [create_file_context_prompt(buf, True) for buf in self.active_buffers]
        file_prompts = [create_file_context_prompt(file) for file in self.files]
        combined_prompt = "\n".join(buf_prompts + file_prompts)
        return FILE_CONTEXT_PROMPT.replace("{{FILES}}", combined_prompt).strip()

    def get_read_file_tool_calls(self):
        return [
            ToolCall(id=str(uuid.uuid4()), name="read_file", input={"path": file})
            for file in self.active_buffers + self.files
        ]
