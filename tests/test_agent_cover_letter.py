"""Agent 7 (Cover Letter) contract tests with a fake ModelClient (Phase 7.2.1.7).

Verifies the ``run()`` -> ``_try_llm()`` -> ``_parse_json()`` -> Pydantic
validation -> post-processing (company/candidate name, contact info, length)
contract against canned ``chat()`` responses.  No real LLM is contacted.
"""

import json

from client.agents.cover_letter import (
    CoverLetterAgent,
    _build_fallback_cover_letter,
    _validate_length,
)
from client.errors import LLMConnectionError
from client.models import CoverLetterOutput


def _jd_payload() -> dict[str, object]:
    return {
        "role_title": "Senior Backend Engineer",
        "company_name": "3Pillar",
        "required_skills": ["Python", "Kubernetes"],
        "preferred_skills": ["PostgreSQL"],
        "keywords": ["microservices"],
    }


def _resume_payload() -> dict[str, object]:
    return {
        "summary": "Engineer with 10 years experience.",
        "skills": ["Python", "Kubernetes", "PostgreSQL"],
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme Corp",
                "dates": "2020-2024",
                "responsibilities": ["Led platform team"],
                "achievements": ["Reduced costs 40%"],
                "metrics": ["$2M annual savings"],
            },
        ],
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
    }


def _strategy_payload() -> dict[str, object]:
    return {
        "keyword_strategy": ["kubernetes", "microservices"],
        "recommended_emphasis": ["platform work"],
    }


def _body_paragraphs(company: str) -> str:
    return (
        "I am writing to express my strong interest in the Senior Backend Engineer "
        f"position at {company}. With over ten years of experience designing and "
        "shipping high-scale APIs and distributed systems, I am confident I can "
        "contribute immediately to the engineering team. I am especially drawn to "
        "the company's focus on digital product development and its reputation for "
        "delivering measurable results for clients. I led a platform team that "
        "rebuilt a fragile transaction pipeline on Python and Kubernetes, reducing "
        "processing time by forty percent and saving two million dollars a year in "
        "infrastructure costs. I take pride in writing clean, maintainable code "
        "with strong test coverage. I mentor engineers through regular code review "
        "and design discussions. I have deep experience with PostgreSQL, Redis, and "
        "event-driven microservices. I own incident response for the services I "
        "build and I am comfortable being on call. I collaborate closely with "
        "product managers and designers to turn ambiguous requirements into "
        "reliable software that ships on time. I enjoy working in fast-paced "
        "environments where engineering excellence matters. I am looking for a "
        "role where I can grow as an engineer while helping the team scale its "
        "platform. Thank you for considering my application. I welcome the "
        "opportunity to discuss how I can help the team succeed. I look forward "
        "to hearing from you. Best regards."
    )


def _opening_only_body(company: str) -> str:
    return (
        "I am writing to express my strong interest in the Senior Backend Engineer "
        f"position at {company}. In my previous role I rebuilt the platform on "
        "Python and Kubernetes, reducing processing time by forty percent and "
        "saving two million dollars a year in infrastructure costs. I take pride "
        "in writing clean, maintainable code with strong test coverage. I mentor "
        "engineers through regular code review and design discussions. I have deep "
        "experience with PostgreSQL, Redis, and event-driven microservices. I own "
        "incident response for the services I build and I am comfortable being on "
        "call. I collaborate closely with product managers and designers to turn "
        "ambiguous requirements into reliable software that ships on time. Thank "
        "you for considering my application. I welcome the opportunity to discuss "
        "how I can help the team succeed. I look forward to hearing from you."
    )


def _letter_payload(company: str) -> str:
    return json.dumps(
        {
            "cover_letter": (
                "Dear Hiring Manager,\n\n"
                f"{_body_paragraphs(company)}\n\n"
                "Sincerely,\nJane Doe"
            )
        }
    )


def _inputs() -> dict[str, object]:
    return {
        "parsed_job_description": _jd_payload(),
        "parsed_resume": _resume_payload(),
        "tailoring_strategy": _strategy_payload(),
    }


class TestCoverLetterHappyPath:
    async def test_llm_happy_path(self, fake_client) -> None:
        client = fake_client(response=_letter_payload("3Pillar"))
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, CoverLetterOutput)
        assert "3Pillar" in result.cover_letter
        assert "Senior Backend Engineer" in result.cover_letter
        assert len(result.cover_letter.split()) >= 200

    async def test_chat_contract(self, fake_client) -> None:
        client = fake_client(response=_letter_payload("3Pillar"))
        agent = CoverLetterAgent(client)
        await agent.run(_inputs())

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["output"] == ["json"]
        assert call["response_format"] == "json"
        assert isinstance(call["json_schema"], dict)
        assert len(call["inputs"]) == 3


class TestCoverLetterCompanySync:
    async def test_resume_company_substituted_with_jd_company(
        self, fake_client
    ) -> None:
        payload = json.dumps(
            {
                "cover_letter": (
                    "Dear Hiring Manager,\n\n"
                    f"{_opening_only_body('Acme Corp')}\n\n"
                    "Sincerely,\nJane Doe"
                )
            }
        )
        client = fake_client(response=payload)
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, CoverLetterOutput)
        assert "3Pillar" in result.cover_letter
        assert "Acme Corp" not in result.cover_letter

    async def test_company_placeholder_token_replaced(self, fake_client) -> None:
        payload = json.dumps(
            {
                "cover_letter": (
                    "Dear Hiring Manager,\n\n"
                    f"{_body_paragraphs('[Company Name]')}\n\n"
                    "Sincerely,\nJane Doe"
                )
            }
        )
        client = fake_client(response=payload)
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, CoverLetterOutput)
        assert "[Company Name]" not in result.cover_letter
        assert "3Pillar" in result.cover_letter

    async def test_candidate_name_placeholder_replaced(self, fake_client) -> None:
        payload = json.dumps(
            {
                "cover_letter": (
                    "Dear Hiring Manager,\n\n"
                    f"{_body_paragraphs('3Pillar')}\n\n"
                    "Sincerely,\n[Your Name]"
                )
            }
        )
        client = fake_client(response=payload)
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert "[Your Name]" not in result.cover_letter
        assert "Jane Doe" in result.cover_letter


class TestCoverLetterFallback:
    async def test_connection_error_builds_fallback_letter(self, fake_client) -> None:
        client = fake_client(error=LLMConnectionError("down"))
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert isinstance(result, CoverLetterOutput)
        assert "3Pillar" in result.cover_letter
        assert "Jane Doe" in result.cover_letter
        assert len(client.calls) == 2

    async def test_empty_input_builds_fallback_letter(self, fake_client) -> None:
        client = fake_client(response=_letter_payload("3Pillar"))
        agent = CoverLetterAgent(client)
        result = await agent.run(
            {
                "parsed_job_description": {},
                "parsed_resume": {},
                "tailoring_strategy": {},
            }
        )

        assert isinstance(result, CoverLetterOutput)
        assert result.cover_letter
        assert client.calls == []

    async def test_fallback_builder_is_wordy(self) -> None:
        letter = _build_fallback_cover_letter(
            _jd_payload(), _resume_payload(), _strategy_payload()
        )
        assert "3Pillar" in letter
        assert "Jane Doe" in letter
        assert 50 <= len(letter.split()) <= 400


class TestCoverLetterLength:
    async def test_too_short_letter_rejected(self, fake_client) -> None:
        payload = json.dumps({"cover_letter": "Too short."})
        client = fake_client(response=payload)
        agent = CoverLetterAgent(client)
        result = await agent.run(_inputs())

        assert result.cover_letter  # falls back to builder
        assert len(client.calls) == 2

    async def test_extreme_short_fails_length_check(self) -> None:
        result = CoverLetterOutput(cover_letter="Too short.")
        assert not _validate_length(result)
