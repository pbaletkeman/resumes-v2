"""
ollama_client.py
Concrete ModelClient implementation for the Ollama API.

Sends structured prompts to a locally-running Ollama model and
returns the response. Supports any model available in the user's
Ollama installation (e.g. qwen3.5, llama3, mistral).
"""

import asyncio

import ollama

from client.model_client import ModelClient


class OllamaClient(ModelClient):
    """LLM client that communicates with a local Ollama instance.

    Uses the ``ollama.AsyncClient`` for non-blocking API calls with
    a 90-second timeout.

    Args:
        model: The Ollama model name to use (e.g. ``"qwen3.5"``).
    """

    def __init__(self, model: str) -> None:
        """Initialize the Ollama client.

        Args:
            model: The Ollama model identifier.
        """
        self.model = model
        self.client = ollama.AsyncClient()

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
            asyncio.TimeoutError: If the model does not respond within 90 seconds.
        """
        task = self._build_compact_prompt(purpose, prompt, output, rules, inputs)

        response: ollama.ChatResponse = await asyncio.wait_for(
            self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": purpose},
                    {"role": "user", "content": task},
                ],
            ),
            timeout=90,
        )

        return response["message"]["content"]

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
