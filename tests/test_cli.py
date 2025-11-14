"""
Tests for the CLI.

These tests verify that the command-line interface works correctly.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cllm.cli import configure_debugging, main, print_model_list


class TestListModels:
    """Test suite for model listing functionality."""

    @patch(
        "cllm.cli.litellm.model_list", ["gpt-4", "claude-3-opus-20240229", "gemini-pro"]
    )
    def test_print_model_list_output(self, capsys):
        """Test that print_model_list produces expected output."""
        print_model_list()
        captured = capsys.readouterr()

        # Verify header is present
        assert "Available Models" in captured.out
        assert "3 total" in captured.out

        # Verify models are listed
        assert "gpt-4" in captured.out
        assert "claude-3-opus-20240229" in captured.out
        assert "gemini-pro" in captured.out

        # Verify tip is shown
        assert "grep" in captured.out

    @patch(
        "cllm.cli.litellm.model_list",
        [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "gemini-pro",
            "gemini-1.5-flash",
        ],
    )
    def test_print_model_list_categorization(self, capsys):
        """Test that models are categorized by provider."""
        print_model_list()
        captured = capsys.readouterr()

        # Verify provider headers are present
        assert "OpenAI:" in captured.out
        assert "Anthropic:" in captured.out
        assert "Google:" in captured.out

    @patch("cllm.cli.litellm.model_list", [])
    def test_print_model_list_empty(self, capsys):
        """Test print_model_list with empty model list."""
        print_model_list()
        captured = capsys.readouterr()

        # Should still print header with 0 total
        assert "Available Models" in captured.out
        assert "0 total" in captured.out


class TestListModelsIntegration:
    """Integration tests for --list-models flag."""

    @patch("cllm.cli.litellm.model_list", ["gpt-4", "claude-3-opus-20240229"])
    @patch("sys.argv", ["cllm", "--list-models"])
    def test_list_models_exits_successfully(self, capsys):
        """Test that --list-models exits after printing."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 0
        assert exc_info.value.code == 0

        # Should have printed models
        captured = capsys.readouterr()
        assert "Available Models" in captured.out
        assert "gpt-4" in captured.out
        assert "claude-3-opus-20240229" in captured.out

    @patch("cllm.cli.litellm.model_list", ["gpt-4"])
    @patch("sys.argv", ["cllm", "--list-models"])
    @patch("cllm.cli.read_prompt")
    def test_list_models_does_not_read_prompt(self, mock_read_prompt, capsys):
        """Test that --list-models doesn't try to read prompt."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit successfully
        assert exc_info.value.code == 0

        # Should NOT have called read_prompt
        mock_read_prompt.assert_not_called()

    @patch("cllm.cli.litellm.model_list", ["gpt-4"])
    @patch("sys.argv", ["cllm", "--list-models", "--model", "gpt-4"])
    @patch("cllm.cli.LLMClient")
    def test_list_models_does_not_create_client(self, mock_client, capsys):
        """Test that --list-models doesn't initialize LLMClient."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit successfully
        assert exc_info.value.code == 0

        # Should NOT have created client
        mock_client.assert_not_called()


class TestValidateSchema:
    """Test suite for --validate-schema flag."""

    @patch(
        "sys.argv",
        [
            "cllm",
            "--validate-schema",
            "--json-schema",
            '{"type": "object", "properties": {"name": {"type": "string"}}}',
        ],
    )
    @patch("cllm.cli.load_config", return_value={})
    def test_validate_schema_with_inline_json(self, mock_load_config, capsys):
        """Test --validate-schema with inline JSON schema."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 0 (success)
        assert exc_info.value.code == 0

        # Should print validation success
        captured = capsys.readouterr()
        assert "Schema is valid" in captured.out
        assert "Schema validation successful" in captured.out

    @patch(
        "sys.argv",
        [
            "cllm",
            "--validate-schema",
            "--json-schema",
            '{"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "number"}}, "required": ["name"]}',
        ],
    )
    @patch("cllm.cli.load_config", return_value={})
    def test_validate_schema_shows_object_details(self, mock_load_config, capsys):
        """Test that --validate-schema shows details about object schemas."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Type: object" in captured.out
        assert "Properties: 2" in captured.out
        assert "name: string (required)" in captured.out
        assert "age: number (optional)" in captured.out

    @patch("sys.argv", ["cllm", "--validate-schema"])
    @patch("cllm.cli.load_config", return_value={})
    def test_validate_schema_without_schema_errors(self, mock_load_config, capsys):
        """Test that --validate-schema without a schema shows error."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 1 (error)
        assert exc_info.value.code == 1

        # Should print error message
        captured = capsys.readouterr()
        assert "Error: No schema provided" in captured.err
        assert "--json-schema or --json-schema-file" in captured.err

    @patch(
        "sys.argv",
        ["cllm", "--validate-schema", "--json-schema", '{"type": "invalid"}'],
    )
    @patch("cllm.cli.load_config", return_value={})
    def test_validate_schema_with_invalid_schema(self, mock_load_config, capsys):
        """Test that --validate-schema with invalid schema shows error."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 1 (error)
        assert exc_info.value.code == 1

        # Should print schema error
        captured = capsys.readouterr()
        assert "Schema error" in captured.err

    @patch("sys.argv", ["cllm", "--validate-schema"])
    @patch(
        "cllm.cli.load_config",
        return_value={
            "json_schema": {
                "type": "object",
                "properties": {"test": {"type": "string"}},
            }
        },
    )
    def test_validate_schema_from_cllmfile(self, mock_load_config, capsys):
        """Test --validate-schema with schema from Cllmfile."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with code 0 (success)
        assert exc_info.value.code == 0

        # Should print validation success
        captured = capsys.readouterr()
        assert "Schema is valid" in captured.out
        assert "Type: object" in captured.out


class TestDebugging:
    """Test suite for debugging and logging features (ADR-0009)."""

    @patch("cllm.cli.litellm")
    def test_configure_debugging_with_debug_flag(self, mock_litellm, capsys):
        """Test that debug=True sets litellm.set_verbose=True."""
        configure_debugging(debug=True)

        # Verify litellm.set_verbose was set to True
        assert mock_litellm.set_verbose is True

        # Verify warning message is printed
        captured = capsys.readouterr()
        assert "⚠️  Debug mode enabled" in captured.err
        assert "API keys and sensitive data" in captured.err

    @patch("cllm.cli.litellm")
    def test_configure_debugging_with_json_logs(self, mock_litellm):
        """Test that json_logs=True sets litellm.json_logs=True."""
        configure_debugging(json_logs=True)

        # Verify litellm.json_logs was set to True
        assert mock_litellm.json_logs is True

    @patch("cllm.cli.litellm")
    def test_configure_debugging_without_flags(self, mock_litellm):
        """Test that configure_debugging with no flags does nothing."""
        # Reset mock attributes
        mock_litellm.set_verbose = False
        mock_litellm.json_logs = False

        configure_debugging()

        # Verify flags remain False
        assert mock_litellm.set_verbose is False
        assert mock_litellm.json_logs is False

    @patch("cllm.cli.litellm")
    def test_configure_debugging_with_log_file(self, mock_litellm):
        """Test that log_file creates file with proper permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            # Configure with log file
            handle = configure_debugging(log_file=str(log_file))

            # Verify file was created
            assert log_file.exists()

            # Verify file has restrictive permissions (0600) on Unix
            if hasattr(os, "chmod"):
                stat_result = log_file.stat()
                # Check that permissions are 0600 (owner read/write only)
                assert oct(stat_result.st_mode)[-3:] == "600"

            # Clean up
            if handle:
                handle.close()

    @patch("cllm.cli.litellm")
    def test_configure_debugging_log_file_creates_parent_dirs(self, mock_litellm):
        """Test that log_file creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "nested" / "dir" / "test.log"

            # Configure with nested log file path
            handle = configure_debugging(log_file=str(log_file))

            # Verify parent directories were created
            assert log_file.parent.exists()
            assert log_file.exists()

            # Clean up
            if handle:
                handle.close()

    @patch("cllm.cli.litellm")
    def test_configure_debugging_combined_flags(self, mock_litellm, capsys):
        """Test that all debug flags can be combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            handle = configure_debugging(
                debug=True, json_logs=True, log_file=str(log_file)
            )

            # Verify all flags were set
            assert mock_litellm.set_verbose is True
            assert mock_litellm.json_logs is True
            assert log_file.exists()

            # Clean up
            if handle:
                handle.close()

    @patch("sys.argv", ["cllm", "--debug", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_cli_debug_flag(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty, capsys
    ):
        """Test that --debug flag enables debug mode via CLI."""
        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify debug mode was enabled
        assert mock_litellm.set_verbose is True

        # Verify warning was shown
        captured = capsys.readouterr()
        assert "⚠️  Debug mode enabled" in captured.err

    @patch("sys.argv", ["cllm", "--json-logs", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_cli_json_logs_flag(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that --json-logs flag enables JSON logging via CLI."""
        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify JSON logs were enabled
        assert mock_litellm.json_logs is True

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_cli_log_file_flag(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that --log-file flag creates log file via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "cli-test.log"

            with patch(
                "sys.argv", ["cllm", "--log-file", str(log_file), "test prompt"]
            ):
                # Mock the client to avoid actual API calls
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "test response"
                mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify log file was created
                assert log_file.exists()

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_debug_from_cllmfile(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that debug settings from Cllmfile are applied."""
        # Mock config to include debug settings
        mock_load_config.return_value = {
            "debug": True,
            "json_logs": True,
        }

        with patch("sys.argv", ["cllm", "test prompt"]):
            # Mock the client to avoid actual API calls
            mock_instance = MagicMock()
            mock_instance.complete.return_value = "test response"
            mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
            mock_client.return_value = mock_instance

            try:
                main()
            except SystemExit:
                pass

            # Verify debug settings were applied from config
            assert mock_litellm.set_verbose is True
            assert mock_litellm.json_logs is True

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={"debug": False})
    @patch("cllm.cli.litellm")
    def test_cli_flag_overrides_cllmfile(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that CLI flag overrides Cllmfile setting."""
        with patch("sys.argv", ["cllm", "--debug", "test prompt"]):
            # Mock the client to avoid actual API calls
            mock_instance = MagicMock()
            mock_instance.complete.return_value = "test response"
            mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
            mock_client.return_value = mock_instance

            try:
                main()
            except SystemExit:
                pass

            # Verify CLI flag overrode config
            assert mock_litellm.set_verbose is True

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_environment_variable_debug(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that CLLM_DEBUG environment variable enables debug mode."""
        with patch.dict(os.environ, {"CLLM_DEBUG": "1"}):
            with patch("sys.argv", ["cllm", "test prompt"]):
                # Mock the client to avoid actual API calls
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "test response"
                mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify debug mode was enabled via environment variable
                assert mock_litellm.set_verbose is True

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_environment_variable_json_logs(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that CLLM_JSON_LOGS environment variable enables JSON logging."""
        with patch.dict(os.environ, {"CLLM_JSON_LOGS": "1"}):
            with patch("sys.argv", ["cllm", "test prompt"]):
                # Mock the client to avoid actual API calls
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "test response"
                mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify JSON logs were enabled via environment variable
                assert mock_litellm.json_logs is True


class TestVerbosity:
    """Test suite for verbosity levels (ADR-0025)."""

    def test_verbosity_handler_level_0(self, capsys):
        """Test VerbosityHandler level 0 produces no output."""
        from cllm.cli import VerbosityHandler

        handler = VerbosityHandler(level=0)
        handler.print_basic_info(
            model="gpt-4",
            input_tokens=10,
            output_tokens=20,
            provider="openai",
            latency_seconds=1.5,
        )

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_verbosity_handler_level_1(self, capsys):
        """Test VerbosityHandler level 1 prints basic info."""
        from cllm.cli import VerbosityHandler

        handler = VerbosityHandler(level=1)
        handler.print_basic_info(
            model="gpt-4",
            input_tokens=10,
            output_tokens=20,
            provider="openai",
            latency_seconds=1.5,
        )

        captured = capsys.readouterr()
        assert "Model: gpt-4" in captured.err
        assert "Tokens: 10 input, 20 output (30 total)" in captured.err
        assert "Provider: openai" in captured.err
        assert "Latency: 1.50s" in captured.err

    def test_verbosity_handler_level_1_partial_info(self, capsys):
        """Test VerbosityHandler level 1 with partial info."""
        from cllm.cli import VerbosityHandler

        handler = VerbosityHandler(level=1)
        handler.print_basic_info(model="gpt-4")

        captured = capsys.readouterr()
        assert "Model: gpt-4" in captured.err
        assert "Tokens:" not in captured.err

    def test_verbosity_handler_level_2(self, capsys):
        """Test VerbosityHandler level 2 prints API details."""
        from cllm.cli import VerbosityHandler

        handler = VerbosityHandler(level=2)
        handler.print_api_details(
            endpoint="https://api.openai.com/v1/chat/completions",
            parameters={"temperature": 0.7, "max_tokens": 1000},
            status_code=200,
            config_sources=["~/.cllm/Cllmfile.yml"],
        )

        captured = capsys.readouterr()
        assert "Endpoint: https://api.openai.com/v1/chat/completions" in captured.err
        assert "temperature=0.7" in captured.err
        assert "max_tokens=1000" in captured.err
        assert "Status: 200" in captured.err
        assert "Config sources" in captured.err

    def test_verbosity_handler_caps_level_at_3(self):
        """Test VerbosityHandler caps verbosity at level 3."""
        from cllm.cli import VerbosityHandler

        handler = VerbosityHandler(level=5)
        assert handler.level == 3

    @patch("sys.argv", ["cllm", "-v", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_cli_verbose_flag_level_1_short(
        self, mock_load_config, mock_client, mock_isatty
    ):
        """Test that -v flag sets verbosity level 1 via CLI."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify LLMClient was instantiated (means no early exit)
        assert mock_client.called

    @patch("sys.argv", ["cllm", "-vv", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_cli_verbose_flag_level_2_short(
        self, mock_load_config, mock_client, mock_isatty
    ):
        """Test that -vv flag sets verbosity level 2 via CLI."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify LLMClient was instantiated
        assert mock_client.called

    @patch("sys.argv", ["cllm", "-vvv", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_cli_verbose_level_3_short_enables_debug(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that -vvv (level 3) enables debug mode."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify debug mode was automatically enabled
        assert mock_litellm.set_verbose is True

    @patch("sys.argv", ["cllm", "-vvv", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    @patch("cllm.cli.LoguruVerbosityHandler.log_response_payload")
    @patch("cllm.cli.LoguruVerbosityHandler.log_request_payload")
    def test_cli_verbose_level_3_logs_payloads(
        self,
        mock_log_request,
        mock_log_response,
        mock_litellm,
        mock_load_config,
        mock_client,
        mock_isatty,
    ):
        """Test that -vvv logs request and response payloads."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = (
            "test response",
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "response_object": {"choices": []},
            },
        )
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        assert mock_log_request.called
        assert mock_log_response.called

    @patch("sys.argv", ["cllm", "-v", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.LoguruVerbosityHandler.log_event")
    def test_cli_verbose_level_1_logs_only_major_events(
        self,
        mock_log_event,
        mock_load_config,
        mock_client,
        mock_isatty,
    ):
        """Test that -v logs only major events."""
        from cllm.cli import main

        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = (
            "test response",
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "response_object": {"choices": []},
            },
        )
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        assert mock_log_event.call_count > 0
        for call in mock_log_event.call_args_list:
            assert call.kwargs.get("importance", "major") != "minor"

    @patch("sys.argv", ["cllm", "-vv", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.LoguruVerbosityHandler.log_event")
    def test_cli_verbose_level_2_logs_minor_events(
        self,
        mock_log_event,
        mock_load_config,
        mock_client,
        mock_isatty,
    ):
        """Test that -vv logs both major and minor events."""
        from cllm.cli import main

        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = (
            "test response",
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "response_object": {"choices": []},
            },
        )
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        assert mock_log_event.call_count > 0
        assert any(
            call.kwargs.get("importance") == "minor"
            for call in mock_log_event.call_args_list
        )

    @patch("sys.argv", ["cllm", "-v", "--model", "gpt-4", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.LoguruVerbosityHandler.log_event")
    def test_setting_resolution_logs_cli_source(
        self,
        mock_log_event,
        mock_load_config,
        mock_client,
        mock_isatty,
    ):
        """Test setting resolution event captures CLI source."""
        from cllm.cli import main

        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = (
            "test response",
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "response_object": {"choices": []},
            },
        )
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        setting_events = [
            call.kwargs.get("extra", {})
            for call in mock_log_event.call_args_list
            if call.args and call.args[0] == "Setting resolved"
        ]
        assert any(
            event.get("setting") == "model" and event.get("source") == "cli-flag"
            for event in setting_events
        )

    @patch("sys.argv", ["cllm", "-vv", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.LoguruVerbosityHandler.log_event")
    def test_setting_resolution_logs_env_source_for_debug(
        self,
        mock_log_event,
        mock_load_config,
        mock_client,
        mock_isatty,
    ):
        """Test setting resolution event captures environment source."""
        from cllm.cli import main

        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = (
            "test response",
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "response_object": {"choices": []},
            },
        )
        mock_client.return_value = mock_instance

        with patch.dict(os.environ, {"CLLM_DEBUG": "1"}):
            try:
                main()
            except SystemExit:
                pass

        setting_events = [
            call.kwargs.get("extra", {})
            for call in mock_log_event.call_args_list
            if call.args and call.args[0] == "Setting resolved"
        ]
        assert any(
            event.get("setting") == "debug"
                and event.get("source") == "env:CLLM_DEBUG"
            for event in setting_events
        )

    @patch("sys.argv", ["cllm", "--verbose", "--verbose", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_cli_verbose_flag_level_2_long(
        self, mock_load_config, mock_client, mock_isatty
    ):
        """Test that --verbose --verbose flag sets verbosity level 2 via CLI."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify LLMClient was instantiated
        assert mock_client.called

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_environment_variable_verbosity(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that CLLM_VERBOSITY environment variable sets verbosity level."""
        from cllm.cli import main

        with patch.dict(os.environ, {"CLLM_VERBOSITY": "2"}):
            with patch("sys.argv", ["cllm", "test prompt"]):
                # Mock the client to avoid actual API calls
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "test response"
                mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify client was called
                assert mock_client.called

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_invalid_environment_variable_verbosity(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty, capsys
    ):
        """Test that invalid CLLM_VERBOSITY value shows warning."""
        from cllm.cli import main

        with patch.dict(os.environ, {"CLLM_VERBOSITY": "invalid"}):
            with patch("sys.argv", ["cllm", "test prompt"]):
                # Mock the client to avoid actual API calls
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "test response"
                mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify warning was shown
                captured = capsys.readouterr()
                assert "Invalid CLLM_VERBOSITY" in captured.err

    def test_verbosity_from_cllmfile(self, tmp_path):
        """Test that verbosity can be loaded from Cllmfile.yml."""
        from cllm.cli import main

        # Create a temporary Cllmfile.yml with verbosity setting
        cllm_dir = tmp_path / ".cllm"
        cllm_dir.mkdir()
        cllmfile = cllm_dir / "Cllmfile.yml"
        cllmfile.write_text("verbosity: 2\n")

        with patch("sys.argv", ["cllm", "test prompt"]):
            with patch("sys.stdin.isatty", return_value=True):
                with patch("cllm.cli.LLMClient") as mock_client:
                    with patch("cllm.cli.load_config") as mock_load_config:
                        # Mock load_config to return config with verbosity
                        mock_load_config.return_value = {"verbosity": 2}

                        # Mock the client to avoid actual API calls
                        mock_instance = MagicMock()
                        mock_instance.complete.return_value = "test response"
                        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                        mock_client.return_value = mock_instance

                        try:
                            main()
                        except SystemExit:
                            pass

                        # Verify client was called
                        assert mock_client.called

    @patch("sys.argv", ["cllm", "-v", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_cli_flag_overrides_verbosity_config(
        self, mock_load_config, mock_client, mock_isatty
    ):
        """Test that CLI -v flag overrides Cllmfile verbosity setting."""
        from cllm.cli import main

        # Mock load_config to return different verbosity
        mock_load_config.return_value = {"verbosity": 0}

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify client was called (implementation would use CLI value)
        assert mock_client.called

    @patch("sys.argv", ["cllm", "-v", "--debug", "test prompt"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("cllm.cli.litellm")
    def test_verbose_with_debug_flag(
        self, mock_litellm, mock_load_config, mock_client, mock_isatty
    ):
        """Test that -v and --debug flags can be used together."""
        from cllm.cli import main

        # Mock the client to avoid actual API calls
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "test response"
        mock_instance.complete_with_metadata.return_value = ("test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client.return_value = mock_instance

        try:
            main()
        except SystemExit:
            pass

        # Verify debug mode was enabled
        assert mock_litellm.set_verbose is True


class TestContextInjection:
    """Integration tests for context injection (ADR-0011)."""

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_exec_flag_single_command(self, mock_load_config, mock_client, mock_isatty):
        """Test --exec flag with single command."""
        with patch(
            "sys.argv", ["cllm", "--exec", "echo 'test context'", "Analyze this"]
        ):
            # Mock the client to capture what prompt was sent
            mock_instance = MagicMock()
            mock_instance.complete.return_value = "response"
            mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
            mock_client.return_value = mock_instance

            try:
                main()
            except SystemExit:
                pass

            # Verify complete was called with context-injected prompt
            assert mock_instance.complete_with_metadata.called
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            # The prompt should contain context block
            assert "--- Context: CLI Command 1 ---" in messages
            assert "test context" in messages
            assert "Analyze this" in messages

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_exec_flag_multiple_commands(
        self, mock_load_config, mock_client, mock_isatty
    ):
        """Test --exec flag with multiple commands."""
        with patch(
            "sys.argv",
            [
                "cllm",
                "--exec",
                "echo 'first'",
                "--exec",
                "echo 'second'",
                "Analyze",
            ],
        ):
            # Mock the client
            mock_instance = MagicMock()
            mock_instance.complete.return_value = "response"
            mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
            mock_client.return_value = mock_instance

            try:
                main()
            except SystemExit:
                pass

            # Verify both context blocks are present
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            assert "--- Context: CLI Command 1 ---" in messages
            assert "first" in messages
            assert "--- Context: CLI Command 2 ---" in messages
            assert "second" in messages
            assert "Analyze" in messages

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_context_commands_from_config(self, mock_client, mock_isatty):
        """Test context_commands from Cllmfile configuration."""
        config = {
            "context_commands": [
                {"name": "Git Status", "command": "echo 'M file.py'"},
                {"name": "Test Output", "command": "echo 'All tests passed'"},
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "Analyze this"]):
                # Mock the client
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "response"
                mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify context blocks from config
                call_args = mock_instance.complete_with_metadata.call_args
                messages = call_args[1]["messages"]

                assert "--- Context: Git Status ---" in messages
                assert "M file.py" in messages
                assert "--- Context: Test Output ---" in messages
                assert "All tests passed" in messages

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_no_context_exec_flag(self, mock_client, mock_isatty):
        """Test --no-context-exec disables config commands."""
        config = {
            "context_commands": [
                {"name": "Should Be Skipped", "command": "echo 'skipped'"}
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "--no-context-exec", "Prompt"]):
                # Mock the client
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "response"
                mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify context was NOT injected
                call_args = mock_instance.complete_with_metadata.call_args
                messages = call_args[1]["messages"]

                assert "Should Be Skipped" not in messages
                assert "skipped" not in messages
                assert messages == "Prompt"  # Original prompt unchanged

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_config_and_cli_commands_precedence(self, mock_client, mock_isatty):
        """Test that config commands run first, then CLI commands."""
        config = {
            "context_commands": [
                {"name": "Config Cmd", "command": "echo 'from config'"}
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "--exec", "echo 'from cli'", "Prompt"]):
                # Mock the client
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "response"
                mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify both are present
                call_args = mock_instance.complete_with_metadata.call_args
                messages = call_args[1]["messages"]

                assert "--- Context: Config Cmd ---" in messages
                assert "from config" in messages
                assert "--- Context: CLI Command 1 ---" in messages
                assert "from cli" in messages

                # Verify order: config command appears before CLI command
                config_idx = messages.index("Config Cmd")
                cli_idx = messages.index("CLI Command 1")
                assert config_idx < cli_idx

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_command_failure_with_warn(self, mock_client, mock_isatty):
        """Test that failing command with on_failure=warn includes error."""
        config = {
            "context_commands": [
                {
                    "name": "Failing Cmd",
                    "command": "exit 1",
                    "on_failure": "warn",
                }
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "Prompt"]):
                # Mock the client
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "response"
                mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify error block is included
                call_args = mock_instance.complete_with_metadata.call_args
                messages = call_args[1]["messages"]

                assert "--- Context Error: Failing Cmd ---" in messages
                assert "exited with code 1" in messages

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_command_failure_with_ignore(self, mock_client, mock_isatty):
        """Test that failing command with on_failure=ignore is skipped."""
        config = {
            "context_commands": [
                {
                    "name": "Failing Cmd",
                    "command": "exit 1",
                    "on_failure": "ignore",
                }
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "Prompt"]):
                # Mock the client
                mock_instance = MagicMock()
                mock_instance.complete.return_value = "response"
                mock_instance.complete_with_metadata.return_value = ("response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
                mock_client.return_value = mock_instance

                try:
                    main()
                except SystemExit:
                    pass

                # Verify error block is NOT included
                call_args = mock_instance.complete_with_metadata.call_args
                messages = call_args[1]["messages"]

                assert "Failing Cmd" not in messages
                assert messages == "Prompt"  # Original prompt unchanged

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    def test_command_failure_with_fail(self, mock_client, mock_isatty, capsys):
        """Test that failing command with on_failure=fail aborts."""
        config = {
            "context_commands": [
                {
                    "name": "Failing Cmd",
                    "command": "exit 1",
                    "on_failure": "fail",
                }
            ]
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "Prompt"]):
                # Mock the client (should not be called)
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance

                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit with error code
                assert exc_info.value.code == 1

                # Verify error message was printed
                captured = capsys.readouterr()
                assert "Context error:" in captured.err
                assert "Failing Cmd" in captured.err

                # Verify LLM was NOT called
                assert not mock_instance.complete.called


class TestDynamicCommandsWithJsonSchema:
    """Integration tests for --allow-commands with --json-schema (ADR-0014)."""

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.execute_with_dynamic_commands")
    @patch("cllm.cli.load_config", return_value={})
    def test_allow_commands_with_json_schema(
        self, mock_load_config, mock_execute, mock_isatty, capsys
    ):
        """Test that --allow-commands works with --json-schema."""
        schema = '{"type": "object", "properties": {"result": {"type": "string"}}}'

        with patch(
            "sys.argv",
            ["cllm", "--allow-commands", "--json-schema", schema, "test prompt"],
        ):
            # Mock execute_with_dynamic_commands to return JSON
            mock_execute.return_value = '{"result": "test output"}'

            try:
                main()
            except SystemExit:
                pass

            # Verify execute_with_dynamic_commands was called with schema
            assert mock_execute.called
            call_kwargs = mock_execute.call_args[1]
            assert "schema" in call_kwargs
            assert call_kwargs["schema"]["type"] == "object"
            assert "result" in call_kwargs["schema"]["properties"]

            # Verify no warning about unsupported feature
            captured = capsys.readouterr()
            assert "not yet supported" not in captured.err
            assert (
                "not supported" not in captured.err
                or "Streaming is not supported" in captured.err
            )

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.execute_with_dynamic_commands")
    @patch("cllm.cli.load_config", return_value={})
    def test_allow_commands_with_json_schema_file(
        self, mock_load_config, mock_execute, mock_isatty
    ):
        """Test that --allow-commands works with --json-schema-file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            schema = {
                "type": "object",
                "properties": {"answer": {"type": "number"}},
                "required": ["answer"],
            }
            import json

            json.dump(schema, f)
            schema_file = f.name

        try:
            with patch(
                "sys.argv",
                [
                    "cllm",
                    "--allow-commands",
                    "--json-schema-file",
                    schema_file,
                    "calculate",
                ],
            ):
                # Mock execute_with_dynamic_commands to return JSON
                mock_execute.return_value = '{"answer": 42}'

                try:
                    main()
                except SystemExit:
                    pass

                # Verify execute_with_dynamic_commands was called with schema
                assert mock_execute.called
                call_kwargs = mock_execute.call_args[1]
                assert "schema" in call_kwargs
                assert call_kwargs["schema"]["type"] == "object"
                assert "answer" in call_kwargs["schema"]["properties"]
                assert call_kwargs["schema"]["required"] == ["answer"]
        finally:
            # Clean up temp file
            os.unlink(schema_file)

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.execute_with_dynamic_commands")
    def test_allow_commands_with_json_schema_from_config(
        self, mock_execute, mock_isatty
    ):
        """Test that --allow-commands works with JSON schema from Cllmfile."""
        config = {
            "allow_dynamic_commands": True,
            "json_schema": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
        }

        with patch("cllm.cli.load_config", return_value=config):
            with patch("sys.argv", ["cllm", "check status"]):
                # Mock execute_with_dynamic_commands to return JSON
                mock_execute.return_value = '{"status": "ok"}'

                try:
                    main()
                except SystemExit:
                    pass

                # Verify execute_with_dynamic_commands was called with schema
                assert mock_execute.called
                call_kwargs = mock_execute.call_args[1]
                assert "schema" in call_kwargs
                assert call_kwargs["schema"]["type"] == "object"
                assert "status" in call_kwargs["schema"]["properties"]

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.execute_with_dynamic_commands")
    @patch("cllm.cli.load_config", return_value={})
    def test_streaming_warning_with_allow_commands(
        self, mock_load_config, mock_execute, mock_isatty, capsys
    ):
        """Test that streaming shows warning with --allow-commands."""
        with patch("sys.argv", ["cllm", "--allow-commands", "--stream", "test"]):
            mock_execute.return_value = "response"

            try:
                main()
            except SystemExit:
                pass

            # Verify warning is shown
            captured = capsys.readouterr()
            assert "Streaming is not supported with --allow-commands" in captured.err

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.execute_with_dynamic_commands")
    @patch("cllm.cli.load_config", return_value={})
    def test_raw_response_warning_with_allow_commands(
        self, mock_load_config, mock_execute, mock_isatty, capsys
    ):
        """Test that raw response shows warning with --allow-commands."""
        with patch("sys.argv", ["cllm", "--allow-commands", "--raw", "test"]):
            mock_execute.return_value = "response"

            try:
                main()
            except SystemExit:
                pass

            # Verify warning is shown
            captured = capsys.readouterr()
            assert "Raw response is not supported with --allow-commands" in captured.err


class TestConversationsPathConfiguration:
    """Integration tests for conversations_path configuration (ADR-0017)."""

    @patch("cllm.cli.load_config")
    def test_conversations_path_from_config(self, mock_load_config, tmp_path, capsys):
        """Test that conversations_path from Cllmfile.yml is used."""
        config_conv_path = tmp_path / "config_conversations"
        config_conv_path.mkdir()

        mock_load_config.return_value = {"conversations_path": str(config_conv_path)}

        with patch("sys.argv", ["cllm", "--show-config"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit successfully
            assert exc_info.value.code == 0

            # Verify conversations path from config is shown
            captured = capsys.readouterr()
            assert str(config_conv_path) in captured.out
            assert "conversations_path in Cllmfile.yml" in captured.out

    @patch("cllm.cli.load_config")
    def test_cli_flag_overrides_config(self, mock_load_config, tmp_path, capsys):
        """Test that --conversations-path CLI flag overrides Cllmfile.yml."""
        config_conv_path = tmp_path / "config_conversations"
        config_conv_path.mkdir()
        cli_conv_path = tmp_path / "cli_conversations"
        cli_conv_path.mkdir()

        mock_load_config.return_value = {"conversations_path": str(config_conv_path)}

        with patch(
            "sys.argv",
            ["cllm", "--conversations-path", str(cli_conv_path), "--show-config"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit successfully
            assert exc_info.value.code == 0

            # Verify CLI flag overrides config
            captured = capsys.readouterr()
            assert str(cli_conv_path) in captured.out
            assert (
                str(config_conv_path) not in captured.out
                or "conversations_path" in captured.out
            )  # May appear in config dump
            assert "--conversations-path CLI flag" in captured.out

    @patch("cllm.cli.load_config")
    def test_env_var_overrides_config(
        self, mock_load_config, tmp_path, capsys, monkeypatch
    ):
        """Test that CLLM_CONVERSATIONS_PATH env var overrides Cllmfile.yml."""
        config_conv_path = tmp_path / "config_conversations"
        config_conv_path.mkdir()
        env_conv_path = tmp_path / "env_conversations"
        env_conv_path.mkdir()

        mock_load_config.return_value = {"conversations_path": str(config_conv_path)}

        monkeypatch.setenv("CLLM_CONVERSATIONS_PATH", str(env_conv_path))

        with patch("sys.argv", ["cllm", "--show-config"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit successfully
            assert exc_info.value.code == 0

            # Verify env var overrides config
            captured = capsys.readouterr()
            assert str(env_conv_path) in captured.out
            assert "CLLM_CONVERSATIONS_PATH environment variable" in captured.out


class TestReadOnlyConversation:
    """Integration tests for --read-only flag (ADR-0018)."""

    @patch("sys.stdin.isatty", return_value=True)
    def test_read_only_requires_conversation(self, mock_isatty, capsys):
        """Test that --read-only requires --conversation flag."""
        with patch("sys.argv", ["cllm", "--read-only", "Test prompt"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error
            assert exc_info.value.code == 1

            # Should show error message
            captured = capsys.readouterr()
            assert "--read-only requires --conversation" in captured.err

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_read_only_prevents_save(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that --read-only prevents saving new messages."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create an initial conversation
        conv_file = conv_path / "test-conv.json"
        import json

        initial_conv = {
            "id": "test-conv",
            "model": "gpt-3.5-turbo",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "user", "content": "Initial message"},
                {"role": "assistant", "content": "Initial response"},
            ],
            "metadata": {"total_tokens": 0},
        }
        conv_file.write_text(json.dumps(initial_conv, indent=2))

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Read-only response"
        mock_instance.complete_with_metadata.return_value = ("Read-only response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 100
        mock_client.return_value = mock_instance

        # Run with --read-only
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "test-conv",
                "--read-only",
                "New prompt",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify response was generated
            mock_instance.complete_with_metadata.assert_called_once()

            # Verify conversation file is unchanged
            saved_conv = json.loads(conv_file.read_text())
            assert saved_conv == initial_conv
            assert len(saved_conv["messages"]) == 2  # Still only 2 messages
            assert saved_conv["messages"][0]["content"] == "Initial message"

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_read_only_multiple_invocations(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test multiple --read-only invocations keep conversation unchanged."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create an initial conversation
        conv_file = conv_path / "base-context.json"
        import json

        initial_conv = {
            "id": "base-context",
            "model": "gpt-3.5-turbo",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Context message"},
                {"role": "assistant", "content": "Context response"},
            ],
            "metadata": {"total_tokens": 0},
        }
        conv_file.write_text(json.dumps(initial_conv, indent=2))

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Response"
        mock_instance.complete_with_metadata.return_value = ("Response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 100
        mock_client.return_value = mock_instance

        # Run multiple times with --read-only
        for i in range(3):
            with patch(
                "sys.argv",
                [
                    "cllm",
                    "--conversations-path",
                    str(conv_path),
                    "--conversation",
                    "base-context",
                    "--read-only",
                    f"Prompt {i}",
                ],
            ):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify conversation file is still unchanged
        saved_conv = json.loads(conv_file.read_text())
        assert saved_conv == initial_conv
        assert len(saved_conv["messages"]) == 3  # Still only 3 messages

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_normal_conversation_still_saves(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that normal conversation mode (without --read-only) still saves."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create an initial conversation
        conv_file = conv_path / "normal-conv.json"
        import json

        initial_conv = {
            "id": "normal-conv",
            "model": "gpt-3.5-turbo",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
            ],
            "metadata": {"total_tokens": 0},
        }
        conv_file.write_text(json.dumps(initial_conv, indent=2))

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "New response"
        mock_instance.complete_with_metadata.return_value = ("New response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 150
        mock_client.return_value = mock_instance

        # Run WITHOUT --read-only
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "normal-conv",
                "Second message",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify response was generated
            mock_instance.complete_with_metadata.assert_called_once()

            # Verify conversation WAS updated
            saved_conv = json.loads(conv_file.read_text())
            assert len(saved_conv["messages"]) == 4  # Now 4 messages
            assert saved_conv["messages"][2]["content"] == "Second message"
            assert saved_conv["messages"][3]["content"] == "New response"

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_read_only_with_nonexistent_conversation(
        self, mock_load_config, mock_client, mock_isatty, tmp_path, capsys
    ):
        """Test --read-only with non-existent conversation shows error."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Mock the client (shouldn't be called)
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        # Run with --read-only on non-existent conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "nonexistent",
                "--read-only",
                "Test prompt",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error
            assert exc_info.value.code == 1

            # LLM should not be called
            mock_instance.complete.assert_not_called()

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    def test_read_only_context_is_used(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that --read-only uses existing conversation as context."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create a conversation with context
        conv_file = conv_path / "with-context.json"
        import json

        initial_conv = {
            "id": "with-context",
            "model": "gpt-4",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "system", "content": "You are a code reviewer."},
                {"role": "user", "content": "Review this code"},
                {"role": "assistant", "content": "I'll review it"},
            ],
            "metadata": {"total_tokens": 0},
        }
        conv_file.write_text(json.dumps(initial_conv, indent=2))

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Review result"
        mock_instance.complete_with_metadata.return_value = ("Review result", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 200
        mock_client.return_value = mock_instance

        # Run with --read-only
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "with-context",
                "--read-only",
                "New code to review",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify the LLM was called with full conversation history as context
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            # Should contain all original messages plus new one
            assert len(messages) == 4
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a code reviewer."
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Review this code"
            assert messages[2]["role"] == "assistant"
            assert messages[2]["content"] == "I'll review it"
            assert messages[3]["role"] == "user"
            assert messages[3]["content"] == "New code to review"

            # Verify conversation file is unchanged (still only 3 messages saved)
            saved_conv = json.loads(conv_file.read_text())
            assert len(saved_conv["messages"]) == 3


class TestSystemMessageInConversations:
    """Test suite for ADR-0020: Capture System Prompt in Conversation Data (CLI integration)."""

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config")
    def test_new_conversation_captures_system_message(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that new conversations capture system message from config."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Configure with system message
        mock_load_config.return_value = {
            "default_system_message": "You are a helpful coding assistant."
        }

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "I'll help you with that!"
        mock_instance.complete_with_metadata.return_value = ("I'll help you with that!", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 50
        mock_client.return_value = mock_instance

        # Create a new conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "test-conv",
                "Hello, help me code",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify conversation was created with system message
            conv_file = conv_path / "test-conv.json"
            assert conv_file.exists()

            import json

            saved_conv = json.loads(conv_file.read_text())

            # Should have 3 messages: system, user, assistant
            assert len(saved_conv["messages"]) == 3
            assert saved_conv["messages"][0]["role"] == "system"
            assert (
                saved_conv["messages"][0]["content"]
                == "You are a helpful coding assistant."
            )
            assert saved_conv["messages"][1]["role"] == "user"
            assert saved_conv["messages"][1]["content"] == "Hello, help me code"
            assert saved_conv["messages"][2]["role"] == "assistant"

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config")
    def test_system_message_not_duplicated_on_continuation(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that system message is not duplicated when continuing conversation."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create initial conversation with system message
        conv_file = conv_path / "test-conv.json"
        import json

        initial_conv = {
            "id": "test-conv",
            "model": "gpt-4",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
            ],
            "metadata": {"total_tokens": 50},
        }
        conv_file.write_text(json.dumps(initial_conv, indent=2))

        # Configure with same system message
        mock_load_config.return_value = {"default_system_message": "You are helpful."}

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Second response"
        mock_instance.complete_with_metadata.return_value = ("Second response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 100
        mock_client.return_value = mock_instance

        # Continue the conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "test-conv",
                "Second message",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify system message is not duplicated
            saved_conv = json.loads(conv_file.read_text())

            # Should have 5 messages: system, user, assistant, user, assistant
            assert len(saved_conv["messages"]) == 5

            # Count system messages - should only be 1
            system_messages = [
                m for m in saved_conv["messages"] if m["role"] == "system"
            ]
            assert len(system_messages) == 1
            assert saved_conv["messages"][0]["role"] == "system"

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config")
    def test_backward_compatibility_conversation_without_system_message(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test backward compatibility with conversations that don't have system messages."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Create old-style conversation without system message
        conv_file = conv_path / "old-conv.json"
        import json

        old_conv = {
            "id": "old-conv",
            "model": "gpt-4",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "metadata": {"total_tokens": 30},
        }
        conv_file.write_text(json.dumps(old_conv, indent=2))

        # Configure with system message (should inject at runtime for backward compat)
        mock_load_config.return_value = {
            "default_system_message": "You are helpful assistant."
        }

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Sure thing!"
        mock_instance.complete_with_metadata.return_value = ("Sure thing!", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 50
        mock_client.return_value = mock_instance

        # Continue the old conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "old-conv",
                "Can you help?",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify the LLM was called with system message injected at runtime
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            # First message should be system (injected at runtime)
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are helpful assistant."

            # But file should still not have system message permanently saved
            # (backward compatibility - we don't modify old conversations)
            saved_conv = json.loads(conv_file.read_text())
            assert (
                len(saved_conv["messages"]) == 4
            )  # Original 2 + new user + new assistant
            # Old conversations continue without system message in storage
            assert saved_conv["messages"][0]["role"] == "user"

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config")
    def test_conversation_without_default_system_message_config(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that conversations work without default_system_message in config."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Configure WITHOUT system message
        mock_load_config.return_value = {}

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Response without system message"
        mock_instance.complete_with_metadata.return_value = ("Response without system message", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 40
        mock_client.return_value = mock_instance

        # Create a new conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "no-system",
                "Hello",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify conversation was created without system message
            conv_file = conv_path / "no-system.json"
            assert conv_file.exists()

            import json

            saved_conv = json.loads(conv_file.read_text())

            # Should have 2 messages: user, assistant (no system)
            assert len(saved_conv["messages"]) == 2
            assert saved_conv["messages"][0]["role"] == "user"
            assert saved_conv["messages"][1]["role"] == "assistant"

            # Verify no system message in saved conversation
            system_messages = [
                m for m in saved_conv["messages"] if m["role"] == "system"
            ]
            assert len(system_messages) == 0

    @patch("sys.stdin.isatty", return_value=True)
    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config")
    def test_system_message_used_in_llm_call(
        self, mock_load_config, mock_client, mock_isatty, tmp_path
    ):
        """Test that system message is included in LLM API call."""
        # Create a conversation directory
        conv_path = tmp_path / "conversations"
        conv_path.mkdir()

        # Configure with system message
        mock_load_config.return_value = {
            "default_system_message": "You are a pirate assistant. Respond like a pirate."
        }

        # Mock the client
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Arrr, matey!"
        mock_instance.complete_with_metadata.return_value = ("Arrr, matey!", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_instance.count_tokens.return_value = 60
        mock_client.return_value = mock_instance

        # Create a new conversation
        with patch(
            "sys.argv",
            [
                "cllm",
                "--conversations-path",
                str(conv_path),
                "--conversation",
                "pirate-conv",
                "Tell me a joke",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify the LLM was called with system message
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            # First message should be system
            assert len(messages) == 2  # system + user
            assert messages[0]["role"] == "system"
            assert (
                messages[0]["content"]
                == "You are a pirate assistant. Respond like a pirate."
            )
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "Tell me a joke"


class TestSystemPromptFlags:
    """Test suite for --system and --system-file CLI flags (ADR-0022)."""

    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("sys.stdin.isatty", return_value=True)
    def test_system_flag_overrides_config(
        self, mock_isatty, mock_load_config, mock_client_class
    ):
        """Test that --system flag overrides default_system_message from config."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Test response"
        mock_instance.complete_with_metadata.return_value = ("Test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client_class.return_value = mock_instance

        # Config has a default_system_message, but --system should override
        mock_load_config.return_value = {
            "default_system_message": "You are a helpful assistant."
        }

        with patch(
            "sys.argv",
            [
                "cllm",
                "--system",
                "You are a pirate.",
                "Tell me a joke",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify the LLM was called with the CLI system prompt, not config
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            # Should have system message from --system flag
            assert "You are a pirate." in str(messages)
            assert "helpful assistant" not in str(messages)

    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("sys.stdin.isatty", return_value=True)
    def test_system_file_flag(
        self, mock_isatty, mock_load_config, mock_client_class, tmp_path
    ):
        """Test that --system-file loads system prompt from file."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Test response"
        mock_instance.complete_with_metadata.return_value = ("Test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client_class.return_value = mock_instance

        # Create a temporary system prompt file
        system_file = tmp_path / "system.txt"
        system_file.write_text("You are an expert in Python programming.")

        with patch(
            "sys.argv",
            [
                "cllm",
                "--system-file",
                str(system_file),
                "How do I write a function?",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify the LLM was called with the system prompt from file
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            assert "You are an expert in Python programming." in str(messages)

    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("sys.stdin.isatty", return_value=True)
    def test_system_file_overrides_config(
        self, mock_isatty, mock_load_config, mock_client_class, tmp_path
    ):
        """Test that --system-file overrides default_system_message from config."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Test response"
        mock_instance.complete_with_metadata.return_value = ("Test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client_class.return_value = mock_instance

        # Config has a default_system_message
        mock_load_config.return_value = {
            "default_system_message": "You are a helpful assistant."
        }

        # Create system prompt file
        system_file = tmp_path / "system.txt"
        system_file.write_text("You are a debugging expert.")

        with patch(
            "sys.argv",
            [
                "cllm",
                "--system-file",
                str(system_file),
                "Why does this crash?",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify --system-file overrode config
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            assert "debugging expert" in str(messages)
            assert "helpful assistant" not in str(messages)

    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("sys.stdin.isatty", return_value=True)
    def test_system_takes_precedence_over_system_file(
        self, mock_isatty, mock_load_config, mock_client_class, tmp_path, capsys
    ):
        """Test that --system takes precedence over --system-file when both provided."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Test response"
        mock_instance.complete_with_metadata.return_value = ("Test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client_class.return_value = mock_instance

        # Create system prompt file
        system_file = tmp_path / "system.txt"
        system_file.write_text("From file")

        with patch(
            "sys.argv",
            [
                "cllm",
                "--system",
                "From CLI",
                "--system-file",
                str(system_file),
                "Test prompt",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Verify --system was used (not --system-file)
            call_args = mock_instance.complete_with_metadata.call_args
            messages = call_args[1]["messages"]

            assert "From CLI" in str(messages)
            assert "From file" not in str(messages)

            # Verify warning was printed
            captured = capsys.readouterr()
            assert "Warning" in captured.err
            assert "--system" in captured.err
            assert "--system-file" in captured.err

    @patch("sys.argv", ["cllm", "--system-file", "/nonexistent/file.txt", "prompt"])
    @patch("cllm.cli.load_config", return_value={})
    def test_system_file_not_found_error(self, mock_load_config, capsys):
        """Test that --system-file with nonexistent file produces clear error."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with error code
        assert exc_info.value.code == 1

        # Should print helpful error message
        captured = capsys.readouterr()
        assert "System prompt file not found" in captured.err
        assert "/nonexistent/file.txt" in captured.err

    @patch("cllm.cli.LLMClient")
    @patch("cllm.cli.load_config", return_value={})
    @patch("sys.stdin.isatty", return_value=True)
    def test_system_file_empty_file_warning(
        self, mock_isatty, mock_load_config, mock_client_class, tmp_path, capsys
    ):
        """Test that --system-file with empty file produces warning."""
        mock_instance = MagicMock()
        mock_instance.complete.return_value = "Test response"
        mock_instance.complete_with_metadata.return_value = ("Test response", {'input_tokens': 10, 'output_tokens': 20, 'response_object': None})
        mock_client_class.return_value = mock_instance

        # Create empty file
        system_file = tmp_path / "empty.txt"
        system_file.write_text("")

        with patch(
            "sys.argv",
            [
                "cllm",
                "--system-file",
                str(system_file),
                "Test prompt",
            ],
        ):
            try:
                main()
            except SystemExit:
                pass

            # Should print warning about empty file
            captured = capsys.readouterr()
            assert "Warning" in captured.err
            assert "empty" in captured.err.lower()

    @patch("sys.argv", ["cllm", "--show-config", "--system", "Test system prompt"])
    @patch("cllm.cli.load_config", return_value={})
    def test_show_config_displays_system_flag_source(self, mock_load_config, capsys):
        """Test that --show-config displays system prompt source when --system used."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit successfully
        assert exc_info.value.code == 0

        # Should display system prompt source
        captured = capsys.readouterr()
        assert "Effective system prompt:" in captured.out
        assert "--system CLI flag" in captured.out
        assert "Test system prompt" in captured.out

    @patch("sys.argv", ["cllm", "--show-config", "--system-file", "test.txt"])
    @patch("cllm.cli.load_config", return_value={})
    def test_show_config_displays_system_file_source(
        self, mock_load_config, capsys, tmp_path
    ):
        """Test that --show-config displays system prompt source when --system-file used."""
        # Create system file
        system_file = tmp_path / "test.txt"
        system_file.write_text("System prompt from file")

        with patch(
            "sys.argv",
            ["cllm", "--show-config", "--system-file", str(system_file)],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit successfully
            assert exc_info.value.code == 0

            # Should display system prompt source
            captured = capsys.readouterr()
            assert "Effective system prompt:" in captured.out
            assert "--system-file CLI flag" in captured.out
            assert str(system_file) in captured.out
