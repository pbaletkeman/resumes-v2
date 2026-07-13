"""
simple.py
A simple example of using the Ollama API to create an agent that responds to user promptsq
"""

import asyncio
import ollama
from ollama import ChatResponse

class SimpleAgent:
    """A simple agent that uses the Ollama API to respond to user prompts."""
    def __init__(self, model: str):
        self.model = model

    async def run(self, prompt: str) -> str:
        """Run the agent with the given prompt and return the response."""
        client = ollama.AsyncClient()

        response: ChatResponse = await client.chat(
            model="qwen3.5",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response["message"]["content"]


async def main() -> None:
    """Main function to run the simple agent."""
    agent = SimpleAgent("qwen3.5")
    result = await agent.run("What is the capital of France?")
    print("Agent:", result)

asyncio.run(main())
