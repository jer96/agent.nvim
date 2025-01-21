import os
from typing import Generator, List

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider
from ..constants import CLAUDE_SONNET
from ..types import CompletionResponse, ContentType, InferenceConfig, Message, TextContent, Tool, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = self._get_client()

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not provided")
        return Anthropic(api_key=api_key)

    def _parse_content(self, response) -> List[ContentType]:
        content_list = []
        for content in response.content:
            if content.type == "text":
                content_list.append(TextContent(text=content.text))
            elif content.type == "tool_use":
                content_list.append(ToolCall(id=content.id, name=content.name, input=content.input))
        return content_list

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(
        self,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        if not self.client:
            raise ValueError("Anthropic client not configured")

        # Use provided config or defaults
        if config is None:
            config = InferenceConfig(model=CLAUDE_SONNET)

        try:
            response = self.client.messages.create(
                system=config.system_prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                model=config.model or CLAUDE_SONNET,
                messages=[msg.model_dump() for msg in messages],
                tools=[tool.model_dump() for tool in tools],
            )

            content = self._parse_content(response)
            return CompletionResponse(content=content)
        except Exception as e:
            raise e

    def complete_stream(
        self,
        *,
        messages: List[Message],
        config: InferenceConfig | None,
    ) -> Generator[str, None, None]:
        if not self.client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.client.messages.create(
                system=config.system_prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                model=config.model or CLAUDE_SONNET,
                messages=[msg.model_dump() for msg in messages],
                stream=True,
            )

            for chunk in response:
                if chunk.type == "content_block_delta" and chunk.delta and chunk.delta.text:
                    yield chunk.delta.text

        except Exception as e:
            raise e
