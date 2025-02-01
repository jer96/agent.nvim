import json
import logging
from typing import AsyncGenerator, Generator, List, Optional

import aioboto3
import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider, StreamState
from ..constants import BEDROCK_ANTHROPIC_VERSION, BEDROCK_CLAUDE, US_EAST_1
from ..types import CompletionResponse, ContentType, InferenceConfig, Message, TextContent, Tool, ToolCall

logger = logging.getLogger(__name__)


class BedrockProvider(LLMProvider):
    def __init__(self):
        self._sync_client = None
        self._async_client = None
        self._async_session = aioboto3.Session()

    @property
    def sync_client(self):
        if self._sync_client is None:
            self._sync_client = boto3.client(service_name="bedrock-runtime", region_name=US_EAST_1)
        return self._sync_client

    async def _get_async_client(self) -> Optional[object]:
        if self._async_client is None:
            self._async_client = await self._async_session.client(
                service_name="bedrock-runtime", region_name=US_EAST_1
            ).__aenter__()
        return self._async_client

    def _parse_content(self, response) -> List[ContentType]:
        content_list = []
        response_content = response["content"]

        for content in response_content:
            if content["type"] == "text":
                content_list.append(TextContent(text=content["text"]))
        return content_list

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        """Synchronous completion using boto3 client"""
        if not self.sync_client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": BEDROCK_ANTHROPIC_VERSION,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
        }

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = self.sync_client.invoke_model(modelId=model_id, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            content = self._parse_content(response_body)
            return CompletionResponse(content=content)
        except Exception as e:
            logger.error(f"Error in complete: {str(e)}")
            raise e

    def complete_stream(
        self,
        *,
        messages: List[Message],
        config: InferenceConfig | None,
    ) -> Generator[ContentType, None, None]:
        """Synchronous streaming completion using boto3 client"""
        if not self.sync_client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": BEDROCK_ANTHROPIC_VERSION,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
        }

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = self.sync_client.invoke_model_with_response_stream(
                modelId=model_id, body=json.dumps(request_body)
            )

            for event in response.get("body"):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    if chunk["delta"]["type"] == "text_delta":
                        yield TextContent(text=chunk["delta"]["text"])

        except Exception as e:
            logger.error(f"Error in complete_stream: {str(e)}")
            raise e

    async def async_complete(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> CompletionResponse:
        """Asynchronous completion using aioboto3 client"""
        client = await self._get_async_client()
        if not client:
            raise ValueError("Bedrock async client not configured")

        request_body = {
            "anthropic_version": BEDROCK_ANTHROPIC_VERSION,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
        }

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = await client.invoke_model(modelId=model_id, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            content = self._parse_content(response_body)
            return CompletionResponse(content=content)
        except Exception as e:
            logger.error(f"Error in async_complete: {str(e)}")
            raise e

    async def async_complete_stream(
        self,
        *,
        messages: List[Message],
        tools: List[Tool],
        config: InferenceConfig | None,
    ) -> AsyncGenerator[ContentType, None]:
        """Asynchronous streaming completion using aioboto3 client with tool support"""
        client = await self._get_async_client()
        if not client:
            raise ValueError("Bedrock async client not configured")

        request_body = {
            "anthropic_version": BEDROCK_ANTHROPIC_VERSION,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
            "tools": [tool.model_dump() for tool in tools] if tools else [],
        }

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = await client.invoke_model_with_response_stream(modelId=model_id, body=json.dumps(request_body))

            stream_state: StreamState = StreamState.DEFAULT
            tool_id, tool_name, tool_input = "", "", ""

            async for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])

                if chunk["type"] == "content_block_delta":
                    if chunk["delta"]["type"] == "text_delta":
                        yield TextContent(text=chunk["delta"]["text"])
                    elif chunk["delta"]["type"] == "input_json_delta" and stream_state == StreamState.PARSING_TOOL:
                        tool_input += chunk["delta"]["partial_json"]

                elif chunk["type"] == "content_block_start":
                    if chunk["content_block"]["type"] == "tool_use":
                        tool_id = chunk["content_block"]["id"]
                        tool_name = chunk["content_block"]["name"]
                        stream_state = StreamState.PARSING_TOOL
                    elif chunk["content_block"]["type"] == "text":
                        stream_state = StreamState.PARSING_MSG

                elif chunk["type"] == "content_block_stop":
                    if stream_state == StreamState.PARSING_TOOL:
                        input_dict = json.loads(tool_input)
                        yield ToolCall(id=tool_id, name=tool_name, input=input_dict)
                        tool_id, tool_name, tool_input = "", "", ""
                    stream_state = StreamState.DEFAULT

        except Exception as e:
            logger.error(f"Error in async_complete_stream: {str(e)}")
            raise e

    async def cleanup(self):
        """Cleanup method to properly close the async client"""
        if self._async_client:
            await self._async_client.__aexit__(None, None, None)
            self._async_client = None
