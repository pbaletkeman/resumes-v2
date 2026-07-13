"""
This module defines the OllamaClient class, which is a concrete implementation of the ModelClient abstract base class. The OllamaClient class provides an interface for interacting with the Ollama model client, allowing users to send chat prompts and receive responses from the model.
The OllamaClient class uses the ollama.AsyncClient to handle asynchronous communication with the Ollama API. It implements the `chat` method, which takes a user prompt as input and returns the model's response as a string.
"""
import asyncio
import json
import ollama

from client.model_client import ModelClient

class OllamaClient(ModelClient):
    """A concrete implementation of the ModelClient for interacting with the Ollama model client."""

    def __init__(self, model: str) -> None:
        """Initialize the OllamaClient with the specified model."""

        self.model = model
        self.client = ollama.AsyncClient()

    async def chat(self, purpose: str, prompt: str, output: list[str], rules: list[str], inputs: list[str]) -> str:
        """Send a lean, structured chat prompt to the Ollama model and return the response."""

        # Build compact prompt that focuses on the task, not parsing
        task = self._build_compact_prompt(purpose, prompt, output, rules, inputs)

        response: ollama.ChatResponse = await asyncio.wait_for(
            self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": purpose},
                    {"role": "user", "content": task}
                ]
            ),
            timeout=90
        )

        return response["message"]["content"]

    def _build_compact_prompt(self, purpose: str, prompt: str, output: list[str], rules: list[str], inputs: list[str]) -> str:
        """Build a compact, structured prompt."""
        parts = [f"Task: {prompt}"]

        if output:
            parts.append(f"Output format: {', '.join(output)}")

        if rules:
            parts.append(f"Rules: {' | '.join(rules)}")

        if inputs:
            parts.append(f"Input: {' | '.join(inputs)}")

        return "\n".join(parts)
