"""Tests for the shared JSON helpers in ``client.json_utils``.

Covers:

- ``parse_json_response``: plain JSON, markdown-fenced JSON, invalid
  input, and the plain-text cover letter fallback.
- ``load_json_safe``: the guarded JSON-object parser used by agent
  post-validation helpers (fence stripping, failure => None).
- ``model_to_json_schema``: builds a strict-mode provider-ready schema
  from a Pydantic model (``additionalProperties: false``, all properties
  required, nested ``$defs`` handled).
"""

from pydantic import BaseModel

from client.json_utils import (
    load_json_safe,
    model_to_json_schema,
    parse_json_response,
)


class TestParseJsonResponse:
    async def test_plain_json(self) -> None:
        assert parse_json_response('{"key": "value"}') == {"key": "value"}

    async def test_json_with_whitespace(self) -> None:
        assert parse_json_response('  {"key": "value"}  ') == {"key": "value"}

    async def test_fenced_json(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        assert parse_json_response(raw) == {"key": "value"}

    async def test_fenced_json_without_language_tag(self) -> None:
        raw = '```\n{"key": "value"}\n```'
        assert parse_json_response(raw) == {"key": "value"}

    async def test_fenced_json_with_surrounding_text(self) -> None:
        raw = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        assert parse_json_response(raw) == {"key": "value"}

    async def test_invalid_json_returns_none(self) -> None:
        assert parse_json_response("not json at all") is None

    async def test_empty_input_returns_none(self) -> None:
        assert parse_json_response("") is None

    async def test_invalid_fenced_json_returns_none(self) -> None:
        raw = "```json\nthis is not valid json\n```"
        assert parse_json_response(raw) is None

    async def test_plain_text_fallback_used_when_substantial(self) -> None:
        raw = "Dear hiring manager, " + ("thank you for your time. " * 4)
        assert parse_json_response(raw, plain_text_fallback="cover_letter") == {
            "cover_letter": raw.strip()
        }

    async def test_plain_text_fallback_ignored_when_short(self) -> None:
        assert (
            parse_json_response("short text", plain_text_fallback="cover_letter")
            is None
        )

    async def test_plain_text_fallback_not_used_without_option(self) -> None:
        raw = "Dear hiring manager, " + ("thank you for your time. " * 4)
        assert parse_json_response(raw) is None


class TestLoadJsonSafe:
    async def test_plain_object(self) -> None:
        assert load_json_safe('{"key": "value"}') == {"key": "value"}

    async def test_fenced_object(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        assert load_json_safe(raw) == {"key": "value"}

    async def test_fenced_object_with_surrounding_text(self) -> None:
        raw = 'Result:\n```json\n{"key": "value"}\n```\nDone.'
        assert load_json_safe(raw) == {"key": "value"}

    async def test_invalid_json_returns_none(self) -> None:
        assert load_json_safe("not json at all") is None

    async def test_malformed_nested_blob_returns_none(self) -> None:
        raw = '{"summary": "x", "experience": '
        assert load_json_safe(raw) is None

    async def test_empty_input_returns_none(self) -> None:
        assert load_json_safe("") is None
        assert load_json_safe("   \t\n  ") is None

    async def test_non_object_json_returns_none(self) -> None:
        # Arrays and scalars are valid JSON but not the objects the
        # post-validation helpers expect.
        assert load_json_safe("[1, 2, 3]") is None
        assert load_json_safe('"just a string"') is None

    async def test_fenced_non_object_returns_none(self) -> None:
        raw = '```json\n["a", "b"]\n```'
        assert load_json_safe(raw) is None


class _SimpleOutput(BaseModel):
    name: str = ""
    skills: list[str] = []


class _DictOutput(BaseModel):
    signals: dict[str, str] = {}


class _NestedOutput(BaseModel):
    summary: str = ""
    items: list[_SimpleOutput] = []


class TestModelToJsonSchema:
    async def test_flat_model_schema(self) -> None:
        schema = model_to_json_schema(_SimpleOutput)

        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"name", "skills"}
        assert schema["properties"]["skills"]["type"] == "array"
        assert schema["properties"]["name"]["type"] == "string"

    async def test_free_form_dict_keeps_value_schema(self) -> None:
        """dict[str, str] fields must not be forced to empty objects."""
        schema = model_to_json_schema(_DictOutput)

        assert schema["type"] == "object"
        # The model object has defined properties -> hardened as usual.
        assert schema["additionalProperties"] is False
        # The free-form dict field keeps its value schema instead of being
        # overwritten with additionalProperties: false (which would force
        # the model to emit an empty object).
        signals = schema["properties"]["signals"]
        assert signals["type"] == "object"
        assert signals["additionalProperties"] == {"type": "string"}

    async def test_nested_model_schema_strictness(self) -> None:
        schema = model_to_json_schema(_NestedOutput)

        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"summary", "items"}

        # The nested $defs entries must also be strict-mode compliant.
        defs = schema["$defs"]
        assert defs["_SimpleOutput"]["additionalProperties"] is False
        assert set(defs["_SimpleOutput"]["required"]) == {"name", "skills"}

    async def test_schema_is_fresh_per_call(self) -> None:
        first = model_to_json_schema(_SimpleOutput)
        second = model_to_json_schema(_SimpleOutput)
        assert first is not second
        assert first == second
