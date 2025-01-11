import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import pynvim


class ConversationStorage:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.storage_enabled, self.storage_path = self._get_storage_config()
        if self.storage_enabled:
            os.makedirs(self.storage_path, exist_ok=True)

    def _get_storage_config(self) -> [bool, Optional[str]]:
        agent_config = self.nvim.vars.get("agent_config", {})
        storage = agent_config.get("storage", {})
        enabled = storage.get("enabled", False)
        path = storage.get("path", None)
        return enabled, path

    def save_conversation(self, conversation_id: str, messages: List[Dict[str, str]]) -> None:
        """Save conversation to a JSON file."""
        if not self.storage_enabled:
            return
        file_path = os.path.join(
            self.storage_path,
            f"conversation_{
                conversation_id}.json",
        )
        data = {"id": conversation_id, "timestamp": datetime.now().isoformat(), "messages": messages}
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_conversation(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        """Load conversation from JSON file."""
        if not self.storage_path:
            return None
        file_path = os.path.join(
            self.storage_path,
            f"conversation_{
                conversation_id}.json",
        )
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data["messages"]
        except FileNotFoundError:
            return None

    def list_conversations(self) -> List[Dict]:
        """List all saved conversations."""
        conversations = []
        if not self.storage_path:
            return conversations
        for filename in os.listdir(self.storage_path):
            if filename.startswith("conversation_") and filename.endswith(".json"):
                file_path = os.path.join(self.storage_path, filename)
                with open(file_path, "r") as f:
                    data = json.load(f)
                    conversations.append(
                        {"id": data["id"], "timestamp": data["timestamp"], "message_count": len(data["messages"])}
                    )
        return sorted(conversations, key=lambda x: x["timestamp"], reverse=True)
