"""Tests for tools module.

Implements tests for:
- ADR-0013: LLM-Driven Dynamic Command Execution
- ADR-0024: Explicit Command Parameter Syntax (hybrid support)
"""

import pytest

from cllm.tools import (
    CommandValidationError,
    Parameter,
    ParsedCommand,
    extract_parameter_hints,
    generate_command_tool,
    get_disallowed_reason,
    is_command_allowed,
    matches_bracket_command,
    parse_command_definition,
    validate_command,
)


class TestIsCommandAllowed:
    """Tests for command validation logic."""

    def test_denylist_blocks_command(self):
        """Denylist should block commands matching patterns."""
        config = {"dynamic_commands": {"deny": ["rm *", "sudo *"]}}

        assert not is_command_allowed("rm -rf /", config)
        assert not is_command_allowed("sudo apt-get install", config)

    def test_denylist_takes_precedence_over_allowlist(self):
        """Denylist should take precedence over allowlist."""
        config = {
            "dynamic_commands": {
                "allow": ["git*"],
                "deny": ["git push --force"],
            }
        }

        assert is_command_allowed("git status", config)
        assert not is_command_allowed("git push --force", config)

    def test_available_commands_allows_exact_match(self):
        """Available commands should allow exact matches."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git status", "description": "Show status"},
                    {"command": "npm test", "description": "Run tests"},
                ]
            }
        }

        assert is_command_allowed("git status", config)
        assert is_command_allowed("npm test", config)

    def test_available_commands_allows_variations(self):
        """Available commands should allow variations with additional args."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git log", "description": "Show log"},
                ]
            }
        }

        assert is_command_allowed("git log", config)
        assert is_command_allowed("git log --oneline", config)
        assert is_command_allowed("git log -10", config)

    def test_available_commands_blocks_unlisted(self):
        """Available commands should block unlisted commands."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git status", "description": "Show status"},
                ]
            }
        }

        assert not is_command_allowed("rm -rf", config)
        assert not is_command_allowed("npm install", config)

    def test_simple_allowlist_with_wildcards(self):
        """Simple allowlist should support wildcard patterns."""
        config = {"dynamic_commands": {"allow": ["git*", "npm test*"]}}

        assert is_command_allowed("git status", config)
        assert is_command_allowed("git log", config)
        assert is_command_allowed("npm test", config)
        assert is_command_allowed("npm test --verbose", config)
        assert not is_command_allowed("rm -rf", config)

    def test_combining_available_commands_and_allowlist(self):
        """Both available_commands and allowlist should be checked."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git status", "description": "Status"},
                ],
                "allow": ["npm*"],
            }
        }

        assert is_command_allowed("git status", config)
        assert is_command_allowed("npm test", config)
        assert not is_command_allowed("rm -rf", config)

    def test_safe_defaults_when_no_config(self):
        """Safe default commands should be allowed when no config."""
        config = {}

        # Safe commands
        assert is_command_allowed("git status", config)
        assert is_command_allowed("cat file.txt", config)
        assert is_command_allowed("ls -la", config)
        assert is_command_allowed("pwd", config)

        # Unsafe commands
        assert not is_command_allowed("rm -rf", config)
        assert not is_command_allowed("sudo apt-get", config)

    def test_empty_dynamic_commands_uses_defaults(self):
        """Empty dynamic_commands config should use safe defaults."""
        config = {"dynamic_commands": {}}

        assert is_command_allowed("git status", config)
        assert not is_command_allowed("rm -rf", config)

    def test_explicit_config_disables_defaults(self):
        """Explicit config should disable safe defaults."""
        config = {"dynamic_commands": {"allow": ["npm*"]}}

        assert is_command_allowed("npm test", config)
        # git status is in safe defaults but not in explicit allowlist
        assert not is_command_allowed("git status", config)


class TestGenerateCommandTool:
    """Tests for tool definition generation."""

    def test_generates_basic_tool(self):
        """Should generate basic tool definition."""
        config = {}
        tool = generate_command_tool(config)

        assert tool["type"] == "function"
        assert tool["function"]["name"] == "execute_bash_command"
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        assert tool["function"]["parameters"]["required"] == ["command", "reason"]

    def test_includes_available_commands_in_description(self):
        """Should include available commands in tool description."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git status", "description": "Show status"},
                    {"command": "npm test", "description": "Run tests"},
                ]
            }
        }
        tool = generate_command_tool(config)
        description = tool["function"]["description"]

        assert "git status" in description
        assert "Show status" in description
        assert "npm test" in description
        assert "Run tests" in description

    def test_handles_missing_description(self):
        """Should handle commands without descriptions gracefully."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "git status"},  # No description
                ]
            }
        }
        tool = generate_command_tool(config)
        description = tool["function"]["description"]

        assert "git status" in description
        assert "No description provided" in description


class TestGetDisallowedReason:
    """Tests for disallowed reason explanations."""

    def test_explains_denylist_block(self):
        """Should explain when command is blocked by denylist."""
        config = {"dynamic_commands": {"deny": ["rm *"]}}
        reason = get_disallowed_reason("rm -rf /", config)

        assert "denylist" in reason.lower()
        assert "rm *" in reason

    def test_explains_not_in_allowlist(self):
        """Should explain when command is not in allowlist."""
        config = {"dynamic_commands": {"allow": ["git*"]}}
        reason = get_disallowed_reason("npm test", config)

        assert "not in the configured allowed commands" in reason

    def test_explains_not_in_safe_defaults(self):
        """Should explain when command is not in safe defaults."""
        config = {}
        reason = get_disallowed_reason("rm -rf", config)

        assert "not in the safe default command list" in reason


class TestValidateCommand:
    """Tests for command validation with exceptions."""

    def test_validates_allowed_command(self):
        """Should not raise for allowed commands."""
        config = {"dynamic_commands": {"allow": ["git*"]}}

        # Should not raise
        validate_command("git status", config)

    def test_raises_for_disallowed_command(self):
        """Should raise CommandValidationError for disallowed commands."""
        config = {"dynamic_commands": {"deny": ["rm *"]}}

        with pytest.raises(CommandValidationError) as exc_info:
            validate_command("rm -rf /", config)

        assert "rm *" in str(exc_info.value)


class TestParseCommandDefinition:
    """Tests for command definition parsing (ADR-0024)."""

    def test_parses_wildcard_syntax(self):
        """Should parse legacy wildcard syntax."""
        parsed = parse_command_definition("cat *")

        assert not parsed.uses_bracket_syntax
        assert parsed.command_prefix == "cat"
        assert len(parsed.parameters) == 0
        assert parsed.original_pattern == "cat *"

    def test_parses_bracket_syntax_with_type_only(self):
        """Should parse bracket syntax with type only (no hint)."""
        parsed = parse_command_definition("cat <path>")

        assert parsed.uses_bracket_syntax
        assert parsed.command_prefix == "cat"
        assert len(parsed.parameters) == 1
        assert parsed.parameters[0].type == "path"
        assert parsed.parameters[0].hint is None
        assert parsed.parameters[0].position == 0

    def test_parses_bracket_syntax_with_type_and_hint(self):
        """Should parse bracket syntax with both type and hint."""
        parsed = parse_command_definition("cat <path:file to read>")

        assert parsed.uses_bracket_syntax
        assert parsed.command_prefix == "cat"
        assert len(parsed.parameters) == 1
        assert parsed.parameters[0].type == "path"
        assert parsed.parameters[0].hint == "file to read"

    def test_parses_multiple_parameters(self):
        """Should parse commands with multiple parameters."""
        parsed = parse_command_definition(
            "curl -X <string:http method> <url:endpoint url>"
        )

        assert parsed.uses_bracket_syntax
        assert parsed.command_prefix == "curl -X"
        assert len(parsed.parameters) == 2
        assert parsed.parameters[0].type == "string"
        assert parsed.parameters[0].hint == "http method"
        assert parsed.parameters[1].type == "url"
        assert parsed.parameters[1].hint == "endpoint url"

    def test_parses_complex_command_prefix(self):
        """Should correctly extract complex command prefixes."""
        parsed = parse_command_definition(
            "curl -X POST -H Content-Type:application/json <url:endpoint>"
        )

        assert parsed.uses_bracket_syntax
        assert parsed.command_prefix == "curl -X POST -H Content-Type:application/json"
        assert len(parsed.parameters) == 1

    def test_parses_various_parameter_types(self):
        """Should parse all supported parameter types."""
        types = ["string", "number", "path", "url", "json", "regex"]

        for param_type in types:
            parsed = parse_command_definition(f"cmd <{param_type}:test>")
            assert parsed.parameters[0].type == param_type

    def test_handles_empty_hint(self):
        """Should handle brackets with colons but empty hints."""
        parsed = parse_command_definition("cmd <string:>")

        assert parsed.uses_bracket_syntax
        assert parsed.parameters[0].type == "string"
        assert parsed.parameters[0].hint == ""  # Empty string, not None


class TestExtractParameterHints:
    """Tests for parameter hint extraction."""

    def test_extracts_hints_from_parsed_command(self):
        """Should extract formatted hints from parsed command."""
        parsed = ParsedCommand(
            uses_bracket_syntax=True,
            command_prefix="cat",
            parameters=[Parameter(type="path", hint="file to read", position=0)],
            original_pattern="cat <path:file to read>",
        )

        hints = extract_parameter_hints(parsed)

        assert "Parameters:" in hints
        assert "path: file to read" in hints

    def test_returns_empty_for_no_parameters(self):
        """Should return empty string when no parameters."""
        parsed = ParsedCommand(
            uses_bracket_syntax=False,
            command_prefix="cat",
            parameters=[],
            original_pattern="cat *",
        )

        hints = extract_parameter_hints(parsed)

        assert hints == ""

    def test_formats_multiple_parameters(self):
        """Should format multiple parameters correctly."""
        parsed = ParsedCommand(
            uses_bracket_syntax=True,
            command_prefix="curl",
            parameters=[
                Parameter(type="string", hint="http method", position=0),
                Parameter(type="url", hint="endpoint", position=1),
            ],
            original_pattern="curl <string:http method> <url:endpoint>",
        )

        hints = extract_parameter_hints(parsed)

        assert "string: http method" in hints
        assert "url: endpoint" in hints


class TestMatchesBracketCommand:
    """Tests for bracket command matching (ADR-0024)."""

    def test_matches_simple_bracket_command(self):
        """Should match simple bracket commands."""
        parsed = parse_command_definition("cat <path>")
        assert matches_bracket_command("cat file.txt", "cat <path>", parsed)

    def test_matches_command_with_hint(self):
        """Should match bracket commands with hints."""
        parsed = parse_command_definition("cat <path:file to read>")
        assert matches_bracket_command(
            "cat README.md", "cat <path:file to read>", parsed
        )

    def test_matches_multiple_parameters(self):
        """Should match commands with multiple parameters."""
        parsed = parse_command_definition("curl -X <string:http method> <url:endpoint>")
        assert matches_bracket_command(
            "curl -X POST https://api.example.com",
            "curl -X <string:http method> <url:endpoint>",
            parsed,
        )

    def test_rejects_wrong_prefix(self):
        """Should reject commands with wrong prefix."""
        parsed = parse_command_definition("cat <path>")
        assert not matches_bracket_command("dog file.txt", "cat <path>", parsed)

    def test_rejects_wrong_parameter_count(self):
        """Should reject commands with wrong parameter count."""
        parsed = parse_command_definition("cat <path>")

        # Too few parameters
        assert not matches_bracket_command("cat", "cat <path>", parsed)

        # Too many parameters
        assert not matches_bracket_command(
            "cat file1.txt file2.txt", "cat <path>", parsed
        )

    def test_requires_exact_prefix_match(self):
        """Should require exact prefix matching."""
        parsed = parse_command_definition("curl -X <string>")

        # Correct prefix
        assert matches_bracket_command("curl -X POST", "curl -X <string>", parsed)

        # Wrong prefix
        assert not matches_bracket_command("curl -x POST", "curl -X <string>", parsed)


class TestBracketSyntaxIntegration:
    """Integration tests for bracket syntax with validation (ADR-0024)."""

    def test_bracket_syntax_allows_matching_command(self):
        """Bracket syntax should allow commands with correct parameters."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "cat <path:file to read>", "description": "Read file"}
                ]
            }
        }

        assert is_command_allowed("cat file.txt", config)
        assert is_command_allowed("cat README.md", config)

    def test_bracket_syntax_rejects_wrong_parameter_count(self):
        """Bracket syntax should reject commands with wrong parameter count."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "cat <path:file to read>", "description": "Read file"}
                ]
            }
        }

        assert not is_command_allowed("cat", config)
        assert not is_command_allowed("cat file1.txt file2.txt", config)

    def test_backward_compatibility_with_wildcard(self):
        """Wildcard syntax should still work alongside bracket syntax."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {"command": "cat <path:file to read>", "description": "New syntax"},
                    {
                        "command": "ls*",
                        "description": "Old syntax",
                    },  # No space before *
                ]
            }
        }

        # Bracket syntax
        assert is_command_allowed("cat file.txt", config)

        # Wildcard syntax (ls* matches ls, ls -la, etc.)
        assert is_command_allowed("ls", config)
        assert is_command_allowed("ls -la", config)
        assert is_command_allowed("lsxyz", config)

    def test_provides_helpful_error_for_bracket_mismatch(self):
        """Should provide parameter count hint for bracket syntax errors."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {
                        "command": "curl -X <string:http method> <url:endpoint>",
                        "description": "Make request",
                    }
                ]
            }
        }

        reason = get_disallowed_reason("curl -X POST", config)

        assert "Expected 2 parameter(s)" in reason
        assert "got 1" in reason

    def test_tool_description_includes_bracket_parameter_hints(self):
        """Tool description should include parameter hints from bracket syntax."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {
                        "command": "curl -X <string:http method> <url:endpoint>",
                        "description": "Make HTTP request",
                    }
                ]
            }
        }

        tool = generate_command_tool(config)
        description = tool["function"]["description"]

        assert "curl -X" in description
        assert "Make HTTP request" in description
        assert "Parameters:" in description
        assert "string: http method" in description
        assert "url: endpoint" in description

    def test_mixed_parameter_types_in_tool_description(self):
        """Should handle mixed parameter types in tool descriptions."""
        config = {
            "dynamic_commands": {
                "available_commands": [
                    {
                        "command": "process <path:input file> <number:timeout seconds> <json:config>",
                        "description": "Process with config",
                    }
                ]
            }
        }

        tool = generate_command_tool(config)
        description = tool["function"]["description"]

        assert "path: input file" in description
        assert "number: timeout seconds" in description
        assert "json: config" in description
