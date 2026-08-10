"""
model_client.py
Abstract base class defining the interface for LLM model clients.

Provides a unified API for sending structured prompts to different
model providers (Ollama, OpenAI, etc.) and receiving responses.

How agents use this file
------------------------
Every agent calls ``ModelClient.chat(...)`` through the registry
(``client/model_registry.py``).  The contract is:

- ``purpose``  -> system message (role/persona)
- ``prompt``   -> user message (task)
- ``output``   -> expected output field names or labels
- ``rules``    -> constraints the model must follow
- ``inputs``   -> raw data/context for the model
- ``response_format`` -> always ``"json"`` (see ``chat`` docstring)
- ``json_schema``     -> optional strict-mode schema for Structured Outputs

The provider-specific prompt text is built by the shared
``build_task_prompt()`` helper at the bottom of this module, so agents
receive identical instructions no matter which provider answers.
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


def build_task_prompt(
    prompt: str,
    output: list[str],
    rules: list[str],
    inputs: list[str],
) -> str:
    """Build the compact, newline-delimited user prompt for a chat call.

    This is the *single* prompt builder shared by every ``ModelClient``
    implementation (Ollama and OpenAI both call it), so the exact text a
    provider receives is identical regardless of which backend is used.

    Sections are only included when the corresponding list is non-empty;
    the ``prompt`` task line is always present.

    Returns:
        A formatted prompt string with labelled sections, one per line::

            Task: <prompt>
            Output format: <output>
            Rules: <rule1> | <rule2>
            Input: <input1> | <input2>
    """
    parts = [f"Task: {prompt}"]

    if output:
        parts.append(f"Output format: {', '.join(output)}")

    if rules:
        parts.append(f"Rules: {' | '.join(rules)}")

    if inputs:
        parts.append(f"Input: {' | '.join(inputs)}")

    return "\n".join(parts)
