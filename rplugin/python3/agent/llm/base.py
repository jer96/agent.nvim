from abc import ABC, abstractmethod
from typing import Dict, Generator, List


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self, *, messages: List[Dict], tools: List[Dict], model: str | None, system_prompt: str | None
    ) -> List[Dict]:
        pass

    @abstractmethod
    def complete_stream(
        self, *, messages: List[Dict], model: str | None, system_prompt: str | None
    ) -> Generator[str, None, None]:
        pass
