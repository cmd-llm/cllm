"""Tool definitions and command validation for dynamic command execution.

Implements ADR-0013: LLM-Driven Dynamic Command Execution
Implements ADR-0024: Explicit Command Parameter Syntax (hybrid support)
"""

import fnmatch
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class CommandValidationError(Exception):
    """Raised when a command fails validation checks."""

    pass


@dataclass
class Parameter:
    """Represents a parameter in a command definition.

    Attributes:
        type: Parameter type (string, number, path, url, json, regex)
        hint: Optional semantic hint for LLM guidance (e.g., "file to read", "endpoint url")
        position: Position of this parameter in the command
    """

    type: str
    hint: Optional[str] = None
    position: int = 0

    def __str__(self) -> str:
        """Format parameter for display in tool descriptions."""
        if self.hint:
            return f"{self.type}: {self.hint}"
        return self.type


@dataclass
class ParsedCommand:
    """Result of parsing a command definition.

    Attributes:
        uses_bracket_syntax: True if command uses bracket syntax (ADR-0024)
        command_prefix: The command prefix (e.g., "cat", "curl -X POST")
        parameters: List of extracted parameters
        original_pattern: The original command pattern as defined
    """

    uses_bracket_syntax: bool
    command_prefix: str
    parameters: List[Parameter]
    original_pattern: str


def parse_command_definition(command_def: str) -> ParsedCommand:
    """Parse a command definition supporting both wildcard and bracket syntax.

    Supports two syntaxes:
    - Legacy: "cat *" (wildcard patterns, backward compatible)
    - New: "cat <path:file to read>" (bracket syntax with types and hints)

    Examples:
        parse_command_definition("cat *")
        => ParsedCommand(uses_bracket_syntax=False, command_prefix="cat", parameters=[])

        parse_command_definition("cat <path:file to read>")
        => ParsedCommand(uses_bracket_syntax=True, command_prefix="cat",
                         parameters=[Parameter(type='path', hint='file to read')])

        parse_command_definition("curl -X <string:http method> <url:endpoint url>")
        => ParsedCommand(uses_bracket_syntax=True,
                         command_prefix="curl -X",
                         parameters=[Parameter(type='string', hint='http method'),
                                    Parameter(type='url', hint='endpoint url')])

    Args:
        command_def: Command definition string

    Returns:
        ParsedCommand with parsed components
    """
    # Check if command uses bracket syntax
    # Pattern matches <type> or <type:hint> where hint can be empty
    bracket_pattern = r"<(\w+)(?::([^>]*))?>"
    matches = list(re.finditer(bracket_pattern, command_def))

    if matches:
        # Extract command prefix (everything before first bracket)
        first_match_start = matches[0].start()
        command_prefix = command_def[:first_match_start].rstrip()

        # Extract parameters
        parameters: List[Parameter] = []
        for position, match in enumerate(matches):
            param_type = match.group(1)
            # Preserve empty strings as hints (group(2) is None only if :hint is missing)
            param_hint = match.group(2)
            parameters.append(
                Parameter(type=param_type, hint=param_hint, position=position)
            )

        return ParsedCommand(
            uses_bracket_syntax=True,
            command_prefix=command_prefix,
            parameters=parameters,
            original_pattern=command_def,
        )
    else:
        # Legacy wildcard syntax
        # Remove trailing wildcards to get the command prefix
        prefix = command_def.rstrip("*").rstrip()
        return ParsedCommand(
            uses_bracket_syntax=False,
            command_prefix=prefix,
            parameters=[],
            original_pattern=command_def,
        )


def extract_parameter_hints(parsed_command: ParsedCommand) -> str:
    """Extract human-readable parameter hints from a parsed command.

    Args:
        parsed_command: A ParsedCommand object

    Returns:
        Formatted string describing parameters, or empty string if no parameters
    """
    if not parsed_command.parameters:
        return ""

    hints = []
    for param in parsed_command.parameters:
        hints.append(f"  - {param}")

    return "Parameters:\n" + "\n".join(hints)


def matches_bracket_command(
    provided_command: str, command_pattern: str, parsed_cmd: ParsedCommand
) -> bool:
    """Check if a provided command matches a bracket syntax pattern.

    Args:
        provided_command: The actual command string provided
        command_pattern: The command pattern with bracket syntax
        parsed_cmd: Pre-parsed command pattern information

    Returns:
        True if the command matches the pattern
    """
    # Split provided command into tokens
    provided_tokens = provided_command.split()
    pattern_tokens = parsed_cmd.command_prefix.split()

    # Check if command starts with the correct prefix
    if len(provided_tokens) < len(pattern_tokens):
        return False

    for i, pattern_token in enumerate(pattern_tokens):
        if provided_tokens[i] != pattern_token:
            return False

    # Check if the number of parameters matches expectations
    # (prefix tokens + number of parameters)
    expected_token_count = len(pattern_tokens) + len(parsed_cmd.parameters)
    if len(provided_tokens) != expected_token_count:
        return False

    return True


# Safe default commands (read-only operations)
SAFE_DEFAULT_COMMANDS = [
    "git status*",
    "git log*",
    "git diff*",
    "git show*",
    "git branch*",
    "ls*",
    "cat *",
    "head *",
    "tail *",
    "grep *",
    "find *",
    "npm test*",
    "pytest*",
    "make test*",
    "df*",
    "ps*",
    "whoami",
    "pwd",
    "echo *",
]


def generate_command_tool(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate LiteLLM tool definition for command execution.

    The tool definition is dynamically built based on the configuration.
    If available_commands with descriptions is provided, those descriptions
    are included to help the LLM choose the right command.

    Supports both legacy wildcard syntax and new bracket syntax (ADR-0024):
    - Wildcard: "cat *"
    - Bracket: "cat <path:file to read>"

    Args:
        config: Configuration dictionary with optional dynamic_commands section

    Returns:
        LiteLLM tool definition dictionary
    """
    base_description = "Execute a bash command to gather information needed to answer the user's question.\n\n"

    dynamic_commands = config.get("dynamic_commands", {})
    available_commands = dynamic_commands.get("available_commands", [])

    if available_commands:
        base_description += "Available commands:\n"
        for cmd_def in available_commands:
            if isinstance(cmd_def, dict):
                cmd = cmd_def.get("command", "")
                desc = cmd_def.get("description", "No description provided")
                base_description += f"- `{cmd}`: {desc}\n"

                # Extract and include parameter hints for bracket syntax (ADR-0024)
                parsed_cmd = parse_command_definition(cmd)
                if parsed_cmd.uses_bracket_syntax and parsed_cmd.parameters:
                    param_hints = extract_parameter_hints(parsed_cmd)
                    base_description += f"  {param_hints}\n"

        base_description += "\nYou can also use variations of these commands with different arguments if needed.\n\n"
    else:
        base_description += """
Common use cases:
- Check file contents (cat, head, tail, grep)
- Examine git status or diffs (git status, git diff, git log)
- Run tests or builds (npm test, pytest, make)
- Check system information (ls, find, ps, df)

"""

    base_description += """
Do NOT use this for:
- Destructive operations (rm, mv, dd)
- Privilege escalation (sudo, su)
- Network operations (curl, wget) unless explicitly allowed
- Writing or modifying files (>, >>, vim, nano)

The command will be validated against allowlists/denylists before execution.
"""

    return {
        "type": "function",
        "function": {
            "name": "execute_bash_command",
            "description": base_description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute (e.g., 'git status', 'npm test', 'cat error.log')",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this command is needed to answer the user's question",
                    },
                },
                "required": ["command", "reason"],
            },
        },
    }


def is_command_allowed(command: str, config: Dict[str, Any]) -> bool:
    """Validate command against available_commands, allowlist, and denylist.

    Supports both legacy wildcard and new bracket syntax (ADR-0024):
    - Wildcard: "cat *" matches "cat file.txt"
    - Bracket: "cat <path:file to read>" matches "cat file.txt" with validation

    Validation precedence:
    1. Denylist (highest precedence - blocks everything)
    2. Available commands (structured definitions with descriptions)
    3. Simple allowlist (wildcard patterns)
    4. Safe defaults (when no explicit configuration)

    Args:
        command: The command string to validate
        config: Configuration dictionary with optional dynamic_commands section

    Returns:
        True if command is allowed, False otherwise
    """
    dynamic_commands = config.get("dynamic_commands", {})

    # Check denylist first (takes precedence over everything)
    denylist = dynamic_commands.get("deny", [])
    for pattern in denylist:
        if fnmatch.fnmatch(command, pattern):
            return False

    # Check available_commands (structured definitions with descriptions)
    # Supports both wildcard and bracket syntax (ADR-0024)
    available_commands = dynamic_commands.get("available_commands", None)
    if available_commands is not None:
        for cmd_def in available_commands:
            if isinstance(cmd_def, dict):
                cmd_pattern = cmd_def.get("command", "")

                # Parse command pattern to determine syntax type
                parsed_cmd = parse_command_definition(cmd_pattern)

                if parsed_cmd.uses_bracket_syntax:
                    # New bracket syntax (ADR-0024): match with parameter validation
                    if matches_bracket_command(command, cmd_pattern, parsed_cmd):
                        return True
                else:
                    # Legacy wildcard syntax: standard fnmatch
                    # Use pattern directly if it already has wildcards, otherwise add trailing wildcard
                    if command == cmd_pattern:
                        return True
                    if "*" in cmd_pattern:
                        # Pattern already has wildcards, use as-is
                        if fnmatch.fnmatch(command, cmd_pattern):
                            return True
                    else:
                        # No wildcards, allow variations with args
                        if fnmatch.fnmatch(command, cmd_pattern + "*"):
                            return True
        # If available_commands is defined but command not found, still check allowlist
        # This allows combining both approaches

    # Check allowlist if defined (simple wildcard patterns)
    allowlist = dynamic_commands.get("allow", None)
    if allowlist is not None:
        for pattern in allowlist:
            if fnmatch.fnmatch(command, pattern):
                return True

    # If either available_commands or allowlist was defined, don't use defaults
    if available_commands is not None or allowlist is not None:
        return False

    # Default: allow safe read-only commands when no explicit configuration
    for pattern in SAFE_DEFAULT_COMMANDS:
        if fnmatch.fnmatch(command, pattern):
            return True

    return False  # Not in safe defaults


def get_disallowed_reason(command: str, config: Dict[str, Any]) -> str:
    """Get a human-readable explanation of why a command was disallowed.

    Supports both legacy wildcard and new bracket syntax (ADR-0024).

    Args:
        command: The command that was rejected
        config: Configuration dictionary

    Returns:
        Explanation string
    """
    dynamic_commands = config.get("dynamic_commands", {})

    # Check if blocked by denylist
    denylist = dynamic_commands.get("deny", [])
    for pattern in denylist:
        if fnmatch.fnmatch(command, pattern):
            return f"Command '{command}' matches denylist pattern: {pattern}"

    # Check if configuration defines allowlist/available_commands but command not in it
    available_commands = dynamic_commands.get("available_commands", None)
    allowlist = dynamic_commands.get("allow", None)

    # If bracket syntax is used, provide more specific feedback about parameter mismatch
    if available_commands is not None:
        for cmd_def in available_commands:
            if isinstance(cmd_def, dict):
                cmd_pattern = cmd_def.get("command", "")
                parsed_cmd = parse_command_definition(cmd_pattern)

                if parsed_cmd.uses_bracket_syntax:
                    # For bracket syntax, check if prefix matches but parameters don't
                    provided_tokens = command.split()
                    pattern_tokens = parsed_cmd.command_prefix.split()

                    if len(provided_tokens) >= len(pattern_tokens):
                        prefix_matches = True
                        for i, pattern_token in enumerate(pattern_tokens):
                            if provided_tokens[i] != pattern_token:
                                prefix_matches = False
                                break

                        if prefix_matches:
                            expected_param_count = len(parsed_cmd.parameters)
                            actual_param_count = len(provided_tokens) - len(
                                pattern_tokens
                            )
                            if actual_param_count != expected_param_count:
                                param_hints = extract_parameter_hints(parsed_cmd)
                                return (
                                    f"Command '{command}' doesn't match pattern '{cmd_pattern}'. "
                                    f"Expected {expected_param_count} parameter(s), got {actual_param_count}.\n"
                                    f"{param_hints}"
                                )

    if available_commands is not None or allowlist is not None:
        return (
            f"Command '{command}' is not in the configured allowed commands. "
            f"See dynamic_commands.available_commands or dynamic_commands.allow in your Cllmfile.yml"
        )

    # Otherwise, not in safe defaults
    return (
        f"Command '{command}' is not in the safe default command list. "
        f"To allow this command, add it to dynamic_commands.allow or dynamic_commands.available_commands "
        f"in your Cllmfile.yml"
    )


def validate_command(command: str, config: Dict[str, Any]) -> None:
    """Validate a command and raise an exception if not allowed.

    Args:
        command: The command to validate
        config: Configuration dictionary

    Raises:
        CommandValidationError: If command is not allowed
    """
    if not is_command_allowed(command, config):
        reason = get_disallowed_reason(command, config)
        raise CommandValidationError(reason)
