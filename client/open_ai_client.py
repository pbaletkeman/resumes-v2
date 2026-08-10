"""
open_ai_client.py
Concrete ModelClient implementation for the OpenAI API.

Sends structured prompts to any OpenAI-compatible model (GPT-4o, GPT-4o-mini, etc.)
via the official openai Python SDK.

The user prompt is built by the shared ``client.model_client.build_task_prompt``
helper, so both providers send identical instructions.
"""

import asyncio
import logging
import time
from typing import Any, cast

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
from client.model_client import ModelClient, build_task_prompt

logger = logging.getLogger(__name__)

# OpenAI Structured Outputs requires a schema name matching ^[a-zA-Z0-9_-]{1,64}$.
_DEFAULT_SCHEMA_NAME = "output"


def _schema_name(json_schema: dict[str, Any]) -> str:
    """Derive a valid OpenAI schema name from a JSON Schema dict.

    Prefers the ``title`` field (Pydantic model name), falling back to a
    fixed ``"output"`` when the title is missing or contains characters
    OpenAI rejects.

    Args:
        json_schema: A JSON Schema dict (e.g. from ``model_to_json_schema``).

    Returns:
        A schema name safe for OpenAI Structured Outputs.
    """
    title = json_schema.get("title")
    if isinstance(title, str) and title.replace("_", "a").replace("-", "a").isalnum():
        return title[:64]
    return _DEFAULT_SCHEMA_NAME


def _response_format_value(json_schema: dict[str, Any] | None) -> dict[str, Any]:
    """Build the ``response_format`` value to pass to the OpenAI SDK.

    With no schema the provider runs in plain JSON mode
    (``{"type": "json_object"}``).  With a JSON Schema dict the provider
    enters OpenAI Structured Outputs via the ``json_schema`` envelope,
    which requires a name, the schema itself, and ``strict: True``.

    Args:
        json_schema: Optional JSON Schema dict from ``model_to_json_schema``.

    Returns:
        The ``response_format`` dict for the OpenAI SDK.
    """
    if json_schema is not None:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": _schema_name(json_schema),
                "schema": json_schema,
                "strict": True,
            },
        }
    return {"type": "json_object"}


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
        response_format: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Send a structured prompt to the OpenAI model and return the response.

        Builds a compact prompt from the provided parameters, sends it as
        a system + user message pair, and returns the model's text output.
        JSON mode is always on via ``response_format={"type": "json_object"}``
        unless a JSON Schema is provided, in which case OpenAI Structured
        Outputs are requested via ``response_format={"type": "json_schema"}``.

        Args:
            purpose: System-level role or persona for this call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.
            response_format: Requested provider-native response mode.
                ``"json"`` is the only supported value and must be passed to
                every call; free-text responses are not part of the contract.
            json_schema: Optional JSON Schema dict (from
                ``client.json_utils.model_to_json_schema``) for OpenAI
                Structured Outputs. When provided,
                ``response_format={"type": "json_schema", ...}`` is used
                instead of ``json_object``. Defaults to ``None``.

        Returns:
            The model's text response.

        Raises:
            LLMConnectionError: If the OpenAI API cannot be reached.
            LLMResponseError: If authentication fails, rate limit is exceeded,
                or the API returns an error.
            LLMTimeoutError: If the model does not respond within 90 seconds.
        """
        task = build_task_prompt(prompt, output, rules, inputs)

        # response_format="json" is the only supported mode; a JSON Schema
        # dict opts in to OpenAI Structured Outputs (json_schema mode).
        response_format_value = _response_format_value(json_schema)

        logger.debug(
            "OpenAI request: model=%s format=%s prompt_len=%d messages=2",
            self.model,
            response_format_value["type"],
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
                    response_format=cast(Any, response_format_value),
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
