from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncGenerator, Generator, List

from .types import (
    CompletionResponse,
    ContentType,
    InferenceConfig,
    Message,
    Tool,
)


class StreamState(Enum):
    DEFAULT = "default"
    PARSING_MSG = "msg_parse"
    PARSING_TOOL = "tool_parse"


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        """
        Complete a conversation with the LLM.

        Args:
            messages: The conversation history
            tools: Available tools that can be used by the LLM
            config: Optional configuration for the completion

        Returns:
            A completion response containing text and/or tool calls
        """
        pass

    @abstractmethod
    def complete_stream(
        self,
        *,
        messages: List[Message],
        config: InferenceConfig | None,
    ) -> Generator[ContentType, None, None]:
        """
        Stream a completion from the LLM.

        Args:
            messages: The conversation history
            config: Optional configuration for the completion

        Returns:
            A generator yielding stream response chunks
        """
        pass

    @abstractmethod
    async def async_complete(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        """Async version of complete"""
        pass

    @abstractmethod
    async def async_complete_stream(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> AsyncGenerator[ContentType, None]:
        """Async version of complete_stream"""
        pass
