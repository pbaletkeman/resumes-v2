"""Agent 5 (ATS Compliance) contract tests with a fake ModelClient (Phase 7.2.1.5).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation contract against canned ``chat()`` responses.  No real LLM is
contacted.
"""

import json

from client.agents.ats_compliance import ATSComplianceAgent
from client.errors import LLMConnectionError
from client.models import ATSComplianceOutput


def _rewritten_payload() -> dict[str, object]:
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
        ],
        "projects": ["Open-source CLI tool"],
        "certifications": ["AWS Solutions Architect"],
        "education": ["B.Sc. Computer Science, U of T"],
    }


def _valid_payload() -> str:
    return json.dumps(
        {
            "ats_score": 85,
            "missing_keywords": ["Kubernetes"],
            "formatting_issues": ["Tables present"],
            "clarity_issues": ["Run-on sentence"],
            "recommended_fixes": ["Replace tables with plain text"],
            "auto_fixes_applied": ["Removed a table"],
            "final_resume": "Senior engineer with 10+ years experience.\n"
            "Skills: Python, Rust, Kubernetes",
        }
    )


class TestATSComplianceHappyPath:
    async def test_valid_compliance(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert isinstance(result, ATSComplianceOutput)
        assert result.ats_score == 85
        assert "Kubernetes" in result.missing_keywords
        assert "Tables present" in result.formatting_issues

    async def test_recommended_fixes_surface(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert any("tables" in fix.lower() for fix in result.recommended_fixes)

    async def test_chat_contract(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ATSComplianceAgent(client)
        await agent.run({"rewritten_resume": _rewritten_payload()})

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)
        assert len(call["inputs"]) == 1


class TestATSCompliancePostValidation:
    async def test_out_of_range_score_rejected_falls_back(self, fake_client) -> None:
        payload = json.dumps(
            {
                "ats_score": 150,
                "missing_keywords": [],
                "formatting_issues": [],
                "clarity_issues": [],
                "recommended_fixes": [],
                "auto_fixes_applied": [],
                "final_resume": "Some resume text.",
            }
        )
        client = fake_client(response=payload)
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert isinstance(result, ATSComplianceOutput)
        assert result.ats_score == 30  # default low-score fallback
        assert len(client.calls) == 2

    async def test_empty_final_resume_filled_from_input(self, fake_client) -> None:
        payload = json.dumps(
            {
                "ats_score": 70,
                "missing_keywords": [],
                "formatting_issues": [],
                "clarity_issues": [],
                "recommended_fixes": [],
                "auto_fixes_applied": [],
                "final_resume": "",
            }
        )
        client = fake_client(response=payload)
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert isinstance(result, ATSComplianceOutput)
        assert "Python" in result.final_resume
        assert "Acme Corp" in result.final_resume


class TestATSComplianceFallback:
    async def test_empty_input_returns_defaults(self, fake_client) -> None:
        client = fake_client(response=_valid_payload())
        agent = ATSComplianceAgent(client)
        result = await agent.run({})

        assert isinstance(result, ATSComplianceOutput)
        assert result.ats_score == 0
        assert client.calls == []

    async def test_connection_error_returns_default_low_score(
        self, fake_client
    ) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert isinstance(result, ATSComplianceOutput)
        assert result.ats_score == 30
        assert len(client.calls) == 2


class TestATSComplianceRetry:
    async def test_strict_retry_round_after_first_exception(self, fake_client) -> None:
        client = fake_client(response=_valid_payload(), fail_calls=1)
        agent = ATSComplianceAgent(client)
        result = await agent.run({"rewritten_resume": _rewritten_payload()})

        assert isinstance(result, ATSComplianceOutput)
        assert result.ats_score == 85
        assert len(client.calls) == 2
