"""
models.py
Pydantic models for structured resume and job description data.

Provides validated schemas that both regex and LLM parsing produce,
ensuring downstream agents always receive consistent fields.
"""

from __future__ import annotations

import json
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


def _coerce_experience_list(v: Any) -> list[ExperienceEntry]:
    """Coerce a list of strings or dicts into ``ExperienceEntry`` objects.

    Handles three common LLM output formats:
    - list[str] -- each string becomes ``responsibilities``
    - list[dict] -- missing keys default to empty strings / lists
    - list[ExperienceEntry] -- passed through unchanged
    """
    if not isinstance(v, list):
        return []
    entries: list[ExperienceEntry] = []
    for item in v:  # type: ignore[reportUnknownVariableType]
        if isinstance(item, ExperienceEntry):
            entries.append(item)
        elif isinstance(item, str):
            entries.append(ExperienceEntry(responsibilities=[item]))
        elif isinstance(item, dict):
            entries.append(
                ExperienceEntry(
                    title=item.get("title", ""),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    company=item.get("company", ""),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    dates=item.get("dates", ""),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    responsibilities=item.get("responsibilities", []),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    achievements=item.get("achievements", []),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    metrics=item.get("metrics", []),  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                )
            )
    return entries


def _coerce_str_list(v: Any) -> list[str]:
    """Coerce a value into a list of strings.

    Handles the LLM returning dicts, ints, or other non-string items
    inside fields that should be ``list[str]``.
    """
    if not isinstance(v, list):
        return [] if v is None else [str(v)]
    result: list[str] = []
    for item in v:  # type: ignore[reportUnknownVariableType]
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Join all values into a single descriptive string
            result.append(" - ".join(str(v) for v in item.values() if v))  # type: ignore[reportUnknownMemberType]
        else:
            result.append(str(item))  # type: ignore[reportUnknownArgumentType]
    return result


class ResumeParsingOutput(BaseModel):
    """Structured output from the Resume Parsing Agent."""

    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = []
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)

    @field_validator("skills", "projects", "certifications", "education", mode="before")
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)

    @field_validator("experience", mode="before")
    @classmethod
    def _coerce_experience(cls, v: Any) -> list[ExperienceEntry]:
        return _coerce_experience_list(v)


class GapAnalysisOutput(BaseModel):
    """Structured output from the Gap Analysis Agent."""

    missing_skills: list[str] = Field(default_factory=list)
    weak_skills: list[str] = Field(default_factory=list)
    strong_matches: list[str] = Field(default_factory=list)
    recommended_emphasis: list[str] = Field(default_factory=list)
    keyword_strategy: list[str] = Field(default_factory=list)
    bullet_point_improvement_plan: list[str] = Field(default_factory=list)
    tone_guidance: str = ""

    @field_validator(
        "missing_skills",
        "weak_skills",
        "strong_matches",
        "recommended_emphasis",
        "keyword_strategy",
        "bullet_point_improvement_plan",
        mode="before",
    )
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)

    @field_validator("tone_guidance", mode="before")
    @classmethod
    def _coerce_tone_guidance(cls, v: Any) -> str:
        if isinstance(v, dict):
            parts: list[str] = []
            for k, val in v.items():  # type: ignore[reportUnknownVariableType, reportUnknownMemberType]
                if val:
                    parts.append(f"{k}: {val}")
            return ", ".join(parts) if parts else ""
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)  # type: ignore[reportUnknownVariableType]
        return str(v) if v else ""


class RewriteOutput(BaseModel):
    """Structured output from the Resume Rewrite Agent."""

    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = []
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)

    @field_validator("experience", mode="before")
    @classmethod
    def _coerce_experience(cls, v: Any) -> list[ExperienceEntry]:
        return _coerce_experience_list(v)


class ATSComplianceOutput(BaseModel):
    """Structured output from the ATS Compliance Agent."""

    ats_score: int = Field(default=0, ge=0, le=100)
    missing_keywords: list[str] = Field(default_factory=list)
    formatting_issues: list[str] = Field(default_factory=list)
    clarity_issues: list[str] = Field(default_factory=list)
    recommended_fixes: list[str] = Field(default_factory=list)
    auto_fixes_applied: list[str] = Field(default_factory=list)
    final_resume: str = ""

    @field_validator(
        "missing_keywords",
        "formatting_issues",
        "clarity_issues",
        "recommended_fixes",
        "auto_fixes_applied",
        mode="before",
    )
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)

    @field_validator("final_resume", mode="before")
    @classmethod
    def _coerce_final_resume(cls, v: Any) -> str:
        if isinstance(v, dict):
            return json.dumps(v, indent=2, default=str)
        if isinstance(v, list):
            result: list[str] = []
            for item in v:  # type: ignore[reportUnknownVariableType]
                result.append(str(item))  # type: ignore[reportUnknownArgumentType]
            return "\n".join(result)
        return str(v) if v else ""


class TonePolishingOutput(BaseModel):
    """Structured output from the Tone Polishing Agent."""

    polished_resume: str = ""


class CoverLetterOutput(BaseModel):
    """Structured output from the Cover Letter Agent."""

    cover_letter: str = ""
