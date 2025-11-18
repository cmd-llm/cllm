"""
Conversation management for multi-turn interactions.

This module implements ADR-0007: Conversation Threading and Context Management.
This module implements ADR-0017: Configurable Conversations Path.
It provides file-based storage for conversation history using JSON format.
"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Conversation:
    """
    Represents a conversation with message history.

    Attributes:
        id: Unique conversation identifier (user-specified or auto-generated)
        created_at: ISO 8601 timestamp of creation
        updated_at: ISO 8601 timestamp of last update
        model: LLM model used for this conversation
        messages: List of message dicts in OpenAI format
        metadata: Additional conversation metadata (tokens, tags, etc.)

    Examples:
        >>> conv = Conversation(
        ...     id="code-review",
        ...     model="gpt-4",
        ...     messages=[{"role": "user", "content": "Review this code"}]
        ... )
        >>> conv.add_message("assistant", "The code looks good...")
        >>> print(conv.total_tokens)
    """

    id: str
    model: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation.

        Args:
            role: Message role ("user", "assistant", or "system")
            content: Message content
        """
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def has_system_message(self) -> bool:
        """
        Check if the conversation has a system message.

        Returns:
            True if the first message is a system message, False otherwise
        """
        return len(self.messages) > 0 and self.messages[0].get("role") == "system"

    def has_context_in_system_message(self) -> bool:
        """
        Check if the conversation's system message contains context command output.

        Context commands produce distinctive markers: "--- Context:" and "--- End Context ---"
        This allows detection of whether context was already executed and stored.

        Returns:
            True if system message contains context markers, False otherwise
        """
        if not self.has_system_message():
            return False

        system_content = self.messages[0].get("content", "")
        return (
            "--- Context:" in system_content and "--- End Context ---" in system_content
        )

    def set_system_message(self, content: str) -> None:
        """
        Set or update the system message for the conversation.

        If a system message already exists (as the first message), it will be updated.
        Otherwise, a new system message will be inserted at the beginning.

        This should typically only be called once when creating a new conversation.

        Args:
            content: System message content
        """
        system_message = {"role": "system", "content": content}

        if self.has_system_message():
            # Update existing system message
            self.messages[0] = system_message
        else:
            # Insert system message at the beginning
            self.messages.insert(0, system_message)

        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get all messages in the conversation.

        Returns:
            List of message dicts in OpenAI format
        """
        return self.messages

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert conversation to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the conversation
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """
        Create a Conversation from a dictionary.

        Args:
            data: Dictionary containing conversation data

        Returns:
            Conversation instance
        """
        return cls(**data)

    @property
    def total_tokens(self) -> int:
        """Get total token count from metadata."""
        value = self.metadata.get("total_tokens", 0)
        if isinstance(value, bool):
            # Prevent True/False from being considered 1/0
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @total_tokens.setter
    def total_tokens(self, value: int) -> None:
        """Set total token count in metadata."""
        self.metadata["total_tokens"] = value


class ConversationManager:
    """
    Manages conversation storage and retrieval.

    Handles CRUD operations for conversations stored as JSON files.

    Storage location precedence (ADR-0017):
      1. CLI flag: --conversations-path (highest)
      2. Environment variable: CLLM_CONVERSATIONS_PATH
      3. Custom .cllm path: <cllm_path>/conversations/ (if --cllm-path or CLLM_PATH set)
      4. Local project: ./.cllm/conversations/ (if .cllm directory exists)
      5. Global home: ~/.cllm/conversations/ (fallback)

    Examples:
        >>> manager = ConversationManager()
        >>> conv = manager.create(id="test", model="gpt-4")
        >>> conv.add_message("user", "Hello")
        >>> manager.save(conv)
        >>> loaded = manager.load("test")
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        cllm_path: Optional[Path] = None,
        conversations_path: Optional[Path] = None,
    ):
        """
        Initialize the conversation manager.

        Args:
            storage_dir: Deprecated. Optional custom storage directory.
                        Use conversations_path instead for explicit path override.
            cllm_path: Optional custom .cllm directory path (from --cllm-path or CLLM_PATH).
                      If set, conversations are stored in <cllm_path>/conversations/
            conversations_path: Optional custom conversations directory path
                              (from --conversations-path or CLLM_CONVERSATIONS_PATH).
                              Takes precedence over all other path settings.
        """
        # Precedence: conversations_path > storage_dir > cllm_path > defaults
        if conversations_path is not None:
            self.storage_dir = Path(conversations_path)
        elif storage_dir is not None:
            # Backwards compatibility: storage_dir is used if provided
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = self._get_default_storage_dir(cllm_path)
        self._ensure_storage_dir()

    def _get_default_storage_dir(self, cllm_path: Optional[Path] = None) -> Path:
        """
        Get the default storage directory following precedence rules.

        Implements ADR-0017: Configurable Conversations Path

        Precedence order:
          1. CLLM_CONVERSATIONS_PATH environment variable
          2. Custom .cllm path (if cllm_path parameter or CLLM_PATH env var set)
          3. Local .cllm directory (project-specific, if exists)
          4. Home .cllm directory (global, fallback)

        Args:
            cllm_path: Optional custom .cllm directory path

        Returns:
            Path to the conversations directory
        """
        # Check CLLM_CONVERSATIONS_PATH environment variable
        env_conversations_path = os.getenv("CLLM_CONVERSATIONS_PATH")
        if env_conversations_path:
            return Path(env_conversations_path)

        # Check for custom .cllm path (cllm_path parameter or CLLM_PATH env var)
        if cllm_path is not None:
            return Path(cllm_path) / "conversations"

        env_cllm_path = os.getenv("CLLM_PATH")
        if env_cllm_path:
            return Path(env_cllm_path) / "conversations"

        # Check for local .cllm directory (project-specific)
        local_dir = Path.cwd() / ".cllm" / "conversations"
        if (Path.cwd() / ".cllm").exists():
            return local_dir

        # Fall back to home directory (global)
        return Path.home() / ".cllm" / "conversations"

    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, conversation_id: str) -> None:
        """
        Validate conversation ID format.

        Args:
            conversation_id: ID to validate

        Raises:
            ValueError: If ID contains invalid characters
        """
        if not conversation_id:
            raise ValueError("Conversation ID cannot be empty")

        # Allow alphanumeric, hyphens, and underscores only
        valid_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )
        if not all(c in valid_chars for c in conversation_id):
            raise ValueError(
                f"Invalid conversation ID: '{conversation_id}'. "
                "Only alphanumeric characters, hyphens, and underscores are allowed."
            )

    def _generate_id(self) -> str:
        """
        Generate a UUID-based conversation ID.

        Returns:
            ID in format: conv-<8-char-hex>
        """
        # Generate UUID and take first 8 hex characters
        short_uuid = uuid.uuid4().hex[:8]
        return f"conv-{short_uuid}"

    def _get_filepath(self, conversation_id: str) -> Path:
        """
        Get the file path for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Path to conversation JSON file
        """
        return self.storage_dir / f"{conversation_id}.json"

    def create(
        self,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        system_message: Optional[str] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            conversation_id: Optional user-specified ID.
                           If None, generates a UUID-based ID.
            model: Optional model name for the conversation
            system_message: Optional system message to set as first message.
                          If provided, will be stored as the first message
                          with role="system" (ADR-0020)

        Returns:
            New Conversation instance

        Raises:
            ValueError: If ID is invalid or conversation already exists
        """
        # Generate ID if not provided
        if conversation_id is None:
            conversation_id = self._generate_id()
        else:
            self._validate_id(conversation_id)

        # Check if conversation already exists
        if self.exists(conversation_id):
            raise ValueError(f"Conversation '{conversation_id}' already exists")

        conversation = Conversation(id=conversation_id, model=model or "")

        # ADR-0020: Capture system prompt in conversation data
        if system_message:
            conversation.set_system_message(system_message)

        return conversation

    def save(self, conversation: Conversation) -> None:
        """
        Save conversation to disk using atomic write.

        Writes to a temporary file first, then renames to prevent corruption.

        Args:
            conversation: Conversation to save

        Raises:
            OSError: If file operations fail
        """
        filepath = self._get_filepath(conversation.id)
        temp_filepath = filepath.with_suffix(".tmp")

        try:
            # Write to temporary file
            with open(temp_filepath, "w") as f:
                json.dump(conversation.to_dict(), f, indent=2)

            # Atomic rename
            temp_filepath.replace(filepath)
        except Exception as e:
            # Clean up temp file if it exists
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise OSError(
                f"Failed to save conversation '{conversation.id}': {e}"
            ) from e

    def load(self, conversation_id: str) -> Conversation:
        """
        Load a conversation from disk.

        Args:
            conversation_id: ID of conversation to load

        Returns:
            Loaded Conversation instance

        Raises:
            FileNotFoundError: If conversation doesn't exist
            ValueError: If JSON is malformed
        """
        filepath = self._get_filepath(conversation_id)

        if not filepath.exists():
            raise FileNotFoundError(f"Conversation '{conversation_id}' not found")

        try:
            with open(filepath) as f:
                data = json.load(f)
            return Conversation.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Malformed conversation file '{conversation_id}': {e}"
            ) from e

    def exists(self, conversation_id: str) -> bool:
        """
        Check if a conversation exists.

        Args:
            conversation_id: ID to check

        Returns:
            True if conversation exists, False otherwise
        """
        filepath = self._get_filepath(conversation_id)
        return filepath.exists()

    def delete(self, conversation_id: str) -> None:
        """
        Delete a conversation.

        Args:
            conversation_id: ID of conversation to delete

        Raises:
            FileNotFoundError: If conversation doesn't exist
        """
        filepath = self._get_filepath(conversation_id)

        if not filepath.exists():
            raise FileNotFoundError(f"Conversation '{conversation_id}' not found")

        filepath.unlink()

    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        List all conversations with metadata.

        Returns:
            List of dicts containing conversation summaries:
            [{"id": "...", "model": "...", "message_count": ..., "updated_at": "..."}]
        """
        conversations = []

        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)

                conversations.append(
                    {
                        "id": data.get("id", ""),
                        "model": data.get("model", ""),
                        "message_count": len(data.get("messages", [])),
                        "updated_at": data.get("updated_at", ""),
                        "created_at": data.get("created_at", ""),
                    }
                )
            except (json.JSONDecodeError, OSError):
                # Skip malformed or inaccessible files
                continue

        # Sort by updated_at descending (most recent first)
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)

        return conversations
