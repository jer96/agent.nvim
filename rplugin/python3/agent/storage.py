import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class ConversationStorage:
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def save_conversation(self, conversation_id: str, messages: List[Dict[str, str]]):
        """Save conversation to a JSON file."""
        file_path = os.path.join(
            self.storage_dir,
            f"conversation_{
                                 conversation_id}.json",
        )
        data = {"id": conversation_id, "timestamp": datetime.now().isoformat(), "messages": messages}
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_conversation(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        """Load conversation from JSON file."""
        file_path = os.path.join(
            self.storage_dir,
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
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("conversation_") and filename.endswith(".json"):
                file_path = os.path.join(self.storage_dir, filename)
                with open(file_path, "r") as f:
                    data = json.load(f)
                    conversations.append(
                        {"id": data["id"], "timestamp": data["timestamp"], "message_count": len(data["messages"])}
                    )
        return sorted(conversations, key=lambda x: x["timestamp"], reverse=True)
