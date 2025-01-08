from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: List[Dict], model: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def complete_stream(
        self, messages: List[Dict], model: Optional[str] = None, system_prompt: str = None
    ) -> Generator[str, None, None]:
        pass
