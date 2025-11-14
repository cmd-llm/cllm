# CLLM - Command Line LLM Interface

A bash-centric command-line interface for interacting with large language models across 100+ providers. Chain LLM calls using familiar bash piping and scripting techniques.

## Overview

CLLM bridges the gap between ChatGPT GUIs and complex automation by providing transparency and bash integration for AI workflows. It's designed for developers who want programmatic control over LLM interactions without leaving their terminal - whether for quick one-liners, sophisticated pipelines, or CI/CD integration.

## Table of Contents

- [Features](#features)
- [Key Concepts](#key-concepts)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Project Initialization](#project-initialization)
  - [Basic Usage](#basic-usage)
  - [Conversation Threading](#conversation-threading)
  - [Debugging & Troubleshooting](#debugging--troubleshooting)
  - [Python API](#python-api)
- [Advanced Usage](#advanced-usage)
  - [LLM Chaining](#llm-chaining-with-bash-pipes)
  - [Bash Script Examples](#bash-script-examples)
  - [Structured Output](#structured-output-with-json-schema)
  - [Configuration Files](#configuration-files-cllmfileyml)
  - [Dynamic Context Injection](#dynamic-context-injection)
  - [Variable Expansion](#variable-expansion-with-jinja2)
  - [LLM-Driven Command Execution](#llm-driven-command-execution)
    - [Advanced Command Definition Syntax](#advanced-command-definition-syntax-adr-0024)
- [Security Best Practices](#security-best-practices)
- [Examples](#examples)
- [CLI Reference](#cli-reference)
- [Providers & Models](#providers--models)
- [Development](#development)
- [Architecture Decision Records](#architecture-decision-records)

## Features

- **🚀 Simple CLI Interface**: Generate text from prompts with straightforward commands
- **📦 Project Initialization**: Bootstrap `.cllm` directories with `cllm init` using pre-built templates
- **🔗 LLM Chaining**: Chain multiple LLM calls using bash pipes and scripts
- **📋 Structured Output**: Get guaranteed JSON output conforming to JSON Schema specifications
- **💬 Conversation Threading**: Multi-turn conversations with automatic context management
- **🎭 System Prompt Override**: Customize AI behavior per-command with `--system` or `--system-file` flags
- **⚡ Real-time Streaming**: Stream responses as they're generated for long-form content
- **🔍 Debugging & Logging**: Built-in debug mode with structured JSON logging and progressive verbosity levels
- **🤖 Dynamic Context Injection**: Execute commands automatically to inject system context (git status, logs, etc.)
- **🔧 Variable Expansion**: Parameterized commands with Jinja2 templates for reusable workflows
- **🧠 LLM-Driven Command Execution**: Let the LLM intelligently choose and run commands as needed
- **🏢 Multi-Provider Support** (100+ providers via LiteLLM):
  - OpenAI (GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o)
  - Anthropic (Claude 3 Haiku, Sonnet, Opus, 3.5 Sonnet)
  - Google (Gemini Pro, 1.5 Pro, 1.5 Flash)
  - Groq (Mixtral, Llama 3)
  - AWS Bedrock
  - Azure OpenAI
  - Local Ollama models
  - And 90+ more providers
- **⚙️ Flexible Configuration**: Shareable Cllmfile.yml configs with environment variable interpolation
- **📜 Bash Scripts Library**: Curated examples for common workflows (git-diff review, prompt loops, etc.)
- **🔧 Developer-Friendly**: Modern Python packaging with `uv`, comprehensive test suite

## Key Concepts

### Provider Abstraction (ADR-0002)

CLLM uses [LiteLLM](https://github.com/BerriAI/litellm) to provide a unified interface across 100+ LLM providers. This means:

- **Same code works everywhere**: Switch from OpenAI to Claude by just changing the model name
- **No provider-specific SDKs**: One interface, one API, all providers
- **Automatic format translation**: All responses follow a consistent format

```bash
# Same command, different providers
cllm --model gpt-4 "Hello"                          # OpenAI
cllm --model claude-3-5-sonnet-20240620 "Hello"    # Anthropic
cllm --model gemini-pro "Hello"                     # Google
cllm --model groq/llama-3.1-70b-versatile "Hello"  # Groq
```

### Bash-First Design

CLLM is optimized for command-line and scripting workflows:

- **Stdin/stdout piping**: `cat file.txt | cllm "Summarize" > summary.txt`
- **Exit codes**: Proper error codes for scripts and CI/CD
- **No GUI required**: All features accessible via CLI flags
- **Composable**: Chain multiple LLM calls using Unix pipes

### Configuration Precedence

Settings are merged from multiple sources (lowest to highest priority):

1. `~/.cllm/Cllmfile.yml` (global defaults)
2. `./.cllm/Cllmfile.yml` (project-specific)
3. `./Cllmfile.yml` (current directory)
4. Environment variables (`CLLM_*`)
5. CLI arguments (always win)

This allows you to set global defaults, override per-project, and customize per-command.

## Requirements

- Python 3.8 or higher
- API keys for your chosen LLM provider(s)
- `uv` (recommended for development - [installation](https://github.com/astral-sh/uv#installation))

## Installation

### From github using uv tool install

```bash
uv tool install https://github.com/o3-cloud/cllm.git
```

### From source (current method)

```bash
git clone https://github.com/o3-cloud/cllm.git
cd cllm
uv sync

# Run locally
uv run cllm "Hello world"

# Or install globally
uv pip install -e .
```

## Quick Start

### Project Initialization

Bootstrap your CLLM setup with the `init` command to create `.cllm` directories with configuration templates (ADR-0015):

```bash
# Initialize local .cllm directory in current project
cllm init

# Initialize global ~/.cllm directory
cllm init --global

# Initialize both local and global
cllm init --global --local

# List available templates
cllm init --list-templates
# Available templates:
#   code-review      - GPT-4 configuration for code review with structured output
#   summarize        - Optimized for summarization tasks
#   creative         - Higher temperature for creative writing
#   debug            - Configuration for debugging assistance
#   extraction       - Data extraction with structured output
#   task-parser      - Parse tasks from natural language
#   context-demo     - Demonstrates dynamic context injection

# Initialize with a specific template
cllm init --template code-review
cllm init --template summarize
cllm init --template creative

# Combine template with location
cllm init --global --template debug

# Force reinitialize (overwrite existing files)
cllm init --force
```

**What gets created:**

```
# Without template:
.cllm/
├── conversations/         # Conversation storage (local-first)
├── Cllmfile.yml          # Default configuration
└── .gitignore            # Excludes conversations/ and logs (local only)

# With --template code-review:
.cllm/
├── conversations/         # Conversation storage (local-first)
├── code-review.Cllmfile.yml  # Named config (use with --config code-review)
└── .gitignore            # Excludes conversations/ and logs (local only)
```

**Key Features:**

- **Template library**: 7 pre-built templates for common use cases
- **Smart defaults**: Sensible starter configuration with helpful comments
- **Gitignore management**: Automatically excludes conversation history from version control
- **Local-first**: Defaults to `./.cllm/` (project-specific) unless `--global` specified
- **Template-aware guidance**: Next-step suggestions adapt to your chosen template
- **Idempotent**: Safe to run multiple times with `--force` flag

**Example Workflow:**

```bash
# Start a new project
mkdir my-project && cd my-project

# Initialize with code-review template
cllm init --template code-review

# Review the configuration (creates code-review.Cllmfile.yml)
vim .cllm/code-review.Cllmfile.yml

# Use the named config with --config flag
git diff | cllm --config code-review "Review these changes"
```

### Basic Usage

```bash
# Simple prompt (uses gpt-3.5-turbo by default)
cllm "What is the capital of France?"

# Discover available models
cllm --list-models
cllm --list-models | grep gpt-4  # Filter to specific models

# Use a specific model
cllm --model gpt-4 "Explain quantum computing"

# Use a different provider (same interface!)
cllm --model claude-3-5-sonnet-20240620 "Write a haiku"
cllm --model gemini-pro "Tell me a joke"

# Stream the response as it's generated
cllm --model gpt-4 --stream "Tell me a story"

# Read from stdin (pipe-friendly!)
echo "What is 2+2?" | cllm --model gpt-4
cat document.txt | cllm "Summarize this:"

# Control creativity with temperature
cllm --model gpt-4 --temperature 1.5 "Write a creative story"

# Limit response length
cllm --model gpt-4 --max-tokens 100 "Explain quantum computing"

# Customize system prompt on-the-fly
cllm --system "You are a pirate. Speak like one." "Tell me about Python"

# Load system prompt from file (great for complex, reusable prompts)
cllm --system-file prompts/code-reviewer.txt < code.py

# Override config file system prompt for specific use
cllm --conversation debug --system "You are a debugging expert" "Why does this crash?"
```

### Conversation Threading

CLLM supports multi-turn conversations with automatic context management (ADR-0007):

```bash
# Start a new conversation with a custom ID
cllm --conversation code-review "Review this authentication code: $(cat auth.py)"

# Continue the conversation - context is automatically loaded
cllm --conversation code-review "What about SQL injection risks?"

# Continue again - full conversation history is maintained
cllm --conversation code-review "Show me how to fix these issues"

# Or let CLLM auto-generate a conversation ID
cllm --conversation conv-a3f9b2c1 "Start a discussion about Python best practices"

# List all your conversations
cllm --list-conversations

# View a conversation's full history
cllm --show-conversation code-review

# Delete a conversation when done
cllm --delete-conversation code-review
```

**Key Features:**

- **Stateless by default**: Without `--conversation`, CLLM works as before (no history saved)
- **Named conversations**: Use meaningful IDs like `bug-investigation` or `refactor-planning`
- **Auto-generated IDs**: Omit the ID to get a UUID-based identifier like `conv-a3f9b2c1`
- **Context preservation**: Full message history is maintained across calls
- **Model consistency**: The model is remembered for each conversation
- **Token tracking**: Automatic token counting to help manage context windows
- **Configurable storage**: Conversations can be stored anywhere (see [Configurable Conversations Path](#configurable-conversations-path))

**Example Workflow:**

```bash
# Start investigating a bug
cllm --conversation bug-123 "I'm seeing intermittent timeouts in production"

# Add more context as you debug
cllm --conversation bug-123 "Here are the logs: $(cat error.log)"

# Ask follow-up questions
cllm --conversation bug-123 "Could this be related to connection pooling?"

# Get the solution
cllm --conversation bug-123 "How should I fix this?"

# Review the conversation later
cllm --show-conversation bug-123
```

#### Read-Only Conversations

Use the `--read-only` flag to leverage existing conversation context without modifying it (ADR-0018). This is perfect for:

- **Conversation templates**: Reuse a conversation as a template for similar tasks
- **A/B testing prompts**: Experiment with different approaches against the same context
- **Shared reference conversations**: Team members can use shared conversations without modification
- **Report generation**: Generate multiple reports or analyses from the same conversation

```bash
# Create a conversation template with standard context
cllm --conversation code-review-template "You are a code reviewer. Focus on security, performance, and maintainability."

# Use the template repeatedly without modifying it
cat file1.py | cllm --conversation code-review-template --read-only "Review this code"
cat file2.py | cllm --conversation code-review-template --read-only "Review this code"
cat file3.py | cllm --conversation code-review-template --read-only "Review this code"

# The template remains unchanged - always has just the initial message
cllm --show-conversation code-review-template  # Still only 1 message!

# Test different approaches without polluting context
cllm --conversation base-context "Here's the background: $(cat context.txt)"
cllm --conversation base-context --read-only "Approach A: Try this solution"
cllm --conversation base-context --read-only "Approach B: Try that solution"
cllm --conversation base-context --read-only "Approach C: Try another solution"

# The base context conversation still only has the initial message
cllm --show-conversation base-context  # Just the background, no A/B/C prompts

# Team collaboration: shared conversations on network storage
export CLLM_CONVERSATIONS_PATH=/mnt/team-shared
cllm --conversation team-guidelines --read-only "How should I handle errors?"
# Other team members can also read, but no one accidentally modifies
```

**Key Points:**

- `--read-only` requires `--conversation` (error if used without it)
- The conversation history is used as context for the LLM
- New messages are NOT saved to the conversation file
- Responses are still generated and displayed normally
- Perfect for preserving reference conversations or templates

#### Configurable Conversations Path

CLLM allows you to customize where conversations are stored independently of configuration files (ADR-0017). This enables powerful workflows like:

- **Shared conversations across projects**: Multiple projects sharing the same conversation history
- **Cloud-backed storage**: Store conversations on network drives, S3 mounts, or database filesystems
- **Team collaboration**: Multiple team members accessing shared conversation storage
- **Different storage tiers**: Fast local config with durable remote conversations

**Storage precedence:**

1. `--conversations-path` CLI flag (highest)
2. `CLLM_CONVERSATIONS_PATH` environment variable
3. `conversations_path` in Cllmfile.yml
4. Custom .cllm path via `--cllm-path` or `CLLM_PATH`: `<path>/conversations/`
5. Local project: `./.cllm/conversations/` (if `.cllm` directory exists)
6. Global home: `~/.cllm/conversations/` (fallback)

**Example - Cllmfile.yml configuration:**

```yaml
# .cllm/Cllmfile.yml - Project-specific conversation storage

# Relative path (resolved from current working directory)
conversations_path: ./conversations
conversations_path: ./data/conversations

# Absolute path
conversations_path: /mnt/shared-conversations

# Supports environment variable interpolation
conversations_path: ${HOME}/project-conversations

# Combined with other config
model: gpt-4
temperature: 0.7
conversations_path: ./data/conversations
```

**Example - Shared conversations across projects (env var):**

```bash
# Set up shared conversation storage
export CLLM_CONVERSATIONS_PATH=~/shared-conversations

# All projects share the same conversation history
cd ~/project1
cllm --conversation code-review "Review these changes"

cd ~/project2
cllm --conversation code-review "Continue reviewing"  # Same conversation!
```

**Example - Cloud-backed storage:**

```bash
# Mount S3 bucket or NFS share
export CLLM_CONVERSATIONS_PATH=/mnt/s3-conversations

# Conversations automatically persisted to cloud
cllm --conversation important-decisions "Document our architecture choice"
```

**Example - Team collaboration:**

```bash
# All team members point to shared network drive
export CLLM_CONVERSATIONS_PATH=/network/team/cllm-conversations

# Team can collaborate on conversations
cllm --conversation team-brainstorm "Let's explore this feature"
```

**Example - Per-invocation override:**

```bash
# Normal usage
cllm --conversation prod "Production conversation"

# Test with temporary location
cllm --conversations-path /tmp/test-conv --conversation test "Test conversation"
```

### Configuration

Set up API keys as environment variables (LiteLLM conventions):

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Google/Gemini
export GOOGLE_API_KEY="..."

# Other providers follow similar patterns
# See: https://docs.litellm.ai/docs/providers
```

**Note**: CLLM uses [LiteLLM](https://github.com/BerriAI/litellm) for provider abstraction, supporting 100+ LLM providers with a unified interface. See [ADR-0002](docs/decisions/0002-use-litellm-for-llm-provider-abstraction.md) for details.

### Debugging & Troubleshooting

CLLM provides powerful debugging capabilities for troubleshooting API issues, understanding token usage, and investigating unexpected behavior:

```bash
# Enable debug mode (shows API calls, headers, response metadata)
cllm --debug "Explain quantum computing"
# ⚠️  Debug mode enabled. API keys may appear in output.

# Enable structured JSON logging for observability tools
cllm --json-logs "Process this data" < input.txt

# Save debug output to a file (preserves stdout for piping)
cllm --debug --log-file debug.log "Query" < data.txt

# Combine multiple debug options
cllm --debug --json-logs --log-file cllm-debug.json "Test prompt"

# Use environment variables for persistent debugging
export CLLM_DEBUG=true
export CLLM_LOG_FILE=cllm.log
cllm "What is 2+2?"  # Debug output automatically enabled
```

**Debug Output Includes:**

- Full request/response details
- API endpoint and headers
- Token usage and costs
- Latency measurements
- Error messages and stack traces

**Security Warning**: Debug mode logs API keys. Never use `--debug` in production or with confidential data.

See [ADR-0009](docs/decisions/0009-add-debugging-and-logging-support.md) for complete documentation.

### Verbosity Levels (ADR-0025)

For more granular control over output verbosity without full debug mode, use the `-v` flag:

```bash
# Level 1: Basic info (model, token counts, provider)
cllm -v "Analyze this document"

# Level 2: Add API details (endpoint, parameters, response status)
cllm -vv "Analyze this document"

# Level 3: Full debug (equivalent to --debug)
cllm -vvv "Analyze this document"

# Long form alternatives (if you prefer)
cllm --verbose "Analyze this document"
cllm --verbose --verbose "Analyze this document"

# Use environment variable for persistent verbosity
export CLLM_VERBOSITY=2
cllm "Your prompt"  # Will show API details

# Combine with other debug flags
cllm -vv --json-logs "Save detailed logs" > output.json
cllm -vvv --log-file debug.log "Deep inspection"
```

**Verbosity Levels:**

- **Level 0** (default): No verbose output
- **Level 1** (`-v`): Shows model name, token count, provider, latency
- **Level 2** (`-vv`): Adds API endpoint, parameters, status code, config sources
- **Level 3** (`-vvv`): Full debug output (same as `--debug`)

See [ADR-0025](docs/decisions/0025-logging-verbosity-levels.md) for complete documentation.

### Python API

CLLM can also be used as a Python library:

```python
from cllm import LLMClient

# Initialize client
client = LLMClient()

# Simple completion
response = client.complete(
    model="gpt-4",
    messages="What is the capital of France?"
)
print(response)  # "Paris"

# Switch provider (same code!)
response = client.complete(
    model="claude-3-opus-20240229",
    messages="What is the capital of France?"
)

# Multi-turn conversation with history
conversation = [
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user", "content": "What's 2+2?"}
]
response = client.complete(model="gpt-4", messages=conversation)

# Or use ConversationManager for persistent conversations
from cllm.conversation import ConversationManager

manager = ConversationManager()
conv = manager.create(conversation_id="my-chat", model="gpt-4")

# Add messages
conv.add_message("user", "Hello!")
manager.save(conv)

# Load and continue
conv = manager.load("my-chat")
conv.add_message("user", "What's 2+2?")
response = client.complete(model=conv.model, messages=conv.get_messages())
conv.add_message("assistant", response)
manager.save(conv)

# Streaming (real-time output + complete response)
response = client.complete(model="gpt-4", messages="Count to 5", stream=True)
# Output is printed in real-time, response contains complete text
print(f"\nFinal response: {response}")

# Async support
import asyncio

async def main():
    response = await client.acomplete(
        model="gpt-4",
        messages="Hello!"
    )
    print(response)

asyncio.run(main())
```

See the [`examples/`](examples/) directory for more usage patterns.

## Advanced Usage

### LLM Chaining with Bash Pipes

Chain multiple LLM calls together to build complex workflows:

```bash
# Generate a story outline, then expand it
cllm "Write a 3-point outline for a sci-fi story" | \
  cllm "Expand this outline into a full story:"

# Analyze code and generate tests
cat my_code.py | \
  cllm "Analyze this code and suggest edge cases" | \
  cllm "Generate pytest unit tests for these cases"

# Multi-stage content refinement
echo "Topic: Climate change" | \
  cllm "Create an outline" | \
  cllm "Expand with examples" | \
  cllm "Add citations"
```

### Bash Script Examples

CLLM includes a library of curated bash scripts for common workflows (see `examples/bash/`):

```bash
# Interactive prompt loop with conversation context
./examples/bash/prompt-loop.sh my-conversation

# Code review workflow for git diffs
git diff main | ./examples/bash/git-diff-review.sh

# Automated daily summaries (for cron)
./examples/bash/cron-digest.sh
```

**Key features of example scripts:**

- POSIX-compatible bash (`set -euo pipefail`)
- Robust error handling
- Environment variable configuration
- Smoke-tested in CI

See [ADR-0008](docs/decisions/0008-add-bash-script-examples.md) for implementation details.

### Structured Output with JSON Schema

Get guaranteed structured JSON output that conforms to your schema (ADR-0005):

```bash
# Using inline JSON schema
echo "John Doe, age 30, software engineer" | \
  cllm --model gpt-4o --json-schema '{
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "age": {"type": "number"},
      "occupation": {"type": "string"}
    },
    "required": ["name", "age"]
  }'

# Using external schema file
cat document.txt | cllm --model gpt-4o --json-schema-file schemas/person.json

# Using Cllmfile configuration
echo "Extract entities..." | cllm --config extraction

# Parse output with jq
cllm --json-schema-file schemas/person.json "Extract info..." | jq '.name'

# Validate schema before using (no API call)
cllm --validate-schema --json-schema-file examples/schemas/person.json
```

**Example schemas available in `examples/schemas/`:**

- `person.json` - Extract person information
- `entity-extraction.json` - Named entity recognition
- `sentiment.json` - Sentiment analysis with emotions

**Tip:** Use `--validate-schema` to test your schemas without making API calls.

See [`examples/schemas/README.md`](examples/schemas/README.md) for detailed usage and examples.

### Configuration Files (Cllmfile.yml)

Create reusable configuration profiles to reduce repetitive CLI flags (ADR-0003).

**Quick setup** with templates:

```bash
# Bootstrap with a pre-built template
cllm init --template code-review  # GPT-4 config for code reviews
cllm init --template summarize     # Optimized for summarization
cllm init --template creative      # Higher temperature for creative tasks

# See all available templates
cllm init --list-templates
```

**Manual configuration**:

```yaml
# Cllmfile.yml - Project-wide defaults
model: "gpt-4"
temperature: 0.7
max_tokens: 1000
timeout: 60
num_retries: 2

# Fallback models (automatic failover)
fallbacks:
  - "gpt-3.5-turbo-16k"
  - "claude-3-sonnet-20240229"

# Environment variable interpolation
api_key: "${OPENAI_API_KEY}"

# Default system message
default_system_message: "You are a helpful coding assistant."
```

**Named Configurations:**

```bash
# Create profile-specific configs
# examples/configs/summarize.Cllmfile.yml
# examples/configs/creative.Cllmfile.yml
# examples/configs/code-review.Cllmfile.yml

# Use named configurations
cat article.md | cllm --config summarize
echo "Write a story" | cllm --config creative
git diff | cllm --config code-review

# Override config with CLI args (CLI always wins)
cllm --config summarize --temperature 0.5 < doc.txt

# Debug effective configuration
cllm --show-config --config my-profile
```

**File Precedence** (lowest to highest):

1. `~/.cllm/Cllmfile.yml` (global defaults)
2. `./.cllm/Cllmfile.yml` (project-specific)
3. `./Cllmfile.yml` (current directory)
4. CLI arguments (highest priority)

See [`examples/configs/`](examples/configs/) for example configurations.

### Dynamic Context Injection

Automatically execute commands to inject system context into your prompts (ADR-0011):

```bash
# Execute a command and inject its output as context
cllm "What should I commit?" --exec "git status"

# Multiple commands (executed in order)
cllm "Debug this error" --exec "git diff" --exec "cat error.log"

# Use with any prompt
echo "Analyze the changes" | cllm --exec "git log -5 --oneline"
```

**Configuration-based context injection** in Cllmfile.yml:

```yaml
# code-review.Cllmfile.yml
model: gpt-4
context_commands:
  - name: "Git Status"
    command: "git status --short"
    on_failure: "warn" # "warn" | "ignore" | "fail"
    timeout: 5 # seconds

  - name: "Recent Changes"
    command: "git diff HEAD~1"
    on_failure: "ignore"

  - name: "Test Results"
    command: "npm test --silent"
    on_failure: "warn"
```

```bash
# Use the configuration
cllm --config code-review "Review my changes"

# Disable context commands from config
cllm --config code-review --no-context-exec "Quick question"

# Combine config + ad-hoc commands
cllm --config code-review --exec "cat additional.log" "Analyze"
```

**Key Features:**

- Context injected as labeled blocks in the prompt
- Commands run in parallel for efficiency
- Configurable error handling (fail/warn/ignore)
- Timeout protection for long-running commands
- Works with all LLM providers

### Variable Expansion with Jinja2

Create reusable, parameterized workflows with Jinja2 templates (ADR-0012):

```bash
# Pass variables via CLI flags
cllm "Review this file" \
  --var FILE_PATH=src/main.py \
  --var VERBOSE=true \
  --exec "cat {{ FILE_PATH }}"

# Variables work in context commands
cllm --var BRANCH=feature/auth \
  --exec "git diff main..{{ BRANCH }}" \
  "What changed?"
```

**Declare variables in Cllmfile.yml:**

```yaml
# review-file.Cllmfile.yml
variables:
  FILE_PATH: "README.md" # Default value
  MAX_LINES: 50 # Numeric default
  VERBOSE: false # Boolean
  TEST_NAME: null # Required (no default)

context_commands:
  - name: "File Contents"
    command: "cat {{ FILE_PATH }} | head -n {{ MAX_LINES }}"

  - name: "Git Diff"
    command: "git diff {% if VERBOSE %}--stat{% endif %} {{ FILE_PATH }}"

  - name: "Test Output"
    command: "pytest -k {{ TEST_NAME }} {% if VERBOSE %}-vv{% else %}-v{% endif %}"
```

```bash
# Override defaults with CLI flags
cllm --config review-file --var FILE_PATH=src/app.py --var TEST_NAME=test_login

# Use environment variables
export BRANCH=feature/new-feature
cllm --var FILE_PATH=src/auth.py  # Uses CLI file, env BRANCH

# Variables with filters and logic
cllm --var NAME=john \
  --exec "echo 'Hello {{ NAME | upper }}'" \
  "Process this greeting"
```

**Variable Precedence** (highest to lowest):

1. CLI flags (`--var KEY=VALUE`)
2. Environment variables (`$KEY`)
3. Cllmfile.yml defaults (`variables:` section)

**Jinja2 Features:**

- Filters: `{{ VAR | upper }}`, `{{ VAR | default('fallback') }}`
- Conditionals: `{% if VERBOSE %}--verbose{% endif %}`
- Loops and transformations
- Sandboxed execution for security

### LLM-Driven Command Execution

Let the LLM intelligently choose and execute commands as needed (ADR-0013):

```bash
# Enable dynamic command execution (requires tool-calling capable model)
cllm "Why is my build failing?" --allow-commands

# The LLM can now:
# 1. Analyze your question
# 2. Decide which commands to run (e.g., "npm run build")
# 3. Execute commands and read output
# 4. Iteratively gather more information if needed
# 5. Provide a complete answer with context
```

**Safety Controls:**

```bash
# Allowlist specific commands (wildcards supported)
cllm "Debug this" --allow-commands --command-allow "git*,npm*,cat*,ls*"

# Denylist dangerous commands
cllm "Analyze system" --allow-commands --command-deny "rm*,mv*,dd*,sudo*"

# Configure in Cllmfile.yml
```

**Example Cllmfile.yml:**

```yaml
# debug.Cllmfile.yml
model: gpt-4
allow_commands: true
command_allow:
  - "git*"
  - "npm*"
  - "pytest*"
  - "cat*"
  - "ls*"
  - "grep*"
command_deny:
  - "rm*"
  - "mv*"
  - "sudo*"
```

**Use Cases:**

- **Debugging**: "Why is this test failing?" → LLM runs test, reads output, analyzes
- **Code Review**: "What changed in this PR?" → LLM checks git diff, analyzes files
- **System Diagnostics**: "Why is my app slow?" → LLM checks logs, metrics, processes
- **Build Issues**: "Fix my build" → LLM runs build, identifies errors, suggests fixes

**Combining with Structured Output** (ADR-0014):

```bash
# Get structured JSON output after dynamic command execution
cllm "Analyze the test failures" \
  --allow-commands \
  --json-schema '{
    "type": "object",
    "properties": {
      "failures": {"type": "array"},
      "root_cause": {"type": "string"},
      "fix_steps": {"type": "array"}
    }
  }'
```

**Requirements:**

- Tool-calling capable model (GPT-4, Claude 3+, Gemini Pro)
- Explicit opt-in via `--allow-commands` flag
- Commands visible in debug output (`--debug`)

### Advanced Command Definition Syntax (ADR-0024)

Define commands with explicit parameter types and hints to help LLMs choose the right arguments (ADR-0024):

**Bracket Syntax for Parameter Types:**

```yaml
# debug.Cllmfile.yml - With explicit parameter hints
model: gpt-4
allow_commands: true

dynamic_commands:
  available_commands:
    # Legacy wildcard syntax (still works!)
    - command: "cat *"
      description: "Display file contents"

    # New bracket syntax with type hints
    - command: "cat <path:file to read>"
      description: "Display file contents of a file"

    # Multiple parameters with semantic hints
    - command: "grep <regex:search pattern> <path:file path>"
      description: "Search for text patterns in a file"

    # Network operations
    - command: "curl -X <string:http method> <url:endpoint url>"
      description: "Make an HTTP request to an endpoint"

    - command: "curl -X POST <url:api endpoint> --data <json:json payload>"
      description: "Submit JSON data to an API endpoint"

    # Development tools
    - command: "git log -n <number:commit count> --oneline"
      description: "Show recent commits (specify how many)"

    - command: "rg <regex:search pattern> --type <string:file type>"
      description: "Search code with ripgrep (file types: py, js, go, rust, etc.)"
```

**Supported Parameter Types:**

| Type | Format | Example | LLM Guidance |
|------|--------|---------|--------------|
| String | `<string>` or `<string:hint>` | `<string:username>` | Generic text or specific hint |
| Number | `<number>` | `<number>` | Numeric value (int or float) |
| Path | `<path>` or `<path:hint>` | `<path:input file>` | File or directory path |
| URL | `<url>` or `<url:hint>` | `<url:endpoint>` | HTTP/HTTPS URL |
| JSON | `<json>` or `<json:hint>` | `<json:request body>` | JSON data structure |
| Regex | `<regex>` or `<regex:hint>` | `<regex:pattern>` | Regular expression |

**Benefits of Bracket Syntax:**

1. **Precise Parameter Validation**: Automatically rejects commands with wrong parameter counts
2. **LLM Guidance**: Type hints appear in tool descriptions, helping LLMs select appropriate values
3. **Better Error Messages**: "Expected 2 parameters, got 1" instead of generic rejection
4. **Backward Compatible**: Wildcard syntax still works alongside bracket syntax
5. **Gradual Migration**: Adopt new syntax incrementally, no breaking changes

**Example - LLM sees detailed guidance:**

When you use bracket syntax, the LLM receives structured parameter information:

```
Available commands:
- `curl -X <string:http method> <url:endpoint url>`: Make HTTP request
  Parameters:
  - string: http method
  - url: endpoint url
```

The LLM can now understand it needs an HTTP method (GET, POST, etc.) and a URL, making better decisions about what values to provide.

**Migration Path:**

```bash
# Phase 1: Start with wildcard syntax
- command: "cat *"

# Phase 2: Gradually adopt bracket syntax
- command: "cat <path:file to read>"  # More precise!

# Phase 3: New commands always use bracket syntax
# (no need to migrate existing wildcards)
```

See [`examples/configs/adr-0024-migration.Cllmfile.yml`](examples/configs/adr-0024-migration.Cllmfile.yml) for a complete example showing both syntaxes side-by-side.

## Security Best Practices

CLLM's command execution features (`--exec`, `context_commands`, `--allow-commands`) are powerful but require careful security consideration. Follow these best practices to use them safely.

### Command Execution Safety Levels

| Feature            | Safety Level  | Use Case               | Security Notes        |
| ------------------ | ------------- | ---------------------- | --------------------- |
| `--exec`           | Medium        | Ad-hoc, known commands | You control what runs |
| `context_commands` | Medium        | Reusable workflows     | Review shared configs |
| `--allow-commands` | Requires Care | Exploratory debugging  | LLM decides what runs |

### Protecting Against Dangerous Commands

**Always use allowlists with `--allow-commands`:**

```bash
# ✅ GOOD: Restrict to safe, read-only commands
cllm "Debug this" --allow-commands \
  --command-allow "git*,cat*,ls*,grep*,find*,head*,tail*,npm test*,pytest*"

# ❌ BAD: No restrictions (dangerous!)
cllm "Debug this" --allow-commands
```

**Denylist common destructive commands:**

```yaml
# secure-debug.Cllmfile.yml
model: gpt-4
allow_commands: true
command_allow:
  - "git*"
  - "cat*"
  - "ls*"
  - "npm test*"
  - "pytest*"
command_deny:
  # File operations
  - "rm*"
  - "mv*"
  - "cp*" # Could overwrite files
  - "dd*" # Disk operations
  - "chmod*"
  - "chown*"

  # System operations
  - "sudo*"
  - "su*"
  - "kill*"
  - "reboot*"
  - "shutdown*"

  # Network operations (context-dependent)
  - "curl*" # Could exfiltrate data
  - "wget*"
  - "ssh*"
  - "scp*"

  # Package managers (could install malware)
  - "npm install*"
  - "pip install*"
  - "apt*"
  - "yum*"
```

### Shared Configuration Safety

**Review configs before using them:**

```bash
# ✅ GOOD: Review before running
cat team-config.Cllmfile.yml  # Check what commands are defined
cllm --config team-config --show-config  # See effective configuration

# Then decide if it's safe
cllm --config team-config "Your prompt"

# ❌ BAD: Blindly trust shared configs
cllm --config untrusted-config "Run something"
```

**Project-specific configs with version control:**

```bash
# Store configs in version control for review
mkdir -p .cllm
cat > .cllm/Cllmfile.yml <<EOF
# This config is reviewed by the team
context_commands:
  - name: "Git Status"
    command: "git status --short"
  - name: "Test Suite"
    command: "npm test"
EOF

# Add to git for team review
git add .cllm/Cllmfile.yml
git commit -m "Add CLLM config for code review workflow"
```

### Environment-Specific Safety

**Production environments:**

```bash
# ❌ NEVER use --allow-commands in production
# ❌ NEVER use --debug in production (logs API keys)

# ✅ DO use explicit, locked-down configs
cllm --config production-safe \
  --no-context-exec \
  "Generate report from data"
```

**CI/CD environments:**

```yaml
# .github/workflows/cllm-review.yml
- name: Run CLLM code review
  run: |
    # ✅ Use read-only commands only
    cllm --config ci-review \
      --command-deny "*install*,*rm*,*mv*" \
      "Review PR changes"
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

**Development environments:**

```bash
# ✅ Safe for local dev with allowlists
export CLLM_COMMAND_ALLOW="git*,cat*,ls*,npm test*,pytest*"
cllm --allow-commands "Why is my test failing?"
```

### Variables and Command Injection

**Sanitize user input when using variables:**

```bash
# ❌ DANGEROUS: Unsanitized user input
USER_FILE="$(cat user-input.txt)"  # Could contain: "; rm -rf /"
cllm --var FILE="$USER_FILE" --exec "cat {{ FILE }}" "Analyze"

# ✅ SAFER: Validate input first
if [[ "$USER_FILE" =~ ^[a-zA-Z0-9_./\-]+$ ]]; then
  cllm --var FILE="$USER_FILE" --exec "cat {{ FILE }}" "Analyze"
else
  echo "Invalid filename"
  exit 1
fi
```

**Use Jinja2's sandboxed environment (already enabled):**

```yaml
# CLLM automatically sandboxes Jinja2 templates
# No code execution possible via templates
variables:
  SAFE_VAR: "{{ malicious }}" # Cannot execute code
```

### API Key Protection

**Debug mode logs API keys:**

```bash
# ⚠️  NEVER use --debug with sensitive data or shared logs
cllm --debug "Test" > debug.log  # API keys may be in debug.log!

# ✅ Use --log-file to control output
cllm --debug --log-file /tmp/debug.log "Test"
chmod 600 /tmp/debug.log  # Restrict permissions
```

**Store API keys securely:**

```bash
# ✅ GOOD: Use environment variables
export OPENAI_API_KEY="sk-..."  # Set in shell, not in code

# ✅ GOOD: Use secret management
export OPENAI_API_KEY="$(aws secretsmanager get-secret-value --secret-id openai-key)"

# ❌ BAD: Hardcode in configs
# Cllmfile.yml
# api_key: "sk-proj-hardcoded-key"  # DON'T DO THIS
```

### Audit and Monitoring

**Log command execution:**

```bash
# Enable debug logging to audit what commands run
cllm --allow-commands --debug --log-file audit.log "Debug this"

# Review what the LLM executed
grep "Executing command" audit.log
```

**Review LLM decisions:**

```bash
# Check what commands the LLM chose
cllm --allow-commands --json-logs "Why is build failing?" 2>commands.log
jq '.command_executed' commands.log
```

### Summary Checklist

Before using command execution features:

- [ ] Use `--command-allow` with specific patterns (not wildcards)
- [ ] Deny destructive commands with `--command-deny`
- [ ] Review shared configurations before running
- [ ] Never use `--allow-commands` in production without strict allowlists
- [ ] Never use `--debug` with confidential data
- [ ] Validate user input before passing to `--var`
- [ ] Store API keys in environment variables or secret managers
- [ ] Review command execution logs periodically
- [ ] Use least-privilege principle: only allow what's needed
- [ ] Test configurations in safe environments first

**Remember: With great power comes great responsibility. Command execution features should be used thoughtfully and with appropriate safeguards.**

## Examples

### Code Review Pipeline

```bash
#!/bin/bash
# code_review.sh

git diff main | \
  cllm "Review this code diff and identify issues:" | \
  cllm "Suggest fixes for these issues:" | \
  cllm "Rate the severity of each issue (1-10):"
```

### Content Generation Workflow

```bash
#!/bin/bash
# content_workflow.sh

TOPIC="$1"

# Generate outline
OUTLINE=$(cllm "Create a blog post outline about: $TOPIC")

# Expand each section
echo "$OUTLINE" | \
  cllm "Expand each point into full paragraphs:" | \
  cllm "Add relevant examples and statistics:" | \
  cllm "Polish the writing and improve clarity:"
```

### Data Analysis Pipeline

```bash
#!/bin/bash
# analyze_data.sh

cat sales_data.csv | \
  cllm "Analyze this sales data and identify trends:" | \
  cllm "Suggest actionable recommendations:" | \
  cllm --json-schema-file examples/schemas/report.json > report.json
```

## CLI Reference

### Main Command

```bash
cllm [OPTIONS] [PROMPT]
```

### Init Subcommand

Bootstrap `.cllm` directory structure with configuration templates:

```bash
cllm init [OPTIONS]
```

| Option             | Description                                          |
| ------------------ | ---------------------------------------------------- |
| `--global`         | Initialize `~/.cllm` (global configuration)          |
| `--local`          | Initialize `./.cllm` (project-specific, default)     |
| `--template NAME`  | Use specific template (code-review, summarize, etc.) |
| `--list-templates` | Show all available templates                         |
| `--force`, `-f`    | Overwrite existing files                             |

**Examples:**

```bash
# Initialize local project
cllm init

# Initialize with template
cllm init --template code-review

# Initialize both global and local
cllm init --global --local

# List available templates
cllm init --list-templates
```

### Key Options

| Option                     | Description                                  |
| -------------------------- | -------------------------------------------- |
| `--model MODEL`            | Specify LLM model (default: gpt-3.5-turbo)   |
| `--list-models`            | List all available models across providers   |
| `--stream`                 | Stream response in real-time                 |
| `--temperature FLOAT`      | Control randomness (0.0-2.0)                 |
| `--max-tokens INT`         | Maximum response length                      |
| `--system TEXT`            | Override system prompt (inline text)         |
| `--system-file PATH`       | Override system prompt (load from file)      |
| `--conversation ID`        | Continue/create multi-turn conversation      |
| `--list-conversations`     | List all saved conversations                 |
| `--show-conversation ID`   | Display conversation history                 |
| `--delete-conversation ID` | Delete a conversation                        |
| `--config NAME`            | Load named Cllmfile configuration            |
| `--show-config`            | Display effective configuration              |
| `--json-schema FILE/URL`   | Enforce JSON schema for structured output    |
| `--validate-schema`        | Validate schema without making API call      |
| `--exec COMMAND`           | Execute command and inject output as context |
| `--no-context-exec`        | Disable context commands from config         |
| `--var KEY=VALUE`          | Set template variable (repeatable)           |
| `--allow-commands`         | Enable LLM-driven dynamic command execution  |
| `--command-allow PATTERN`  | Allowlist commands (wildcards supported)     |
| `--command-deny PATTERN`   | Denylist commands (wildcards supported)      |
| `--debug`                  | Enable debug mode (⚠️ logs API keys)         |
| `--json-logs`              | Enable structured JSON logging               |
| `--log-file PATH`          | Write debug output to file                   |
| `-v`, `-vv`, `-vvv`        | Set verbosity level (1, 2, or 3)             |
| `--verbose`                | Increase verbosity level (long form, repeatable) |
| `--help`                   | Show help message                            |

## Providers & Models

CLLM supports 100+ providers through LiteLLM. Use `cllm --list-models` to see all available models.

### Popular Providers

#### OpenAI

- `gpt-3.5-turbo` (default)
- `gpt-4`, `gpt-4-turbo`, `gpt-4o`
- `gpt-4o-mini`

#### Anthropic

- `claude-3-haiku-20240307`
- `claude-3-sonnet-20240229`
- `claude-3-opus-20240229`
- `claude-3-5-sonnet-20240620`

#### Google

- `gemini-pro`, `gemini-1.5-pro`, `gemini-1.5-flash`

#### Groq (Fast Inference)

- `groq/mixtral-8x7b-32768`
- `groq/llama-3.1-70b-versatile`
- `groq/llama-3.3-70b-versatile`

#### Ollama (Local Models)

- `ollama/llama3`, `ollama/codellama`, `ollama/mistral`
- Any custom Ollama model

#### Other Providers

- AWS Bedrock, Azure OpenAI, Cohere, Replicate, Together AI, Hugging Face, and 90+ more

#### Model Discovery

```bash
# List all 1343+ available models
cllm --list-models

# Filter by provider
cllm --list-models | grep -i anthropic
cllm --list-models | grep -i gpt-4
```

See [LiteLLM Providers](https://docs.litellm.ai/docs/providers) for complete list and setup instructions.

## Environment Variables

### Provider API Keys

```bash
# Provider API keys (LiteLLM conventions)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export GROQ_API_KEY="gsk_..."
export AZURE_API_KEY="..."
export COHERE_API_KEY="..."
# See https://docs.litellm.ai/docs/providers for all providers
```

### CLLM Configuration

```bash
# Default model (optional)
export CLLM_DEFAULT_MODEL="gpt-4"

# Debug settings (ADR-0009)
export CLLM_DEBUG=true
export CLLM_JSON_LOGS=true
export CLLM_LOG_FILE=/path/to/debug.log
```

## Development

### Setup

```bash
git clone https://github.com/o3-cloud/cllm.git
cd cllm
uv sync
```

### Run Tests

```bash
uv run pytest
```

### Build

```bash
uv build
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with ❤️ by the O3 Cloud team
- Inspired by the need for transparent, scriptable LLM workflows
- Thanks to all contributors and the open-source community

## Support

- 📖 [Documentation](https://github.com/o3-cloud/cllm/wiki)
- 🐛 [Issue Tracker](https://github.com/o3-cloud/cllm/issues)
- 💬 [Discussions](https://github.com/o3-cloud/cllm/discussions)

## Architecture Decision Records

CLLM's architecture and features are documented in ADRs (Architecture Decision Records):

- [ADR-0001](docs/decisions/0001-use-uv-as-package-manager.md): Use uv as Package Manager (10-100x faster than pip)
- [ADR-0002](docs/decisions/0002-use-litellm-for-llm-provider-abstraction.md): Use LiteLLM for Provider Abstraction (100+ providers)
- [ADR-0003](docs/decisions/0003-cllmfile-configuration-system.md): Cllmfile Configuration System (YAML configs)
- [ADR-0004](docs/decisions/0004-add-list-models-cli-flag.md): Add `--list-models` CLI Flag (model discovery)
- [ADR-0005](docs/decisions/0005-add-structured-output-support.md): Structured Output with JSON Schema
- [ADR-0006](docs/decisions/0006-support-remote-json-schema-urls.md): Support Remote JSON Schema URLs
- [ADR-0007](docs/decisions/0007-conversation-threading-and-context-management.md): Conversation Threading & Context Management
- [ADR-0008](docs/decisions/0008-add-bash-script-examples.md): Bash Script Examples Library
- [ADR-0009](docs/decisions/0009-add-debugging-and-logging-support.md): Debugging & Logging Support
- [ADR-0010](docs/decisions/0010-implement-litellm-streaming-support.md): LiteLLM Streaming Support
- [ADR-0011](docs/decisions/0011-dynamic-context-injection-via-command-execution.md): Dynamic Context Injection via Command Execution
- [ADR-0012](docs/decisions/0012-variable-expansion-in-context-commands.md): Variable Expansion in Context Commands with Jinja2 Templates
- [ADR-0013](docs/decisions/0013-llm-driven-dynamic-command-execution.md): LLM-Driven Dynamic Command Execution
- [ADR-0014](docs/decisions/0014-json-structured-output-with-allow-commands.md): JSON Structured Output with --allow-commands
- [ADR-0015](docs/decisions/0015-add-init-command-for-directory-setup.md): Init Command for Directory Setup (project bootstrapping with templates)
- [ADR-0016](docs/decisions/0016-configurable-cllm-directory-path.md): Configurable .cllm Directory Path (custom config locations)
- [ADR-0017](docs/decisions/0017-configurable-conversations-path.md): Configurable Conversations Path (independent control over conversation storage)
- [ADR-0022](docs/decisions/0022-cli-flag-for-system-prompt-override.md): CLI Flag for System Prompt Override (per-command system prompt customization)
- [ADR-0024](docs/decisions/0024-explicit-command-parameter-syntax.md): Explicit Command Parameter Syntax (bracket syntax with type hints for dynamic commands)

## Roadmap

**Completed:**

- ✅ Multi-provider support (100+ providers)
- ✅ Real-time streaming responses
- ✅ Conversation threading
- ✅ Structured JSON output with schema validation
- ✅ Configuration file system with templates
- ✅ Project initialization command (`cllm init`)
- ✅ Debugging and logging
- ✅ Model discovery
- ✅ Bash script examples
- ✅ Dynamic context injection via command execution
- ✅ Variable expansion with Jinja2 templates
- ✅ LLM-driven dynamic command execution (agentic workflows)
- ✅ Combined JSON schema with dynamic commands

**Planned:**

- [ ] Enhanced error recovery and retry strategies
- [ ] Token usage tracking and cost estimation
- [ ] Built-in prompt templates library
- [ ] Prompt caching support
- [ ] Multimodal support (images, audio)
- [ ] Plugin system for extensibility
- [ ] Integration with popular dev tools (VSCode, Emacs)
- [ ] Interactive command approval/confirmation mode
- [ ] Command execution history and replay

---

**Star ⭐ this repository if you find it useful!**
