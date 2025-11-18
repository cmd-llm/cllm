"""Tests for agent module (ADR-0013: LLM-Driven Dynamic Command Execution)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cllm.agent import (
    AgentExecutionError,
    execute_single_command,
    execute_with_dynamic_commands,
)


class TestExecuteSingleCommand:
    """Tests for single command execution."""

    def test_executes_successful_command(self):
        """Should execute command and return output."""
        output = execute_single_command("echo hello", timeout=5)
        assert "hello" in output.lower()

    def test_handles_command_failure(self):
        """Should return error message for failed commands."""
        # Command that will fail
        output = execute_single_command("exit 1", timeout=5)
        assert "error" in output.lower()

    def test_respects_timeout(self):
        """Should timeout long-running commands."""
        # Sleep command should timeout
        output = execute_single_command("sleep 10", timeout=1)
        assert "timeout" in output.lower() or "error" in output.lower()


class TestExecuteWithDynamicCommands:
    """Tests for agentic execution loop."""

    @patch("cllm.agent.litellm.completion")
    def test_executes_single_tool_call(self, mock_completion):
        """Should execute command when LLM requests it."""
        # Mock LLM responses
        tool_call_response = MagicMock()
        tool_call_response.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_123",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo test",
                                        "reason": "Testing",
                                    }
                                )
                            ),
                        )
                    ]
                ),
            )
        ]

        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="The command output was: test"),
            )
        ]

        mock_completion.side_effect = [tool_call_response, final_response]

        config = {
            "model": "gpt-4",
            "dynamic_commands": {"allow": ["echo*"]},
        }

        result = execute_with_dynamic_commands("Run echo test", config)
        assert "test" in result

    @patch("cllm.agent.litellm.completion")
    def test_rejects_disallowed_command(self, mock_completion):
        """Should reject commands not in allowlist."""
        # Mock LLM requesting disallowed command
        tool_call_response = MagicMock()
        tool_call_response.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_123",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "rm -rf /",
                                        "reason": "Cleanup",
                                    }
                                )
                            ),
                        )
                    ]
                ),
            )
        ]

        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="I cannot execute that command."),
            )
        ]

        mock_completion.side_effect = [tool_call_response, final_response]

        config = {
            "model": "gpt-4",
            "dynamic_commands": {"deny": ["rm *"]},
        }

        result = execute_with_dynamic_commands("Delete everything", config)
        # Should continue after validation error
        assert "cannot" in result.lower()

    @patch("cllm.agent.litellm.completion")
    def test_handles_max_commands_limit(self, mock_completion):
        """Should gracefully handle max commands limit by making final synthesis call."""
        # Mock LLM always requesting more commands
        tool_call_response = MagicMock()
        tool_call_response.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_123",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo test",
                                        "reason": "Testing",
                                    }
                                )
                            ),
                        )
                    ],
                    model_dump=MagicMock(
                        return_value={"role": "assistant", "content": ""}
                    ),
                ),
            )
        ]

        # Mock final synthesis response
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(
                    content="Final synthesis response",
                    model_dump=MagicMock(
                        return_value={
                            "role": "assistant",
                            "content": "Final synthesis response",
                        }
                    ),
                ),
            )
        ]

        # Return tool_call_response for first 3 calls, then final_response for synthesis
        mock_completion.side_effect = [tool_call_response] * 3 + [final_response]

        config = {
            "model": "gpt-4",
            "dynamic_commands": {"allow": ["echo*"], "max_commands": 3},
        }

        result = execute_with_dynamic_commands("Keep echoing", config)

        # Should return the final synthesis response instead of raising error
        assert result == "Final synthesis response"
        # Should have called completion 4 times (3 tool calls + 1 final synthesis)
        assert mock_completion.call_count == 4

    @patch("cllm.agent.litellm.completion")
    def test_handles_immediate_response(self, mock_completion):
        """Should handle LLM providing answer without tool calls."""
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="The answer is 42"),
            )
        ]

        mock_completion.return_value = final_response

        config = {"model": "gpt-4"}

        result = execute_with_dynamic_commands("What is the answer?", config)
        assert "42" in result

    @patch("cllm.agent.litellm.completion")
    def test_includes_system_message(self, mock_completion):
        """Should include default_system_message in initial call."""
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="Response"),
            )
        ]

        mock_completion.return_value = final_response

        config = {
            "model": "gpt-4",
            "default_system_message": "You are a helpful assistant.",
        }

        execute_with_dynamic_commands("Test", config)

        # Check that first call included system message
        call_args = mock_completion.call_args[1]
        messages = call_args["messages"]
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."

    @patch("cllm.agent.litellm.completion")
    def test_handles_multiple_tool_calls(self, mock_completion):
        """Should handle multiple sequential tool calls."""
        # First tool call
        tool_call_1 = MagicMock()
        tool_call_1.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_1",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo first",
                                        "reason": "First test",
                                    }
                                )
                            ),
                        )
                    ]
                ),
            )
        ]

        # Second tool call
        tool_call_2 = MagicMock()
        tool_call_2.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_2",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo second",
                                        "reason": "Second test",
                                    }
                                )
                            ),
                        )
                    ]
                ),
            )
        ]

        # Final response
        final = MagicMock()
        final.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="Both commands executed"),
            )
        ]

        mock_completion.side_effect = [tool_call_1, tool_call_2, final]

        config = {
            "model": "gpt-4",
            "dynamic_commands": {"allow": ["echo*"]},
        }

        result = execute_with_dynamic_commands("Run two commands", config)
        assert "executed" in result.lower()

    @patch("cllm.agent.litellm.completion")
    def test_handles_parallel_tool_calls(self, mock_completion):
        """Should handle multiple parallel tool calls in a single response."""
        # LLM makes two tool calls at once
        parallel_tool_calls = MagicMock()
        parallel_tool_calls.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_1",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo first",
                                        "reason": "First parallel command",
                                    }
                                )
                            ),
                        ),
                        MagicMock(
                            id="call_2",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo second",
                                        "reason": "Second parallel command",
                                    }
                                )
                            ),
                        ),
                    ]
                ),
            )
        ]

        # Final response after both commands
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(content="Both commands executed successfully"),
            )
        ]

        mock_completion.side_effect = [parallel_tool_calls, final_response]

        config = {"model": "gpt-4", "dynamic_commands": {"allow": ["echo*"]}}
        result = execute_with_dynamic_commands("Run two commands", config)

        assert "Both commands executed successfully" in result

        # Verify both tool calls were processed
        assert mock_completion.call_count == 2

        # Check that the second call includes responses for BOTH tool_call_ids
        second_call_messages = mock_completion.call_args_list[1][1]["messages"]
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        assert tool_messages[0]["tool_call_id"] == "call_1"
        assert tool_messages[1]["tool_call_id"] == "call_2"

    @patch("cllm.agent.litellm.completion")
    def test_handles_api_error(self, mock_completion):
        """Should handle LLM API errors gracefully."""
        mock_completion.side_effect = Exception("API Error")

        config = {"model": "gpt-4"}

        with pytest.raises(AgentExecutionError) as exc_info:
            execute_with_dynamic_commands("Test", config)

        assert "API call failed" in str(exc_info.value)

    @patch("cllm.agent.litellm.completion")
    def test_supports_json_schema(self, mock_completion):
        """Should support JSON schema with dynamic commands (ADR-0014)."""
        # Mock LLM requesting a tool call
        tool_call_response = MagicMock()
        tool_call_response.choices = [
            MagicMock(
                finish_reason="tool_calls",
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="call_123",
                            function=MagicMock(
                                arguments=json.dumps(
                                    {
                                        "command": "echo test",
                                        "reason": "Testing",
                                    }
                                )
                            ),
                        )
                    ]
                ),
            )
        ]

        # Mock final response with JSON structure
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(
                    content='{"result": "test output", "status": "success"}'
                ),
            )
        ]

        mock_completion.side_effect = [tool_call_response, final_response]

        config = {
            "model": "gpt-4",
            "dynamic_commands": {"allow": ["echo*"]},
        }

        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["result", "status"],
        }

        result = execute_with_dynamic_commands("Run echo test", config, schema=schema)

        # Verify result matches schema structure
        assert "test output" in result
        assert "success" in result

        # Verify schema was passed to litellm.completion
        # Check both calls (tool call and final response)
        for call in mock_completion.call_args_list:
            call_kwargs = call[1]
            assert "response_format" in call_kwargs
            assert call_kwargs["response_format"]["type"] == "json_schema"
            assert (
                call_kwargs["response_format"]["json_schema"]["name"]
                == "response_schema"
            )
            assert call_kwargs["response_format"]["json_schema"]["schema"] == schema

    @patch("cllm.agent.litellm.completion")
    def test_json_schema_without_tool_calls(self, mock_completion):
        """Should support JSON schema when LLM responds immediately without tool calls."""
        # Mock final response with JSON structure (no tool calls)
        final_response = MagicMock()
        final_response.choices = [
            MagicMock(
                finish_reason="stop",
                message=MagicMock(
                    content='{"answer": 42, "explanation": "The answer to everything"}'
                ),
            )
        ]

        mock_completion.return_value = final_response

        config = {"model": "gpt-4"}

        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "number"},
                "explanation": {"type": "string"},
            },
            "required": ["answer"],
        }

        result = execute_with_dynamic_commands(
            "What is the answer?", config, schema=schema
        )

        # Verify result is JSON
        assert "42" in result
        assert "answer" in result

        # Verify schema was passed to litellm.completion
        call_kwargs = mock_completion.call_args[1]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["schema"] == schema
