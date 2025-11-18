"""
Command-line interface for CLLM.

Provides a bash-centric CLI for interacting with LLMs across multiple providers.
Implements ADR-0005: Add Structured Output Support with JSON Schema
Implements ADR-0009: Add Debugging and Logging Support
Implements ADR-0025: Logging Verbosity Levels
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import litellm

from .agent import AgentExecutionError, execute_with_dynamic_commands
from .client import LLMClient
from .config import (
    ConfigurationError,
    clear_schema_cache,
    get_config_sources,
    load_config,
    load_json_schema,
    merge_config_with_args,
    validate_against_schema,
)
from .context import (
    ContextCommand,
    FailureMode,
    inject_context,
    parse_context_commands,
)
from .conversation import Conversation, ConversationManager
from .init import InitError, initialize, list_available_templates
from .logging_handler import LoguruVerbosityHandler
from .templates import TemplateError, build_template_context
from .tools import CommandValidationError


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="cllm",
        description="Command-line interface for interacting with large language models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple completion with OpenAI
  cllm "What is the capital of France?" --model gpt-4

  # Use a different provider (Anthropic)
  cllm "Explain APIs briefly" --model claude-3-opus-20240229

  # Streaming response
  cllm "Tell me a story" --model gpt-4 --stream

  # Read from stdin
  echo "What is 2+2?" | cllm --model gpt-4

  # Control creativity with temperature
  cllm "Write a creative story" --model gpt-4 --temperature 1.5

  # Limit response length
  cllm "Explain quantum computing" --model gpt-4 --max-tokens 100

  # Use custom system prompt
  cllm --system "You are a pirate. Speak like one." "Tell me about Python"

  # Load system prompt from file
  cllm --system-file prompts/code-reviewer.txt < code.py

Subcommands:
  init                  Initialize .cllm directory structure
                        Run 'cllm init --help' for more information

Supported Providers (partial list):
  - OpenAI: gpt-4, gpt-3.5-turbo
  - Anthropic: claude-3-opus-20240229, claude-3-sonnet-20240229
  - Google: gemini-pro
  - And 100+ more via LiteLLM

For full provider list: https://docs.litellm.ai/docs/providers
        """,
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send to the LLM (reads from stdin if not provided)",
    )

    parser.add_argument(
        "-m",
        "--model",
        default="gpt-3.5-turbo",
        help="Model to use (default: gpt-3.5-turbo)",
    )

    parser.add_argument(
        "-t", "--temperature", type=float, help="Sampling temperature (0.0 to 2.0)"
    )

    parser.add_argument("--max-tokens", type=int, help="Maximum tokens to generate")

    parser.add_argument(
        "--system",
        metavar="TEXT",
        help="System prompt to use (overrides default_system_message in config)",
    )

    parser.add_argument(
        "--system-file",
        metavar="PATH",
        help="Load system prompt from file (overrides default_system_message in config)",
    )

    parser.add_argument(
        "-s",
        "--stream",
        action="store_true",
        help="Stream the response as it's generated",
    )

    parser.add_argument("--raw", action="store_true", help="Output raw JSON response")

    parser.add_argument(
        "-c",
        "--config",
        metavar="NAME",
        help="Use named configuration file (e.g., 'summarize' loads summarize.Cllmfile.yml)",
    )

    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Display effective configuration and exit",
    )

    parser.add_argument(
        "--cllm-path",
        metavar="PATH",
        help="Custom .cllm directory path (overrides default search and CLLM_PATH env var)",
    )

    parser.add_argument(
        "--conversations-path",
        metavar="PATH",
        help="Custom conversations directory path (overrides --cllm-path and CLLM_CONVERSATIONS_PATH env var)",
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all available models and exit",
    )

    parser.add_argument(
        "--json-schema",
        metavar="SCHEMA",
        help="JSON schema for structured output (inline JSON string)",
    )

    parser.add_argument(
        "--json-schema-file",
        metavar="FILE",
        help="Path to JSON schema file for structured output",
    )

    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate the JSON schema and exit (no LLM call made)",
    )

    parser.add_argument(
        "--clear-schema-cache",
        action="store_true",
        help="Clear all cached remote schemas and exit",
    )

    # Conversation management arguments
    parser.add_argument(
        "--conversation",
        metavar="ID",
        help="Use or create conversation with specified ID (auto-generates if ID not provided)",
    )

    parser.add_argument(
        "--list-conversations",
        action="store_true",
        help="List all stored conversations and exit",
    )

    parser.add_argument(
        "--show-conversation",
        metavar="ID",
        help="Display conversation contents and exit",
    )

    parser.add_argument(
        "--delete-conversation",
        metavar="ID",
        help="Delete conversation and exit",
    )

    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Load conversation context without saving new messages (requires --conversation)",
    )

    # Debugging and logging arguments (ADR-0009)
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (verbose logging) - ⚠️  Logs API keys - NOT for production",
    )

    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Enable JSON structured logging",
    )

    parser.add_argument(
        "--log-file",
        metavar="PATH",
        help="Write debug/log output to file instead of stderr",
    )

    # Verbosity levels (ADR-0025)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity level (use -v, -vv, or -vvv for levels 1, 2, 3)",
    )

    # Context injection arguments (ADR-0011)
    parser.add_argument(
        "--exec",
        action="append",
        metavar="COMMAND",
        dest="context_exec",
        help="Execute command and inject output into context (can be used multiple times)",
    )

    parser.add_argument(
        "--no-context-exec",
        action="store_true",
        help="Disable context commands from configuration file",
    )

    # Dynamic command execution arguments (ADR-0013)
    parser.add_argument(
        "--allow-commands",
        action="store_true",
        help="Enable LLM-driven dynamic command execution (requires tool-calling capable model)",
    )

    parser.add_argument(
        "--command-allow",
        metavar="PATTERNS",
        help="Comma-separated command patterns to allow (e.g., 'git*,npm*')",
    )

    parser.add_argument(
        "--command-deny",
        metavar="PATTERNS",
        help="Comma-separated command patterns to deny (takes precedence over allow)",
    )

    parser.add_argument(
        "--confirm-commands",
        action="store_true",
        help="Prompt for confirmation before executing each command",
    )

    # Variable expansion arguments (ADR-0012)
    parser.add_argument(
        "--var",
        action="append",
        metavar="KEY=VALUE",
        dest="variables",
        help="Set template variable (e.g., --var FILE_PATH=src/main.py). Can be used multiple times.",
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    return parser


def _collect_request_parameters(
    config: Dict[str, Any], kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """Build a concise parameter dictionary for logging."""
    params = {
        k: v for k, v in kwargs.items() if k not in {"raw_response", "response_format"}
    }
    for key in ("temperature", "max_tokens"):
        if key in config and key not in params:
            params[key] = config[key]
    return params


def _extract_endpoint_from_kwargs(kwargs: Dict[str, Any]) -> Optional[str]:
    """Best-effort extraction of the API endpoint from LiteLLM kwargs."""
    for key in ("api_base", "base_url", "api_endpoint", "endpoint"):
        if key in kwargs and kwargs[key]:
            return str(kwargs[key])
    return None


def _serialize_for_logging(payload: Any) -> str:
    """Serialize arbitrary payloads for TRACE-level logging."""

    def _default(obj: Any) -> Any:
        if isinstance(obj, set):
            return list(obj)
        for attr in ("model_dump", "dict"):
            if hasattr(obj, attr):
                try:
                    return getattr(obj, attr)()
                except TypeError:
                    continue
        if hasattr(obj, "__dict__"):
            return {
                key: value
                for key, value in obj.__dict__.items()
                if not key.startswith("_")
            }
        return str(obj)

    try:
        return json.dumps(payload, indent=2, default=_default)
    except (TypeError, ValueError):
        return repr(payload)


def _log_request_summary(
    handler: "LoguruVerbosityHandler",
    *,
    model: str,
    provider: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    latency_seconds: float,
    parameters: Optional[Dict[str, Any]],
    config_sources: Optional[list[str]],
    endpoint: Optional[str],
) -> None:
    """Emit structured logs for the completed request."""
    if handler.level == 0:
        return

    handler.print_basic_info(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=provider,
        latency_seconds=latency_seconds,
    )

    if handler.level >= 2:
        handler.print_api_details(
            endpoint=endpoint,
            parameters=parameters if parameters else None,
            status_code=200,
            config_sources=config_sources if config_sources else None,
        )
        handler.log_response_status(200, latency_seconds * 1000)


def _log_response_payload_if_needed(
    handler: "LoguruVerbosityHandler",
    metadata: Dict[str, Any],
    fallback: Any,
) -> None:
    """Log the raw response payload when TRACE verbosity is enabled."""
    if handler.level < 3:
        return

    response_obj = metadata.get("response_object") or fallback
    if response_obj is None:
        return
    handler.log_response_payload(_serialize_for_logging(response_obj))


def _preview_text(value: Optional[str], limit: int = 160) -> Optional[str]:
    """Return a truncated preview string for logging."""
    if not value:
        return None
    value = value.strip()
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def _log_event(
    handler: "LoguruVerbosityHandler",
    run_id: str,
    message: str,
    *,
    importance: str = "major",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an event with consistent metadata (run_id, importance)."""
    if importance == "minor" and handler.level < 2:
        return

    payload = {"run_id": run_id}
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})
    handler.log_event(message, importance=importance, extra=payload)


def _log_minor_event(
    handler: "LoguruVerbosityHandler",
    run_id: str,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Helper to emit minor events only when verbosity >= 2."""
    _log_event(handler, run_id, message, importance="minor", extra=extra)


def _log_response_metadata(
    handler: "LoguruVerbosityHandler",
    run_id: str,
    response_obj: Any,
) -> None:
    """Log provider metadata extracted from the raw response object."""
    if handler.level == 0 or response_obj is None:
        return

    def _get_attr(obj: Any, attr: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr)
        return getattr(obj, attr, None)

    request_id = _get_attr(response_obj, "id")
    status = _get_attr(response_obj, "status")
    created = _get_attr(response_obj, "created")
    system_fingerprint = _get_attr(response_obj, "system_fingerprint")
    model_name = _get_attr(response_obj, "model")

    finish_reason = None
    choices = _get_attr(response_obj, "choices")
    if choices:
        choice = choices[0]
        if isinstance(choice, dict):
            finish_reason = choice.get("finish_reason")
        else:
            finish_reason = getattr(choice, "finish_reason", None)

    meta = {
        "request_id": request_id,
        "status": status,
        "model": model_name,
        "finish_reason": finish_reason,
        "created": created,
        "system_fingerprint": system_fingerprint,
    }

    if any(value is not None for value in meta.values()):
        _log_minor_event(
            handler,
            run_id,
            "Provider response metadata",
            extra=meta,
        )


def _determine_setting_source(
    key: str,
    cli_args: Dict[str, Any],
    env_overrides: Dict[str, str],
    file_config: Dict[str, Any],
) -> str:
    """Determine where a setting originated from."""
    if key in cli_args:
        return "cli-flag"
    if key in env_overrides:
        return f"env:{env_overrides[key]}"
    if key in file_config:
        return "config-file"
    return "default"


def _log_setting_resolution(
    handler: "LoguruVerbosityHandler",
    run_id: str,
    *,
    key: str,
    value: Any,
    source: str,
    importance: str = "minor",
) -> None:
    """Log where a configuration setting came from."""
    _log_event(
        handler,
        run_id,
        "Setting resolved",
        importance=importance,
        extra={"setting": key, "value": value, "source": source},
    )


def read_prompt(prompt_arg: Optional[str]) -> str:
    """
    Read the prompt from argument or stdin.

    Args:
        prompt_arg: The prompt from command line arguments

    Returns:
        The prompt text
    """
    stdin_content = ""

    # Read from stdin if available
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()

    # Combine prompt_arg and stdin if both exist
    if prompt_arg and stdin_content:
        return f"{prompt_arg}\n{stdin_content}"
    elif prompt_arg:
        return prompt_arg
    elif stdin_content:
        return stdin_content

    # No prompt provided
    print("Error: No prompt provided. Use 'cllm --help' for usage.", file=sys.stderr)
    sys.exit(1)


def load_system_prompt_from_file(file_path: str) -> str:
    """
    Load system prompt from a file.

    Args:
        file_path: Path to the system prompt file

    Returns:
        The system prompt text

    Raises:
        SystemExit: If file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"Error: System prompt file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(
                f"Error: System prompt path is not a file: {file_path}", file=sys.stderr
            )
            sys.exit(1)

        # Read file with UTF-8 encoding
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print(f"Warning: System prompt file is empty: {file_path}", file=sys.stderr)

        return content
    except OSError as e:
        print(
            f"Error: Cannot read system prompt file '{file_path}': {e}", file=sys.stderr
        )
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(
            f"Error: System prompt file is not valid UTF-8: {file_path}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_variables(var_list: Optional[list[str]]) -> Dict[str, Any]:
    """
    Parse --var KEY=VALUE arguments into a dictionary.

    Implements ADR-0012: Variable Expansion in Context Commands

    Args:
        var_list: List of "KEY=VALUE" strings from --var arguments

    Returns:
        Dictionary of parsed variables

    Raises:
        SystemExit: If variable format is invalid
    """
    if not var_list:
        return {}

    variables = {}
    for var_str in var_list:
        if "=" not in var_str:
            print(
                f"Error: Invalid variable format '{var_str}'. "
                f"Expected KEY=VALUE (e.g., --var FILE_PATH=src/main.py)",
                file=sys.stderr,
            )
            sys.exit(1)

        key, value = var_str.split("=", 1)  # Split on first '=' only

        # Validate variable name (must match [A-Za-z_][A-Za-z0-9_]*)
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            print(
                f"Error: Invalid variable name '{key}'. "
                f"Variable names must start with a letter or underscore "
                f"and contain only letters, numbers, and underscores.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Try to parse value as boolean or number for convenience
        # "true"/"false" -> bool, numeric strings -> int/float, else -> str
        if value.lower() == "true":
            variables[key] = True
        elif value.lower() == "false":
            variables[key] = False
        elif value.isdigit():
            variables[key] = int(value)
        elif value.replace(".", "", 1).replace("-", "", 1).isdigit():
            # Check if it's a float
            try:
                variables[key] = float(value)
            except ValueError:
                variables[key] = value
        else:
            variables[key] = value

    return variables


def print_model_list():
    """
    Print a list of all available models from LiteLLM.

    Models are organized by provider for better readability while
    maintaining bash-friendly formatting (grep-able, one model per line).
    """
    # Get all models from LiteLLM
    models = sorted(litellm.model_list)

    # Define common provider prefixes and their display names
    provider_prefixes = {
        "openai/": "OpenAI",
        "anthropic/": "Anthropic",
        "claude-": "Anthropic",
        "gpt-": "OpenAI",
        "google/": "Google",
        "gemini": "Google",
        "azure/": "Azure",
        "bedrock/": "AWS Bedrock",
        "cohere/": "Cohere",
        "command-": "Cohere",
        "replicate/": "Replicate",
        "huggingface/": "HuggingFace",
        "together_ai/": "Together AI",
        "palm/": "Google PaLM",
        "openrouter/": "OpenRouter",
        "vertex_ai/": "Vertex AI",
        "groq/": "Groq",
        "mistral/": "Mistral",
        "deepseek": "DeepSeek",
        "databricks/": "Databricks",
        "ollama/": "Ollama",
    }

    # Categorize models by provider
    categorized = {}
    uncategorized = []

    for model in models:
        matched = False
        for prefix, provider_name in provider_prefixes.items():
            if model.startswith(prefix) or (
                prefix.endswith("-") and prefix.rstrip("-") in model
            ):
                if provider_name not in categorized:
                    categorized[provider_name] = []
                categorized[provider_name].append(model)
                matched = True
                break

        if not matched:
            uncategorized.append(model)

    # Print header
    print(f"Available Models ({len(models)} total)")
    print("=" * 60)
    print()

    # Print categorized models
    for provider in sorted(categorized.keys()):
        print(f"{provider}:")
        for model in categorized[provider]:
            print(f"  {model}")
        print()

    # Print uncategorized models
    if uncategorized:
        print("Other Providers:")
        for model in uncategorized:
            print(f"  {model}")
        print()

    # Print usage hint
    print("=" * 60)
    print("Tip: Use grep to filter models, e.g., 'cllm --list-models | grep gpt'")


def print_conversation_list(manager: ConversationManager):
    """
    Print a list of all conversations.

    Args:
        manager: ConversationManager instance
    """
    conversations = manager.list_conversations()

    if not conversations:
        print("No conversations found.")
        print(
            "\nTip: Create a conversation with 'cllm --conversation <id> \"your prompt\"'"
        )
        return

    print(f"Conversations ({len(conversations)} total)")
    print("=" * 80)
    print()

    for conv in conversations:
        print(f"ID: {conv['id']}")
        print(f"  Model: {conv['model']}")
        print(f"  Messages: {conv['message_count']}")
        print(f"  Updated: {conv['updated_at']}")
        print()


def print_conversation(manager: ConversationManager, conversation_id: str):
    """
    Print the contents of a conversation.

    Args:
        manager: ConversationManager instance
        conversation_id: ID of conversation to display
    """
    try:
        conv = manager.load(conversation_id)
        print(f"Conversation: {conv.id}")
        print(f"Model: {conv.model}")
        print(f"Created: {conv.created_at}")
        print(f"Updated: {conv.updated_at}")
        print(f"Messages: {len(conv.messages)}")
        if conv.total_tokens > 0:
            print(f"Total tokens: {conv.total_tokens}")
        print("=" * 80)
        print()

        for i, msg in enumerate(conv.messages, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            print(f"[{i}] {role}:")
            print(content)
            print()

    except FileNotFoundError:
        print(f"Error: Conversation '{conversation_id}' not found", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def delete_conversation(manager: ConversationManager, conversation_id: str):
    """
    Delete a conversation.

    Args:
        manager: ConversationManager instance
        conversation_id: ID of conversation to delete
    """
    try:
        manager.delete(conversation_id)
        print(f"Deleted conversation: {conversation_id}")
    except FileNotFoundError:
        print(f"Error: Conversation '{conversation_id}' not found", file=sys.stderr)
        sys.exit(1)


def configure_debugging(
    debug: bool = False,
    json_logs: bool = False,
    log_file: Optional[str] = None,
) -> Optional[object]:
    """
    Configure LiteLLM debugging and logging.

    Implements ADR-0009: Add Debugging and Logging Support

    Args:
        debug: Enable verbose debug mode (sets litellm.set_verbose=True)
        json_logs: Enable JSON structured logging (sets litellm.json_logs=True)
        log_file: Optional path to log file (redirects stderr if provided)

    Returns:
        File handle if log_file is provided, None otherwise

    Side effects:
        - Sets litellm.set_verbose if debug=True
        - Sets litellm.json_logs if json_logs=True
        - Redirects stderr to log file if log_file is provided
        - Prints warning to stderr if debug=True
    """
    log_file_handle = None

    # Handle log file redirection first (before any output)
    if log_file:
        try:
            log_path = Path(log_file)
            # Create parent directories if needed
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # Open file with restrictive permissions (0600)
            # Open in append mode to allow multiple commands to write to same file
            log_file_handle = open(log_path, "a")
            # Set restrictive permissions on Unix-like systems
            if hasattr(os, "chmod"):
                os.chmod(log_path, 0o600)
            # Redirect stderr to log file
            sys.stderr = log_file_handle
        except OSError as e:
            print(f"Error: Cannot open log file '{log_file}': {e}", file=sys.stderr)
            sys.exit(1)

    # Show warning if debug mode is enabled
    if debug:
        print(
            "⚠️  Debug mode enabled. API keys and sensitive data may appear in output.",
            file=sys.stderr,
        )
        print(
            "⚠️  Do NOT use debug mode in production or with confidential data.",
            file=sys.stderr,
        )
        print(file=sys.stderr)  # Blank line for readability

    # Configure LiteLLM debugging
    if debug:
        litellm.set_verbose = True

    if json_logs:
        litellm.json_logs = True

    return log_file_handle


def extract_provider_from_model(model: str) -> str:
    """
    Extract provider name from model identifier.

    Handles various LiteLLM model formats:
    - Direct provider name: "gpt-4", "claude-3-opus-20240229", "gemini-pro"
    - Prefix format: "openai/gpt-4", "anthropic/claude-3"
    - Custom/Ollama format: "ollama/neural-chat"

    Args:
        model: Model identifier

    Returns:
        Provider name in lowercase
    """
    # Handle prefix format (openai/gpt-4 -> openai)
    if "/" in model:
        return model.split("/")[0].lower()

    # Handle model-based detection
    model_lower = model.lower()

    # OpenAI
    if model_lower.startswith("gpt-"):
        return "openai"

    # Anthropic
    if model_lower.startswith("claude-"):
        return "anthropic"

    # Google Gemini
    if model_lower.startswith("gemini"):
        return "google"

    # Groq
    if "groq" in model_lower:
        return "groq"

    # Cohere
    if "command-" in model_lower or "cohere" in model_lower:
        return "cohere"

    # Mistral
    if "mistral" in model_lower:
        return "mistral"

    # Meta Llama
    if "llama" in model_lower:
        return "meta"

    # DeepSeek
    if "deepseek" in model_lower:
        return "deepseek"

    # AWS Bedrock
    if "bedrock" in model_lower:
        return "aws"

    # Azure
    if "azure" in model_lower:
        return "azure"

    # Default: return the model prefix if it looks like it
    parts = model.split("-")
    if parts:
        return parts[0].lower()

    return "unknown"


# VerbosityHandler is now provided by LoguruVerbosityHandler from logging_handler module
# Maintains backward compatibility with existing code
VerbosityHandler = LoguruVerbosityHandler


def create_init_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the init command.

    Implements ADR-0023: Configurable Init with CLI Flags
    """
    parser = argparse.ArgumentParser(
        prog="cllm init",
        description="Initialize .cllm directory structure with optional templates and configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize local .cllm directory
  cllm init

  # Initialize global ~/.cllm directory
  cllm init --global

  # Initialize both local and global
  cllm init --global --local

  # Initialize with a template
  cllm init --template code-review
  cllm init --template summarize

  # Initialize with configuration flags (ADR-0023)
  cllm init --model gpt-4 --temperature 0.7
  cllm init --system "You are a helpful coding assistant"

  # Combine template with flag overrides (ADR-0023)
  cllm init --template code-review --model gpt-4
  cllm init --template creative --temperature 0.9 --max-tokens 3000

  # List available templates
  cllm init --list-templates

  # Force reinitialize (overwrite existing files)
  cllm init --force
        """,
    )

    parser.add_argument(
        "--global",
        dest="global_init",
        action="store_true",
        help="Initialize global ~/.cllm directory",
    )

    parser.add_argument(
        "--local",
        dest="local_init",
        action="store_true",
        help="Initialize local ./.cllm directory (default if no location specified)",
    )

    parser.add_argument(
        "--template",
        "-t",
        metavar="NAME",
        help="Use a specific template (e.g., code-review, summarize, creative)",
    )

    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available templates and exit",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing files and directories",
    )

    parser.add_argument(
        "--cllm-path",
        metavar="PATH",
        help="Custom .cllm directory path (overrides default locations)",
    )

    # Configuration flags (ADR-0023)
    # These mirror the standard cllm CLI flags and will be written to Cllmfile.yml

    parser.add_argument(
        "-m",
        "--model",
        metavar="MODEL",
        help="Model to use (e.g., gpt-4, claude-3-opus-20240229)",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        metavar="TEMP",
        help="Sampling temperature (0.0 to 2.0)",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        help="Maximum tokens to generate",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help="Request timeout in seconds",
    )

    parser.add_argument(
        "--system",
        metavar="TEXT",
        help="System prompt (sets default_system_message in config)",
    )

    parser.add_argument(
        "--system-file",
        metavar="PATH",
        help="Load system prompt from file (sets default_system_message in config)",
    )

    return parser


def handle_init_command(args: list[str]) -> None:
    """
    Handle the init subcommand.

    Implements ADR-0016: Configurable .cllm Directory Path
    Implements ADR-0023: Configurable Init with CLI Flags

    Args:
        args: Command-line arguments (excluding 'init')
    """
    parser = create_init_parser()
    parsed_args = parser.parse_args(args)

    # Handle --list-templates
    if parsed_args.list_templates:
        list_available_templates()
        sys.exit(0)

    # ADR-0023: Handle --system and --system-file conflict
    if parsed_args.system and parsed_args.system_file:
        print(
            "Error: Cannot specify both --system and --system-file",
            file=sys.stderr,
        )
        sys.exit(1)

    # ADR-0023: Build configuration overrides from CLI flags
    config_overrides = {}

    if parsed_args.model is not None:
        config_overrides["model"] = parsed_args.model

    if parsed_args.temperature is not None:
        config_overrides["temperature"] = parsed_args.temperature

    if parsed_args.max_tokens is not None:
        config_overrides["max_tokens"] = parsed_args.max_tokens

    if parsed_args.timeout is not None:
        config_overrides["timeout"] = parsed_args.timeout

    if parsed_args.system is not None:
        config_overrides["default_system_message"] = parsed_args.system
    elif parsed_args.system_file is not None:
        # Load system prompt from file
        system_prompt = load_system_prompt_from_file(parsed_args.system_file)
        config_overrides["default_system_message"] = system_prompt

    # ADR-0016: Check for custom path (CLI flag > CLLM_PATH env var)
    custom_path = parsed_args.cllm_path or os.getenv("CLLM_PATH")

    # Initialize directories
    try:
        initialize(
            global_init=parsed_args.global_init,
            local_init=parsed_args.local_init,
            template_name=parsed_args.template,
            force=parsed_args.force,
            cllm_path=custom_path,
            config_overrides=config_overrides if config_overrides else None,
        )
    except InitError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    # Check if first argument is 'init' - handle as subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        # Remove 'init' from argv and handle separately
        handle_init_command(sys.argv[2:])
        return

    parser = create_parser()
    args = parser.parse_args()
    run_id = uuid.uuid4().hex[:8]

    try:
        # Load configuration from files (ADR-0016: support custom .cllm path)
        file_config = load_config(config_name=args.config, cllm_path=args.cllm_path)
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build CLI args dict (only non-None values)
    cli_args = {}
    if args.model and args.model != "gpt-3.5-turbo":  # Only if explicitly set
        cli_args["model"] = args.model
    if args.temperature is not None:
        cli_args["temperature"] = args.temperature
    if args.max_tokens is not None:
        cli_args["max_tokens"] = args.max_tokens
    if args.stream:
        cli_args["stream"] = args.stream
    if args.raw:
        cli_args["raw_response"] = args.raw
    if args.json_schema is not None:
        cli_args["json_schema"] = args.json_schema
    if args.json_schema_file is not None:
        cli_args["json_schema_file"] = args.json_schema_file
    # Debug flags (ADR-0009)
    if args.debug:
        cli_args["debug"] = args.debug
    if args.json_logs:
        cli_args["json_logs"] = args.json_logs
    if args.log_file is not None:
        cli_args["log_file"] = args.log_file
    # Verbosity level (ADR-0025)
    if args.verbose > 0:
        cli_args["verbosity"] = args.verbose

    # Merge config with CLI args (CLI takes precedence)
    config = merge_config_with_args(file_config, cli_args)

    # Handle system prompt CLI flags (ADR-0022)
    # Precedence: --system > --system-file > default_system_message in config
    if args.system:
        # --system flag takes highest precedence
        config["default_system_message"] = args.system
        if args.system_file:
            # Warn if both flags are provided
            print(
                "Warning: Both --system and --system-file provided. Using --system (inline text).",
                file=sys.stderr,
            )
    elif args.system_file:
        # --system-file takes second precedence
        system_prompt_from_file = load_system_prompt_from_file(args.system_file)
        config["default_system_message"] = system_prompt_from_file

    # Handle dynamic command execution flags (ADR-0013)
    # These are processed after config merge to ensure proper precedence
    if args.allow_commands:
        config["allow_dynamic_commands"] = True

    if args.command_allow:
        # Parse comma-separated patterns
        patterns = [p.strip() for p in args.command_allow.split(",") if p.strip()]
        if "dynamic_commands" not in config:
            config["dynamic_commands"] = {}
        config["dynamic_commands"]["allow"] = patterns

    if args.command_deny:
        # Parse comma-separated patterns
        patterns = [p.strip() for p in args.command_deny.split(",") if p.strip()]
        if "dynamic_commands" not in config:
            config["dynamic_commands"] = {}
        config["dynamic_commands"]["deny"] = patterns

    if args.confirm_commands:
        if "dynamic_commands" not in config:
            config["dynamic_commands"] = {}
        config["dynamic_commands"]["require_confirmation"] = True

    env_overrides: Dict[str, str] = {}

    # Support environment variables for debug settings (ADR-0009)
    # Precedence: CLI flags > Cllmfile > Environment variables
    if "debug" not in config and os.getenv("CLLM_DEBUG") == "1":
        config["debug"] = True
        env_overrides["debug"] = "CLLM_DEBUG"
    if "json_logs" not in config and os.getenv("CLLM_JSON_LOGS") == "1":
        config["json_logs"] = True
        env_overrides["json_logs"] = "CLLM_JSON_LOGS"
    if "log_file" not in config and os.getenv("CLLM_LOG_FILE"):
        config["log_file"] = os.getenv("CLLM_LOG_FILE")
        env_overrides["log_file"] = "CLLM_LOG_FILE"

    # Support environment variable for verbosity level (ADR-0025)
    # Precedence: CLI flags > Cllmfile > Environment variables
    if "verbosity" not in config and os.getenv("CLLM_VERBOSITY"):
        try:
            config["verbosity"] = int(os.getenv("CLLM_VERBOSITY"))
            env_overrides["verbosity"] = "CLLM_VERBOSITY"
        except ValueError:
            print(
                f"Warning: Invalid CLLM_VERBOSITY value: {os.getenv('CLLM_VERBOSITY')} (must be 0-3)",
                file=sys.stderr,
            )

    # Set defaults if not in config
    if "model" not in config:
        config["model"] = "gpt-3.5-turbo"

    # Handle verbosity levels (ADR-0025)
    # Verbosity level 3 automatically enables debug mode
    verbosity_level = config.get("verbosity", 0)
    if verbosity_level == 3:
        config["debug"] = True

    # Configure debugging and logging (ADR-0009)
    # Do this early so debug output is captured for all operations
    log_file_handle = configure_debugging(
        debug=config.get("debug", False),
        json_logs=config.get("json_logs", False),
        log_file=config.get("log_file"),
    )

    # Create VerbosityHandler instance for output during execution
    verbosity_handler = VerbosityHandler(level=verbosity_level)
    config_sources_for_logging: Optional[list[str]] = None
    if verbosity_handler.level >= 2:
        config_sources_for_logging = get_config_sources(
            config_name=args.config, cllm_path=args.cllm_path
        )
    _log_event(
        verbosity_handler,
        run_id,
        "Configuration merged",
        extra={
            "config": args.config or "default",
            "sources": len(config_sources_for_logging or []),
            "verbosity": verbosity_level,
            "json_logs": config.get("json_logs", False),
        },
    )

    tracked_settings = [
        ("model", "major"),
        ("verbosity", "major"),
        ("debug", "minor"),
        ("json_logs", "minor"),
        ("log_file", "minor"),
    ]
    for key, importance in tracked_settings:
        if key not in config and key != "verbosity":
            continue
        value = config.get(key, 0 if key == "verbosity" else None)
        if value is None and key in {"log_file"}:
            continue
        source = _determine_setting_source(key, cli_args, env_overrides, file_config)
        _log_setting_resolution(
            verbosity_handler,
            run_id,
            key=key,
            value=value,
            source=source,
            importance=importance,
        )

    # Handle JSON schema with proper precedence
    # Precedence: --json-schema > --json-schema-file > json_schema in config > json_schema_file in config
    schema: Optional[Dict[str, Any]] = None
    schema_source: Optional[str] = None
    try:
        if "json_schema" in config and isinstance(config["json_schema"], str):
            # CLI flag --json-schema (inline JSON string)
            schema = load_json_schema(json.loads(config["json_schema"]))
            schema_source = (
                "cli:inline-json" if "json_schema" in cli_args else "config:inline-json"
            )
        elif "json_schema" in config and isinstance(config["json_schema"], dict):
            # Cllmfile inline schema (already parsed from YAML)
            schema = load_json_schema(config["json_schema"])
            schema_source = "config:inline-yaml"
        elif "json_schema_file" in config:
            # CLI flag --json-schema-file or Cllmfile json_schema_file
            schema = load_json_schema(config["json_schema_file"])
            schema_source = (
                f"cli:file:{config['json_schema_file']}"
                if "json_schema_file" in cli_args
                else f"config:file:{config['json_schema_file']}"
            )
    except (json.JSONDecodeError, ConfigurationError) as e:
        print(f"Schema error: {e}", file=sys.stderr)
        sys.exit(1)
    if schema is not None:
        schema_props = schema.get("properties") if isinstance(schema, dict) else None
        _log_event(
            verbosity_handler,
            run_id,
            "Structured schema enabled",
            extra={
                "type": schema.get("type") if isinstance(schema, dict) else "unknown",
                "property_count": (
                    len(schema_props) if isinstance(schema_props, dict) else 0
                ),
                "source": schema_source,
            },
        )

    # Initialize conversation manager (needed for conversation commands)
    # ADR-0017: Support custom conversations path with proper precedence
    # Precedence: --conversations-path > CLLM_CONVERSATIONS_PATH > conversations_path in config > --cllm-path > CLLM_PATH > defaults
    conversations_path = None
    if args.conversations_path:
        # CLI flag takes highest precedence
        conversations_path = Path(args.conversations_path)
    elif os.getenv("CLLM_CONVERSATIONS_PATH"):
        # Environment variable takes second precedence
        conversations_path = Path(os.getenv("CLLM_CONVERSATIONS_PATH"))
    elif "conversations_path" in config:
        # Configuration file takes third precedence
        conversations_path = Path(config["conversations_path"])

    cllm_path = None
    if args.cllm_path:
        cllm_path = Path(args.cllm_path)

    conversation_manager = ConversationManager(
        cllm_path=cllm_path, conversations_path=conversations_path
    )

    cllm_path_source = (
        "--cllm-path"
        if args.cllm_path
        else ("env:CLLM_PATH" if os.getenv("CLLM_PATH") else "auto")
    )
    _log_event(
        verbosity_handler,
        run_id,
        ".cllm path resolved",
        extra={
            "path": str(cllm_path) if cllm_path else "(auto)",
            "source": cllm_path_source,
        },
    )
    if args.conversations_path:
        conversations_source = "--conversations-path"
    elif os.getenv("CLLM_CONVERSATIONS_PATH"):
        conversations_source = "env:CLLM_CONVERSATIONS_PATH"
    elif "conversations_path" in config:
        conversations_source = "config:conversations_path"
    elif args.cllm_path or os.getenv("CLLM_PATH"):
        conversations_source = "cllm_path"
    elif (Path.cwd() / ".cllm").exists():
        conversations_source = "local:.cllm"
    else:
        conversations_source = "home:.cllm"
    _log_event(
        verbosity_handler,
        run_id,
        "Conversation storage resolved",
        extra={
            "path": str(conversation_manager.storage_dir),
            "source": conversations_source,
        },
    )

    # Handle --list-conversations
    if args.list_conversations:
        print_conversation_list(conversation_manager)
        sys.exit(0)

    # Handle --show-conversation
    if args.show_conversation:
        print_conversation(conversation_manager, args.show_conversation)
        sys.exit(0)

    # Handle --delete-conversation
    if args.delete_conversation:
        delete_conversation(conversation_manager, args.delete_conversation)
        sys.exit(0)

    # Validate --read-only requires --conversation (ADR-0018)
    if args.read_only and not args.conversation:
        print("Error: --read-only requires --conversation", file=sys.stderr)
        sys.exit(1)

    # Build template context for variable expansion (ADR-0012)
    cli_vars = parse_variables(args.variables)

    raw_config_vars = config.get("variables")
    if raw_config_vars is None:
        config_vars = {}
    elif isinstance(raw_config_vars, dict):
        config_vars = raw_config_vars
    else:
        print(
            "Error: 'variables' section in configuration must be a mapping of variable names to defaults.",
            file=sys.stderr,
        )
        sys.exit(1)

    if "variables" in config:
        config["variables"] = config_vars

    env_vars = {
        var_name: os.environ[var_name]
        for var_name in config_vars
        if var_name in os.environ
    }

    try:
        template_context = build_template_context(cli_vars, config_vars, env_vars)
    except TemplateError as e:  # noqa: F823
        print(f"Variable error: {e}", file=sys.stderr)
        sys.exit(1)
    _log_minor_event(
        verbosity_handler,
        run_id,
        "Template variables prepared",
        extra={
            "cli_vars": len(cli_vars),
            "config_defaults": len(config_vars),
            "environment_overrides": len(env_vars),
        },
    )

    # Handle --show-config
    if args.show_config:
        sources = get_config_sources(config_name=args.config, cllm_path=args.cllm_path)
        print("Configuration sources (in order of precedence):")
        if sources:
            for source in sources:
                print(f"  - {source}")
        else:
            print("  (no configuration files found)")
        # Show effective .cllm path if custom (ADR-0016)
        if args.cllm_path:
            print(f"\nCustom .cllm path: {args.cllm_path}")
        elif os.getenv("CLLM_PATH"):
            print(f"\nCustom .cllm path (from CLLM_PATH): {os.getenv('CLLM_PATH')}")
        # Show effective conversations path (ADR-0017)
        print(f"\nEffective conversations path: {conversation_manager.storage_dir}")
        if args.conversations_path:
            print("  Source: --conversations-path CLI flag")
        elif os.getenv("CLLM_CONVERSATIONS_PATH"):
            print("  Source: CLLM_CONVERSATIONS_PATH environment variable")
        elif "conversations_path" in config:
            print("  Source: conversations_path in Cllmfile.yml")
        elif args.cllm_path or os.getenv("CLLM_PATH"):
            print("  Source: Custom .cllm path")
        elif (Path.cwd() / ".cllm").exists():
            print("  Source: Local .cllm directory")
        else:
            print("  Source: Global home directory")
        # Show effective system prompt source (ADR-0022)
        if "default_system_message" in config:
            print("\nEffective system prompt:")
            if args.system:
                print("  Source: --system CLI flag")
            elif args.system_file:
                print(f"  Source: --system-file CLI flag ({args.system_file})")
            elif "default_system_message" in file_config:
                print("  Source: default_system_message in Cllmfile.yml")
            else:
                print("  Source: (no system prompt configured)")
            # Show preview of system prompt (first 100 chars)
            preview = config["default_system_message"][:100]
            if len(config["default_system_message"]) > 100:
                preview += "..."
            print(f"  Preview: {preview}")
        else:
            print("\nEffective system prompt: (no system prompt configured)")
        print("\nEffective configuration:")
        print(json.dumps(config, indent=2))
        print("\nResolved variables:")
        if template_context:
            print(json.dumps(template_context, indent=2, sort_keys=True))
        else:
            print("  (no variables defined)")
        sys.exit(0)

    # Handle --list-models
    if args.list_models:
        print_model_list()
        sys.exit(0)

    # Handle --clear-schema-cache
    if args.clear_schema_cache:
        count = clear_schema_cache()
        if count > 0:
            print(f"Cleared {count} cached schema(s)")
        else:
            print("No cached schemas found")
        sys.exit(0)

    # Handle --validate-schema
    if args.validate_schema:
        if schema is None:
            print(
                "Error: No schema provided. Use --json-schema or --json-schema-file",
                file=sys.stderr,
            )
            sys.exit(1)

        print("✓ Schema is valid!")
        print("\nSchema details:")
        print(f"  Type: {schema.get('type', 'not specified')}")

        if schema.get("type") == "object":
            props = schema.get("properties", {})
            print(f"  Properties: {len(props)}")
            if props:
                print("  Fields:")
                for prop_name, prop_schema in props.items():
                    prop_type = prop_schema.get("type", "any")
                    required = (
                        "(required)"
                        if prop_name in schema.get("required", [])
                        else "(optional)"
                    )
                    print(f"    - {prop_name}: {prop_type} {required}")
        elif schema.get("type") == "array":
            items = schema.get("items", {})
            print(f"  Items type: {items.get('type', 'any')}")

        print("\n✓ Schema validation successful")
        sys.exit(0)

    # Read prompt (not needed for --show-config, --list-models, or --validate-schema)
    prompt = read_prompt(args.prompt)
    _log_event(
        verbosity_handler,
        run_id,
        "Prompt captured",
        extra={
            "characters": len(prompt),
            "multiline": "\n" in prompt,
        },
    )

    # Parse context commands (ADR-0011, ADR-0021)
    context_commands = []

    # Parse context_commands from config (if not disabled)
    if not args.no_context_exec:
        try:
            context_commands = parse_context_commands(config)
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)

    # Add CLI --exec commands (these run after config commands)
    if args.context_exec:
        for i, cmd_str in enumerate(args.context_exec):
            # Create ContextCommand from CLI string
            # Use generic naming: "Command 1", "Command 2", etc.
            cli_cmd = ContextCommand(
                name=f"CLI Command {i+1}",
                command=cmd_str,
                on_failure=FailureMode.WARN,  # Default to warn for CLI commands
                timeout=10,
            )
            context_commands.append(cli_cmd)
    _log_minor_event(
        verbosity_handler,
        run_id,
        "Context commands registered",
        extra={"count": len(context_commands), "disabled": args.no_context_exec},
    )

    # ADR-0021: Context will be handled differently for conversation vs stateless mode
    # - Conversation mode: Execute once during creation, store in system message
    # - Stateless mode: Inject into prompt (current behavior)

    # Initialize client
    client = LLMClient()

    # Extract parameters for LLM call
    model = config.get("model", "gpt-3.5-turbo")
    stream = config.get("stream", False)
    raw_response = config.get("raw_response", False)

    # Prepare kwargs for client.complete()
    # Pass through all LiteLLM parameters from config
    kwargs = {
        k: v
        for k, v in config.items()
        if k
        not in [
            "model",
            "stream",
            "raw_response",
            "default_system_message",
            "json_schema",
            "json_schema_file",
            "context_commands",  # ADR-0011: context injection config
            "variables",  # ADR-0012: variable expansion config
            "debug",  # ADR-0009: debug mode config
            "json_logs",  # ADR-0009: JSON logging config
            "log_file",  # ADR-0009: log file config
            "allow_dynamic_commands",  # ADR-0013: dynamic command execution flag
            "dynamic_commands",  # ADR-0013: dynamic command execution config
        ]
    }

    # Handle conversation mode
    conversation: Optional[Conversation] = None
    messages_for_llm = None

    if args.conversation:
        # Load existing conversation or create new one
        try:
            if conversation_manager.exists(args.conversation):
                conversation = conversation_manager.load(args.conversation)
                _log_event(
                    verbosity_handler,
                    run_id,
                    "Conversation loaded",
                    extra={
                        "id": args.conversation,
                        "messages": len(conversation.get_messages()),
                    },
                )
                # Ensure model matches if conversation has a model set
                if conversation.model and conversation.model != model:
                    requested_model = model
                    print(
                        f"Warning: Conversation uses model '{conversation.model}', "
                        f"but you specified '{model}'. Using '{conversation.model}'.",
                        file=sys.stderr,
                    )
                    model = conversation.model
                    _log_event(
                        verbosity_handler,
                        run_id,
                        "Conversation model enforced",
                        extra={
                            "conversation_model": conversation.model,
                            "requested_model": requested_model,
                        },
                    )
            else:
                # ADR-0018: --read-only requires an existing conversation
                if args.read_only:
                    print(
                        f"Error: Conversation '{args.conversation}' not found. "
                        f"--read-only requires an existing conversation.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                # Create new conversation
                # ADR-0020 + ADR-0021: Build combined system message (system prompt + context)
                system_parts = []

                # Part 1: System prompt (if configured)
                if "default_system_message" in config:
                    system_parts.append(config["default_system_message"])

                # Part 2: Context commands (if configured)
                if context_commands:
                    try:
                        # Execute context commands in parallel (ADR-0021)
                        from dataclasses import replace

                        from .context import (
                            execute_commands,
                            format_context_block,
                            format_error_block,
                        )
                        from .templates import TemplateError, render_command_template

                        # Render command templates
                        rendered_commands = []
                        for cmd in context_commands:
                            try:
                                rendered_command = render_command_template(
                                    cmd.command, template_context
                                )
                                rendered_commands.append(
                                    replace(cmd, command=rendered_command)
                                )
                            except TemplateError as err:
                                print(
                                    f"Template error in context command '{cmd.name}': {err}",
                                    file=sys.stderr,
                                )
                                sys.exit(1)

                        # Execute all commands in parallel
                        results = execute_commands(
                            rendered_commands, cwd=Path.cwd(), parallel=True
                        )

                        # Format context blocks
                        context_blocks = []
                        for cmd, result in zip(rendered_commands, results):
                            _log_event(
                                verbosity_handler,
                                run_id,
                                "Context command executed",
                                importance="minor" if result.success else "major",
                                extra={
                                    "name": cmd.name,
                                    "success": result.success,
                                    "on_failure": cmd.on_failure.value,
                                    "has_output": bool(result.output),
                                    "error": result.error_message,
                                    "output_preview": _preview_text(result.output),
                                },
                            )
                            if result.success:
                                context_blocks.append(format_context_block(result))
                            else:
                                # Handle failure according to on_failure setting
                                if cmd.on_failure == FailureMode.FAIL:
                                    print(
                                        f"Context error: Command '{cmd.name}' failed: {result.error_message}",
                                        file=sys.stderr,
                                    )
                                    sys.exit(1)
                                elif cmd.on_failure == FailureMode.WARN:
                                    context_blocks.append(format_error_block(result))
                                # IGNORE: skip this command's output

                        # Add context to system message if any succeeded
                        if context_blocks:
                            context_content = "\n\n".join(context_blocks)
                            system_parts.append(context_content)

                    except RuntimeError as e:
                        print(f"Context error: {e}", file=sys.stderr)
                        sys.exit(1)

                # Combine system prompt and context
                combined_system_message = (
                    "\n\n".join(system_parts) if system_parts else None
                )

                conversation = conversation_manager.create(
                    conversation_id=args.conversation,
                    model=model,
                    system_message=combined_system_message,
                )
                _log_event(
                    verbosity_handler,
                    run_id,
                    "Conversation created",
                    extra={"id": args.conversation, "model": model},
                )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Build messages list with conversation history
        messages_for_llm = conversation.get_messages().copy()

        # ADR-0020 + ADR-0021: System message (with context) should already be in conversation.messages
        # For backward compatibility: if conversation doesn't have system message or context,
        # inject at runtime (but don't save to conversation)
        needs_runtime_injection = False
        runtime_system_parts = []

        # Check if we need to inject system prompt at runtime (backward compat)
        if "default_system_message" in config and not conversation.has_system_message():
            runtime_system_parts.append(config["default_system_message"])
            needs_runtime_injection = True

        # Check if we need to inject context at runtime (backward compat)
        if context_commands and not conversation.has_context_in_system_message():
            try:
                # Execute and inject context at runtime (transient, not saved)
                prompt = inject_context(
                    prompt=prompt,
                    commands=context_commands,
                    cwd=Path.cwd(),
                    parallel=True,
                    template_context=template_context,
                )
                _log_minor_event(
                    verbosity_handler,
                    run_id,
                    "Context commands injected",
                    extra={
                        "count": len(context_commands),
                        "mode": "conversation-runtime",
                    },
                )
            except RuntimeError as e:
                print(f"Context error: {e}", file=sys.stderr)
                sys.exit(1)
            except TemplateError as e:
                print(f"Template error: {e}", file=sys.stderr)
                sys.exit(1)

        # Inject system message at runtime if needed (backward compat for old conversations)
        if needs_runtime_injection:
            combined = "\n\n".join(runtime_system_parts)
            messages_for_llm.insert(0, {"role": "system", "content": combined})

        # Add new user message
        messages_for_llm.append({"role": "user", "content": prompt})

    else:
        # Stateless mode - inject context into prompt (ADR-0021: stateless keeps current behavior)
        if context_commands:
            try:
                prompt = inject_context(
                    prompt=prompt,
                    commands=context_commands,
                    cwd=Path.cwd(),
                    parallel=True,
                    template_context=template_context,
                )
                _log_minor_event(
                    verbosity_handler,
                    run_id,
                    "Context commands injected",
                    extra={"count": len(context_commands), "mode": "stateless"},
                )
            except RuntimeError as e:
                print(f"Context error: {e}", file=sys.stderr)
                sys.exit(1)
            except TemplateError as e:
                print(f"Template error: {e}", file=sys.stderr)
                sys.exit(1)

        # Handle default_system_message if present
        if "default_system_message" in config:
            # Prepend system message to prompt
            system_msg = config["default_system_message"]
            prompt = f"{system_msg}\n\n{prompt}"

        messages_for_llm = prompt

    provider = extract_provider_from_model(model)

    # Add response_format for structured output if schema is present
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "response_schema",
                "schema": schema,
            },
        }

    if raw_response:
        kwargs["raw_response"] = True

    request_parameter_summary = _collect_request_parameters(config, kwargs)
    configured_endpoint = _extract_endpoint_from_kwargs(kwargs)

    # Check if dynamic command execution is enabled (ADR-0013)
    if config.get("allow_dynamic_commands", False):
        # Use agentic execution loop instead of regular LLM call
        try:
            # Dynamic commands don't support streaming or raw response yet
            if stream:
                print(
                    "Warning: Streaming is not supported with --allow-commands. Disabling streaming.",
                    file=sys.stderr,
                )

            if raw_response:
                print(
                    "Warning: Raw response is not supported with --allow-commands.",
                    file=sys.stderr,
                )

            _log_event(
                verbosity_handler,
                run_id,
                "Executing dynamic commands",
                extra={
                    "model": model,
                    "provider": provider,
                    "schema": bool(schema),
                },
            )
            # Execute with dynamic commands (ADR-0014: now supports JSON schema)
            # Track latency for verbose output (ADR-0025)
            start_time = time.time()
            response = execute_with_dynamic_commands(
                prompt=(
                    prompt
                    if messages_for_llm is None or isinstance(messages_for_llm, str)
                    else messages_for_llm[-1]["content"]
                ),
                config=config,
                require_confirmation=config.get("dynamic_commands", {}).get(
                    "require_confirmation", args.confirm_commands
                ),
                verbose=config.get("debug", False),
                schema=schema,  # ADR-0014: Pass schema for structured output
            )
            latency_seconds = time.time() - start_time

            # Print verbose output for dynamic commands (ADR-0025)
            # Note: token counts not available in dynamic command mode
            if verbosity_handler.level > 0:
                verbosity_handler.print_basic_info(
                    model=model,
                    input_tokens=None,  # Not tracked in dynamic command mode
                    output_tokens=None,
                    provider=provider,
                    latency_seconds=latency_seconds,
                )

            print(response)
            _log_event(
                verbosity_handler,
                run_id,
                "Dynamic commands complete",
                extra={"latency_ms": int(latency_seconds * 1000)},
            )

            # Save conversation if in conversation mode (ADR-0018: skip if read-only)
            if conversation is not None and not args.read_only:
                conversation.add_message("user", prompt)
                conversation.add_message("assistant", response)
                # Update token count
                try:
                    tokens = client.count_tokens(model, conversation.get_messages())
                    conversation.total_tokens = tokens
                except Exception:
                    pass  # Token counting is optional
                conversation_manager.save(conversation)
                _log_event(
                    verbosity_handler,
                    run_id,
                    "Conversation updated",
                    extra={
                        "id": conversation.conversation_id,
                        "total_tokens": getattr(conversation, "total_tokens", None),
                    },
                )

        except AgentExecutionError as e:
            verbosity_handler.log_exception(e)
            print(f"Agent error: {e}", file=sys.stderr)
            if log_file_handle:
                log_file_handle.close()
            sys.exit(1)
        except CommandValidationError as e:
            verbosity_handler.log_exception(e)
            print(f"Command validation error: {e}", file=sys.stderr)
            if log_file_handle:
                log_file_handle.close()
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.", file=sys.stderr)
            if log_file_handle:
                log_file_handle.close()
            sys.exit(130)
        finally:
            if log_file_handle:
                log_file_handle.close()
        return

    if verbosity_handler.level >= 3 and messages_for_llm is not None:
        request_payload = {"model": model, "messages": messages_for_llm}
        if kwargs:
            request_payload["params"] = kwargs
        verbosity_handler.log_request_payload(_serialize_for_logging(request_payload))

    _log_event(
        verbosity_handler,
        run_id,
        "Sending LLM request",
        extra={
            "model": model,
            "provider": provider,
            "stream": bool(stream),
            "schema": bool(schema),
            "raw_response": raw_response,
            "conversation": args.conversation is not None,
        },
    )

    try:
        # Make the request
        if stream:
            # Streaming mode - client.complete() now handles display internally (ADR-0010)
            # and returns the complete response
            # Track latency for verbose output (ADR-0025)
            start_time = time.time()
            complete_response, metadata = client.complete_with_metadata(
                model=model, messages=messages_for_llm, stream=True, **kwargs
            )
            latency_seconds = time.time() - start_time

            # Print verbose output (ADR-0025)
            if verbosity_handler.level > 0:
                _log_request_summary(
                    verbosity_handler,
                    model=model,
                    provider=provider,
                    input_tokens=metadata.get("input_tokens"),
                    output_tokens=metadata.get("output_tokens"),
                    latency_seconds=latency_seconds,
                    parameters=(
                        request_parameter_summary if request_parameter_summary else None
                    ),
                    config_sources=config_sources_for_logging,
                    endpoint=configured_endpoint,
                )
            _log_response_payload_if_needed(
                verbosity_handler, metadata, complete_response
            )
            _log_response_metadata(
                verbosity_handler,
                run_id,
                metadata.get("response_object") or complete_response,
            )
            _log_event(
                verbosity_handler,
                run_id,
                "LLM response completed",
                extra={
                    "mode": "stream",
                    "latency_ms": int(latency_seconds * 1000),
                },
            )

            # Validate against schema if present
            if schema is not None:
                try:
                    parsed_response = json.loads(complete_response)
                    validate_against_schema(parsed_response, schema)
                except json.JSONDecodeError as e:
                    print(
                        f"\nWarning: Response is not valid JSON: {e}", file=sys.stderr
                    )
                    sys.exit(1)
                except ConfigurationError as e:
                    print(f"\nValidation error: {e}", file=sys.stderr)
                    sys.exit(1)
                else:
                    _log_minor_event(
                        verbosity_handler,
                        run_id,
                        "Schema validation passed",
                        extra={"mode": "stream"},
                    )

            # Save conversation if in conversation mode (ADR-0018: skip if read-only)
            if conversation is not None and not args.read_only:
                conversation.add_message("user", prompt)
                conversation.add_message("assistant", complete_response)
                # Update token count
                try:
                    tokens = client.count_tokens(model, conversation.get_messages())
                    conversation.total_tokens = tokens
                except Exception:
                    pass  # Token counting is optional
                conversation_manager.save(conversation)
                _log_event(
                    verbosity_handler,
                    run_id,
                    "Conversation updated",
                    extra={
                        "id": conversation.conversation_id,
                        "total_tokens": getattr(conversation, "total_tokens", None),
                    },
                )
        else:
            # Non-streaming mode
            # Track latency for verbose output (ADR-0025)
            start_time = time.time()
            response, metadata = client.complete_with_metadata(
                model=model, messages=messages_for_llm, **kwargs
            )
            latency_seconds = time.time() - start_time

            # Print verbose output (ADR-0025)
            if verbosity_handler.level > 0:
                _log_request_summary(
                    verbosity_handler,
                    model=model,
                    provider=provider,
                    input_tokens=metadata.get("input_tokens"),
                    output_tokens=metadata.get("output_tokens"),
                    latency_seconds=latency_seconds,
                    parameters=(
                        request_parameter_summary if request_parameter_summary else None
                    ),
                    config_sources=config_sources_for_logging,
                    endpoint=configured_endpoint,
                )
            _log_response_payload_if_needed(verbosity_handler, metadata, response)
            _log_response_metadata(
                verbosity_handler, run_id, metadata.get("response_object")
            )
            _log_event(
                verbosity_handler,
                run_id,
                "LLM response completed",
                extra={
                    "mode": "complete",
                    "latency_ms": int(latency_seconds * 1000),
                },
            )

            if raw_response:
                print(json.dumps(response, indent=2))
            else:
                # Validate against schema if present
                if schema is not None:
                    try:
                        parsed_response = json.loads(response)
                        validate_against_schema(parsed_response, schema)
                    except json.JSONDecodeError as e:
                        print(
                            f"Error: Response is not valid JSON: {e}", file=sys.stderr
                        )
                        print(f"Response: {response}", file=sys.stderr)
                        sys.exit(1)
                    except ConfigurationError as e:
                        print(f"Validation error: {e}", file=sys.stderr)
                        print(f"Response: {response}", file=sys.stderr)
                        sys.exit(1)
                    else:
                        _log_minor_event(
                            verbosity_handler,
                            run_id,
                            "Schema validation passed",
                            extra={"mode": "complete"},
                        )

                print(response)

                # Save conversation if in conversation mode (ADR-0018: skip if read-only)
                if conversation is not None and not args.read_only:
                    conversation.add_message("user", prompt)
                    conversation.add_message("assistant", response)
                    # Update token count
                    try:
                        tokens = client.count_tokens(model, conversation.get_messages())
                        conversation.total_tokens = tokens
                    except Exception:
                        pass  # Token counting is optional
                    conversation_manager.save(conversation)
                    _log_event(
                        verbosity_handler,
                        run_id,
                        "Conversation updated",
                        extra={
                            "id": conversation.conversation_id,
                            "total_tokens": getattr(conversation, "total_tokens", None),
                        },
                    )

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.", file=sys.stderr)
        # Close log file if it was opened
        if log_file_handle:
            log_file_handle.close()
        sys.exit(130)
    except Exception as e:
        verbosity_handler.log_exception(e)
        print(f"Error: {e}", file=sys.stderr)
        # Close log file if it was opened
        if log_file_handle:
            log_file_handle.close()
        sys.exit(1)
    finally:
        # Ensure log file is closed
        if log_file_handle:
            log_file_handle.close()


if __name__ == "__main__":
    main()
