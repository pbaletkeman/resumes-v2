"""Agent 6 (Tone Polishing) contract tests with a fake ModelClient (Phase 7.2.1.6).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation contract against canned ``chat()`` responses.  No real LLM is
contacted.
"""

import json

from client.agents.tone_polishing import TonePolishingAgent
from client.errors import LLMConnectionError
from client.models import TonePolishingOutput

RESUME_TEXT = (
    "Senior engineer with 10+ years experience.\n"
    "Skills: Python, Rust, Kubernetes\n"
    "Led platform team at Acme Corp.\n"
)


class TestTonePolishingHappyPath:
    async def test_polished_resume_returned(self, fake_client) -> None:
        client = fake_client(response=json.dumps({"polished_resume": "Polished text."}))
        agent = TonePolishingAgent(client)
        result = await agent.run({"ats_optimized_resume": RESUME_TEXT})

        assert isinstance(result, TonePolishingOutput)
        assert result.polished_resume == "Polished text."

    async def test_chat_contract(self, fake_client) -> None:
        client = fake_client(response=json.dumps({"polished_resume": "x"}))
        agent = TonePolishingAgent(client)
        await agent.run({"ats_optimized_resume": RESUME_TEXT})

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)
        assert call["inputs"] == [RESUME_TEXT]


class TestTonePolishingCoercion:
    async def test_empty_polished_resume_filled_from_input(self, fake_client) -> None:
        client = fake_client(response=json.dumps({"polished_resume": "  "}))
        agent = TonePolishingAgent(client)
        result = await agent.run({"ats_optimized_resume": RESUME_TEXT})

        assert isinstance(result, TonePolishingOutput)
        assert result.polished_resume == RESUME_TEXT


class TestTonePolishingFallback:
    async def test_connection_error_returns_input_unchanged(self, fake_client) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = TonePolishingAgent(client)
        result = await agent.run({"ats_optimized_resume": RESUME_TEXT})

        assert isinstance(result, TonePolishingOutput)
        assert result.polished_resume == RESUME_TEXT
        assert len(client.calls) == 2

    async def test_empty_input_returns_defaults(self, fake_client) -> None:
        client = fake_client(response=json.dumps({"polished_resume": "x"}))
        agent = TonePolishingAgent(client)
        result = await agent.run({"ats_optimized_resume": ""})

        assert isinstance(result, TonePolishingOutput)
        assert result.polished_resume == ""
        assert client.calls == []


class TestTonePolishingRetry:
    async def test_strict_retry_round_after_first_exception(self, fake_client) -> None:
        client = fake_client(
            response=json.dumps({"polished_resume": "Polished text."}), fail_calls=1
        )
        agent = TonePolishingAgent(client)
        result = await agent.run({"ats_optimized_resume": RESUME_TEXT})

        assert isinstance(result, TonePolishingOutput)
        assert result.polished_resume == "Polished text."
        assert len(client.calls) == 2
