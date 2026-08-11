"""Shared fixtures for the pytest suite.

Fixtures (all auto-discovered by pytest via this ``conftest.py``):

- ``fake_client``: the ``FakeClient`` *class*, so each test configures its own
  canned-response instance.  Used by every per-agent contract test.
- ``configure_test_logging`` (autouse): pins root logging to ``WARNING`` so
  suite output stays quiet.
- ``sample_resume_path`` / ``sample_jd_path``: paths to the checked-in sample
  files under ``sample/``.
- ``sample_resume`` / ``sample_jd``: raw text of those sample files.
- ``markdown_resume`` / ``markdown_jd``: small inline markdown documents used
  by the ``FormatDetector`` regex tests.
- ``rewrite_output`` / ``cover_letter_output``: fully-populated output models
  used by the renderer and formatter tests.
"""

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
    """Keep test output quiet by raising the root logger to ``WARNING``."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s %(levelname)s: %(message)s",
    )


@pytest.fixture
def sample_resume_path() -> Path:
    """Path to ``sample/resume/Peter-Letkeman-Resume.txt``."""
    return SAMPLE_DIR / "resume" / "Peter-Letkeman-Resume.txt"


@pytest.fixture
def sample_jd_path() -> Path:
    """Path to ``sample/jobs/3Pillar.txt``."""
    return SAMPLE_DIR / "jobs" / "3Pillar.txt"


@pytest.fixture
def sample_resume(sample_resume_path: Path) -> str:
    """Raw text of the sample resume file."""
    return sample_resume_path.read_text()


@pytest.fixture
def sample_jd(sample_jd_path: Path) -> str:
    """Raw text of the sample job description file."""
    return sample_jd_path.read_text()


@pytest.fixture
def markdown_resume() -> str:
    """Small inline markdown resume for ``FormatDetector`` regex tests."""
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
    """Small inline markdown job description for ``FormatDetector`` regex tests."""
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
