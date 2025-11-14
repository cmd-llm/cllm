"""Logging handler for verbosity-based output using loguru."""

import json
import sys
from typing import Any, Dict, Optional

from loguru import logger


class LoguruVerbosityHandler:
    """Manages loguru configuration based on verbosity levels."""

    def __init__(self, verbosity: int = 0, level: Optional[int] = None):
        """
        Initialize the verbosity handler.

        Args:
            verbosity: Verbosity level (0 = none, 1 = INFO, 2 = DEBUG, 3+ = TRACE)
            level: Deprecated. Use verbosity instead. Provided for backward compatibility.
        """
        # Support both 'level' (old API) and 'verbosity' (new API) for backward compatibility
        if level is not None:
            self.verbosity = min(level, 3)  # Cap at level 3
        else:
            self.verbosity = min(verbosity, 3)  # Cap at level 3
        self._configure_logger()

    @property
    def level(self) -> int:
        """Backward compatibility property for accessing verbosity level."""
        return self.verbosity

    def _configure_logger(self) -> None:
        """Configure loguru based on verbosity level."""
        # Remove default handler
        logger.remove()

        if self.verbosity == 0:
            # No logging
            return

        # Determine log level based on verbosity
        if self.verbosity == 1:
            level = "INFO"
        elif self.verbosity == 2:
            level = "DEBUG"
        else:  # 3+
            level = "TRACE"

        # Custom format with colors (concise, no timestamps for CLI usage)
        fmt = (
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        )

        # Add stderr handler with color support
        logger.add(
            sys.stderr,
            format=fmt,
            level=level,
            colorize=True,
        )

    def log_model_info(self, model: str, provider: Optional[str] = None) -> None:
        """Log model and provider information."""
        if self.verbosity < 1:
            return
        logger.info(f"Model: {model}")
        if provider:
            logger.info(f"Provider: {provider}")

    def log_tokens(
        self, input_tokens: Optional[int], output_tokens: Optional[int]
    ) -> None:
        """Log token information."""
        if self.verbosity < 1 or input_tokens is None or output_tokens is None:
            return
        total = input_tokens + output_tokens
        logger.info(
            f"Tokens: {input_tokens} input, {output_tokens} output ({total} total)"
        )

    def log_latency(self, latency_seconds: float) -> None:
        """Log request latency."""
        if self.verbosity < 1:
            return
        logger.info(f"Latency: {latency_seconds:.2f}s")

    def log_endpoint(self, endpoint: str) -> None:
        """Log API endpoint being called."""
        if self.verbosity < 2:
            return
        logger.debug(f"Endpoint: {endpoint}")

    def log_parameters(self, parameters: Optional[Dict[str, Any]]) -> None:
        """Log request parameters."""
        if self.verbosity < 2 or not parameters:
            return
        params_str = ", ".join(f"{k}={parameters[k]}" for k in sorted(parameters))
        logger.debug(f"Parameters: {params_str}")

    def log_response_status(self, status_code: int, response_time_ms: float) -> None:
        """Log response status and timing."""
        if self.verbosity < 2:
            return
        logger.debug(f"Response: status={status_code}, time={response_time_ms:.0f}ms")

    def log_config_loaded(self, config_path: str) -> None:
        """Log configuration source."""
        if self.verbosity < 2:
            return
        logger.debug(f"Config loaded from: {config_path}")

    def log_request_payload(self, payload: str) -> None:
        """Log full request payload (TRACE level)."""
        if self.verbosity < 3:
            return
        logger.trace(f"Request Payload: {payload}")

    def log_response_payload(self, payload: str) -> None:
        """Log full response payload (TRACE level)."""
        if self.verbosity < 3:
            return
        logger.trace(f"Response Payload: {payload}")

    def log_headers(self, headers: str) -> None:
        """Log HTTP headers (TRACE level)."""
        if self.verbosity < 3:
            return
        logger.trace(f"HTTP Headers: {headers}")

    def log_exception(self, exc: Exception) -> None:
        """Log exception with context."""
        if self.verbosity < 1:
            return
        logger.exception(f"Request failed with exception: {exc}")

    def log_event(
        self,
        message: str,
        *,
        importance: str = "major",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a lifecycle event with optional metadata."""
        importance = importance.lower()
        if importance not in {"major", "minor"}:
            importance = "major"

        if importance == "major":
            if self.verbosity < 1:
                return
            log_fn = logger.info
        else:
            if self.verbosity < 2:
                return
            log_fn = logger.debug

        if extra:
            try:
                formatted = json.dumps(extra, sort_keys=True, default=str)
            except (TypeError, ValueError):
                formatted = str(extra)
            log_fn(f"{message} | {formatted}")
        else:
            log_fn(message)

    # Backward compatibility methods for existing CLI code
    def print_basic_info(
        self,
        model: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        latency_seconds: Optional[float] = None,
    ) -> None:
        """Print basic info (level 1) - backward compatible wrapper."""
        if self.verbosity < 1:
            return

        self.log_model_info(model, provider)

        if input_tokens is not None and output_tokens is not None:
            self.log_tokens(input_tokens, output_tokens)

        if latency_seconds is not None:
            self.log_latency(latency_seconds)

    def print_api_details(
        self,
        endpoint: Optional[str] = None,
        parameters: Optional[dict] = None,
        status_code: Optional[int] = None,
        config_sources: Optional[list] = None,
    ) -> None:
        """Print API details (level 2) - backward compatible wrapper."""
        if self.verbosity < 2:
            return

        if endpoint:
            self.log_endpoint(endpoint)

        if parameters:
            self.log_parameters(parameters)

        if status_code:
            logger.debug(f"Status: {status_code}")

        if config_sources:
            logger.debug(f"Config sources: {', '.join(config_sources)}")
            for source in config_sources:
                self.log_config_loaded(source)
