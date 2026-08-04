"""
resume_parsing.py
Resume Parsing Agent -- converts resumes into structured JSON.

Uses an LLM to parse a resume into a ``ResumeParsingOutput`` model.
Falls back to ``FormatDetector.parse_resume()`` on LLM failure or
validation errors.
"""

import logging
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.format_detector import FormatDetector
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import ExperienceEntry, ResumeParsingOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Resume Parsing Agent. "
    "Your job is to convert a resume into structured JSON. "
    "Extract the following fields: "
    "summary, skills (normalize terms), "
    "experience (list of roles with: title, company, dates, "
    "responsibilities, achievements, metrics), "
    "projects, certifications, education. "
    "Rules: "
    "Preserve all quantifiable metrics. "
    "Convert bullet points into structured lists. "
    "Do not infer missing information. "
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

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(resume_text, strict=(attempt == 1))
            if result is not None:
                return result

        # Fallback to regex
        logger.info("LLM parsing failed, falling back to regex")
        return await self._regex_fallback(resume_text)

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
            return ResumeParsingOutput(**data)
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

        return ResumeParsingOutput(
            summary=parsed.summary,
            skills=parsed.skills,
            experience=experience,
            projects=parsed.projects,
            certifications=parsed.certifications,
            education=parsed.education,
        )


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
