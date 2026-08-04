"""
json_utils.py
Shared JSON helpers for LLM responses and provider JSON schemas.

Consolidates the per-agent ``_parse_json`` / ``_safe_json`` helpers into a
single ``parse_json_response`` and provides ``model_to_json_schema`` for
provider-native Structured Outputs (see resume-todo.md §8.7 / §8.8).
"""

import json
import logging
import re
from typing import Any, cast

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_response(
    raw: str,
    *,
    plain_text_fallback: str | None = None,
) -> dict[str, Any] | None:
    """Best-effort JSON extraction from an LLM response.

    Handles responses wrapped in markdown fences (`` ```json ... ``` ``).
    When ``plain_text_fallback`` is set and the response is not valid
    JSON, a substantial plain-text response (>50 chars) is treated as the
    value for that key instead of failing (used by the cover letter agent,
    whose content is naturally free text).

    Args:
        raw: The raw LLM response text.
        plain_text_fallback: If provided, fall back to ``{key: text}``
            when the response is not valid JSON and is substantial.

    Returns:
        A parsed dict, or ``None`` on failure.
    """
    text = raw.strip()
    logger.debug("JSON parse input: %s", text[:300] if text else "<empty>")
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed: dict[str, Any] = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        if plain_text_fallback is not None and len(text) > 50:
            logger.debug(
                "Failed to parse as JSON, treating as plain text %s",
                plain_text_fallback,
            )
            return {plain_text_fallback: text}
        logger.warning("Failed to parse LLM response as JSON")
        return None


def model_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build a provider-ready JSON Schema from a Pydantic model.

    Wraps ``model.model_json_schema()`` and post-processes it for
    Structured Outputs strict mode: ``additionalProperties: false`` on
    every object and every property listed in ``required``.

    Returns the raw JSON Schema dict (with a ``title`` from Pydantic).
    The caller's provider client is responsible for wrapping it in the
    provider-specific envelope.

    Args:
        model: A Pydantic model class (e.g. ``JDParsingOutput``).

    Returns:
        A JSON Schema dict suitable for passing as Ollama ``format`` or
        OpenAI ``response_format={"type": "json_schema", ...}``.
    """
    schema = model.model_json_schema()
    _make_schema_strict(schema)
    return schema


def _make_schema_strict(schema: dict[str, Any]) -> None:
    """Post-process a JSON schema for strict mode in place.

    OpenAI Structured Outputs strict mode rejects schemas with optional
    properties, so every defined property is moved into ``required`` and
    ``additionalProperties`` is set to ``false`` on objects with an
    explicit ``properties`` map (including nested ``$defs``).

    Free-form dict fields (``dict[str, str]``) have no ``properties`` —
    Pydantic emits ``{"type": "object", "additionalProperties": {...}}``.
    Those keep their value schema; setting ``additionalProperties: false``
    on them would force the model to emit an empty object.

    Args:
        schema: A JSON Schema dict, mutated in place.
    """
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties")
        if isinstance(properties, dict):
            typed_properties = cast(dict[str, Any], properties)
            schema["required"] = sorted(typed_properties.keys())
            schema["additionalProperties"] = False
            for prop_schema in typed_properties.values():
                if isinstance(prop_schema, dict):
                    _make_schema_strict(cast(dict[str, Any], prop_schema))
    elif schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            _make_schema_strict(cast(dict[str, Any], items))

    defs = schema.get("$defs")
    if isinstance(defs, dict):
        typed_defs = cast(dict[str, Any], defs)
        for definition in typed_defs.values():
            if isinstance(definition, dict):
                _make_schema_strict(cast(dict[str, Any], definition))
