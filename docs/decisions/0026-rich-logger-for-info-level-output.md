# Loguru Logger for Info-Level Output

## Context and Problem Statement

While ADR-0025 established the `-v`, `-vv`, `-vvv` verbosity level framework, the actual output formatting remains basic and text-only. Current implementation uses simple print statements and string formatting, which:

- Lack structure and context (missing timestamps, source locations)
- Don't capture request/response lifecycle in a queryable format
- Difficult to correlate with external events or persist for later analysis
- Can't selectively log different parts of the request flow
- Are inconsistent with application logging best practices

Users debugging API issues need structured, contextual logging with timestamps and source information. A professional logging approach would significantly improve the debugging experience and enable better problem diagnosis.

## Decision Drivers

- **Structured Logging**: Timestamps and source locations provide context for debugging
- **Professional Quality**: Production-grade logging library with advanced features
- **Powerful Filtering**: Configure what gets logged at different verbosity levels
- **Exception Handling**: Automatic context on errors with full tracebacks
- **Lifecycle Tracking**: Timestamps show request/response lifecycle and timing
- **Log Rotation & Persistence**: Built-in support for file logging with rotation
- **Flexibility**: Configure format, colors, and output destinations easily
- **Minimal Configuration**: Works out-of-the-box with sensible defaults
- **Active Development**: Well-maintained library with strong community support
- **Python Best Practices**: Replaces standard library `logging` with more developer-friendly API

## Considered Options

- **Option 1**: Use `loguru` for powerful structured logging with color support and advanced features
- **Option 2**: Use `rich` library for beautiful, human-friendly formatting with colors, tables, and panels
- **Option 3**: Use `structlog` for machine-parseable structured logging with custom formatters
- **Option 4**: Create custom ANSI color formatting without external dependencies
- **Option 5**: Use `colorama` for cross-platform color support with custom formatting

## Decision Outcome

Chosen option: **"Option 1: Use `loguru` for structured logging"**, because:

1. **Structured Logging**: Timestamps and source information provide essential debugging context
2. **Professional Logging Library**: Replaces Python's `logging` module with more powerful, developer-friendly API
3. **Powerful Filtering**: Configure what gets logged at each verbosity level with fine-grained control
4. **Lifecycle Tracking**: Request/response timestamps and latency automatically captured
5. **Exception Handling**: Automatic context and full tracebacks on errors
6. **Production Ready**: Built-in log rotation, file management, and persistence features
7. **Color Output by Default**: Beautiful colored output on TTY, automatic degradation on non-TTY

### Consequences

- Good, because structured logs include timestamps and source locations for full context
- Good, because professional-grade logging library with advanced features (rotation, filtering)
- Good, because supports both interactive terminals and non-TTY output (automatic detection)
- Good, because adds only one production dependency (loguru is lightweight, ~100KB)
- Good, because integrates seamlessly with ADR-0025's verbosity framework
- Good, because existing `--debug`, `--json-logs`, `--log-file` flags work unchanged
- Good, because terminal auto-detection with colored output on TTY, plain text on non-TTY
- Good, because exception handling with automatic context and full tracebacks
- Good, because built-in file rotation and persistence for long-running sessions
- Neutral, because log format with timestamps adds some lines to output
- Neutral, because timestamp format needs configuration for brevity
- Bad, because adds external dependency (though widely trusted, actively maintained)

### Confirmation

This decision will be validated through:

- **Structured Output Testing**: Verify logs include timestamps, levels, and source information
- **Non-TTY Testing**: Verify output degrades to plain text when piped or redirected
- **Integration Tests**: `-v` with `--json-logs`, `--log-file`, and `--debug` produce correct output
- **Dependency Tests**: Verify `loguru` installation doesn't break existing workflows
- **Performance Tests**: Confirm negligible overhead from structured logging
- **Exception Testing**: Verify exceptions include full context and tracebacks
- **Format Configuration**: Verify timestamp and level format is appropriate for CLI usage

## Pros and Cons of the Options

### Option 1: Use `loguru`

The `loguru` library (https://github.com/Delgan/loguru) provides powerful structured logging with beautiful formatting.

- Good, because replaces Python's `logging` module with simpler, more powerful API
- Good, because automatic exception handling with full context and tracebacks
- Good, because fine-grained filtering to show different info at different verbosity levels
- Good, because auto-detects TTY and applies colors intelligently (degrades gracefully)
- Good, because built-in file rotation and persistence for long-running sessions
- Good, because structured format enables parsing logs programmatically
- Good, because widely used and trusted in Python ecosystem (proven reliability)
- Good, because excellent documentation and examples (learning curve is minimal)
- Good, because includes timestamps and source location by default (debugging context)
- Neutral, because timestamp format takes up space (but can be configured)
- Neutral, because log level prefixes add some output volume
- Bad, because adds production dependency (though lightweight: ~100KB)

**Example usage:**

```python
from loguru import logger

# Configure logger for CLI usage
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}",
    colorize=True
)

# Info-level logging
logger.info("Model: {model}", model="gpt-4")
logger.info("Provider: {provider}", provider="openai")
logger.info("Tokens: {input} input, {output} output", input=50, output=120)

# Debug-level for more details
logger.debug("Endpoint: {endpoint}", endpoint="https://api.openai.com/v1/chat/completions")
logger.debug("Parameters: temperature={temp}, max_tokens={tokens}", temp=0.7, tokens=500)

# Trace-level for full payload
logger.trace("Request payload: {payload}", payload=request_json)
```

### Option 2: Use `rich` library

The `rich` library is specifically designed for beautiful terminal output with tables, panels, and colors.

- Good, because specifically designed for CLI applications (tables, panels, colors built-in)
- Good, because zero-config on all platforms (colors work automatically)
- Good, because extensive feature set (tables, panels, progress bars, syntax highlighting)
- Good, because auto-detects TTY and degrades gracefully (handles piping/CI)
- Good, because widely used and trusted in Python ecosystem
- Neutral, because visual output is opinionated (limited customization)
- Bad, because optimized for immediate visual output, not structured logging
- Bad, because doesn't include timestamps or source location by default
- Bad, because output is ephemeral (not suitable for log persistence)
- Bad, because requires manual formatting of request/response data

**Example usage:**

```python
from rich.console import Console
from rich.table import Table

console = Console()
console.print("[bold cyan]Model:[/bold cyan] gpt-4")

table = Table(title="Request Parameters")
table.add_row("temperature", "0.7")
console.print(table)
```

### Option 3: Use `structlog`

The `structlog` library provides machine-parseable structured logging with custom formatters.

- Good, because structures logs for machine parsing and analytics
- Good, because flexible formatting with custom renderers
- Neutral, because designed for systems with complex logging needs
- Bad, because adds significant complexity for our use case (overkill)
- Bad, because requires understanding structured logging concepts
- Bad, because primary use case is backend systems, not CLI output
- Bad, because not purpose-built for beautiful terminal formatting

### Option 4: Create custom ANSI formatting

Implement custom color and formatting logic without external libraries.

- Good, because zero additional dependencies
- Good, because full control over output format
- Neutral, because works on any platform (standard ANSI codes)
- Bad, because requires writing and maintaining all formatting logic
- Bad, because harder to handle edge cases (terminal width, colors on Windows)
- Bad, because reinvents the wheel (already solved by established libraries)
- Bad, because maintenance burden and potential bugs

### Option 5: Use `colorama`

The `colorama` library provides cross-platform color support with minimal overhead.

- Good, because lightweight (only handles colors, not formatting)
- Good, because minimal additional code needed
- Neutral, because adequate for basic coloring but limited formatting
- Bad, because lacks table, panel, and structured formatting features
- Bad, because requires building all formatting logic manually
- Bad, because less modern than `rich`
- Bad, because doesn't handle TTY detection as elegantly

## More Information

### Integration with ADR-0025

The `loguru` library will be configured to output the information defined by ADR-0025's verbosity levels:

**Level 1 (`-v`): Basic Information**

Logs at `INFO` level:

```
INFO     | cllm.client:complete:145 | Model: gpt-4
INFO     | cllm.client:complete:146 | Provider: openai
INFO     | cllm.client:complete:147 | Tokens: 50 input, 120 output (170 total)
INFO     | cllm.client:complete:148 | Latency: 1.23s
```

**Level 2 (`-vv`): API Details**

Logs at `INFO` and `DEBUG` levels:

```
INFO     | cllm.client:complete:145 | Model: gpt-4
DEBUG    | cllm.client:_make_request:234 | Endpoint: https://api.openai.com/v1/chat/completions
DEBUG    | cllm.client:_make_request:235 | Parameters: temperature=0.7, max_tokens=500, top_p=1.0
DEBUG    | cllm.client:_handle_response:312 | Response: status=200, time=237ms
DEBUG    | cllm.config:load:89 | Config loaded from: ~/.cllm/Cllmfile.yml
```

**Level 3 (`-vvv`): Full Debug Output**

Logs at `INFO`, `DEBUG`, and `TRACE` levels:

```
INFO     | cllm.client:complete:145 | Model: gpt-4
TRACE    | cllm.client:_make_request:234 | Request Payload: {"model": "gpt-4", "messages": [...], "temperature": 0.7, ...}
TRACE    | cllm.client:_handle_response:312 | Response Payload: {"choices": [{"message": {...}}], "usage": {...}}
TRACE    | cllm.client:_handle_response:320 | HTTP Headers: Authorization: Bearer sk-..., Content-Type: application/json
```

### Implementation Strategy

**Phase 1: Loguru Setup and Configuration**

- Add `loguru` to `pyproject.toml` dependencies
- Remove default `loguru` handler and configure custom format
- Set up log level filtering based on verbosity flag (`-v` = INFO, `-vv` = DEBUG, `-vvv` = TRACE)
- Create a logger instance in `cli.py` with appropriate configuration

**Phase 2: Integrate with VerbosityHandler**

- Create `LoguruVerbosityHandler` class that wraps the logger
- Configure log level based on verbosity argument
- Add methods for logging at different stages (request start, API call, response received, config loaded)
- Format log messages to be concise and informative

**Phase 3: Instrumentation**

- Add logging calls to `client.py` for request/response lifecycle
- Log configuration sources and parameters
- Log endpoint information and timing data
- Add exception logging with context

### Code Structure

```python
# src/cllm/logging_handler.py (new file)

from loguru import logger
import sys

class LoguruVerbosityHandler:
    """Manages loguru configuration based on verbosity levels."""

    def __init__(self, verbosity: int = 0):
        self.verbosity = verbosity
        self.configure_logger()

    def configure_logger(self):
        """Configure loguru based on verbosity level."""
        logger.remove()  # Remove default handler

        # Set log level based on verbosity
        if self.verbosity == 0:
            return  # No logging
        elif self.verbosity == 1:
            level = "INFO"
        elif self.verbosity == 2:
            level = "DEBUG"
        else:  # 3+
            level = "TRACE"

        # Custom format with colors
        fmt = (
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        )

        logger.add(sys.stderr, format=fmt, level=level, colorize=True)

    def log_model_info(self, model, provider):
        """Log model and provider information."""
        logger.info(f"Model: {model}")
        logger.info(f"Provider: {provider}")

    def log_tokens(self, input_tokens, output_tokens):
        """Log token information."""
        total = input_tokens + output_tokens
        logger.info(f"Tokens: {input_tokens} input, {output_tokens} output ({total} total)")
```

### Integration with Existing CLI

```python
# In src/cllm/cli.py

from cllm.logging_handler import LoguruVerbosityHandler

# Initialize logger
verbosity_handler = LoguruVerbosityHandler(verbosity=args.verbosity)

# Use throughout the request lifecycle
verbosity_handler.log_model_info(model="gpt-4", provider="openai")
verbosity_handler.log_tokens(input_tokens=50, output_tokens=120)
```

### TTY Detection and Graceful Degradation

Loguru automatically detects TTY:

```python
logger.add(sys.stderr, colorize=True)

# Loguru automatically:
# - Applies ANSI colors when connected to TTY
# - Removes ANSI codes when piped/redirected
# - Degrades gracefully for CI/CD environments
# - Respects NO_COLOR environment variable
```

### Dependency Management

Adding to `pyproject.toml`:

```toml
[project]
dependencies = [
    "litellm>=1.0.0",
    "loguru>=0.7.0",  # Structured logging
    # ... other dependencies
]
```

Version constraint: `loguru>=0.7.0` (stable, widely-used version with good compatibility)

### Security Considerations

1. **API Key Redaction**: Level 3 output shows request payloads which may contain API keys
   - Same warning as existing `--debug` flag
   - Document clearly in help text
   - Consider adding `--redact-keys` flag for safer logging

2. **Terminal History**: Colored output may be visible in shell history
   - Recommend `export HISTCONTROL=ignorespace` before running sensitive commands
   - Document security best practices

3. **Rich Rendering**: Tables and panels are purely visual formatting
   - No security impact beyond traditional text output
   - Render consistently across platforms

### Performance Considerations

`rich` has minimal performance overhead:

- Console initialization: ~1ms
- Formatting a table with 5 rows: ~0.5ms
- Panel rendering: ~0.2ms
- **Total impact**: <5ms for typical level 2 output (negligible vs. LLM latency of 1000+ms)

No memory concerns: `rich` streams output, doesn't buffer large amounts.

### Cross-Platform Support

- **macOS/Linux**: Full ANSI color and Unicode support
- **Windows**: `rich` auto-detects Terminal and PowerShell color support
- **CI/CD**: Auto-detects non-TTY and outputs plain text
- **SSH/Remote**: Works over SSH connections that support ANSI codes
- **Piping**: Degrades to plain text when output is piped

---

## AI-Specific Extensions

### AI Guidance Level

**Chosen level: Flexible**

Implement the `rich` integration while adapting:

- Output formatting based on what works best with different terminal widths
- Table structure and column widths optimized for readability
- Visual design that balances beauty with clarity
- Additional enhancements (e.g., progress indicators) if beneficial
- Optimization based on real-world usage feedback

### AI Tool Preferences

- **Preferred AI tools**: Claude Code for implementation
- **Model parameters**: Standard temperature for balanced accuracy
- **Special instructions**:
  - Ensure all existing tests continue to pass
  - Test output on various terminal widths (80, 120, 180 columns)
  - Verify output degrades gracefully when not connected to TTY
  - Test on both Unix (macOS/Linux) and Windows environments
  - Verify color support is properly detected on all platforms

### Test Expectations

**Unit Tests:**

- `test_loguru_handler_initialization()`: Handler configures loguru correctly
- `test_verbosity_level_0()`: No logging when verbosity=0
- `test_verbosity_level_1()`: Logs at INFO level when verbosity=1
- `test_verbosity_level_2()`: Logs at DEBUG level when verbosity=2
- `test_verbosity_level_3()`: Logs at TRACE level when verbosity=3
- `test_log_format()`: Log format includes level, module, line number, and message
- `test_tty_detection()`: Logger applies colors on TTY, removes on non-TTY
- `test_no_color_respected()`: `NO_COLOR` environment variable disables colors
- `test_log_methods()`: `log_model_info()`, `log_tokens()` output correct messages

**Integration Tests:**

- `test_verbosity_with_loguru_handler()`: `-v` flag configures loguru correctly
- `test_loguru_with_json_logs()`: `--json-logs` works with loguru output
- `test_loguru_with_log_file()`: Output redirected to file includes all info
- `test_piped_output()`: `cllm -v | tee output.txt` produces plain text (no ANSI)
- `test_cli_flag_precedence()`: CLI flags override config file settings
- `test_multiple_providers()`: Output works with OpenAI, Anthropic, Google
- `test_exception_context()`: Exceptions logged with full context and traceback

**Format Tests:**

- Verify each log line includes: level, module:line, and message
- Verify timestamps are not added by default (kept concise for CLI)
- Verify colors work correctly on different terminal types
- Verify output is readable on 80-column terminals

### Dependencies

- **Related ADRs**:
  - ADR-0025: Logging verbosity levels (provides the structure this implements)
  - ADR-0009: Debugging and logging support (complements these features)
  - ADR-0003: Cllmfile configuration (configuration integration)

- **System components**:
  - `src/cllm/cli.py`: Initialize LoguruVerbosityHandler with verbosity level
  - `src/cllm/client.py`: Add logging calls for request/response lifecycle
  - `src/cllm/config.py`: Add logging for configuration loading
  - New file: `src/cllm/logging_handler.py`: LoguruVerbosityHandler class

- **External dependencies**:
  - `loguru>=0.7.0`: Structured logging library
  - `litellm`: Data source for logging output

### Timeline

- **Implementation deadline**: No hard deadline (enhancement)
- **First review**: After initial implementation and integration tests pass
- **Revision triggers**:
  - User feedback on visual formatting
  - Issues with specific terminal emulators
  - Performance concerns
  - New verbosity features added to ADR-0025

### Risk Assessment

#### Technical Risks

- **Terminal Compatibility (LOW)**: Loguru colors may not work on very old terminals
  - **Mitigation**: Loguru auto-detects and removes ANSI codes when needed
  - **Mitigation**: Test on multiple terminal types before release
  - **Mitigation**: Respect `NO_COLOR` environment variable

- **Log Format Verbosity (LOW)**: Log format with level/module:line adds overhead
  - **Mitigation**: Keep format concise (no timestamps by default)
  - **Mitigation**: Test output is readable on 80-column terminals
  - **Mitigation**: Allow format customization via environment variables

- **Performance Impact (LOW)**: Logging may add latency to fast requests
  - **Mitigation**: Benchmark on actual API calls (LLM latency >> logging overhead)
  - **Mitigation**: Use lazy evaluation for expensive log data

- **Logging Noise (LOW)**: Too many log lines may overwhelm users
  - **Mitigation**: Keep log messages concise and focused
  - **Mitigation**: Only log relevant information at each verbosity level

#### Business Risks

- **Dependency Management (LOW)**: Adding `loguru` increases supply chain surface area
  - **Mitigation**: Loguru is widely used and actively maintained
  - **Mitigation**: Pin to stable version in pyproject.toml
  - **Mitigation**: Regular dependency updates and security monitoring

- **User Expectations (LOW)**: Log format may be unfamiliar to some users
  - **Mitigation**: Provide clear examples in documentation
  - **Mitigation**: Help text explains what each verbosity level shows
  - **Mitigation**: Log output is self-explanatory (level, location, message)

### Human Review

- **Review required**: After initial implementation
- **Reviewers**: Maintainers (Owen Zanzal)
- **Approval criteria**:
  - All existing tests pass (no regression with ADR-0025)
  - All new rich formatting tests pass
  - Output is readable and visually appealing at all verbosity levels
  - Non-TTY output degrades to plain text correctly
  - Works on multiple terminal emulators (at least macOS Terminal, iTerm, Windows Terminal)
  - Performance overhead is negligible (<5ms additional latency)
  - Documentation updated with visual examples of each level
  - Security warnings about API key exposure are prominent

### Feedback Log

_(To be filled after implementation)_

- Implementation date: \_\_\_
- Actual outcomes: \_\_\_
- Challenges encountered: \_\_\_
- Lessons learned: \_\_\_
- Suggested improvements: \_\_\_
