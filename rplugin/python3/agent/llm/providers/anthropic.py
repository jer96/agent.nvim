import json
import logging
import os
from typing import AsyncGenerator, Generator, List

from anthropic import Anthropic, AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider, StreamState
from ..constants import CLAUDE_SONNET
from ..types import CompletionResponse, ContentType, InferenceConfig, Message, TextContent, Tool, ToolCall

logger = logging.getLogger(__name__)

logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.sync_client = self._get_sync_client()
        self.async_client = self._get_async_client()

    def _get_sync_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not provided")
        return Anthropic(api_key=api_key)

    def _get_async_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not provided")
        return AsyncAnthropic(api_key=api_key)

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
        if not self.sync_client:
            raise ValueError("Anthropic client not configured")

        # Use provided config or defaults
        if config is None:
            config = InferenceConfig(model=CLAUDE_SONNET)

        try:
            response = self.sync_client.messages.create(
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
    ) -> Generator[ContentType, None, None]:
        if not self.sync_client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.sync_client.messages.create(
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

    async def async_complete(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        if not self.async_client:
            raise ValueError("Anthropic async client not configured")

        if config is None:
            config = InferenceConfig(model=CLAUDE_SONNET)

        try:
            response = await self.async_client.messages.create(
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

    async def async_complete_stream(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> AsyncGenerator[ContentType, None]:
        if not self.async_client:
            raise ValueError("Anthropic async client not configured")

        try:
            response = await self.async_client.messages.create(
                system=config.system_prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                model=config.model or CLAUDE_SONNET,
                messages=[msg.model_dump() for msg in messages],
                tools=[tool.model_dump() for tool in tools],
                stream=True,
            )
            stream_state: StreamState = StreamState.DEFAULT
            tool_id, tool_name, tool_input = "", "", ""
            async for chunk in response:
                if chunk.type == "content_block_delta":
                    if chunk.delta.type == "text_delta":
                        yield TextContent(text=chunk.delta.text)
                    elif chunk.delta.type == "input_json_delta" and stream_state == StreamState.PARSING_TOOL:
                        tool_input += chunk.delta.partial_json
                elif chunk.type == "content_block_start":
                    if chunk.content_block.type == "tool_use":
                        tool_id = chunk.content_block.id
                        tool_name = chunk.content_block.name
                        stream_state = StreamState.PARSING_TOOL
                    elif chunk.content_block.type == "text":
                        stream_state = StreamState.PARSING_MSG
                elif chunk.type == "content_block_stop":
                    if stream_state == StreamState.PARSING_TOOL:
                        input_dict = {}
                        if tool_input:
                            input_dict = json.loads(tool_input)
                        yield ToolCall(id=tool_id, name=tool_name, input=input_dict)
                        tool_id, tool_name, tool_input = "", "", ""
                    stream_state = StreamState.DEFAULT

        except Exception as e:
            raise e
