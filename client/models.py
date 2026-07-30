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


class ExperienceEntry(BaseModel):
    """A single role within a work experience section."""

    title: str = ""
    company: str = ""
    dates: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class ResumeParsingOutput(BaseModel):
    """Structured output from the Resume Parsing Agent."""

    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = []
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class GapAnalysisOutput(BaseModel):
    """Structured output from the Gap Analysis Agent."""

    missing_skills: list[str] = Field(default_factory=list)
    weak_skills: list[str] = Field(default_factory=list)
    strong_matches: list[str] = Field(default_factory=list)
    recommended_emphasis: list[str] = Field(default_factory=list)
    keyword_strategy: list[str] = Field(default_factory=list)
    bullet_point_improvement_plan: list[str] = Field(default_factory=list)
    tone_guidance: str = ""


class RewriteOutput(BaseModel):
    """Structured output from the Resume Rewrite Agent."""

    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = []
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class ATSComplianceOutput(BaseModel):
    """Structured output from the ATS Compliance Agent."""

    ats_score: int = Field(default=0, ge=0, le=100)
    missing_keywords: list[str] = Field(default_factory=list)
    formatting_issues: list[str] = Field(default_factory=list)
    clarity_issues: list[str] = Field(default_factory=list)
    recommended_fixes: list[str] = Field(default_factory=list)
    auto_fixes_applied: list[str] = Field(default_factory=list)
    final_resume: str = ""


class TonePolishingOutput(BaseModel):
    """Structured output from the Tone Polishing Agent."""

    polished_resume: str = ""


class CoverLetterOutput(BaseModel):
    """Structured output from the Cover Letter Agent."""

    cover_letter: str = ""
