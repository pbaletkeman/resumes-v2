"""Shared LLM-call + validation scaffolding for the LLM-only agents.

Gap Analysis, ATS Compliance, and Tone Polishing follow the same
``_try_llm`` shape: build the prompt, call ``client.chat`` once, parse the
JSON response, and validate it into the agent's output model.  Only the
prompt strings and the output model differ between agents.

This module holds that shared scaffolding so each agent file keeps only
its agent-specific prompt/rules and its post-processing step.  The
two-attempt retry loop stays in each agent's ``run()`` because the
deterministic fallback differs per agent (empty model vs. pass-through).
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.json_utils import parse_json_response
from client.model_client import ModelClient

logger = logging.getLogger(__name__)


def serialize(value: Any) -> str:
    """Serialize a Pydantic model or dict to a JSON string.

    Args:
        value: A Pydantic model, a dict, or any other value.

    Returns:
        A JSON string (``str(value)`` as a last resort).
    """
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(), indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, default=str)
    return str(value)


async def chat_and_validate[T: BaseModel](
    client: ModelClient,
    *,
    purpose: str,
    prompt: str,
    rules: list[str],
    inputs: list[str],
    json_schema: dict[str, Any],
    output_model: type[T],
    agent_label: str,
    strict: bool,
) -> T | None:
    """Run one chat call and validate the response into ``output_model``.

    Encapsulates the scaffolding every LLM-only agent repeats: attempt
    logging, provider-error handling (returns ``None``), response logging,
    JSON parsing, and Pydantic validation with a verbose error log.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
        purpose: System-level role/persona for the call.
        prompt: The agent-specific user prompt.
        rules: Constraints passed to the model.
        inputs: Serialized context data for the model.
        json_schema: Strict-mode output schema for Structured Outputs.
        output_model: The agent's Pydantic output type to validate into.
        agent_label: Human-readable agent name used in log messages.
        strict: Whether this is the stricter retry attempt.

    Returns:
        A validated instance of ``output_model``, or ``None`` on failure.
    """
    logger.debug(
        "LLM %s attempt=%s prompt_len=%d",
        agent_label,
        "strict" if strict else "normal",
        len(prompt),
    )

    try:
        raw = await client.chat(
            purpose=purpose,
            prompt=prompt,
            output=["json"],
            rules=rules,
            inputs=inputs,
            response_format="json",
            json_schema=json_schema,
        )
    except (
        NotImplementedError,
        LLMConnectionError,
        LLMResponseError,
        LLMTimeoutError,
    ):
        logger.exception(
            "LLM %s failed (attempt %s)",
            agent_label,
            "strict" if strict else "normal",
        )
        return None

    logger.debug("LLM %s response: %s", agent_label, raw[:200] if raw else "<empty>")
    data = parse_json_response(raw)
    if data is None:
        return None

    try:
        return output_model(**data)
    except ValidationError as exc:
        data_keys = list(data.keys()) if hasattr(data, "keys") else str(type(data))
        data_preview = (
            json.dumps(data, indent=2, default=str)[:500] if data else "<None>"
        )
        logger.warning(
            "LLM %s output failed Pydantic validation: %s\n"
            "  parsed data keys: %s\n"
            "  parsed data: %s",
            agent_label,
            exc,
            data_keys,
            data_preview,
        )
        return None
