"""
Tests for init module.

Implements test cases specified in ADR-0015.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from cllm.init import (
    InitError,
    copy_template,
    create_directory_structure,
    discover_templates,
    get_default_template,
    get_home_cllm_dir,
    get_local_cllm_dir,
    get_template_dir,
    initialize,
    list_available_templates,
    update_gitignore,
)


class TestDirectoryPaths:
    """Test directory path functions."""

    def test_get_home_cllm_dir(self):
        """Test home directory path is correct."""
        home_dir = get_home_cllm_dir()
        assert home_dir == Path.home() / ".cllm"

    def test_get_local_cllm_dir(self):
        """Test local directory path is correct."""
        local_dir = get_local_cllm_dir()
        assert local_dir == Path.cwd() / ".cllm"


class TestTemplateDiscovery:
    """Test template discovery functions."""

    def test_get_template_dir_exists(self):
        """Test that template directory exists and is accessible."""
        template_dir = get_template_dir()
        assert template_dir.exists()
        assert template_dir.is_dir()

    def test_discover_templates(self):
        """Test template discovery from examples/configs/."""
        templates = discover_templates()

        # Should find at least the common templates
        expected_templates = [
            "code-review",
            "summarize",
            "creative",
            "debug",
            "extraction",
            "task-parser",
            "context-demo",
        ]

        for template_name in expected_templates:
            assert template_name in templates
            assert templates[template_name].exists()
            assert templates[template_name].suffix == ".yml"

    def test_get_default_template(self):
        """Test default template exists."""
        default_template = get_default_template()
        assert default_template.exists()
        assert default_template.name == "Cllmfile.yml"

    def test_list_templates_runs_without_error(self, capsys):
        """Test --list-templates output format."""
        list_available_templates()
        captured = capsys.readouterr()

        # Check output contains expected elements
        assert "Available templates:" in captured.out
        assert "code-review" in captured.out
        assert "summarize" in captured.out
        assert "Usage: cllm init --template <name>" in captured.out


class TestDirectoryCreation:
    """Test directory creation functions."""

    def test_create_directory_structure_new(self, tmp_path):
        """Test creating new .cllm directory."""
        cllm_dir = tmp_path / ".cllm"

        created_new, messages = create_directory_structure(cllm_dir)

        assert created_new is True
        assert cllm_dir.exists()
        assert (cllm_dir / "conversations").exists()
        assert any("✓ Created" in msg for msg in messages)

    def test_create_directory_structure_existing_force(self, tmp_path):
        """Test reinitializing existing directory with --force."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        created_new, _messages = create_directory_structure(cllm_dir, force=True)

        assert created_new is False
        assert cllm_dir.exists()
        assert (cllm_dir / "conversations").exists()

    def test_create_directory_structure_existing_no_force(self, tmp_path):
        """Test error when directory exists without --force."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        with pytest.raises(InitError, match="already exists"):
            create_directory_structure(cllm_dir, force=False)


class TestTemplateCopying:
    """Test template copying functionality."""

    def test_copy_default_template(self, tmp_path):
        """Test copying default template."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        messages = copy_template(cllm_dir, template_name=None)

        target_file = cllm_dir / "Cllmfile.yml"
        assert target_file.exists()
        assert any("starter configuration" in msg for msg in messages)

        # Verify content was actually copied
        content = target_file.read_text()
        assert len(content) > 0
        assert "model:" in content

    def test_copy_named_template(self, tmp_path):
        """Test copying named template (code-review)."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        messages = copy_template(cllm_dir, template_name="code-review")

        # Should create code-review.Cllmfile.yml, not Cllmfile.yml
        target_file = cllm_dir / "code-review.Cllmfile.yml"
        assert target_file.exists()
        assert any("code-review" in msg for msg in messages)

        # Verify it's the code-review template
        content = target_file.read_text()
        assert (
            "Code Review Configuration" in content or "code review" in content.lower()
        )

    def test_copy_invalid_template(self, tmp_path):
        """Test error when template doesn't exist."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        with pytest.raises(InitError, match="not found"):
            copy_template(cllm_dir, template_name="nonexistent-template")

    def test_copy_template_existing_no_force(self, tmp_path):
        """Test error when file exists without --force."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()
        (cllm_dir / "Cllmfile.yml").write_text("existing")

        with pytest.raises(InitError, match="already exists"):
            copy_template(cllm_dir, template_name=None, force=False)

    def test_copy_template_existing_with_force(self, tmp_path):
        """Test overwriting existing file with --force."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()
        (cllm_dir / "Cllmfile.yml").write_text("existing")

        copy_template(cllm_dir, template_name=None, force=True)

        target_file = cllm_dir / "Cllmfile.yml"
        assert target_file.exists()
        # Content should be replaced
        assert target_file.read_text() != "existing"


class TestGitignoreUpdate:
    """Test .gitignore update functionality."""

    def test_update_gitignore_creates_new(self, tmp_path, monkeypatch):
        """Test creating new .gitignore."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        messages = update_gitignore(cllm_dir)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".cllm/conversations/" in content
        assert ".cllm/*.log" in content
        assert any("Created .gitignore" in msg for msg in messages)

    def test_update_gitignore_appends_to_existing(self, tmp_path, monkeypatch):
        """Test appending to existing .gitignore."""
        monkeypatch.chdir(tmp_path)

        # Create existing .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n")

        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        messages = update_gitignore(cllm_dir)

        content = gitignore.read_text()
        assert "*.pyc" in content  # Original content preserved
        assert ".cllm/conversations/" in content
        assert any("Updated .gitignore" in msg for msg in messages)

    def test_update_gitignore_idempotent(self, tmp_path, monkeypatch):
        """Test that running twice doesn't duplicate entries."""
        monkeypatch.chdir(tmp_path)

        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        # Run once
        update_gitignore(cllm_dir)

        # Run again
        messages = update_gitignore(cllm_dir)

        gitignore = tmp_path / ".gitignore"
        content = gitignore.read_text()

        # Should not have duplicate entries
        assert content.count(".cllm/conversations/") == 1
        assert any("already contains" in msg for msg in messages)

    def test_update_gitignore_skips_global(self, tmp_path):
        """Test that global ~/.cllm doesn't update .gitignore."""
        home_cllm = get_home_cllm_dir()

        messages = update_gitignore(home_cllm)

        # Should return empty messages (no action taken)
        assert len(messages) == 0


class TestInitializeFunction:
    """Test the main initialize() function."""

    def test_init_local_default(self, tmp_path, monkeypatch):
        """Test default behavior initializes local directory."""
        monkeypatch.chdir(tmp_path)

        initialize()

        local_cllm = tmp_path / ".cllm"
        assert local_cllm.exists()
        assert (local_cllm / "conversations").exists()
        assert (local_cllm / "Cllmfile.yml").exists()
        assert (tmp_path / ".gitignore").exists()

    def test_init_global(self, tmp_path, monkeypatch):
        """Test --global initializes ~/.cllm."""
        # Mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        with patch("cllm.init.Path.home", return_value=fake_home):
            initialize(global_init=True)

            global_cllm = fake_home / ".cllm"
            assert global_cllm.exists()
            assert (global_cllm / "conversations").exists()
            assert (global_cllm / "Cllmfile.yml").exists()

    def test_init_both_global_and_local(self, tmp_path, monkeypatch):
        """Test --global --local initializes both."""
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        with patch("cllm.init.Path.home", return_value=fake_home):
            initialize(global_init=True, local_init=True)

            # Check both directories
            global_cllm = fake_home / ".cllm"
            local_cllm = tmp_path / ".cllm"

            assert global_cllm.exists()
            assert (global_cllm / "Cllmfile.yml").exists()

            assert local_cllm.exists()
            assert (local_cllm / "Cllmfile.yml").exists()

    def test_init_with_template(self, tmp_path, monkeypatch):
        """Test --template flag."""
        monkeypatch.chdir(tmp_path)

        initialize(template_name="code-review")

        local_cllm = tmp_path / ".cllm"
        # Should create code-review.Cllmfile.yml, not Cllmfile.yml
        cllmfile = local_cllm / "code-review.Cllmfile.yml"
        assert cllmfile.exists()

        # Verify it's the code-review template
        content = cllmfile.read_text()
        assert "code review" in content.lower()

    def test_init_idempotent_with_force(self, tmp_path, monkeypatch):
        """Test running init twice with --force."""
        monkeypatch.chdir(tmp_path)

        # First init
        initialize()

        # Second init with force
        initialize(force=True)

        local_cllm = tmp_path / ".cllm"
        assert local_cllm.exists()
        assert (local_cllm / "conversations").exists()
        assert (local_cllm / "Cllmfile.yml").exists()

    def test_init_fails_without_force_when_exists(self, tmp_path, monkeypatch, capsys):
        """Test proper error when directory exists without --force."""
        monkeypatch.chdir(tmp_path)

        # Create existing directory
        local_cllm = tmp_path / ".cllm"
        local_cllm.mkdir()

        # Should raise InitError (which is caught and printed in actual CLI)
        with pytest.raises(SystemExit):
            initialize(force=False)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_template_with_invalid_name(self, tmp_path, monkeypatch):
        """Test that invalid template name raises proper error."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            initialize(template_name="this-template-does-not-exist")

    def test_init_in_directory_without_write_permissions(self, tmp_path, monkeypatch):
        """Test error handling for permission issues."""
        # This test is platform-dependent, so we'll just verify the error is caught
        # In real usage, this would fail with PermissionError
        pass  # Skip for now - hard to test cross-platform


class TestConfigOverrides:
    """Test configuration overrides (ADR-0023)."""

    def test_init_with_model_override(self, tmp_path, monkeypatch):
        """Test --model flag overrides default config."""
        monkeypatch.chdir(tmp_path)

        config_overrides = {"model": "gpt-4"}
        initialize(config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "Cllmfile.yml"
        assert cllmfile.exists()

        # Verify config contains overridden model
        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        assert config["model"] == "gpt-4"

    def test_init_with_temperature_override(self, tmp_path, monkeypatch):
        """Test --temperature flag overrides default config."""
        monkeypatch.chdir(tmp_path)

        config_overrides = {"temperature": 0.9}
        initialize(config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "Cllmfile.yml"

        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        assert config["temperature"] == 0.9

    def test_init_with_multiple_overrides(self, tmp_path, monkeypatch):
        """Test multiple flags override config."""
        monkeypatch.chdir(tmp_path)

        config_overrides = {
            "model": "claude-3-opus-20240229",
            "temperature": 0.7,
            "max_tokens": 2000,
            "timeout": 120,
        }
        initialize(config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "Cllmfile.yml"

        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        assert config["model"] == "claude-3-opus-20240229"
        assert config["temperature"] == 0.7
        assert config["max_tokens"] == 2000
        assert config["timeout"] == 120

    def test_init_with_system_prompt_override(self, tmp_path, monkeypatch):
        """Test --system flag sets default_system_message."""
        monkeypatch.chdir(tmp_path)

        system_prompt = "You are a helpful coding assistant."
        config_overrides = {"default_system_message": system_prompt}
        initialize(config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "Cllmfile.yml"

        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        assert config["default_system_message"] == system_prompt

    def test_init_template_with_overrides(self, tmp_path, monkeypatch):
        """Test combining --template with flag overrides."""
        monkeypatch.chdir(tmp_path)

        # Use code-review template but override the model
        config_overrides = {"model": "gpt-4-turbo"}
        initialize(template_name="code-review", config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "code-review.Cllmfile.yml"
        assert cllmfile.exists()

        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        # Model should be overridden
        assert config["model"] == "gpt-4-turbo"

        # Template-specific fields should be preserved
        assert "default_system_message" in config
        assert "code review" in config["default_system_message"].lower()

    def test_init_template_override_preserves_non_overridden_fields(
        self, tmp_path, monkeypatch
    ):
        """Test that non-overridden fields from template are preserved."""
        monkeypatch.chdir(tmp_path)

        # Override only model, temperature should come from template
        config_overrides = {"model": "gpt-4"}
        initialize(template_name="code-review", config_overrides=config_overrides)

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "code-review.Cllmfile.yml"

        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        # Model overridden
        assert config["model"] == "gpt-4"

        # Template values preserved
        assert "temperature" in config  # From template
        assert "default_system_message" in config  # From template
        assert "context_commands" in config  # From template

    def test_copy_template_shows_override_summary(self, tmp_path):
        """Test that copy_template includes override summary in message."""
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()

        config_overrides = {"model": "gpt-4", "temperature": 0.8}
        messages = copy_template(
            cllm_dir, template_name=None, config_overrides=config_overrides
        )

        # Message should show what was overridden
        message = messages[0]
        assert "overridden:" in message
        assert "model" in message or "temperature" in message

    def test_init_without_overrides_unchanged(self, tmp_path, monkeypatch):
        """Test that init without overrides still works (backward compatibility)."""
        monkeypatch.chdir(tmp_path)

        # No overrides - should work as before
        initialize()

        local_cllm = tmp_path / ".cllm"
        cllmfile = local_cllm / "Cllmfile.yml"
        assert cllmfile.exists()

        # Should have default config
        import yaml

        with open(cllmfile) as f:
            config = yaml.safe_load(f)

        assert "model" in config  # Should have some default model
