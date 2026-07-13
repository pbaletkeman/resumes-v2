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

    async def run(self, prompt: str) -> str:
        return await self.client.chat(prompt)


async def main() -> None:
    """Main function to run the simple agent."""

    provider = "ollama"  # or "openai"

    if provider == "ollama":
        client = OllamaClient("qwen3.5")
    else:
        client = OpenAIClient("gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY") or "")

    agent = SimpleAgent(client)

    result = await agent.run("What is the capital of France?")
    print("Agent:", result)

asyncio.run(main())
