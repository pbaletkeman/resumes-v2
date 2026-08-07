"""Agent 1 (JD Parsing) contract tests with a fake ModelClient (Phase 7.2.1.1).

Verifies the documented ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` ->
Pydantic validation -> regex fallback contract against canned ``chat()``
responses.  No real LLM is contacted.
"""

import json

import pytest

from client.agents.jd_parsing import _STRICT_RULES, _SYSTEM_PROMPT, JDParsingAgent
from client.errors import LLMConnectionError
from client.models import JDParsingOutput

JD_TEXT = (
    "Acme Corporation is hiring a Senior Backend Engineer.\n"
    "Requirements: Python, PostgreSQL, Docker.\n"
    "Responsibilities: design REST APIs, optimize queries.\n"
)


def _valid_payload() -> str:
    return json.dumps(
        {
            "role_title": "Senior Backend Engineer",
            "company_name": "Acme Corporation",
            "seniority_level": "senior",
            "required_skills": ["Python", "PostgreSQL"],
            "preferred_skills": ["Docker"],
            "responsibilities": ["Design REST APIs", "Optimize queries"],
            "keywords": ["python", "postgres"],
            "industry_terms": ["fintech"],
            "company_signals": {"company_name": "Acme Corporation"},
        }
    )


@pytest.fixture
def jd_inputs() -> dict[str, str]:
    return {"job_description": JD_TEXT}


class TestJDParsingHappyPath:
    async def test_valid_json_returns_parsed_output(
        self, fake_client, jd_inputs
    ) -> None:
        client = fake_client(response=_valid_payload())
        agent = JDParsingAgent(client)
        result = await agent.run(jd_inputs)

        assert isinstance(result, JDParsingOutput)
        assert result.role_title == "Senior Backend Engineer"
        assert result.company_name == "Acme Corporation"
        assert result.required_skills == ["Python", "PostgreSQL"]

    async def test_chat_contract(self, fake_client, jd_inputs) -> None:
        client = fake_client(response=_valid_payload())
        agent = JDParsingAgent(client)
        await agent.run(jd_inputs)

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["purpose"] == _SYSTEM_PROMPT
        assert call["output"] == ["json"]
        assert call["inputs"] == [JD_TEXT]
        assert call["response_format"] == "json"
        assert call["json_schema"] is not None
        assert isinstance(call["json_schema"], dict)

    async def test_company_name_synced_into_signals(
        self, fake_client, jd_inputs
    ) -> None:
        client = fake_client(response=_valid_payload())
        agent = JDParsingAgent(client)
        result = await agent.run(jd_inputs)

        assert result.company_signals.get("company_name") == "Acme Corporation"


class TestJDParsingFallback:
    async def test_malformed_json_falls_back_to_regex(
        self, fake_client, jd_inputs
    ) -> None:
        client = fake_client(response="this is not json")
        agent = JDParsingAgent(client)
        result = await agent.run(jd_inputs)

        assert isinstance(result, JDParsingOutput)
        assert len(client.calls) == 2  # both LLM attempts consumed

    async def test_connection_error_falls_back_to_regex(
        self, fake_client, jd_inputs
    ) -> None:
        client = fake_client(error=LLMConnectionError("ollama down"))
        agent = JDParsingAgent(client)
        result = await agent.run(jd_inputs)

        assert isinstance(result, JDParsingOutput)
        assert len(client.calls) == 2


class TestJDParsingRetry:
    async def test_strict_retry_round_after_first_exception(
        self, fake_client, jd_inputs
    ) -> None:
        client = fake_client(response=_valid_payload(), fail_calls=1)
        agent = JDParsingAgent(client)
        result = await agent.run(jd_inputs)

        assert isinstance(result, JDParsingOutput)
        assert result.role_title == "Senior Backend Engineer"
        assert len(client.calls) == 2
        assert client.calls[0]["rules"] != _STRICT_RULES
        assert client.calls[1]["rules"] == _STRICT_RULES


class TestJDParsingEmptyInput:
    async def test_empty_job_description_returns_defaults(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = JDParsingAgent(client)
        result = await agent.run({"job_description": ""})

        assert isinstance(result, JDParsingOutput)
        assert result.role_title == ""
        assert client.calls == []
