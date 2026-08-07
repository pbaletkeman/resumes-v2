"""Shared fixtures for tests."""

import logging
from pathlib import Path
from typing import Any

import pytest

from client.errors import LLMConnectionError
from client.models import CoverLetterOutput, ExperienceEntry, RewriteOutput

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample"


class FakeClient:
    """Stub ``ModelClient`` that records calls and serves canned responses.

    Supports three behaviours (used across the Phase 7.2.1 agent tests):

    - ``response``: a single payload returned on every ``chat()`` call.
    - ``responses_by_purpose``: a payload map keyed by the ``purpose`` arg.
    - ``error``: an exception raised on every call.
    - ``fail_calls``: raise ``error`` (default ``LLMConnectionError``) on the
      first *N* calls, then serve responses — used to exercise the one-strict-retry
      path (attempt 0 fails, attempt 1 = ``strict=True`` succeeds).

    Every call is appended to ``calls`` so tests can assert the documented
    ``chat`` contract (``purpose``/``prompt``/``output``/``rules``/``inputs``/
    ``response_format``/``json_schema``).
    """

    def __init__(
        self,
        response: str = "",
        responses_by_purpose: dict[str, str] | None = None,
        error: Exception | None = None,
        fail_calls: int = 0,
    ) -> None:
        self.response = response
        self.responses_by_purpose = responses_by_purpose or {}
        self.error = error
        self.fail_calls = fail_calls
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
        response_format: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "purpose": purpose,
                "prompt": prompt,
                "output": output,
                "rules": rules,
                "inputs": inputs,
                "response_format": response_format,
                "json_schema": json_schema,
            }
        )
        if self.fail_calls > 0:
            self.fail_calls -= 1
            raise (self.error or LLMConnectionError("fake connection error"))
        if self.error is not None:
            raise self.error
        if purpose in self.responses_by_purpose:
            return self.responses_by_purpose[purpose]
        return self.response


@pytest.fixture
def fake_client() -> type[FakeClient]:
    """Provide the ``FakeClient`` class so tests configure per-case instances."""
    return FakeClient


@pytest.fixture(autouse=True)
def configure_test_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s %(levelname)s: %(message)s",
    )


@pytest.fixture
def sample_resume_path() -> Path:
    return SAMPLE_DIR / "resume" / "Peter-Letkeman-Resume.txt"


@pytest.fixture
def sample_jd_path() -> Path:
    return SAMPLE_DIR / "jobs" / "3Pillar.txt"


@pytest.fixture
def sample_resume(sample_resume_path: Path) -> str:
    return sample_resume_path.read_text()


@pytest.fixture
def sample_jd(sample_jd_path: Path) -> str:
    return sample_jd_path.read_text()


@pytest.fixture
def markdown_resume() -> str:
    return """# Jane Doe

## Summary

Senior engineer with 10 years of experience.

## Skills

- Python
- TypeScript
- PostgreSQL

## Experience

- Senior Developer | Acme Corp (2020 - Present)
- Developer | Startup Inc (2016 - 2020)

## Education

- B.S. Computer Science, MIT (2016)
"""


@pytest.fixture
def markdown_jd() -> str:
    return """Senior Backend Engineer

Key Responsibilities
- Design and build RESTful APIs
- Optimize database queries
- Mentor junior developers

Qualifications
- 5+ years of Python experience
- Strong SQL knowledge
- Experience with cloud platforms

Nice to Have
- Kubernetes experience
- GraphQL knowledge
"""


@pytest.fixture
def rewrite_output() -> RewriteOutput:
    """A RewriteOutput populated with every section."""
    return RewriteOutput(
        summary="Senior engineer with 10+ years experience.",
        skills=["Python", "Rust", "Kubernetes"],
        experience=[
            ExperienceEntry(
                title="Staff Engineer",
                company="Acme Corp",
                dates="2020-2024",
                responsibilities=["Led platform team"],
                achievements=["Reduced costs 40%"],
                metrics=["$2M annual savings"],
            ),
            ExperienceEntry(
                title="Senior Engineer",
                company="Globex",
                dates="2016-2020",
                responsibilities=["Built microservices"],
            ),
        ],
        projects=["Open-source CLI tool"],
        certifications=["AWS Solutions Architect"],
        education=["B.Sc. Computer Science, U of T"],
    )


@pytest.fixture
def cover_letter_output() -> CoverLetterOutput:
    """A CoverLetterOutput with body and closing text."""
    return CoverLetterOutput(
        cover_letter="Dear Hiring Manager,\n\n"
        "I am excited to apply for the role.\n\n"
        "Best regards,\nJane Doe"
    )
