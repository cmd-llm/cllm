"""
Core LLM client implementation using LiteLLM.

This module implements ADR-0002: Use LiteLLM for LLM Provider Abstraction.
It provides a unified interface for interacting with 100+ LLM providers
using the OpenAI-compatible API format.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from litellm import acompletion, completion, stream_chunk_builder, token_counter


class LLMClient:
    """
    Unified LLM client for interacting with multiple providers.

    Uses LiteLLM to provide a consistent interface across OpenAI, Anthropic,
    Google, Cohere, AWS Bedrock, and 100+ other providers.

    Examples:
        >>> client = LLMClient()
        >>> # Using OpenAI
        >>> response = client.complete("gpt-4", "Hello, world!")
        >>> print(response)

        >>> # Using Anthropic (same interface)
        >>> response = client.complete("claude-3-opus-20240229", "Hello, world!")
        >>> print(response)

        >>> # Streaming responses
        >>> for chunk in client.complete("gpt-4", "Tell me a story", stream=True):
        ...     print(chunk, end="", flush=True)
    """

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize the LLM client.

        Args:
            api_keys: Optional dictionary of provider API keys.
                     If not provided, will use environment variables.
                     Keys should match LiteLLM's conventions:
                     - OPENAI_API_KEY for OpenAI
                     - ANTHROPIC_API_KEY for Anthropic
                     - GOOGLE_API_KEY for Google/Gemini
                     - COHERE_API_KEY for Cohere
                     etc.
        """
        if api_keys:
            for key, value in api_keys.items():
                os.environ[key] = value

    def complete(
        self,
        model: str,
        messages: Union[str, List[Dict[str, str]]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a completion using the specified model.

        This is a synchronous wrapper that uses asyncio.run() for streaming
        (per ADR-0010) to handle LiteLLM's async generator behavior.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus-20240229", "gemini-pro")
            messages: Either a string prompt or a list of message dicts in OpenAI format.
                     Single prompt: "Hello"
                     Conversation history:
                     [{"role": "user", "content": "Hello"},
                      {"role": "assistant", "content": "Hi there!"},
                      {"role": "user", "content": "How are you?"}]
            stream: If True, prints streaming output in real-time and returns complete response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters to pass to litellm.completion()

        Returns:
            If stream=False: The text content of the response (string)
            If stream=True: Complete response object with full message content (after streaming display)
            If raw_response=True in kwargs: The raw LiteLLM response object

        Raises:
            Exception: Provider-specific errors (mapped to OpenAI exception types by LiteLLM)
        """
        # Convert string prompt to messages format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # Build parameters
        params = {
            "model": model,
            "messages": messages,
        }

        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        # Add any additional parameters
        params.update(kwargs)

        # Check if user wants raw response
        raw_response = params.pop("raw_response", False)

        # Handle streaming with async wrapper (ADR-0010 TEST 2)
        if stream:

            async def _async_stream():
                response = await acompletion(**params, stream=True)
                chunks = []
                async for chunk in response:
                    chunks.append(chunk)
                    content = (
                        chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        or ""
                    )
                    if content:
                        print(content, end="", flush=True)
                print()  # Final newline
                return stream_chunk_builder(chunks, messages=messages)

            complete_response = asyncio.run(_async_stream())

            # Return raw response if requested, otherwise extract content
            if raw_response:
                return complete_response
            return complete_response.choices[0].message.content

        # Non-streaming path
        response = completion(**params, stream=False)

        # Return raw response if requested
        if raw_response:
            return response

        # Extract and return the text content
        return response["choices"][0]["message"]["content"]

    async def acomplete(
        self,
        model: str,
        messages: Union[str, List[Dict[str, str]]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Union[str, Dict[str, Any]]:
        """
        Async version of complete().

        Args:
            Same as complete()

        Returns:
            Same as complete()
        """
        # Convert string prompt to messages format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # Build parameters
        params = {
            "model": model,
            "messages": messages,
        }

        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        # Add any additional parameters
        params.update(kwargs)

        # Check if user wants raw response
        raw_response = params.pop("raw_response", False)

        # Handle streaming with async iteration (ADR-0010)
        if stream:
            response = await acompletion(**params, stream=True)
            chunks = []
            async for chunk in response:
                chunks.append(chunk)
                content = (
                    chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                )
                if content:
                    print(content, end="", flush=True)
            print()  # Final newline
            complete_response = stream_chunk_builder(chunks, messages=messages)

            # Return raw response if requested, otherwise extract content
            if raw_response:
                return complete_response
            return complete_response.choices[0].message.content

        # Non-streaming path
        response = await acompletion(**params, stream=False)

        # Return raw response if requested
        if raw_response:
            return response

        # Extract and return the text content
        return response["choices"][0]["message"]["content"]

    def complete_with_metadata(
        self,
        model: str,
        messages: Union[str, List[Dict[str, str]]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate a completion and return both the response and metadata.

        This is useful for extracting token usage, timing, and other metadata
        for verbose output (ADR-0025).

        Args:
            Same as complete()

        Returns:
            Tuple of (response_text, metadata_dict)
            where metadata_dict contains:
            - input_tokens: Number of input tokens
            - output_tokens: Number of output tokens
            - response_object: Full LiteLLM response object
        """
        # Convert string prompt to messages format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # Build parameters
        params = {
            "model": model,
            "messages": messages,
        }

        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        # Add any additional parameters (excluding raw_response)
        params.update(kwargs)
        params.pop("raw_response", None)

        # Metadata dictionary
        metadata: Dict[str, Any] = {
            "input_tokens": None,
            "output_tokens": None,
            "response_object": None,
        }

        # Handle streaming
        if stream:

            async def _async_stream():
                response = await acompletion(**params, stream=True)
                chunks = []
                async for chunk in response:
                    chunks.append(chunk)
                    content = (
                        chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        or ""
                    )
                    if content:
                        print(content, end="", flush=True)
                print()  # Final newline
                complete_response = stream_chunk_builder(chunks, messages=messages)
                return complete_response

            response_obj = asyncio.run(_async_stream())
            metadata["response_object"] = response_obj

            # Extract token usage if available
            if hasattr(response_obj, "usage"):
                metadata["input_tokens"] = getattr(
                    response_obj.usage, "prompt_tokens", None
                )
                metadata["output_tokens"] = getattr(
                    response_obj.usage, "completion_tokens", None
                )
            elif isinstance(response_obj, dict) and "usage" in response_obj:
                metadata["input_tokens"] = response_obj["usage"].get("prompt_tokens")
                metadata["output_tokens"] = response_obj["usage"].get(
                    "completion_tokens"
                )

            content = (
                response_obj.choices[0].message.content
                if hasattr(response_obj, "choices")
                else response_obj["choices"][0]["message"]["content"]
            )
            return content, metadata

        # Non-streaming path
        response = completion(**params, stream=False)
        metadata["response_object"] = response

        # Extract token usage
        if isinstance(response, dict) and "usage" in response:
            metadata["input_tokens"] = response["usage"].get("prompt_tokens")
            metadata["output_tokens"] = response["usage"].get("completion_tokens")
        elif hasattr(response, "usage"):
            metadata["input_tokens"] = getattr(
                response.usage, "prompt_tokens", None
            )
            metadata["output_tokens"] = getattr(
                response.usage, "completion_tokens", None
            )

        # Extract and return the text content
        if isinstance(response, dict):
            content = response["choices"][0]["message"]["content"]
        else:
            content = response.choices[0].message.content

        return content, metadata

    def count_tokens(
        self, model: str, messages: Union[str, List[Dict[str, str]]]
    ) -> int:
        """
        Count tokens in messages for the specified model.

        Useful for managing context windows in conversation history.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus-20240229")
            messages: Either a string prompt or list of message dicts

        Returns:
            Estimated token count

        Examples:
            >>> client = LLMClient()
            >>> tokens = client.count_tokens("gpt-4", "Hello, world!")
            >>> print(tokens)
            4
        """
        # Convert string prompt to messages format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        try:
            return token_counter(model=model, messages=messages)
        except Exception:
            # Fallback: rough estimate if token_counter fails
            # Average ~4 characters per token
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            return total_chars // 4

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """
        Convenience method for multi-turn chat conversations.

        Args:
            model: Model name
            messages: List of message dicts in OpenAI format
                     [{"role": "user", "content": "Hello"},
                      {"role": "assistant", "content": "Hi!"},
                      {"role": "user", "content": "How are you?"}]
            **kwargs: Additional parameters

        Returns:
            The assistant's response text
        """
        return self.complete(model=model, messages=messages, **kwargs)
