"""Shared fixtures for tests."""

import logging
from pathlib import Path

import pytest

from client.models import CoverLetterOutput, ExperienceEntry, RewriteOutput

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample"


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
