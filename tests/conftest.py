"""Shared fixtures for tests."""

from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample"


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
