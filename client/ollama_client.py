"""
ollama_client.py
Concrete ModelClient implementation for the Ollama API.

    Sends structured prompts to a locally-running Ollama model and
    returns the response. Supports any model available in the user's
    Ollama installation (e.g. qwen2.5:7b-instruct, llama3, mistral).
"""

import asyncio
import logging
import time
from typing import Any

import ollama

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.model_client import ModelClient

logger = logging.getLogger(__name__)


class OllamaClient(ModelClient):
    """LLM client that communicates with a local Ollama instance.

    Uses the ``ollama.AsyncClient`` for non-blocking API calls with
    a configurable timeout (default 300 seconds).

    Args:
        model: The Ollama model name to use (e.g. ``"qwen2.5:7b-instruct"``).
        timeout: Request timeout in seconds (default 300).
    """

    def __init__(self, model: str, timeout: int = 300) -> None:
        """Initialize the Ollama client.

        Args:
            model: The Ollama model identifier.
            timeout: Request timeout in seconds (default 300).
        """
        self.model = model
        self.timeout = timeout
        self.client: ollama.AsyncClient = ollama.AsyncClient()

    async def chat(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
        response_format: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Send a structured prompt to the Ollama model and return the response.

        Builds a compact prompt from the provided parameters, sends it as
        a system + user message pair, and returns the model's text output.
        JSON mode is always on via ``format="json"`` unless a JSON Schema
        is provided, in which case ``format`` carries the schema dict for
        provider Structured Outputs.

        Args:
            purpose: System-level role or persona for this call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.
            response_format: Requested provider-native response mode.
                ``"json"`` is the only supported value and must be passed to
                every call; free-text responses are not part of the contract.
            json_schema: Optional JSON Schema dict (from
                ``client.json_utils.model_to_json_schema``) for Ollama
                Structured Outputs. When provided, ``format`` carries the
                schema dict instead of ``"json"``. Defaults to ``None``.

        Returns:
            The model's text response.

        Raises:
            LLMConnectionError: If the Ollama server cannot be reached.
            LLMResponseError: If Ollama returns an error response.
            LLMTimeoutError: If the model does not respond within 90 seconds.
        """
        task = self._build_compact_prompt(purpose, prompt, output, rules, inputs)
        actual_format: Any = json_schema if json_schema is not None else "json"

        logger.debug(
            "Ollama request: model=%s format=%s prompt_len=%d messages=2",
            self.model,
            actual_format,
            len(task),
        )
        start = time.monotonic()

        try:
            response = await asyncio.wait_for(
                self.client.chat(  # pyright: ignore[reportUnknownMemberType]
                    model=self.model,
                    messages=[
                        {"role": "system", "content": purpose},
                        {"role": "user", "content": task},
                    ],
                    stream=False,
                    # response_format="json" is the only supported mode; a
                    # JSON Schema dict opts in to provider Structured Outputs
                    format=actual_format,
                ),
                timeout=self.timeout,
            )
        except ollama.RequestError as e:
            logger.warning("Ollama connection failed: %s", e, exc_info=True)
            raise LLMConnectionError(
                f"Cannot connect to Ollama. Is the server running? {e}"
            ) from e
        except ollama.ResponseError as e:
            logger.warning("Ollama response error: %s", e, exc_info=True)
            raise LLMResponseError(
                f"Ollama returned an error for model '{self.model}': {e}"
            ) from e
        except TimeoutError as e:
            logger.warning(
                "Ollama timeout after %ds for model %s",
                self.timeout,
                self.model,
                exc_info=True,
            )
            raise LLMTimeoutError(
                f"Ollama model '{self.model}' did not respond within {self.timeout}s"
            ) from e

        content = response.message.content
        if content is None:
            logger.warning("Ollama returned empty response for model %s", self.model)
            raise LLMResponseError(
                f"Ollama model '{self.model}' returned an empty response"
            )

        elapsed = time.monotonic() - start
        logger.debug(
            "Ollama response: model=%s response_len=%d latency=%.1fs",
            self.model,
            len(content),
            elapsed,
        )
        return content

    def _build_compact_prompt(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
    ) -> str:
        """Build a compact, newline-delimited prompt string.

        Args:
            purpose: System-level role (used for context, not included in output).
            prompt: The primary task description.
            output: Expected output field names.
            rules: Constraints or guidelines.
            inputs: Additional context data.

        Returns:
            A formatted prompt string with labelled sections.
        """
        parts = [f"Task: {prompt}"]

        if output:
            parts.append(f"Output format: {', '.join(output)}")

        if rules:
            parts.append(f"Rules: {' | '.join(rules)}")

        if inputs:
            parts.append(f"Input: {' | '.join(inputs)}")

        return "\n".join(parts)
