import os
from typing import Dict, Generator, List, Optional

import pynvim
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

SYSTEM_PROMPT = "You are an AI assistant embedded into Neovim text editor."
CLAUDE_SONNET = "claude-3-5-sonnet-latest"
MAX_TOKENS = 4096
TEMP = 0.7


class LLMProvider:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self._setup_credentials()
        self.client = Anthropic(api_key=self.anthropic_key)

    def _setup_credentials(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.anthropic_key:
            self.nvim.err_write("Warning: No API keys configured for any LLM provider\n")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def anthropic_complete(self, messages: List[Dict], model: Optional[str] = CLAUDE_SONNET) -> str:
        """Get completion from Anthropic"""

        if not self.anthropic_key:
            raise ValueError("Anthropic API key not configured")

        response = self.client.messages.create(
            system=SYSTEM_PROMPT,
            temperature=TEMP,
            max_tokens=MAX_TOKENS,
            model=model,
            messages=messages,
        )
        return response.content[0].text

    def anthropic_complete_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = CLAUDE_SONNET,
    ) -> Generator[str, None, None]:
        """Get streaming completion from Anthropic"""
        if not self.anthropic_key:
            raise ValueError("Anthropic API key not configured")

        response = self.client.messages.create(
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
