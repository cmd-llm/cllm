"""
Tests for conversation management functionality.

These tests verify the Conversation and ConversationManager classes
as specified in ADR-0007: Conversation Threading and Context Management.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cllm.conversation import Conversation, ConversationManager


class TestConversation:
    """Test suite for Conversation dataclass."""

    def test_conversation_creation(self):
        """Test basic conversation creation."""
        conv = Conversation(id="test-conv", model="gpt-4")
        assert conv.id == "test-conv"
        assert conv.model == "gpt-4"
        assert conv.messages == []
        assert isinstance(conv.metadata, dict)

    def test_conversation_with_messages(self):
        """Test conversation creation with initial messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        conv = Conversation(id="test", model="gpt-4", messages=messages)
        assert len(conv.messages) == 2
        assert conv.messages == messages

    def test_add_message(self):
        """Test adding messages to a conversation."""
        conv = Conversation(id="test", model="gpt-4")
        conv.add_message("user", "Hello, world!")
        assert len(conv.messages) == 1
        assert conv.messages[0]["role"] == "user"
        assert conv.messages[0]["content"] == "Hello, world!"

    def test_get_messages(self):
        """Test retrieving all messages."""
        messages = [{"role": "user", "content": "Test"}]
        conv = Conversation(id="test", model="gpt-4", messages=messages)
        retrieved = conv.get_messages()
        assert retrieved == messages

    def test_to_dict(self):
        """Test conversion to dictionary."""
        conv = Conversation(id="test", model="gpt-4")
        conv.add_message("user", "Hello")
        data = conv.to_dict()

        assert data["id"] == "test"
        assert data["model"] == "gpt-4"
        assert len(data["messages"]) == 1
        assert "created_at" in data
        assert "updated_at" in data
        assert "metadata" in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "test",
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "created_at": "2025-10-27T10:00:00Z",
            "updated_at": "2025-10-27T10:00:00Z",
            "metadata": {"total_tokens": 100},
        }
        conv = Conversation.from_dict(data)

        assert conv.id == "test"
        assert conv.model == "gpt-4"
        assert len(conv.messages) == 1
        assert conv.total_tokens == 100

    def test_total_tokens_property(self):
        """Test total tokens property."""
        conv = Conversation(id="test", model="gpt-4")
        assert conv.total_tokens == 0

        conv.total_tokens = 150
        assert conv.total_tokens == 150
        assert conv.metadata["total_tokens"] == 150

    def test_updated_at_changes_on_add_message(self):
        """Test that updated_at timestamp changes when adding messages."""
        conv = Conversation(id="test", model="gpt-4")
        initial_updated_at = conv.updated_at

        # Small delay to ensure timestamp changes
        import time

        time.sleep(0.01)
        conv.add_message("user", "Hello")

        assert conv.updated_at != initial_updated_at


class TestConversationManager:
    """Test suite for ConversationManager."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_storage):
        """Create a ConversationManager with temporary storage."""
        return ConversationManager(storage_dir=temp_storage)

    def test_manager_initialization(self, temp_storage):
        """Test manager initialization creates storage directory."""
        manager = ConversationManager(storage_dir=temp_storage)
        assert manager.storage_dir == temp_storage
        assert temp_storage.exists()

    def test_manager_default_storage_precedence_local(self, tmp_path, monkeypatch):
        """Test manager prefers local .cllm directory when it exists."""
        # Create a temporary directory with .cllm folder
        local_cllm = tmp_path / ".cllm"
        local_cllm.mkdir()

        # Change to that directory
        monkeypatch.chdir(tmp_path)

        manager = ConversationManager()
        expected_path = tmp_path / ".cllm" / "conversations"
        assert manager.storage_dir == expected_path

    def test_manager_default_storage_precedence_global(self, tmp_path, monkeypatch):
        """Test manager falls back to home directory when no local .cllm exists."""
        # Change to a temp directory without .cllm folder
        monkeypatch.chdir(tmp_path)

        manager = ConversationManager()
        expected_path = Path.home() / ".cllm" / "conversations"
        assert manager.storage_dir == expected_path

    def test_generate_id(self, manager):
        """Test UUID-based ID generation."""
        conv_id = manager._generate_id()
        assert conv_id.startswith("conv-")
        assert len(conv_id) == 13  # "conv-" + 8 hex chars

    def test_validate_id_valid(self, manager):
        """Test ID validation with valid IDs."""
        # Should not raise
        manager._validate_id("valid-id-123")
        manager._validate_id("test_conversation")
        manager._validate_id("conv-abc123")

    def test_validate_id_invalid_characters(self, manager):
        """Test ID validation rejects invalid characters."""
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            manager._validate_id("invalid id with spaces")

        with pytest.raises(ValueError, match="Invalid conversation ID"):
            manager._validate_id("invalid/id/slashes")

        with pytest.raises(ValueError, match="Invalid conversation ID"):
            manager._validate_id("invalid@id.com")

    def test_validate_id_empty(self, manager):
        """Test ID validation rejects empty strings."""
        with pytest.raises(ValueError, match="cannot be empty"):
            manager._validate_id("")

    def test_create_conversation_with_auto_id(self, manager):
        """Test creating conversation with auto-generated ID."""
        conv = manager.create()
        assert conv.id.startswith("conv-")
        assert len(conv.id) == 13

    def test_create_conversation_with_custom_id(self, manager):
        """Test creating conversation with user-specified ID."""
        conv = manager.create(conversation_id="my-conversation")
        assert conv.id == "my-conversation"

    def test_create_conversation_with_model(self, manager):
        """Test creating conversation with model specified."""
        conv = manager.create(conversation_id="test", model="gpt-4")
        assert conv.id == "test"
        assert conv.model == "gpt-4"

    def test_create_conversation_invalid_id(self, manager):
        """Test that invalid IDs are rejected."""
        with pytest.raises(ValueError, match="Invalid conversation ID"):
            manager.create(conversation_id="invalid id!")

    def test_create_conversation_duplicate_id(self, manager):
        """Test that duplicate IDs are rejected."""
        conv = manager.create(conversation_id="test")
        manager.save(conv)  # Save to disk so it exists
        with pytest.raises(ValueError, match="already exists"):
            manager.create(conversation_id="test")

    def test_save_and_load_conversation(self, manager):
        """Test saving and loading a conversation."""
        conv = manager.create(conversation_id="test", model="gpt-4")
        conv.add_message("user", "Hello")
        conv.add_message("assistant", "Hi there!")

        manager.save(conv)

        loaded = manager.load("test")
        assert loaded.id == conv.id
        assert loaded.model == conv.model
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["content"] == "Hello"

    def test_save_creates_json_file(self, manager, temp_storage):
        """Test that save creates a JSON file."""
        conv = manager.create(conversation_id="test")
        manager.save(conv)

        filepath = temp_storage / "test.json"
        assert filepath.exists()

        # Verify JSON is well-formed
        with open(filepath) as f:
            data = json.load(f)
        assert data["id"] == "test"

    def test_save_atomic_write(self, manager, temp_storage):
        """Test that save uses atomic write (temp file + rename)."""
        conv = manager.create(conversation_id="test")

        # Simulate partial write failure
        original_replace = Path.replace

        def mock_replace(self, target):
            # Verify temp file exists before rename
            assert self.suffix == ".tmp"
            assert self.exists()
            original_replace(self, target)

        with patch.object(Path, "replace", mock_replace):
            manager.save(conv)

        # Verify final file exists and temp file is cleaned up
        assert (temp_storage / "test.json").exists()
        assert not (temp_storage / "test.json.tmp").exists()

    def test_load_nonexistent_conversation(self, manager):
        """Test loading a conversation that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.load("nonexistent")

    def test_load_malformed_json(self, manager, temp_storage):
        """Test loading a conversation with malformed JSON."""
        # Create a malformed JSON file
        filepath = temp_storage / "malformed.json"
        with open(filepath, "w") as f:
            f.write("{invalid json")

        with pytest.raises(ValueError, match="Malformed conversation"):
            manager.load("malformed")

    def test_exists(self, manager):
        """Test checking if a conversation exists."""
        assert not manager.exists("test")

        conv = manager.create(conversation_id="test")
        manager.save(conv)

        assert manager.exists("test")

    def test_delete_conversation(self, manager, temp_storage):
        """Test deleting a conversation."""
        conv = manager.create(conversation_id="test")
        manager.save(conv)

        assert (temp_storage / "test.json").exists()

        manager.delete("test")

        assert not (temp_storage / "test.json").exists()

    def test_delete_nonexistent_conversation(self, manager):
        """Test deleting a conversation that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.delete("nonexistent")

    def test_list_conversations_empty(self, manager):
        """Test listing conversations when none exist."""
        conversations = manager.list_conversations()
        assert conversations == []

    def test_list_conversations_single(self, manager):
        """Test listing a single conversation."""
        conv = manager.create(conversation_id="test", model="gpt-4")
        conv.add_message("user", "Hello")
        manager.save(conv)

        conversations = manager.list_conversations()
        assert len(conversations) == 1
        assert conversations[0]["id"] == "test"
        assert conversations[0]["model"] == "gpt-4"
        assert conversations[0]["message_count"] == 1

    def test_list_conversations_sorted_by_updated(self, manager):
        """Test that conversations are sorted by updated_at (most recent first)."""
        import time

        # Create conversations with slight delays
        conv1 = manager.create(conversation_id="first", model="gpt-4")
        manager.save(conv1)

        time.sleep(0.01)

        conv2 = manager.create(conversation_id="second", model="gpt-4")
        manager.save(conv2)

        time.sleep(0.01)

        conv3 = manager.create(conversation_id="third", model="gpt-4")
        manager.save(conv3)

        conversations = manager.list_conversations()
        assert conversations[0]["id"] == "third"
        assert conversations[1]["id"] == "second"
        assert conversations[2]["id"] == "first"

    def test_list_conversations_skips_malformed(self, manager, temp_storage):
        """Test that list_conversations skips malformed JSON files."""
        # Create a valid conversation
        conv = manager.create(conversation_id="valid")
        manager.save(conv)

        # Create a malformed JSON file
        malformed_path = temp_storage / "malformed.json"
        with open(malformed_path, "w") as f:
            f.write("{invalid")

        # Should only return the valid conversation
        conversations = manager.list_conversations()
        assert len(conversations) == 1
        assert conversations[0]["id"] == "valid"

    def test_save_and_load_preserves_metadata(self, manager):
        """Test that metadata is preserved across save/load."""
        conv = manager.create(conversation_id="test")
        conv.total_tokens = 500
        conv.metadata["tags"] = ["code-review", "python"]

        manager.save(conv)
        loaded = manager.load("test")

        assert loaded.total_tokens == 500
        assert loaded.metadata["tags"] == ["code-review", "python"]

    def test_conversation_roundtrip(self, manager):
        """Test complete roundtrip: create, modify, save, load."""
        # Create conversation
        conv = manager.create(conversation_id="roundtrip", model="claude-3-opus")

        # Add messages
        conv.add_message("user", "What is Python?")
        conv.add_message(
            "assistant",
            "Python is a high-level programming language.",
        )
        conv.add_message("user", "Tell me more")

        # Set metadata
        conv.total_tokens = 250

        # Save
        manager.save(conv)

        # Load
        loaded = manager.load("roundtrip")

        # Verify everything matches
        assert loaded.id == "roundtrip"
        assert loaded.model == "claude-3-opus"
        assert len(loaded.messages) == 3
        assert loaded.total_tokens == 250
        assert loaded.messages[0]["content"] == "What is Python?"
        assert loaded.messages[1]["role"] == "assistant"
        assert loaded.messages[2]["content"] == "Tell me more"


class TestConversationPathPrecedence:
    """Test suite for conversation path precedence (ADR-0017)."""

    def test_conversations_path_parameter_takes_precedence(self, tmp_path):
        """Test that conversations_path parameter takes highest precedence."""
        # Set up different paths
        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir()
        cllm_dir = tmp_path / "cllm"
        cllm_dir.mkdir()

        # conversations_path should take precedence over cllm_path
        manager = ConversationManager(
            cllm_path=cllm_dir, conversations_path=conversations_dir
        )

        assert manager.storage_dir == conversations_dir

    def test_cllm_conversations_path_env_var(self, tmp_path, monkeypatch):
        """Test CLLM_CONVERSATIONS_PATH environment variable."""
        conversations_dir = tmp_path / "env_conversations"
        conversations_dir.mkdir(parents=True)

        # Set environment variable
        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(conversations_dir))

        manager = ConversationManager()
        assert manager.storage_dir == conversations_dir

    def test_conversations_path_precedence_over_env_var(self, tmp_path, monkeypatch):
        """Test that CLI conversations_path takes precedence over environment variable."""
        env_dir = tmp_path / "env_conversations"
        env_dir.mkdir()
        cli_dir = tmp_path / "cli_conversations"
        cli_dir.mkdir()

        # Set environment variable
        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(env_dir))

        # CLI parameter should override env var
        manager = ConversationManager(conversations_path=cli_dir)
        assert manager.storage_dir == cli_dir

    def test_cllm_path_with_conversations_subdirectory(self, tmp_path):
        """Test that cllm_path creates conversations subdirectory."""
        cllm_dir = tmp_path / "custom_cllm"
        cllm_dir.mkdir()

        manager = ConversationManager(cllm_path=cllm_dir)
        expected_path = cllm_dir / "conversations"
        assert manager.storage_dir == expected_path

    def test_cllm_path_env_var_conversations(self, tmp_path, monkeypatch):
        """Test CLLM_PATH environment variable creates conversations subdirectory."""
        cllm_dir = tmp_path / "env_cllm"
        cllm_dir.mkdir()

        monkeypatch.setenv("CLLM_PATH", str(cllm_dir))

        manager = ConversationManager()
        expected_path = cllm_dir / "conversations"
        assert manager.storage_dir == expected_path

    def test_conversations_path_precedence_over_cllm_path(self, tmp_path):
        """Test that conversations_path takes precedence over cllm_path."""
        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir()
        cllm_dir = tmp_path / "cllm"
        cllm_dir.mkdir()

        manager = ConversationManager(
            cllm_path=cllm_dir, conversations_path=conversations_dir
        )

        # conversations_path should win
        assert manager.storage_dir == conversations_dir

    def test_conversations_path_precedence_over_cllm_path_env(
        self, tmp_path, monkeypatch
    ):
        """Test that CLLM_CONVERSATIONS_PATH takes precedence over CLLM_PATH."""
        conversations_dir = tmp_path / "conversations"
        conversations_dir.mkdir()
        cllm_dir = tmp_path / "cllm"
        cllm_dir.mkdir()

        monkeypatch.setenv("CLLM_PATH", str(cllm_dir))
        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(conversations_dir))

        manager = ConversationManager()

        # CLLM_CONVERSATIONS_PATH should win
        assert manager.storage_dir == conversations_dir

    def test_full_precedence_order(self, tmp_path, monkeypatch):
        """Test complete precedence order from ADR-0017."""
        # Create all possible paths
        cli_conversations = tmp_path / "cli_conversations"
        cli_conversations.mkdir()
        env_conversations = tmp_path / "env_conversations"
        env_conversations.mkdir()
        cllm_path_dir = tmp_path / "cllm_path"
        cllm_path_dir.mkdir()

        # Set environment variables
        monkeypatch.setenv("CLLM_PATH", str(cllm_path_dir))
        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(env_conversations))

        # Test 1: CLI conversations_path wins over everything
        manager1 = ConversationManager(
            cllm_path=cllm_path_dir, conversations_path=cli_conversations
        )
        assert manager1.storage_dir == cli_conversations

        # Test 2: Env var CLLM_CONVERSATIONS_PATH wins over CLLM_PATH
        manager2 = ConversationManager()
        assert manager2.storage_dir == env_conversations

        # Test 3: CLLM_PATH used when CLLM_CONVERSATIONS_PATH not set
        monkeypatch.delenv("CLLM_CONVERSATIONS_PATH")
        manager3 = ConversationManager()
        assert manager3.storage_dir == cllm_path_dir / "conversations"

    def test_local_cllm_fallback(self, tmp_path, monkeypatch):
        """Test fallback to local .cllm directory when no overrides set."""
        # Create local .cllm directory
        local_cllm = tmp_path / ".cllm"
        local_cllm.mkdir()

        # Change to that directory
        monkeypatch.chdir(tmp_path)

        manager = ConversationManager()
        expected_path = tmp_path / ".cllm" / "conversations"
        assert manager.storage_dir == expected_path

    def test_home_directory_fallback(self, tmp_path, monkeypatch):
        """Test fallback to home directory when no other options available."""
        # Change to a directory without .cllm
        monkeypatch.chdir(tmp_path)

        manager = ConversationManager()
        expected_path = Path.home() / ".cllm" / "conversations"
        assert manager.storage_dir == expected_path

    def test_storage_dir_backwards_compatibility(self, tmp_path):
        """Test that storage_dir parameter still works for backwards compatibility."""
        storage = tmp_path / "custom_storage"
        storage.mkdir()

        manager = ConversationManager(storage_dir=storage)
        assert manager.storage_dir == storage

    def test_conversations_path_auto_creation(self, tmp_path):
        """Test that conversations directory is auto-created if parent exists."""
        conversations_dir = tmp_path / "conversations"
        # Don't create the directory - it should be auto-created

        manager = ConversationManager(conversations_path=conversations_dir)
        assert manager.storage_dir.exists()
        assert manager.storage_dir == conversations_dir


class TestConversationPathFromConfig:
    """Test suite for conversations_path from Cllmfile.yml (ADR-0017)."""

    def test_config_conversations_path_used(self, tmp_path, monkeypatch):
        """Test that conversations_path from config is used when set."""
        # This simulates the CLI passing the config value to ConversationManager
        config_path = tmp_path / "config_conversations"
        config_path.mkdir()

        # CLI would parse config and pass this value
        manager = ConversationManager(conversations_path=config_path)
        assert manager.storage_dir == config_path

    def test_config_path_precedence_over_defaults(self, tmp_path, monkeypatch):
        """Test that config conversations_path takes precedence over defaults."""
        # Create local .cllm directory
        local_cllm = tmp_path / ".cllm"
        local_cllm.mkdir()

        # Change to that directory
        monkeypatch.chdir(tmp_path)

        # Config path should override local .cllm
        config_path = tmp_path / "from_config"
        config_path.mkdir()

        manager = ConversationManager(conversations_path=config_path)

        # Should use config path, not local .cllm/conversations
        assert manager.storage_dir == config_path
        assert manager.storage_dir != local_cllm / "conversations"

    def test_env_var_precedence_over_config(self, tmp_path, monkeypatch):
        """Test that CLLM_CONVERSATIONS_PATH env var takes precedence over config."""
        env_path = tmp_path / "from_env"
        env_path.mkdir()
        config_path = tmp_path / "from_config"
        config_path.mkdir()

        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(env_path))

        # Even if config path is passed, env var should not be used
        # because CLI should resolve the precedence before calling ConversationManager
        # This test verifies the manager uses what it's given
        manager = ConversationManager(conversations_path=config_path)
        assert manager.storage_dir == config_path

        # If no conversations_path is passed, env var should be used
        manager2 = ConversationManager()
        assert manager2.storage_dir == env_path

    def test_relative_path_from_config(self, tmp_path, monkeypatch):
        """Test that relative paths work from Cllmfile.yml."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Relative path should be stored as-is and work correctly
        from pathlib import Path

        relative_path = Path("./conversations")

        manager = ConversationManager(conversations_path=relative_path)

        # Path is stored as relative (normalized)
        assert manager.storage_dir == Path("conversations")
        assert manager.storage_dir.exists()  # Should be auto-created

        # But it resolves to the correct absolute path when used
        assert manager.storage_dir.resolve() == tmp_path / "conversations"


class TestSystemMessageCapture:
    """Test suite for ADR-0020: Capture System Prompt in Conversation Data."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_storage):
        """Create a ConversationManager with temporary storage."""
        return ConversationManager(storage_dir=temp_storage)

    def test_has_system_message_empty_conversation(self):
        """Test has_system_message returns False for empty conversation."""
        conv = Conversation(id="test", model="gpt-4")
        assert not conv.has_system_message()

    def test_has_system_message_with_system_message(self):
        """Test has_system_message returns True when system message exists."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[{"role": "system", "content": "You are helpful."}],
        )
        assert conv.has_system_message()

    def test_has_system_message_with_user_message_first(self):
        """Test has_system_message returns False when first message is not system."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert not conv.has_system_message()

    def test_set_system_message_on_empty_conversation(self):
        """Test setting system message on empty conversation."""
        conv = Conversation(id="test", model="gpt-4")
        conv.set_system_message("You are a helpful assistant.")

        assert len(conv.messages) == 1
        assert conv.messages[0]["role"] == "system"
        assert conv.messages[0]["content"] == "You are a helpful assistant."

    def test_set_system_message_updates_existing(self):
        """Test setting system message updates existing system message."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[{"role": "system", "content": "Old system message"}],
        )
        conv.set_system_message("New system message")

        assert len(conv.messages) == 1
        assert conv.messages[0]["role"] == "system"
        assert conv.messages[0]["content"] == "New system message"

    def test_set_system_message_inserts_before_user_messages(self):
        """Test setting system message inserts at beginning even with existing messages."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        )
        conv.set_system_message("You are helpful.")

        assert len(conv.messages) == 3
        assert conv.messages[0]["role"] == "system"
        assert conv.messages[0]["content"] == "You are helpful."
        assert conv.messages[1]["role"] == "user"
        assert conv.messages[2]["role"] == "assistant"

    def test_create_conversation_with_system_message(self, manager):
        """Test creating a conversation with system message."""
        conv = manager.create(
            conversation_id="test",
            model="gpt-4",
            system_message="You are a helpful assistant.",
        )

        assert conv.id == "test"
        assert conv.model == "gpt-4"
        assert len(conv.messages) == 1
        assert conv.messages[0]["role"] == "system"
        assert conv.messages[0]["content"] == "You are a helpful assistant."

    def test_create_conversation_without_system_message(self, manager):
        """Test creating a conversation without system message."""
        conv = manager.create(conversation_id="test", model="gpt-4")

        assert conv.id == "test"
        assert conv.model == "gpt-4"
        assert len(conv.messages) == 0
        assert not conv.has_system_message()

    def test_save_and_load_conversation_with_system_message(self, manager):
        """Test saving and loading conversation preserves system message."""
        conv = manager.create(
            conversation_id="test",
            model="gpt-4",
            system_message="You are a helpful assistant.",
        )
        conv.add_message("user", "Hello")
        conv.add_message("assistant", "Hi there!")
        manager.save(conv)

        loaded = manager.load("test")
        assert len(loaded.messages) == 3
        assert loaded.messages[0]["role"] == "system"
        assert loaded.messages[0]["content"] == "You are a helpful assistant."
        assert loaded.messages[1]["role"] == "user"
        assert loaded.messages[2]["role"] == "assistant"

    def test_backward_compatibility_load_without_system_message(self, manager):
        """Test loading old conversations without system message works."""
        # Create conversation manually without system message (simulating old format)
        conv = Conversation(
            id="old-conv",
            model="gpt-4",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        )
        manager.save(conv)

        # Load and verify
        loaded = manager.load("old-conv")
        assert not loaded.has_system_message()
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["role"] == "user"

    def test_system_message_persisted_in_json(self, manager):
        """Test system message is persisted in JSON file."""
        conv = manager.create(
            conversation_id="test",
            model="gpt-4",
            system_message="You are a coding assistant.",
        )
        manager.save(conv)

        # Read JSON file directly
        filepath = manager.storage_dir / "test.json"
        with open(filepath) as f:
            data = json.load(f)

        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "system"
        assert data["messages"][0]["content"] == "You are a coding assistant."

    def test_system_message_not_duplicated_on_multiple_turns(self, manager):
        """Test system message is not duplicated when adding messages."""
        conv = manager.create(
            conversation_id="test",
            model="gpt-4",
            system_message="You are helpful.",
        )

        # Add multiple turns
        conv.add_message("user", "First question")
        conv.add_message("assistant", "First answer")
        conv.add_message("user", "Second question")
        conv.add_message("assistant", "Second answer")

        # Count system messages - should only be 1
        system_messages = [m for m in conv.messages if m["role"] == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "You are helpful."
        assert conv.messages[0]["role"] == "system"  # Should be first

    def test_empty_system_message_not_added(self, manager):
        """Test empty system message is not added."""
        conv = manager.create(conversation_id="test", model="gpt-4", system_message="")

        assert len(conv.messages) == 0
        assert not conv.has_system_message()

    def test_none_system_message_not_added(self, manager):
        """Test None system message is not added."""
        conv = manager.create(
            conversation_id="test", model="gpt-4", system_message=None
        )

        assert len(conv.messages) == 0
        assert not conv.has_system_message()


class TestContextInSystemMessage:
    """Test suite for ADR-0021: Context Injection as Persistent System Context."""

    def test_has_context_empty_conversation(self):
        """Test has_context_in_system_message returns False for empty conversation."""
        conv = Conversation(id="test", model="gpt-4")
        assert not conv.has_context_in_system_message()

    def test_has_context_no_system_message(self):
        """Test has_context_in_system_message returns False when no system message."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
        )
        assert not conv.has_context_in_system_message()

    def test_has_context_system_message_without_context(self):
        """Test has_context_in_system_message returns False for system message without context."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
        )
        assert not conv.has_context_in_system_message()

    def test_has_context_with_context_markers(self):
        """Test has_context_in_system_message returns True when context markers present."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are helpful.\n\n--- Context: Test ---\nSome context\n--- End Context ---",
                }
            ],
        )
        assert conv.has_context_in_system_message()

    def test_has_context_only_context_no_prompt(self):
        """Test has_context_in_system_message returns True for context-only system message."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "--- Context: Git Status ---\nM file.py\n--- End Context ---",
                }
            ],
        )
        assert conv.has_context_in_system_message()

    def test_has_context_multiple_context_blocks(self):
        """Test has_context_in_system_message with multiple context blocks."""
        conv = Conversation(
            id="test",
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "--- Context: Time ---\n2025-10-31\n--- End Context ---\n\n--- Context: Git ---\nM file.py\n--- End Context ---",
                }
            ],
        )
        assert conv.has_context_in_system_message()

    def test_has_context_partial_markers(self):
        """Test has_context_in_system_message returns False with only partial markers."""
        # Only start marker
        conv1 = Conversation(
            id="test1",
            model="gpt-4",
            messages=[
                {"role": "system", "content": "--- Context: Test ---\nNo end marker"}
            ],
        )
        assert not conv1.has_context_in_system_message()

        # Only end marker
        conv2 = Conversation(
            id="test2",
            model="gpt-4",
            messages=[{"role": "system", "content": "No start\n--- End Context ---"}],
        )
        assert not conv2.has_context_in_system_message()
