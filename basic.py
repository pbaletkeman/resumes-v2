"""
basic.py
Simple example demonstrating a single-agent LLM call.

Shows how to create a ``SimpleAgent`` backed by either an Ollama or
OpenAI model client and run a one-shot prompt.
"""

import asyncio
import os

from client.model_client import ModelClient
from client.ollama_client import OllamaClient
from client.open_ai_client import OpenAIClient


class SimpleAgent:
    """A thin wrapper that delegates chat calls to a ``ModelClient``.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        """Initialize the agent with a model client.

        Args:
            client: An LLM client implementing ``ModelClient.chat``.
        """
        self.client = client

    async def run(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
    ) -> str:
        """Run the agent with the given prompt and return the response.

        Args:
            purpose: System-level role or persona.
            prompt: The user-facing task or question.
            output: Expected output field names.
            rules: Constraints or guidelines.
            inputs: Additional context data.

        Returns:
            The model's text response.
        """
        return await self.client.chat(purpose, prompt, output, rules, inputs)


async def main() -> None:
    """Run a simple geography question through the agent."""
    provider = "ollama"  # or "openai"

    if provider == "ollama":
        client = OllamaClient("qwen3.5")
    else:
        client = OpenAIClient(
            "gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY") or ""
        )

    agent = SimpleAgent(client)
    purpose: str = "Answer questions about geography."
    prompt: str = "What is the capital of France?"
    output: list[str] = ["geography knowledge"]
    rules: list[str] = [
        "Provide accurate and concise answers.",
        "Do not provide personal opinions.",
    ]
    inputs: list[str] = ["question for the user"]

    result = await agent.run(purpose, prompt, output, rules, inputs)
    print("Agent:", result)


asyncio.run(main())
