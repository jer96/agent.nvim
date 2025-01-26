import json
import logging
from typing import Generator, List

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider
from ..constants import ANTHROPIC_VERSION, BEDROCK_CLAUDE, US_EAST_1
from ..types import CompletionResponse, ContentType, InferenceConfig, Message, TextContent, Tool

logger = logging.getLogger(__name__)


class BedrockProvider(LLMProvider):
    def __init__(self):
        self.client = self._get_client()

    def _get_client(self):
        return boto3.client(service_name="bedrock-runtime", region_name=US_EAST_1)

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
        if not self.client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": ANTHROPIC_VERSION,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
        }
        logger.debug("bedrock completion")

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = self.client.invoke_model(modelId=model_id, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            content = self._parse_content(response_body)
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
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": config.system_prompt,
            "messages": [msg.model_dump() for msg in messages],
        }

        try:
            model_id = config.model or BEDROCK_CLAUDE
            response = self.client.invoke_model_with_response_stream(modelId=model_id, body=json.dumps(request_body))
            for event in response.get("body"):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    if chunk["delta"]["type"] == "text_delta":
                        yield chunk["delta"]["text"]

        except Exception as e:
            raise e
