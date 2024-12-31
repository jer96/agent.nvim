import os
from typing import Optional

import openai
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential


class LLMProvider:
    def __init__(self, nvim):
        self.nvim = nvim
        self._setup_credentials()

    def _setup_credentials(self):
        """Setup API credentials from Neovim config"""
        config = self.nvim.vars.get("agent_config", {})

        # Load from config or environment
        openai.api_key = config.get("api_keys", {}).get("openai") or os.getenv(
            "OPENAI_API_KEY"
        )
        self.anthropic_key = config.get("api_keys", {}).get("anthropic") or os.getenv(
            "ANTHROPIC_API_KEY"
        )

        if not openai.api_key and not self.anthropic_key:
            self.nvim.err_write(
                "Warning: No API keys configured for any LLM provider\n"
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def complete(self, prompt: str, model: Optional[str] = None) -> str:
        """Get completion from specified model"""
        self.nvim.out_write("made it inside complete")
        config = self.nvim.vars.get("agent_config", {})
        model = model or config.get("models", {}).get(
            "default", "claude-3-5-sonnet-20241022"
        )

        # TODO: change provider handling
        if "claude" in model:
            self.nvim.out_write("chose claude")
            return self._anthropic_complete(prompt, model.split("/")[-1])
        else:
            return self._openai_complete(prompt, model)

    def _openai_complete(self, prompt: str, model: str) -> str:
        """Get completion from OpenAI"""
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured")

        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content

    def _anthropic_complete(self, prompt: str, model: str) -> str:
        """Get completion from Anthropic"""
        if not self.anthropic_key:
            raise ValueError("Anthropic API key not configured")

        client = Anthropic(api_key=self.anthropic_key)
        response = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
        )
        return response.content[0].text
