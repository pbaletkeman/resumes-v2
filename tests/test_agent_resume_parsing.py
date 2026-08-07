"""Agent 2 (Resume Parsing) contract tests with a fake ModelClient (Phase 7.2.1.2).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation -> regex fallback contract against canned ``chat()`` responses.
No real LLM is contacted.
"""

import json

from client.agents.resume_parsing import ResumeParsingAgent
from client.errors import LLMConnectionError
from client.models import ResumeParsingOutput


def _valid_payload() -> str:
    return json.dumps(
        {
            "summary": "Backend engineer with 5 years experience.",
            "skills": ["Python", "PostgreSQL"],
            "experience": [
                {
                    "title": "Staff Engineer",
                    "company": "Acme",
                    "dates": "2020-2024",
                    "responsibilities": ["Led platform team"],
                },
                {
                    "title": "Senior Engineer",
                    "company": "Globex",
                    "dates": "2016-2020",
                    "responsibilities": ["Built microservices"],
                },
            ],
            "projects": ["CLI tool"],
            "certifications": ["AWS Solutions Architect"],
            "education": ["B.Sc. Computer Science"],
            "name": "Jane Doe",
            "phone": "555-1234",
            "email": "jane@example.com",
            "linkedin": "linkedin.com/in/jane",
            "github": "github.com/jane",
        }
    )


class TestResumeParsingHappyPath:
    async def test_valid_parse(self, fake_client, sample_resume) -> None:
        client = fake_client(response=_valid_payload())
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert result.name == "Jane Doe"
        assert result.email == "jane@example.com"
        assert len(result.experience) == 2

    async def test_experience_sorted_most_recent_first(
        self, fake_client, sample_resume
    ) -> None:
        client = fake_client(response=_valid_payload())
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        companies = [entry.company for entry in result.experience]
        assert companies == ["Acme", "Globex"]

    async def test_chat_contract(self, fake_client, sample_resume) -> None:
        client = fake_client(response=_valid_payload())
        agent = ResumeParsingAgent(client)
        await agent.run({"resume": sample_resume})

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["inputs"] == [sample_resume]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)


class TestResumeParsingFallback:
    async def test_malformed_json_falls_back_to_regex(
        self, fake_client, sample_resume
    ) -> None:
        client = fake_client(response="not json at all")
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert result.name == "Peter Letkeman"
        assert len(client.calls) == 2

    async def test_connection_error_falls_back_to_regex(
        self, fake_client, sample_resume
    ) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert len(result.experience) >= 1
        assert len(client.calls) == 2

    async def test_missing_experience_key_defaults_to_empty(
        self, fake_client, sample_resume
    ) -> None:
        payload = json.dumps(
            {
                "summary": "Engineer.",
                "skills": ["Python"],
                "name": "Jane Doe",
            }
        )
        client = fake_client(response=payload)
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert result.experience == []
        assert result.skills == ["Python"]


class TestResumeParsingCoercion:
    async def test_skills_list_of_dicts_coerced(
        self, fake_client, sample_resume
    ) -> None:
        payload = json.dumps(
            {
                "summary": "Engineer.",
                "skills": [{"0": "Python"}, {"1": "Rust"}],
                "experience": [],
                "name": "Jane Doe",
            }
        )
        client = fake_client(response=payload)
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert "Python" in result.skills
        assert "Rust" in result.skills

    async def test_experience_list_of_strings_coerced(
        self, fake_client, sample_resume
    ) -> None:
        payload = json.dumps(
            {
                "summary": "Engineer.",
                "skills": ["Python"],
                "experience": ["Staff Engineer | Acme | 2020-2024"],
                "name": "Jane Doe",
            }
        )
        client = fake_client(response=payload)
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert len(result.experience) == 1
        assert result.experience[0].responsibilities == [
            "Staff Engineer | Acme | 2020-2024"
        ]


class TestResumeParsingRetry:
    async def test_strict_retry_round_after_first_exception(
        self, fake_client, sample_resume
    ) -> None:
        client = fake_client(response=_valid_payload(), fail_calls=1)
        agent = ResumeParsingAgent(client)
        result = await agent.run({"resume": sample_resume})

        assert isinstance(result, ResumeParsingOutput)
        assert result.name == "Jane Doe"
        assert len(client.calls) == 2
