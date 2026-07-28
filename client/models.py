"""
models.py
Pydantic models for structured resume and job description data.

Provides validated schemas that both regex and LLM parsing produce,
ensuring downstream agents always receive consistent fields.
"""

from pydantic import BaseModel, Field


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
