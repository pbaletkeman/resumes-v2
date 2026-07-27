"""
model_client.py
Abstract base class defining the interface for LLM model clients.

Provides a unified API for sending structured prompts to different
model providers (Ollama, OpenAI, etc.) and receiving responses.
"""

from abc import ABC, abstractmethod


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
    ) -> str:
        """Send a structured prompt to the model and return the response.

        Args:
            purpose: System-level role or persona for this specific call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.

        Returns:
            The model's text response.

        Raises:
            NotImplementedError: Always; must be overridden by subclasses.
        """
        ...
