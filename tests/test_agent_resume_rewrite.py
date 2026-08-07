"""Agent 4 (Resume Rewrite) contract tests with a fake ModelClient (Phase 7.2.1.4).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation -> post-validation (Phase 4.3.A) contract against canned
``chat()`` responses.  No real LLM is contacted.
"""

import json

from client.agents.resume_rewrite import _SCHEMA_HINT, _STRICT_RULES, ResumeRewriteAgent
from client.errors import LLMConnectionError
from client.models import RewriteOutput


def _resume_payload() -> dict[str, object]:
    return {
        "summary": "Senior engineer with 10+ years experience.",
        "skills": ["Python", "Rust", "Kubernetes"],
        "experience": [
            {
                "title": "Staff Engineer",
                "company": "Acme Corp",
                "dates": "2020-2024",
                "responsibilities": ["Led platform team"],
                "achievements": ["Reduced costs 40%"],
                "metrics": ["$2M annual savings"],
            },
            {
                "title": "Senior Engineer",
                "company": "Globex",
                "dates": "2016-2020",
                "responsibilities": ["Built microservices"],
                "achievements": [],
                "metrics": [],
            },
        ],
        "projects": ["Open-source CLI tool"],
        "certifications": ["AWS Solutions Architect"],
        "education": ["B.Sc. Computer Science, U of T"],
    }


def _strategy_payload() -> dict[str, object]:
    return {
        "missing_skills": ["Kubernetes"],
        "keyword_strategy": ["kubernetes", "microservices"],
        "recommended_emphasis": ["platform work"],
    }


def _valid_payload() -> str:
    return json.dumps(
        {
            "summary": "Senior engineer with 10+ years experience.",
            "skills": ["Python", "Rust", "Kubernetes"],
            "experience": [
                {
                    "title": "Staff Engineer",
                    "company": "Acme Corp",
                    "dates": "2020-2024",
                    "responsibilities": ["Led platform team"],
                    "achievements": ["Reduced costs 40%"],
                    "metrics": ["$2M annual savings"],
                },
                {
                    "title": "Senior Engineer",
                    "company": "Globex",
                    "dates": "2016-2020",
                    "responsibilities": ["Built microservices"],
                    "achievements": [],
                    "metrics": [],
                },
            ],
            "projects": ["Open-source CLI tool"],
            "certifications": ["AWS Solutions Architect"],
            "education": ["B.Sc. Computer Science, U of T"],
        }
    )


def _inputs() -> dict[str, object]:
    return {
        "parsed_resume": _resume_payload(),
        "tailoring_strategy": _strategy_payload(),
        "parsed_job_description": {"required_skills": ["Python", "Kubernetes"]},
    }


class TestResumeRewriteHappyPath:
    async def test_valid_rewrite(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert "Python" in result.skills
        assert len(result.experience) == 2

    async def test_chat_contract(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ResumeRewriteAgent(client)
        await agent.run(_inputs())

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)
        assert len(call["inputs"]) == 2


class TestResumeRewritePostValidation:
    async def test_out_of_order_experience_is_sorted(self, fake_client) -> None:
        payload = json.dumps(
            {
                "summary": "Senior engineer.",
                "skills": ["Python", "Rust", "Kubernetes"],
                "experience": [
                    {
                        "title": "Senior Engineer",
                        "company": "Globex",
                        "dates": "2016-2020",
                        "responsibilities": ["Built microservices"],
                        "achievements": [],
                        "metrics": [],
                    },
                    {
                        "title": "Staff Engineer",
                        "company": "Acme Corp",
                        "dates": "2020-2024",
                        "responsibilities": ["Led platform team"],
                        "achievements": [],
                        "metrics": [],
                    },
                ],
                "projects": [],
                "certifications": ["AWS Solutions Architect"],
                "education": [],
            }
        )
        client = fake_client(response=payload)
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        companies = [entry.company for entry in result.experience]
        assert companies == ["Acme Corp", "Globex"]

    async def test_unparseable_dates_sink_to_tail(self, fake_client) -> None:
        payload = json.dumps(
            {
                "summary": "Senior engineer.",
                "skills": ["Python", "Rust", "Kubernetes"],
                "experience": [
                    {
                        "title": "Staff Engineer",
                        "company": "Acme Corp",
                        "dates": "2020-2024",
                        "responsibilities": ["Led platform team"],
                        "achievements": [],
                        "metrics": [],
                    },
                    {
                        "title": "Senior Engineer",
                        "company": "Globex",
                        "dates": "Present",
                        "responsibilities": ["Built microservices"],
                        "achievements": [],
                        "metrics": [],
                    },
                ],
                "projects": [],
                "certifications": ["AWS Solutions Architect"],
                "education": [],
            }
        )
        client = fake_client(response=payload)
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert result.experience[0].company == "Acme Corp"
        assert result.experience[1].company == "Globex"

    async def test_fabricated_skill_dropped(self, fake_client) -> None:
        payload = json.dumps(
            {
                "summary": "Senior engineer.",
                "skills": ["Python", "Rust", "Kubernetes", "COBOL"],
                "experience": [
                    {
                        "title": "Staff Engineer",
                        "company": "Acme Corp",
                        "dates": "2020-2024",
                        "responsibilities": ["Led platform team"],
                        "achievements": [],
                        "metrics": [],
                    },
                    {
                        "title": "Senior Engineer",
                        "company": "Globex",
                        "dates": "2016-2020",
                        "responsibilities": ["Built microservices"],
                        "achievements": [],
                        "metrics": [],
                    },
                ],
                "projects": [],
                "certifications": ["AWS Solutions Architect"],
                "education": [],
            }
        )
        client = fake_client(response=payload)
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert "COBOL" not in result.skills


class TestResumeRewriteFallback:
    async def test_connection_error_falls_back_to_parsed_resume(
        self, fake_client
    ) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert len(result.experience) == 2
        assert len(client.calls) == 2

    async def test_fabricated_company_rejected(self, fake_client) -> None:
        payload = json.dumps(
            {
                "summary": "Senior engineer.",
                "skills": ["Python", "Rust", "Kubernetes"],
                "experience": [
                    {
                        "title": "Director",
                        "company": "Fake Corp",
                        "dates": "2020-2024",
                        "responsibilities": [],
                        "achievements": [],
                        "metrics": [],
                    },
                ],
                "projects": [],
                "certifications": ["AWS Solutions Architect"],
                "education": [],
            }
        )
        client = fake_client(response=payload)
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert result.experience[0].company == "Acme Corp"
        assert len(client.calls) == 2


class TestResumeRewriteRetry:
    async def test_strict_retry_round_toggles_rules(self, fake_client) -> None:
        client = fake_client(response=_valid_payload(), fail_calls=1)
        agent = ResumeRewriteAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, RewriteOutput)
        assert len(client.calls) == 2
        assert client.calls[0]["rules"] != _STRICT_RULES + [_SCHEMA_HINT]
        assert client.calls[1]["rules"] == _STRICT_RULES + [_SCHEMA_HINT]
