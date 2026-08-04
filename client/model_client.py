"""
model_client.py
Abstract base class defining the interface for LLM model clients.

Provides a unified API for sending structured prompts to different
model providers (Ollama, OpenAI, etc.) and receiving responses.
"""

from abc import ABC, abstractmethod
from typing import Any


class ModelClient(ABC):
    """Abstract base class for LLM model clients.

    Subclasses must implement the ``chat`` method to send a structured
    prompt to their specific model provider and return the response.
    """

    @abstractmethod
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
        """Send a structured prompt to the model and return the response.

        Args:
            purpose: System-level role or persona for this specific call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.
            response_format: Requested provider-native response mode.
                ``"json"`` is the only supported value and must be passed to
                every call; free-text responses are not part of the contract.
            json_schema: Optional JSON Schema dict (from
                ``client.json_utils.model_to_json_schema``) for provider
                Structured Outputs. When provided, the provider is asked
                to conform output to the schema instead of plain JSON
                mode. Defaults to ``None`` (plain JSON mode).

        Returns:
            The model's text response.

        Raises:
            NotImplementedError: Always; must be overridden by subclasses.
        """
        ...
