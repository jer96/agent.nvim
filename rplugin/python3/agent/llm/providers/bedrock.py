import json
from typing import Dict, Generator, List, Optional

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider
from ..constants import BEDROCK_CLAUDE, MAX_TOKENS, SYSTEM_PROMPT, TEMPERATURE, US_EAST_1


class BedrockProvider(LLMProvider):
    def __init__(self, nvim):
        self.nvim = nvim
        self.client = self._get_client()

    def _get_client(self):
        return boto3.client(service_name="bedrock-runtime", region_name=US_EAST_1)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(self, messages: List[Dict], model: Optional[str] = BEDROCK_CLAUDE) -> str:
        if not self.client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        try:
            response = self.client.invoke_model(modelId=model, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            self.nvim.err_write(f"Bedrock API error: {str(e)}\n")
            raise

    def complete_stream(
        self, messages: List[Dict], model: Optional[str] = BEDROCK_CLAUDE, system_prompt: str = SYSTEM_PROMPT
    ) -> Generator[str, None, None]:
        if not self.client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "system": system_prompt,
            "messages": messages,
        }

        try:
            response = self.client.invoke_model_with_response_stream(modelId=model, body=json.dumps(request_body))
            for event in response.get("body"):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    if chunk["delta"]["type"] == "text_delta":
                        yield chunk["delta"]["text"]

        except Exception as e:
            self.nvim.err_write(f"Bedrock streaming API error: {str(e)}\n")
            raise
