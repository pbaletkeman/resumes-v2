"""
models.py
Pydantic models for structured resume and job description data.

Provides validated schemas that both regex and LLM parsing produce,
ensuring downstream agents always receive consistent fields.

Why coercion exists
-------------------
The LLM providers are asked to return JSON matching these models, but
they do not always comply: a field declared as ``list[str]`` may arrive
as a dict or a single string, and a ``str`` field may arrive as a dict or
list.  Rather than rejecting the whole response (and falling back to
regex/template output), the ``mode="before"`` validators in this module
*forgive* the LLM at the model boundary and coerce the value into the
declared shape.  The helpers are pure and deterministic: the same input
always produces the same output, so the pipeline output shapes are
stable and testable.

Notes
-----
- ``model_dump()`` of these models is what downstream agents and the web
  API consume; validators must never change the final dict shape.
- ``model_to_json_schema()`` in ``client/json_utils.py`` derives the
  provider JSON Schema from these models.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, Field, field_validator


class ParsedResume(BaseModel):
    """Structured representation of a parsed resume (regex / FormatDetector).

    The flat ``list[str]`` fields are produced by section-based regex
    extraction; contact fields are the raw text the detector found.
    """

    name: str = Field(
        default="Unknown", description="Candidate's full name as found on the resume."
    )
    title: str = Field(
        default="Unknown", description="Headline or most recent job title."
    )
    summary: str = Field(
        default="", description="Professional summary or objective text, if any."
    )
    skills: list[str] = Field(
        default_factory=list, description="Skill keywords found on the resume."
    )
    experience: list[str] = Field(
        default_factory=list,
        description="Raw experience section lines (one per entry).",
    )
    projects: list[str] = Field(
        default_factory=list, description="Project descriptions, one per project."
    )
    education: list[str] = Field(
        default_factory=list, description="Education entries, one per degree/school."
    )
    certifications: list[str] = Field(
        default_factory=list, description="Certification names, one per entry."
    )
    keywords: list[str] = Field(
        default_factory=list, description="Keywords extracted from the resume text."
    )
    raw: str = Field(
        default="",
        description="Full original resume text (for reference / fallback).",
    )
    phone: str = Field(
        default="", description="Phone number exactly as written, if found."
    )
    email: str = Field(
        default="", description="Email address exactly as written, if found."
    )
    linkedin: str = Field(default="", description="LinkedIn profile URL, if found.")
    github: str = Field(default="", description="GitHub profile URL, if found.")


class ParsedJobDescription(BaseModel):
    """Structured representation of a parsed job description (regex).

    Produced by ``FormatDetector.parse_job_description()``; the flat
    ``list[str]`` fields mirror the JD's section list items.
    """

    title: str = Field(
        default="Position", description="Job title stated at the top of the posting."
    )
    responsibilities: list[str] = Field(
        default_factory=list, description="Responsibilities section items."
    )
    requirements: list[str] = Field(
        default_factory=list, description="Requirements / qualifications items."
    )
    nice_to_have: list[str] = Field(
        default_factory=list, description="Nice-to-have / preferred items."
    )
    raw: str = Field(default="", description="Full original job description text.")


class JDParsingOutput(BaseModel):
    """Structured output from the JD Parsing Agent (Agent 1)."""

    role_title: str = Field(
        default="", description="Job title as stated in the posting."
    )
    company_name: str = Field(
        default="",
        description="Employer name exactly as written in the JD; empty if absent.",
    )
    seniority_level: str = Field(
        default="",
        description="One of: junior, mid, senior, lead, executive.",
    )
    required_skills: list[str] = Field(
        default_factory=list, description="Skills the JD marks as required."
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Skills the JD marks as preferred/nice-to-have.",
    )
    responsibilities: list[str] = Field(
        default_factory=list, description="Responsibilities listed for the role."
    )
    keywords: list[str] = Field(
        default_factory=list, description="Important keywords / phrases from the JD."
    )
    industry_terms: list[str] = Field(
        default_factory=list,
        description="Industry-specific terminology used in the JD.",
    )
    company_signals: dict[str, str] = Field(
        default_factory=dict,
        description="Signals about the company (e.g. company_name, size, industry).",
    )

    @field_validator("company_signals", mode="before")
    @classmethod
    def _coerce_company_signals(cls, v: Any) -> dict[str, str]:
        """Accept a bare list of strings and convert it to a numbered dict.

        Some LLMs return ``company_signals`` as a list (e.g.
        ``["growing startup", "Series B"]``) instead of the declared
        dict.  We keep the items in order under numeric keys ``"1"``,
        ``"2"``, ... so nothing is lost.

        Returns:
            The dict unchanged when it is already a dict, otherwise the
            numbered dict built from the list.
        """
        if isinstance(v, list):
            signals: dict[str, str] = {}
            for index, item in enumerate(cast(list[Any], v)):
                signals[str(index + 1)] = item if isinstance(item, str) else str(item)
            return signals
        return cast(dict[str, str], v)


class ExperienceEntry(BaseModel):
    """A single role within a work experience section."""

    title: str = Field(default="", description="Job title of the role.")
    company: str = Field(default="", description="Employer company name.")
    dates: str = Field(
        default="", description="Employment date range, e.g. '2020-2024'."
    )
    responsibilities: list[str] = Field(
        default_factory=list, description="Role responsibilities as bullet points."
    )
    achievements: list[str] = Field(
        default_factory=list, description="Notable achievements for the role."
    )
    metrics: list[str] = Field(
        default_factory=list,
        description="Quantifiable metrics for the role (e.g. '40% reduction').",
    )


def _coerce_experience_list(v: Any) -> list[ExperienceEntry]:
    """Coerce a list of strings or dicts into ``ExperienceEntry`` objects.

    Handles three common LLM output shapes:

    - ``list[str]``: each string becomes that entry's ``responsibilities``.
    - ``list[dict]``: missing keys default to empty strings / lists.
    - ``list[ExperienceEntry]``: passed through unchanged.

    Non-list input yields an empty list (the agent will fall back).

    Returns:
        A list of ``ExperienceEntry`` objects.
    """
    if not isinstance(v, list):
        return []
    entries: list[ExperienceEntry] = []
    for item in cast(list[Any], v):
        if isinstance(item, ExperienceEntry):
            entries.append(item)
        elif isinstance(item, str):
            entries.append(ExperienceEntry(responsibilities=[item]))
        elif isinstance(item, dict):
            entry_data = cast(dict[str, Any], item)
            entries.append(
                ExperienceEntry(
                    title=entry_data.get("title", ""),
                    company=entry_data.get("company", ""),
                    dates=entry_data.get("dates", ""),
                    responsibilities=entry_data.get("responsibilities", []),
                    achievements=entry_data.get("achievements", []),
                    metrics=entry_data.get("metrics", []),
                )
            )
    return entries


def _coerce_str_list(v: Any) -> list[str]:
    """Coerce a value into a list of strings.

    Handles the LLM returning dicts, ints, or other non-string items
    inside fields that should be ``list[str]``.

    Rules:
    - ``None`` or non-list input -> empty list (``None``) or one-item list.
    - A string item is kept as-is.
    - A dict item is flattened to ``" - ".join(values)``.
    - Any other item is converted with ``str()``.

    Returns:
        A list of strings.
    """
    if not isinstance(v, list):
        return [] if v is None else [str(v)]

    result: list[str] = []
    for item in cast(list[Any], v):
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Join all dict values into a single descriptive string.
            item_dict = cast(dict[str, Any], item)
            joined = " - ".join(str(value) for value in item_dict.values() if value)
            result.append(joined)
        else:
            result.append(str(item))
    return result


def _coerce_str(v: Any) -> str:
    """Coerce a value into a string.

    Handles the LLM returning a dict or list where a ``str`` field is
    expected (e.g. a structured contact object for ``phone``/``email``).
    Dicts are flattened to ``key: value`` pairs joined with ``", "``;
    lists are joined with ``", "``; anything falsy becomes ``""``.

    Returns:
        The coerced string.
    """
    if isinstance(v, dict):
        parts: list[str] = []
        for key, value in cast(dict[str, Any], v).items():
            if value:
                parts.append(f"{key}: {value}")
        return ", ".join(parts) if parts else ""
    if isinstance(v, list):
        return ", ".join(str(item) for item in cast(list[Any], v))
    return str(v) if v else ""


class ResumeParsingOutput(BaseModel):
    """Structured output from the Resume Parsing Agent (Agent 2)."""

    summary: str = Field(
        default="", description="Professional summary extracted from the resume."
    )
    skills: list[str] = Field(
        default_factory=list, description="Canonicalized skills present on the resume."
    )
    experience: list[ExperienceEntry] = Field(
        default_factory=list[ExperienceEntry],
        description="Work experience entries, most recent first.",
    )
    projects: list[str] = Field(
        default_factory=list, description="Projects described on the resume."
    )
    certifications: list[str] = Field(
        default_factory=list, description="Certifications exactly as written."
    )
    education: list[str] = Field(
        default_factory=list, description="Education entries exactly as written."
    )
    name: str = Field(
        default="",
        description="Candidate's full name exactly as it appears; empty if absent.",
    )
    phone: str = Field(
        default="", description="Phone number exactly as written; empty if absent."
    )
    email: str = Field(
        default="", description="Email address exactly as written; empty if absent."
    )
    linkedin: str = Field(
        default="", description="LinkedIn profile URL; empty if absent."
    )
    github: str = Field(default="", description="GitHub profile URL; empty if absent.")

    @field_validator("skills", "projects", "certifications", "education", mode="before")
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)

    @field_validator("experience", mode="before")
    @classmethod
    def _coerce_experience(cls, v: Any) -> list[ExperienceEntry]:
        return _coerce_experience_list(v)

    @field_validator("name", "phone", "email", "linkedin", "github", mode="before")
    @classmethod
    def _coerce_contact_fields(cls, v: Any) -> str:
        return _coerce_str(v)


class GapAnalysisOutput(BaseModel):
    """Structured output from the Gap Analysis Agent (Agent 3)."""

    missing_skills: list[str] = Field(
        default_factory=list, description="JD-required skills missing from the resume."
    )
    weak_skills: list[str] = Field(
        default_factory=list,
        description="Skills present but under-evidenced on the resume.",
    )
    strong_matches: list[str] = Field(
        default_factory=list, description="Skills the resume already matches strongly."
    )
    recommended_emphasis: list[str] = Field(
        default_factory=list, description="Sections/points to emphasize when tailoring."
    )
    keyword_strategy: list[str] = Field(
        default_factory=list, description="Keywords to weave into the rewritten resume."
    )
    bullet_point_improvement_plan: list[str] = Field(
        default_factory=list,
        description="Concrete bullet-point improvement suggestions.",
    )
    tone_guidance: str = Field(
        default="", description="Recommended tone for the rewritten resume."
    )

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
        """Coerce ``tone_guidance`` to a string.

        Delegates to the shared :func:`_coerce_str` helper: the LLM
        sometimes returns the tone guidance as a dict or list structure;
        flatten it, keep a plain string as-is, and map falsy values to
        ``""``.
        """
        return _coerce_str(v)


class RewriteOutput(BaseModel):
    """Structured output from the Resume Rewrite Agent (Agent 4)."""

    summary: str = Field(
        default="", description="Rewritten, ATS-aligned professional summary."
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Rewritten skills section (JD keywords first).",
    )
    experience: list[ExperienceEntry] = Field(
        default_factory=list[ExperienceEntry],
        description="Rewritten experience, most recent first.",
    )
    projects: list[str] = Field(
        default_factory=list, description="Rewritten project descriptions."
    )
    certifications: list[str] = Field(
        default_factory=list, description="All certifications from the input resume."
    )
    education: list[str] = Field(
        default_factory=list, description="Education entries (unchanged from input)."
    )

    @field_validator("experience", mode="before")
    @classmethod
    def _coerce_experience(cls, v: Any) -> list[ExperienceEntry]:
        return _coerce_experience_list(v)


class ATSComplianceOutput(BaseModel):
    """Structured output from the ATS Compliance Agent (Agent 5)."""

    ats_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="ATS compatibility score from 0 to 100.",
    )
    missing_keywords: list[str] = Field(
        default_factory=list, description="JD keywords missing from the resume."
    )
    formatting_issues: list[str] = Field(
        default_factory=list, description="ATS-unfriendly formatting problems found."
    )
    clarity_issues: list[str] = Field(
        default_factory=list, description="Wording/clarity problems found."
    )
    recommended_fixes: list[str] = Field(
        default_factory=list, description="Fixes the agent recommends."
    )
    auto_fixes_applied: list[str] = Field(
        default_factory=list, description="Fixes the agent actually applied."
    )
    final_resume: str = Field(
        default="", description="Full corrected resume text (ATS-optimized)."
    )

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
        """Coerce ``final_resume`` to a string.

        The resume body is long free text and the LLM sometimes wraps it
        in a structure:
        - a dict -> pretty-printed JSON (``json.dumps(indent=2)``);
        - a list -> lines joined with newlines;
        - a plain string -> unchanged (empty stays empty).
        """
        if isinstance(v, dict):
            return json.dumps(v, indent=2, default=str)
        if isinstance(v, list):
            lines = [str(item) for item in cast(list[Any], v)]
            return "\n".join(lines)
        return str(v) if v else ""


class TonePolishingOutput(BaseModel):
    """Structured output from the Tone Polishing Agent (Agent 6)."""

    polished_resume: str = Field(
        default="", description="Full resume text with improved tone and phrasing."
    )


class CoverLetterOutput(BaseModel):
    """Structured output from the Cover Letter Agent (Agent 7)."""

    cover_letter: str = Field(
        default="", description="Full tailored cover letter text."
    )
