"""
json_utils.py
Shared JSON helpers for LLM responses and provider JSON schemas.

Three functions every agent relies on:

- ``parse_json_response``: best-effort conversion of a raw LLM response
  string into a dict.  This is the single replacement for the per-agent
  ``_parse_json`` / ``_safe_json`` helpers, so all agents parse LLM
  output the same way (fence stripping, JSON decode, cover-letter
  fallback, logging).
- ``load_json_safe``: the guarded ``json.loads`` used by the agent
  post-validation helpers when they re-parse a JSON blob that an earlier
  agent embedded in a string field.  Returns ``None`` instead of raising,
  so every validation site shares one obvious "parse or fail" path.
- ``model_to_json_schema``: builds a strict-mode, provider-ready JSON
  Schema from a Pydantic output model.  Each agent passes the result to
  ``ModelClient.chat(json_schema=...)`` so providers can run Structured
  Outputs instead of plain JSON mode.
"""

import json
import logging
import re
from typing import Any, cast

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


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
    fence_match = _JSON_FENCE_RE.search(text)
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


@staticmethod
def load_json_safe(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from a string, returning None on any failure.

    This is the single shared replacement for the repeated guarded
    ``try: json.loads(...) / except (json.JSONDecodeError, TypeError)``
    blocks in the agent post-validation helpers.  It never raises.

    Behavior:
    - Strips a surrounding markdown fence (`` ```json ... ``` ``) when
      present, mirroring ``parse_json_response``.
    - Returns ``None`` when the text is not valid JSON, when the parsed
      value is not a JSON object (e.g. a list or scalar), or when
      ``text`` is empty.
    - Returns the parsed dict otherwise.

    ``TypeError`` is also guarded because ``json.loads`` raises it for
    non-string inputs (defensive: callers pass LLM-produced values).

    Args:
        text: Raw text expected to contain a JSON object.

    Returns:
        The parsed dict, or ``None`` when parsing fails.
    """
    if not text.strip():
        return None
    candidate = text.strip()
    fence_match = _JSON_FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()
    try:
        parsed: Any = json.loads(candidate)
    except json.JSONDecodeError, TypeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return cast(dict[str, Any], parsed)


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
