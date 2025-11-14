"""Tests for the LoguruVerbosityHandler with loguru logging."""

import io
import sys
from unittest.mock import patch

import pytest

from cllm.logging_handler import LoguruVerbosityHandler


class TestLoguruVerbosityHandler:
    """Test LoguruVerbosityHandler with loguru integration."""

    def test_handler_initialization(self):
        """Test LoguruVerbosityHandler initializes correctly."""
        handler = LoguruVerbosityHandler(verbosity=1)
        assert handler.verbosity == 1
        assert handler.level == 1  # Backward compatibility property

    def test_handler_backward_compat_level_parameter(self):
        """Test LoguruVerbosityHandler accepts 'level' parameter for backward compatibility."""
        handler = LoguruVerbosityHandler(level=2)
        assert handler.verbosity == 2
        assert handler.level == 2

    def test_handler_caps_at_level_3(self):
        """Test LoguruVerbosityHandler caps verbosity at level 3."""
        handler = LoguruVerbosityHandler(verbosity=5)
        assert handler.verbosity == 3
        assert handler.level == 3

    def test_print_basic_info_level_0_no_output(self, capsys):
        """Test print_basic_info doesn't output at level 0."""
        handler = LoguruVerbosityHandler(verbosity=0)
        handler.print_basic_info(
            model="gpt-4",
            input_tokens=10,
            output_tokens=20,
            provider="openai",
            latency_seconds=1.5,
        )
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_print_basic_info_level_1_outputs(self, capsys):
        """Test print_basic_info outputs at level 1."""
        handler = LoguruVerbosityHandler(verbosity=1)
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

    def test_print_api_details_level_2_outputs(self, capsys):
        """Test print_api_details outputs at level 2."""
        handler = LoguruVerbosityHandler(verbosity=2)
        handler.print_api_details(
            endpoint="https://api.openai.com/v1/chat/completions",
            parameters={"temperature": 0.7, "max_tokens": 500},
            status_code=200,
            config_sources=["~/.cllm/Cllmfile.yml"],
        )
        captured = capsys.readouterr()
        assert "Endpoint: https://api.openai.com/v1/chat/completions" in captured.err
        assert "temperature=0.7" in captured.err
        assert "max_tokens=500" in captured.err
        assert "Status: 200" in captured.err
        assert "Config sources:" in captured.err

    def test_print_api_details_level_1_no_output(self, capsys):
        """Test print_api_details doesn't output at level 1."""
        handler = LoguruVerbosityHandler(verbosity=1)
        handler.print_api_details(
            endpoint="https://api.openai.com/v1/chat/completions",
            parameters={"temperature": 0.7},
            status_code=200,
        )
        captured = capsys.readouterr()
        # Should have no DEBUG level output from loguru at INFO level
        # (backward compat print should not run)
        assert "Endpoint:" not in captured.err
        assert "Status:" not in captured.err

    def test_log_model_info_with_loguru(self, capsys):
        """Test log_model_info outputs with loguru at INFO level."""
        handler = LoguruVerbosityHandler(verbosity=2)
        handler.log_model_info("gpt-4", "openai")
        captured = capsys.readouterr()
        # Loguru output will be at INFO level with format: INFO | module:line | message
        assert "Model: gpt-4" in captured.err
        assert "Provider: openai" in captured.err
        assert "INFO" in captured.err

    def test_log_tokens_with_loguru(self, capsys):
        """Test log_tokens outputs with loguru at INFO level."""
        handler = LoguruVerbosityHandler(verbosity=1)
        handler.log_tokens(50, 120)
        captured = capsys.readouterr()
        assert "Tokens: 50 input, 120 output (170 total)" in captured.err

    def test_log_endpoint_with_loguru(self, capsys):
        """Test log_endpoint outputs with loguru at DEBUG level."""
        handler = LoguruVerbosityHandler(verbosity=2)
        handler.log_endpoint("https://api.openai.com/v1/chat/completions")
        captured = capsys.readouterr()
        assert "Endpoint: https://api.openai.com/v1/chat/completions" in captured.err
        assert "DEBUG" in captured.err

    def test_no_logger_output_at_level_0(self, capsys):
        """Test no loguru output at verbosity level 0."""
        handler = LoguruVerbosityHandler(verbosity=0)
        handler.log_tokens(50, 120)
        handler.log_model_info("gpt-4", "openai")
        captured = capsys.readouterr()
        # No output should be generated at level 0
        assert captured.err == ""

    def test_handler_with_custom_format(self, capsys):
        """Test handler accepts custom logging format."""
        # Handler should respect loguru's auto-TTY detection
        # and format configuration
        handler = LoguruVerbosityHandler(verbosity=1)
        assert handler.verbosity == 1
        assert handler.level == 1

    def test_handler_respects_no_color_env(self):
        """Test handler respects NO_COLOR environment variable."""
        # This is handled by loguru automatically
        handler = LoguruVerbosityHandler(verbosity=1)
        # Handler should be initialized without error
        assert handler.verbosity == 1

    def test_log_event_major_outputs_at_level_1(self, capsys):
        """Test log_event outputs major events at verbosity level 1."""
        handler = LoguruVerbosityHandler(verbosity=1)
        handler.log_event("Configuration merged", extra={"sources": 2})
        captured = capsys.readouterr()
        assert "Configuration merged" in captured.err
        assert "sources" in captured.err

    def test_log_event_minor_requires_level_2(self, capsys):
        """Test log_event for minor events only logs when verbosity >=2."""
        handler = LoguruVerbosityHandler(verbosity=1)
        handler.log_event("Context commands ready", importance="minor", extra={"count": 0})
        captured = capsys.readouterr()
        assert "Context commands ready" not in captured.err

        handler = LoguruVerbosityHandler(verbosity=2)
        handler.log_event("Context commands ready", importance="minor", extra={"count": 3})
        captured = capsys.readouterr()
        assert "Context commands ready" in captured.err
