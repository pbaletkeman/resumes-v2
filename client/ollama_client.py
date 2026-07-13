import ollama

from client.model_client import ModelClient

class OllamaClient(ModelClient):
    def __init__(self, model: str):
        self.model = model
        self.client = ollama.AsyncClient()

    async def chat(self, prompt: str) -> str:
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"]
