"""
simple.py
A simple example of using the Ollama API to create an agent that responds to user promptsq
"""

import asyncio
import os

from client.model_client import ModelClient
from client.ollama_client import OllamaClient
from client.open_ai_client import OpenAIClient

class SimpleAgent:
    """A simple agent that uses a ModelClient to respond to user prompts."""
    def __init__(self, client: ModelClient):
        self.client = client

    async def run(self, purpose: str, prompt: str, output: list[str],  rules: list[str], inputs: list[str]) -> str:
        """Run the agent with the given prompt and return the response."""
        return await self.client.chat(purpose, prompt, output, rules, inputs)


async def main() -> None:
    """Main function to run the simple agent."""

    provider = "ollama"  # or "openai"

    if provider == "ollama":
        client = OllamaClient("qwen3.5")
    else:
        client = OpenAIClient("gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY") or "")

    agent = SimpleAgent(client)
    purpose: str = "Answer questions about geography."
    prompt: str = "What is the capital of France?"
    output: list[str] = ["geography knowledge"]
    rules: list[str] = ["Provide accurate and concise answers.", "Do not provide personal opinions."]
    inputs: list[str] = ["question for the user"]

    result = await agent.run(purpose, prompt, output,  rules, inputs)
    print("Agent:", result)

asyncio.run(main())
