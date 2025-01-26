import json
import os
from datetime import datetime
from typing import List, Optional

import pynvim
from pydantic import ValidationError

from .llm.types import Conversation, ConversationMetadata, Message


class ChatStorage:
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

    def save_conversation(self, conversation_id: str, messages: List[Message]) -> None:
        """Save conversation to a JSON file."""
        if not self.storage_enabled:
            return

        conversation_file = f"conversation_{conversation_id}.json"
        file_path = os.path.join(self.storage_path, conversation_file)
        try:
            conversation = Conversation(id=conversation_id, timestamp=datetime.now(), messages=messages)
            with open(file_path, "w") as f:
                json.dump(conversation.model_dump(mode="json"), f, indent=2)
        except ValidationError as e:
            self.nvim.err_write(f"Validation error while saving: {str(e)}\n")
        except Exception as e:
            self.nvim.err_write(f"Error saving conversation: {str(e)}\n")

    def load_conversation(self, conversation_id: str) -> Optional[List[Message]]:
        """Load conversation from JSON file using Pydantic."""
        if not self.storage_path:
            return None

        conversation_file = f"conversation_{conversation_id}.json"
        file_path = os.path.join(self.storage_path, conversation_file)

        try:
            # Read JSON file and convert directly to Pydantic model
            with open(file_path, "r") as f:
                conversation = Conversation.model_validate_json(f.read())
                return conversation.messages

        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            self.nvim.err_write(f"Error decoding conversation file: {file_path}\n")
            return None
        except Exception as e:
            self.nvim.err_write(f"Error loading conversation: {str(e)}\n")
            return None

    def list_conversations(self) -> List[ConversationMetadata]:
        """List all saved conversations using Pydantic models."""
        conversations = []
        if not self.storage_path:
            return conversations

        for filename in os.listdir(self.storage_path):
            if not (filename.startswith("conversation_") and filename.endswith(".json")):
                continue

            file_path = os.path.join(self.storage_path, filename)
            try:
                # Read and parse each conversation file
                with open(file_path, "r") as f:
                    conversation = Conversation.model_validate_json(f.read())

                    # Create metadata model
                    metadata = ConversationMetadata(
                        id=conversation.id, timestamp=conversation.timestamp, message_count=len(conversation.messages)
                    )
                    conversations.append(metadata)

            except Exception as e:
                self.nvim.err_write(
                    f"Error reading conversation file {
                        filename}: {str(e)}\n"
                )
                continue

        # Sort by timestamp descending
        return sorted(conversations, key=lambda x: x.timestamp, reverse=True)
