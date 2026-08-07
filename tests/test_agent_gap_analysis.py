"""Agent 3 (Gap Analysis) contract tests with a fake ModelClient (Phase 7.2.1.3).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation contract against canned ``chat()`` responses.  Gap analysis has
no regex fallback -- on total LLM failure it returns a default
``GapAnalysisOutput``.  No real LLM is contacted.
"""

import json

from client.agents.gap_analysis import GapAnalysisAgent
from client.errors import LLMConnectionError
from client.models import GapAnalysisOutput


def _jd_payload() -> dict[str, object]:
    return {
        "role_title": "Senior Backend Engineer",
        "required_skills": ["Python", "Docker"],
        "preferred_skills": ["Kubernetes"],
        "keywords": ["python", "microservices"],
    }


def _resume_payload() -> dict[str, object]:
    return {
        "summary": "Engineer",
        "skills": ["Python"],
        "experience": [],
    }


def _valid_payload() -> str:
    return json.dumps(
        {
            "missing_skills": ["Docker"],
            "weak_skills": ["SQL"],
            "strong_matches": ["Python"],
            "recommended_emphasis": ["microservices"],
            "keyword_strategy": ["docker", "microservices"],
            "bullet_point_improvement_plan": ["Quantify impact"],
            "tone_guidance": "Confident and direct",
        }
    )


class TestGapAnalysisHappyPath:
    async def test_llm_happy_path(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = GapAnalysisAgent(client)
        result = await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        assert isinstance(result, GapAnalysisOutput)
        assert "Docker" in result.missing_skills
        assert "Python" in result.strong_matches

    async def test_chat_contract(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = GapAnalysisAgent(client)
        await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)
        assert len(call["inputs"]) == 2

    async def test_prompt_receives_deterministic_missing_skills(
        self, fake_client
    ) -> None:
        client = fake_client(response=_valid_payload())
        agent = GapAnalysisAgent(client)
        await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        prompt = client.calls[0]["prompt"]
        assert "NORMALIZED SKILLS" in prompt
        assert "missing:" in prompt


class TestGapAnalysisFallback:
    async def test_llm_failure_returns_defaults(self, fake_client) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = GapAnalysisAgent(client)
        result = await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        assert isinstance(result, GapAnalysisOutput)
        assert result.missing_skills == []
        assert len(client.calls) == 2

    async def test_malformed_json_returns_defaults(self, fake_client) -> None:
        client = fake_client(response="not json")
        agent = GapAnalysisAgent(client)
        result = await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        assert isinstance(result, GapAnalysisOutput)
        assert result.missing_skills == []
        assert len(client.calls) == 2

    async def test_empty_input_returns_defaults(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = GapAnalysisAgent(client)
        result = await agent.run({"parsed_job_description": {}, "parsed_resume": {}})

        assert isinstance(result, GapAnalysisOutput)
        assert result.missing_skills == []
        assert client.calls == []


class TestGapAnalysisRetry:
    async def test_strict_retry_round_after_first_exception(self, fake_client) -> None:
        client = fake_client(response=_valid_payload(), fail_calls=1)
        agent = GapAnalysisAgent(client)
        result = await agent.run(
            {
                "parsed_job_description": _jd_payload(),
                "parsed_resume": _resume_payload(),
            }
        )

        assert isinstance(result, GapAnalysisOutput)
        assert "Docker" in result.missing_skills
        assert len(client.calls) == 2
