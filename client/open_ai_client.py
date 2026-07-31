"""
open_ai_client.py
Concrete ModelClient implementation for the OpenAI API.

Sends structured prompts to any OpenAI-compatible model (GPT-4o, GPT-4o-mini, etc.)
via the official openai Python SDK.
"""

import asyncio
import logging
import time

from openai import (
    APIConnectionError,
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion

from client.errors import (
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
)
from client.model_client import ModelClient

logger = logging.getLogger(__name__)


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
            LLMConnectionError: If the OpenAI API cannot be reached.
            LLMResponseError: If authentication fails, rate limit is exceeded,
                or the API returns an error.
            LLMTimeoutError: If the model does not respond within 90 seconds.
        """
        parts = [f"Task: {prompt}"]

        if output:
            parts.append(f"Output format: {', '.join(output)}")

        if rules:
            parts.append(f"Rules: {' | '.join(rules)}")

        if inputs:
            parts.append(f"Input: {' | '.join(inputs)}")

        task = "\n".join(parts)

        logger.debug(
            "OpenAI request: model=%s prompt_len=%d messages=2",
            self.model,
            len(task),
        )
        start = time.monotonic()

        try:
            response: ChatCompletion = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": purpose},
                        {"role": "user", "content": task},
                    ],
                ),
                timeout=90,
            )
        except AuthenticationError as e:
            logger.warning("OpenAI auth failed: %s", e, exc_info=True)
            raise LLMResponseError(
                f"Invalid OpenAI API key for model '{self.model}'"
            ) from e
        except RateLimitError as e:
            logger.warning("OpenAI rate limit exceeded: %s", e, exc_info=True)
            raise LLMResponseError(
                f"OpenAI rate limit exceeded for model '{self.model}'"
            ) from e
        except APIConnectionError as e:
            logger.warning("OpenAI connection failed: %s", e, exc_info=True)
            raise LLMConnectionError(
                f"Cannot connect to OpenAI API for model '{self.model}'"
            ) from e
        except APIError as e:
            logger.warning("OpenAI API error: %s", e, exc_info=True)
            raise LLMResponseError(
                f"OpenAI API error for model '{self.model}': {e}"
            ) from e
        except TimeoutError as e:
            logger.warning(
                "OpenAI timeout after 90s for model %s",
                self.model,
                exc_info=True,
            )
            raise LLMTimeoutError(
                f"OpenAI model '{self.model}' did not respond within 90 seconds"
            ) from e

        content = response.choices[0].message.content
        if content is None:
            logger.warning("OpenAI returned empty response for model %s", self.model)
            raise LLMResponseError(
                f"OpenAI model '{self.model}' returned an empty response"
            )

        elapsed = time.monotonic() - start
        logger.debug(
            "OpenAI response: model=%s response_len=%d latency=%.1fs",
            self.model,
            len(content),
            elapsed,
        )
        return content
