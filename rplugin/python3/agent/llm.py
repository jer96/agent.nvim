import json
import os
from typing import Dict, Generator, List, Optional

import boto3
import pynvim
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

SYSTEM_PROMPT = "You are an AI assistant embedded into Neovim text editor."
CLAUDE_SONNET = "claude-3-5-sonnet-latest"
BEDROCK_CLAUDE = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
US_EAST_1 = "us-east-1"
MAX_TOKENS = 4096
TEMP = 0.7


class LLMProvider:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.anthropic_client = self._get_anthropic_client()
        self.bedrock_client = self._get_bedrock_client()

    def _get_anthropic_client(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.anthropic_key:
            self.nvim.err_write("Warning: No API keys configured for any LLM provider\n")

        return Anthropic(api_key=self.anthropic_key)

    def _get_bedrock_client(self):
        return boto3.client(service_name="bedrock-runtime", region_name=US_EAST_1)

    def anthropic_complete_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = CLAUDE_SONNET,
    ) -> Generator[str, None, None]:
        """Get streaming completion from Anthropic"""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.anthropic_client.messages.create(
                system=SYSTEM_PROMPT,
                temperature=TEMP,
                max_tokens=MAX_TOKENS,
                model=model,
                messages=messages,
                stream=True,
            )

            for chunk in response:
                if chunk.type == "content_block_delta" and chunk.delta and chunk.delta.text:
                    yield chunk.delta.text

        except Exception as e:
            self.nvim.err_write(f"Anthropic streaming API error: {str(e)}\n")
            raise

    def bedrock_complete_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = BEDROCK_CLAUDE,
    ) -> Generator[str, None, None]:
        """Get streaming completion from Bedrock"""
        if not self.bedrock_client:
            raise ValueError("Bedrock client not configured")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "temperature": TEMP,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        try:
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=model, body=json.dumps(request_body)
            )
            for event in response.get("body"):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    if chunk["delta"]["type"] == "text_delta":
                        yield chunk["delta"]["text"]

        except Exception as e:
            self.nvim.err_write(f"Bedrock streaming API error: {str(e)}\n")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def anthropic_complete(self, messages: List[Dict], model: Optional[str] = CLAUDE_SONNET) -> str:
        """Get completion from Anthropic"""

        if not self.anthropic_client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.anthropic_client.messages.create(
                system=SYSTEM_PROMPT,
                temperature=TEMP,
                max_tokens=MAX_TOKENS,
                model=model,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            self.nvim.err_write(f"Anthropic API error: {str(e)}\n")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def bedrock_complete(self, messages: List[Dict], model: Optional[str] = BEDROCK_CLAUDE) -> str:
        """Get completion from Bedrock"""
        if not self.bedrock_client:
            raise ValueError("Bedrock client not configured")

        # Convert messages to Claude format
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "assistant", "content": msg["content"]})

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "temperature": TEMP,
            "system": SYSTEM_PROMPT,
            "messages": formatted_messages,
        }

        try:
            response = self.bedrock_client.invoke_model(modelId=model, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            self.nvim.err_write(f"Bedrock API error: {str(e)}\n")
            raise
