"""
open_ai_client.py
Concrete ModelClient implementation for the OpenAI API.

Sends structured prompts to any OpenAI-compatible model (GPT-4o, GPT-4o-mini, etc.)
via the official openai Python SDK.
"""

import asyncio

from openai import AsyncOpenAI

from client.model_client import ModelClient


class OpenAIClient(ModelClient):
    """LLM client that communicates with the OpenAI API.

    Uses the ``openai.AsyncOpenAI`` client for non-blocking API calls with
    a 90-second timeout.

    Args:
        model: The OpenAI model name (e.g. ``"gpt-4o-mini"``).
        api_key: The OpenAI API key.
    """

    def __init__(self, model: str, api_key: str) -> None:
        """Initialize the OpenAI client.

        Args:
            model: The OpenAI model identifier.
            api_key: The API key for authentication.
        """
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
    ) -> str:
        """Send a structured prompt to the OpenAI model and return the response.

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
        parts = [f"Task: {prompt}"]

        if output:
            parts.append(f"Output format: {', '.join(output)}")

        if rules:
            parts.append(f"Rules: {' | '.join(rules)}")

        if inputs:
            parts.append(f"Input: {' | '.join(inputs)}")

        task = "\n".join(parts)

        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": purpose},
                    {"role": "user", "content": task},
                ],
            ),
            timeout=90,
        )
        return response.choices[0].message.content
