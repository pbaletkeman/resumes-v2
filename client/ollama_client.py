"""
ollama_client.py
Concrete ModelClient implementation for the Ollama API.

    Sends structured prompts to a locally-running Ollama model and
    returns the response. Supports any model available in the user's
    Ollama installation (e.g. qwen2.5:7b-instruct, llama3, mistral).
"""

import asyncio

import ollama

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.model_client import ModelClient


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
    ) -> str:
        """Send a structured prompt to the Ollama model and return the response.

        Builds a compact prompt from the provided parameters, sends it as
        a system + user message pair, and returns the model's text output.

        Args:
            purpose: System-level role or persona for this call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.

        Returns:
            The model's text response.

        Raises:
            LLMConnectionError: If the Ollama server cannot be reached.
            LLMResponseError: If Ollama returns an error response.
            LLMTimeoutError: If the model does not respond within 90 seconds.
        """
        task = self._build_compact_prompt(purpose, prompt, output, rules, inputs)

        try:
            response = await asyncio.wait_for(
                self.client.chat(  # pyright: ignore[reportUnknownMemberType]
                    model=self.model,
                    messages=[
                        {"role": "system", "content": purpose},
                        {"role": "user", "content": task},
                    ],
                    stream=False,
                ),
                timeout=self.timeout,
            )
        except ollama.RequestError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama. Is the server running? {e}"
            ) from e
        except ollama.ResponseError as e:
            raise LLMResponseError(
                f"Ollama returned an error for model '{self.model}': {e}"
            ) from e
        except TimeoutError as e:
            raise LLMTimeoutError(
                f"Ollama model '{self.model}' did not respond within {self.timeout}s"
            ) from e

        content = response.message.content
        if content is None:
            raise LLMResponseError(
                f"Ollama model '{self.model}' returned an empty response"
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
