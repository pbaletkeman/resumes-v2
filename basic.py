"""
basic.py
Simple example demonstrating a single-agent LLM call.

Shows how to create a ``SimpleAgent`` backed by either an Ollama or
OpenAI model client and run a one-shot prompt.
"""

import asyncio
import os

from client.model_client import ModelClient
from client.model_registry import ModelClientRegistry
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
        client = OpenAIClient("gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY") or "")

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


async def per_agent_model_example() -> None:
    """Demonstrate using different models for different agents.

    This example shows how to use the ``ModelClientRegistry`` to assign
    different LLM models to different agents in a pipeline.
    """
    # Create a registry
    registry = ModelClientRegistry()

    # Register different models for different use cases
    registry.register("fast", OllamaClient("qwen3.5"))
    # registry.register("smart", OpenAIClient("gpt-4o", api_key="..."))

    # Set a default model for all agents
    registry.set_default_client("fast")

    # Override specific agents with different models
    # registry.set_agent_client("cover_letter_agent", "smart")
    # registry.set_agent_client("tone_polishing_agent", "smart")

    # Create agents using the registry
    fast_client = registry.get_client_for_agent("jd_parsing_agent")
    agent1 = SimpleAgent(fast_client)

    # All agents use "fast" by default
    agent2 = SimpleAgent(registry.get_client_for_agent("resume_parsing_agent"))

    # Run a simple test
    purpose = "Answer a question."
    prompt = "What is 2 + 2?"
    output = ["math knowledge"]
    rules = ["Be concise."]
    inputs = ["basic math"]

    result1 = await agent1.run(purpose, prompt, output, rules, inputs)
    print("Agent 1 (fast):", result1)

    result2 = await agent2.run(purpose, prompt, output, rules, inputs)
    print("Agent 2 (fast):", result2)


if __name__ == "__main__":
    asyncio.run(main())
