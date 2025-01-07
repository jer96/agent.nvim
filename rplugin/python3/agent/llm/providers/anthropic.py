import os
from typing import Dict, Generator, List, Optional

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base import LLMProvider
from ..constants import CLAUDE_SONNET, MAX_TOKENS, SYSTEM_PROMPT, TEMPERATURE


class AnthropicProvider(LLMProvider):
    def __init__(self, nvim):
        self.nvim = nvim
        self.client = self._get_client()

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            self.nvim.err_write("Warning: Anthropic API key not configured\n")
        return Anthropic(api_key=api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(self, messages: List[Dict], model: Optional[str] = CLAUDE_SONNET) -> str:
        if not self.client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.client.messages.create(
                system=SYSTEM_PROMPT,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                model=model,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            self.nvim.err_write(f"Anthropic API error: {str(e)}\n")
            raise

    def complete_stream(self, messages: List[Dict], model: Optional[str] = CLAUDE_SONNET) -> Generator[str, None, None]:
        if not self.client:
            raise ValueError("Anthropic client not configured")

        try:
            response = self.client.messages.create(
                system=SYSTEM_PROMPT,
                temperature=TEMPERATURE,
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
