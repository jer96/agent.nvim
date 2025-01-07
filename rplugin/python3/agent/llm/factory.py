from enum import Enum
from typing import Callable, Dict, Optional, Union

import pynvim

from .base import LLMProvider
from .providers.anthropic import AnthropicProvider
from .providers.bedrock import BedrockProvider


class ModelProvider(Enum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"


class LLMProviderFactory:
    _providers: Dict[ModelProvider, Callable[[pynvim.Nvim], LLMProvider]] = {
        ModelProvider.ANTHROPIC: lambda nvim: AnthropicProvider(nvim),
        ModelProvider.BEDROCK: lambda nvim: BedrockProvider(nvim),
    }

    @classmethod
    def create(cls, nvim: pynvim.Nvim, model_provider: Optional[Union[str, ModelProvider]] = None) -> LLMProvider:
        # model provider provided as input to function
        if isinstance(model_provider, str):
            model_provider = ModelProvider(model_provider)

        if not model_provider:
            # model provider provided from config
            agent_config = nvim.vars.get("agent_config", {})
            if isinstance(agent_config, dict):
                config_model_provider = agent_config.get("model_provider", "anthropic")
                model_provider = ModelProvider(config_model_provider)
            else:
                model_provider = ModelProvider.ANTHROPIC

        provider_creator = cls._providers.get(model_provider)

        return provider_creator(nvim)
