"""
models.py
Pydantic models for structured resume and job description data.

Provides validated schemas that both regex and LLM parsing produce,
ensuring downstream agents always receive consistent fields.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ParsedResume(BaseModel):
    """Structured representation of a parsed resume."""

    name: str = "Unknown"
    title: str = "Unknown"
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    raw: str = ""


class ParsedJobDescription(BaseModel):
    """Structured representation of a parsed job description."""

    title: str = "Position"
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    raw: str = ""


class JDParsingOutput(BaseModel):
    """Structured output from the JD Parsing Agent."""

    role_title: str = ""
    seniority_level: str = ""  # "junior", "mid", "senior", "lead", "executive"
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    industry_terms: list[str] = Field(default_factory=list)
    company_signals: dict[str, str] = Field(default_factory=dict)

    @field_validator("company_signals", mode="before")
    @classmethod
    def _coerce_company_signals(cls, v: Any) -> dict[str, str]:
        """Accept a list of strings and convert to a numbered dict."""
        if isinstance(v, list):
            typed_v: list[str] = v  # type: ignore[assignment]
            result: dict[str, str] = {}
            for i, item in enumerate(typed_v):
                result[str(i + 1)] = item
            return result
        return v
