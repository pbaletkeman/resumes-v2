"""
resume_parsing.py
Resume Parsing Agent — converts resumes into structured JSON.

Uses an LLM to parse a resume into a ``ResumeParsingOutput`` model.
Falls back to ``FormatDetector.parse_resume()`` on LLM failure or
validation errors.  The "try LLM twice, then fall back" loop comes from
``client.agents._retry`` — see :func:`retry_llm_then_fallback`.
"""

import logging
import re
from typing import Any

from pydantic import ValidationError

from client.agents._retry import retry_llm_then_fallback
from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.format_detector import FormatDetector
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import ExperienceEntry, ResumeParsingOutput
from client.skills import SkillNormalizer

logger = logging.getLogger(__name__)

_NORMALIZER = SkillNormalizer()

_SYSTEM_PROMPT = (
    "You are the Resume Parsing Agent. "
    "Your job is to convert a resume into structured JSON. "
    "Extract the following fields: "
    "summary, skills (normalize terms), "
    "experience (list of roles with: title, company, dates, "
    "responsibilities, achievements, metrics), "
    "projects, certifications, education, "
    "name, phone, email, linkedin, github. "
    "Rules: "
    "Preserve all quantifiable metrics. "
    "Convert bullet points into structured lists. "
    "Do not infer missing information. "
    "Normalize all skills to their canonical form "
    "(e.g., 'JS' -> 'JavaScript', 'React.js' -> 'React', "
    "'AWS' -> 'Amazon Web Services'). "
    "Extract the candidate's full name exactly as it appears at the top "
    "of the resume; empty string if absent. "
    "Extract the candidate's phone number, email address, "
    "LinkedIn profile URL, and GitHub profile URL exactly as they "
    "appear in the resume; empty string if absent. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "Do not infer missing information",
    "No markdown, no explanation -- just the JSON object",
]


class ResumeParsingAgent:
    """Agent that parses resumes into structured JSON.

    Tries LLM extraction first.  On failure or validation error, falls
    back to ``FormatDetector`` regex parsing and wraps the result in a
    ``ResumeParsingOutput``.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> ResumeParsingOutput:
        """Parse a resume into structured fields.

        Args:
            inputs: Must contain ``"resume"`` (str).

        Returns:
            A validated ``ResumeParsingOutput``.
        """
        resume_text = inputs.get("resume", "")
        if not resume_text:
            logger.debug("Resume parsing: empty input, returning defaults")
            return ResumeParsingOutput()

        logger.debug("Resume parsing: input_len=%d", len(resume_text))

        # Attempt LLM extraction (with one retry), then fall back to regex.
        return await retry_llm_then_fallback(
            try_llm=lambda strict: self._try_llm(resume_text, strict=strict),
            fallback=lambda: self._regex_fallback(resume_text),
            agent_name="Resume parsing",
        )

    async def _try_llm(
        self, resume_text: str, *, strict: bool = False
    ) -> ResumeParsingOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            resume_text: Raw resume text.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``ResumeParsingOutput``, or ``None`` on failure.
        """
        prompt = f"Extract structured data from this resume:\n\n{resume_text}"
        rules = (
            _STRICT_RULES
            if strict
            else [
                "Output only valid JSON",
                "Do not infer missing information",
            ]
        )

        logger.debug(
            "LLM resume attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[resume_text],
                response_format="json",
                json_schema=model_to_json_schema(ResumeParsingOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM resume parsing failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM resume response: %s", raw[:200] if raw else "<empty>")
        data = self._parse_json(raw)
        if data is None:
            return None

        try:
            parsed = ResumeParsingOutput(**data)
            parsed.experience = _sort_experience(parsed.experience)
            parsed.skills = _NORMALIZER.normalize_list(parsed.skills)
            return parsed
        except ValidationError:
            logger.warning("LLM output failed Pydantic validation")
            return None

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from an LLM response.

        Thin wrapper over :func:`client.json_utils.parse_json_response`.
        Handles responses wrapped in markdown fences.
        """
        return parse_json_response(raw)

    @staticmethod
    async def _regex_fallback(resume_text: str) -> ResumeParsingOutput:
        """Fall back to FormatDetector regex parsing.

        Converts flat ``ParsedResume`` fields into the structured
        ``ResumeParsingOutput`` schema, wrapping experience entries
        as ``ExperienceEntry`` objects where possible.

        Args:
            resume_text: Raw resume text.

        Returns:
            A ``ResumeParsingOutput`` built from regex-extracted fields.
        """
        fd = FormatDetector()
        parsed = await fd.parse_resume(resume_text)

        logger.debug(
            "Regex fallback results: skills=%d experience=%d projects=%d",
            len(parsed.skills),
            len(parsed.experience),
            len(parsed.projects),
        )

        experience: list[ExperienceEntry] = []
        for entry in parsed.experience:
            experience.append(_parse_experience_line(entry))
        experience = _sort_experience(experience)

        return ResumeParsingOutput(
            summary=parsed.summary,
            skills=_NORMALIZER.normalize_list(parsed.skills),
            experience=experience,
            projects=parsed.projects,
            certifications=parsed.certifications,
            education=parsed.education,
            name=_normalize_extracted_name(parsed.name),
            phone=parsed.phone,
            email=parsed.email,
            linkedin=parsed.linkedin,
            github=parsed.github,
        )


def _normalize_extracted_name(name: str) -> str:
    """Normalize a FormatDetector-extracted name for the resume schema.

    ``FormatDetector`` uses ``"Unknown"`` as its not-found sentinel; the
    ``ResumeParsingOutput.name`` field uses an empty string for absence.
    """
    if not name:
        return ""
    stripped = name.strip()
    return stripped if stripped != "Unknown" else ""


def _extract_start_year(dates: str) -> int | None:
    """Return the first 4-digit year in a dates string, or None.

    Args:
        dates: A dates field such as ``"2020 - Present"``.

    Returns:
        The first ``\\d{4}`` match as an int, or ``None`` when absent.
    """
    match = re.search(r"(\d{4})", dates)
    if match is None:
        return None
    return int(match.group(1))


def _sort_experience(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Sort experience entries most-recent-first (idempotent).

    Entries without a parseable start year sink to the tail, preserving
    their original relative order.  No entries are dropped.
    """
    if not entries:
        return entries
    if not any(_extract_start_year(entry.dates) is not None for entry in entries):
        return entries  # nothing to sort

    def _sort_key(entry: ExperienceEntry) -> tuple[int, int]:
        year = _extract_start_year(entry.dates)
        if year is None:
            return (1, 0)  # no year: tail, stable keeps relative order
        return (0, -year)  # most-recent-first

    return sorted(entries, key=_sort_key)


def _parse_experience_line(line: str) -> ExperienceEntry:
    """Best-effort parse of a flat experience string into an ExperienceEntry.

    Attempts to split on common delimiters (|, --, at, -, etc.) to extract
    title, company, and dates.  Falls back to putting the full line into
    ``responsibilities`` if parsing fails.
    """
    # Pattern: "Title | Company | Dates" or "Title - Company - Dates"
    for sep in [" | ", " -- ", " \u2013 ", " - ", " at "]:
        if sep in line:
            parts = [p.strip() for p in line.split(sep)]
            if len(parts) >= 2:
                logger.debug(
                    "Experience parse: title=%s company=%s dates=%s",
                    parts[0],
                    parts[1] if len(parts) > 1 else "",
                    parts[2] if len(parts) > 2 else "",
                )
                return ExperienceEntry(
                    title=parts[0],
                    company=parts[1] if len(parts) > 1 else "",
                    dates=parts[2] if len(parts) > 2 else "",
                    responsibilities=[line],
                )

    # No delimiter found -- put the whole line as responsibility
    logger.debug("Experience parse: no delimiter found, full line as responsibility")
    return ExperienceEntry(responsibilities=[line])
