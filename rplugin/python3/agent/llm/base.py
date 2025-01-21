from abc import ABC, abstractmethod
from typing import Generator, List

from .types import (
    CompletionResponse,
    InferenceConfig,
    Message,
    StreamResponse,
    Tool,
)


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
    ) -> Generator[StreamResponse, None, None]:
        """
        Stream a completion from the LLM.

        Args:
            messages: The conversation history
            config: Optional configuration for the completion

        Returns:
            A generator yielding stream response chunks
        """
        pass
