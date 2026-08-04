"""Tests for the response_format plumbing in LLM clients.

Covers:

- ``OllamaClient`` always passes ``format="json"`` to the underlying
  ``ollama.AsyncClient.chat`` (stubbed, no real Ollama server).
- ``OpenAIClient`` always passes ``response_format={"type": "json_object"}``
  (stubbed ``AsyncOpenAI``).
- Every ``client.chat(...)`` call site passes ``response_format`` so a
  future call cannot silently regress to prompt-only JSON.
"""

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from client.ollama_client import OllamaClient
from client.open_ai_client import OpenAIClient

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every non-provider call site that must pass ``response_format``.
# The provider implementations (ollama_client.py, open_ai_client.py) are
# excluded -- they are the providers, covered by the dedicated stub tests.
CALL_SITE_FILES = [
    "basic.py",
    "pipeline.py",
    "client/agents/jd_parsing.py",
    "client/agents/resume_parsing.py",
    "client/agents/gap_analysis.py",
    "client/agents/resume_rewrite.py",
    "client/agents/ats_compliance.py",
    "client/agents/tone_polishing.py",
    "client/agents/cover_letter.py",
    "client/format_detector.py",
]


class _StubAsyncClient:
    """Stub for ``ollama.AsyncClient`` that records chat kwargs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))


class _StubCompletions:
    """Stub for ``client.chat.completions`` recording create kwargs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )


class _StubAsyncOpenAI:
    """Stub for ``AsyncOpenAI`` exposing ``chat.completions.create``."""

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_StubCompletions())


def _chat_call_blocks(source: str) -> list[str]:
    """Extract the full text of each ``.chat(`` call (balanced parens).

    Args:
        source: The Python source text of a module.

    Returns:
        The text of every ``.chat(`` call from ``.chat(`` through its
        matching closing parenthesis.
    """
    blocks: list[str] = []
    for match in re.finditer(r"\.chat\(", source):
        start = match.start()
        depth = 0
        i = match.end() - 1
        while i < len(source):
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(source[start : i + 1])
                    break
            i += 1
    return blocks


class TestOllamaClientJsonMode:
    async def test_always_passes_format_json(self) -> None:
        client = OllamaClient("test-model")
        stub = _StubAsyncClient()
        client.client = stub  # type: ignore[assignment]

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert len(stub.calls) == 1
        assert stub.calls[0]["format"] == "json"
        assert stub.calls[0]["model"] == "test-model"
        assert stub.calls[0]["stream"] is False

    async def test_returns_message_content(self) -> None:
        client = OllamaClient("test-model")
        stub = _StubAsyncClient()
        client.client = stub  # type: ignore[assignment]

        result = await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert result == '{"ok": true}'


class TestOllamaClientStructuredOutputs:
    async def test_schema_dict_used_as_format_when_provided(self) -> None:
        client = OllamaClient("test-model")
        stub = _StubAsyncClient()
        client.client = stub  # type: ignore[assignment]
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
            json_schema=schema,
        )

        assert len(stub.calls) == 1
        assert stub.calls[0]["format"] == schema

    async def test_plain_json_mode_when_no_schema(self) -> None:
        client = OllamaClient("test-model")
        stub = _StubAsyncClient()
        client.client = stub  # type: ignore[assignment]

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert len(stub.calls) == 1
        assert stub.calls[0]["format"] == "json"


class TestOpenAIClientJsonMode:
    async def test_always_passes_response_format_json_object(self) -> None:
        client = OpenAIClient("test-model", api_key="test-key")
        stub = _StubAsyncOpenAI()
        client.client = stub  # type: ignore[assignment]

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert len(stub.chat.completions.calls) == 1
        assert stub.chat.completions.calls[0]["response_format"] == {
            "type": "json_object"
        }
        assert stub.chat.completions.calls[0]["model"] == "test-model"

    async def test_returns_message_content(self) -> None:
        client = OpenAIClient("test-model", api_key="test-key")
        stub = _StubAsyncOpenAI()
        client.client = stub  # type: ignore[assignment]

        result = await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert result == '{"ok": true}'


class TestOpenAIClientStructuredOutputs:
    async def test_schema_builds_json_schema_envelope(self) -> None:
        client = OpenAIClient("test-model", api_key="test-key")
        stub = _StubAsyncOpenAI()
        client.client = stub  # type: ignore[assignment]
        schema = {
            "title": "TestOutput",
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
        }

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
            json_schema=schema,
        )

        assert len(stub.chat.completions.calls) == 1
        response_format = stub.chat.completions.calls[0]["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["name"] == "TestOutput"
        assert response_format["json_schema"]["schema"] == schema
        assert response_format["json_schema"]["strict"] is True

    async def test_plain_json_mode_when_no_schema(self) -> None:
        client = OpenAIClient("test-model", api_key="test-key")
        stub = _StubAsyncOpenAI()
        client.client = stub  # type: ignore[assignment]

        await client.chat(
            purpose="purpose",
            prompt="prompt",
            output=["json"],
            rules=["rule"],
            inputs=["input"],
            response_format="json",
        )

        assert len(stub.chat.completions.calls) == 1
        assert stub.chat.completions.calls[0]["response_format"] == {
            "type": "json_object"
        }

    async def test_schema_name_falls_back_without_valid_title(self) -> None:
        from client.open_ai_client import _schema_name

        assert _schema_name({"title": "Test Output!"}) == "output"
        assert _schema_name({"type": "object"}) == "output"
        assert _schema_name({"title": "A" * 100}) == "A" * 64


class TestEveryCallSitePassesResponseFormat:
    def test_all_client_chat_call_sites_pass_response_format(self) -> None:
        for rel in CALL_SITE_FILES:
            source = (REPO_ROOT / rel).read_text(encoding="utf-8")
            blocks = _chat_call_blocks(source)
            assert blocks, f"{rel}: expected at least one client.chat call"
            for block in blocks:
                assert "response_format" in block, (
                    f"{rel}: call missing response_format: {block!r}"
                )

    def test_call_site_count_is_stable(self) -> None:
        """Guard against a new call site being added without the parameter."""
        total = 0
        for rel in CALL_SITE_FILES:
            source = (REPO_ROOT / rel).read_text(encoding="utf-8")
            total += len(_chat_call_blocks(source))
        assert total == 11
