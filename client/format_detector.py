"""
format_detector.py
Document parser for job descriptions and resumes.

Extracts structured fields (skills, experience, requirements, etc.) from
plain-text or Markdown documents. Uses regex-based detection first; falls
back to an LLM when regex returns little or no data.
"""

import json
import logging
import re
from typing import Any

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.model_client import ModelClient
from client.models import ParsedJobDescription, ParsedResume

logger = logging.getLogger(__name__)


class FormatDetector:
    """Parses resumes and job descriptions into validated Pydantic models.

    Uses regex-based detection (Markdown headings, bullet markers) first.
    When regex returns little or no data and an LLM client is available,
    falls back to an LLM call for more robust extraction.

    Args:
        client: Optional `ModelClient` for LLM fallback.  When `None`
            (the default), only regex parsing is used.
    """

    def __init__(self, client: ModelClient | None = None) -> None:
        self.client = client

    async def parse_resume(self, content: str) -> ParsedResume:
        """Parse a resume into structured fields.

        Tries regex extraction first. If the result is sparse and an LLM
        client is available, falls back to LLM-based extraction.

        Args:
            content: Raw resume text (Markdown or plain text).

        Returns:
            Validated `ParsedResume` with all fields populated.
        """
        data: dict[str, Any] = {
            "name": FormatDetector._extract_name(content),
            "title": FormatDetector._extract_title(content),
            "summary": FormatDetector._extract_section(
                content, r"##\s*Summary|##\s*Professional Summary"
            ),
            "skills": FormatDetector._extract_list_section(content, r"##\s*Skills"),
            "experience": FormatDetector._extract_list_section(
                content, r"##\s*Experience"
            ),
            "education": FormatDetector._extract_list_section(
                content, r"##\s*Education"
            ),
            "certifications": FormatDetector._extract_list_section(
                content, r"##\s*Certifications|##\s*Certification"
            ),
            "raw": content,
        }

        if self._is_insufficient_resume(data) and self.client is not None:
            logger.info("Regex parsing sparse, falling back to LLM")
            llm_result = await self._llm_parse_resume(content)
            if llm_result:
                data.update(llm_result)

        return ParsedResume(**data)

    async def parse_job_description(self, content: str) -> ParsedJobDescription:
        """Parse a job description into structured fields.

        Tries regex extraction first. If the result is sparse and an LLM
        client is available, falls back to LLM-based extraction.

        Args:
            content: Raw job description text.

        Returns:
            Validated `ParsedJobDescription` with all fields populated.
        """
        data: dict[str, Any] = {
            "title": FormatDetector._extract_job_title(content),
            "responsibilities": FormatDetector._extract_bullet_points(
                content,
                "responsibilities|responsibility|day to day|what you'll do",
            ),
            "requirements": FormatDetector._extract_bullet_points(
                content,
                "qualifications|requirements|what we're looking for|what you'll bring",
            ),
            "nice_to_have": FormatDetector._extract_bullet_points(
                content, "nice to have"
            ),
            "raw": content,
        }

        if self._is_insufficient_jd(data) and self.client is not None:
            logger.info("Regex parsing sparse, falling back to LLM")
            llm_result = await self._llm_parse_job_description(content)
            if llm_result:
                data.update(llm_result)

        return ParsedJobDescription(**data)

    @staticmethod
    def _extract_name(content: str) -> str:
        """Extract the person's name from a resume.

        Looks for a top-level Markdown heading (`# Name`) as the first
        meaningful line.

        Args:
            content: Raw resume text.

        Returns:
            The extracted name, or `"Unknown"` if not found.
        """
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# ") and len(line) > 2:
                return line[2:].strip()
        return "Unknown"

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract the job title from a resume.

        Looks for the first `##` heading within the first 5 lines.

        Args:
            content: Raw resume text.

        Returns:
            The extracted title, or `"Unknown"` if not found.
        """
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## ") and i < 5:
                return line[3:].strip()
        return "Unknown"

    @staticmethod
    def _extract_job_title(content: str) -> str:
        """Extract the position title from a job description.

        Returns the first non-empty, non-heading line in the first 5 lines.

        Args:
            content: Raw job description text.

        Returns:
            The extracted title, or `"Position"` if not found.
        """
        lines = content.split("\n")
        for line in lines[:5]:
            if len(line) > 5 and not line.startswith("#"):
                return line.strip()
        return "Position"

    @staticmethod
    def _extract_section(content: str, pattern: str) -> str:
        """Extract text between a matching heading and the next heading.

        Args:
            content: Full document text.
            pattern: Regex pattern to match the section heading.

        Returns:
            The section body text, or an empty string if not found.
        """
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            return ""

        start = match.end()
        next_header = re.search(r"^##\s+", content[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(content)
        return content[start:end].strip()

    @staticmethod
    def _extract_list_section(content: str, pattern: str) -> list[str]:
        """Extract bullet-point items from a Markdown section.

        Finds the section matching `pattern`, then extracts all lines
        starting with `-` or `*`.

        Args:
            content: Full document text.
            pattern: Regex pattern to match the section heading.

        Returns:
            List of extracted bullet-point strings.
        """
        section = FormatDetector._extract_section(content, pattern)
        if not section:
            return []

        bullets = re.findall(r"^[-*]\s+(.+?)$", section, re.MULTILINE)
        return [b.strip() for b in bullets if b.strip()]

    @staticmethod
    def _extract_bullet_points(content: str, keyword: str) -> list[str]:
        """Extract bullet points following a keyword-matching line.

        Searches for a line containing any of the pipe-separated keywords,
        then collects the bullet points that follow it.

        Args:
            content: Full document text.
            keyword: Pipe-separated keywords to search for (e.g.
                `"requirements|qualifications"`).

        Returns:
            List of extracted bullet-point strings.
        """
        safe_keyword = "|".join(re.escape(p) for p in keyword.split("|"))
        pattern = rf"(?i)(?:{safe_keyword}).*?\n((?:[-*]\s+.+?\n)*)"
        match = re.search(pattern, content)
        if not match:
            return []

        bullets_text = match.group(1)
        if not bullets_text:
            return []
        bullets = re.findall(r"^[-*]\s+(.+?)$", bullets_text, re.MULTILINE)
        return [b.strip() for b in bullets if b.strip()]

    # ------------------------------------------------------------------
    # Insufficiency checks
    # ------------------------------------------------------------------

    @staticmethod
    def _is_insufficient_resume(result: dict[str, Any]) -> bool:
        """Return True if regex parsing returned too little data."""
        empty_lists = sum(
            1
            for v in result.values()
            if isinstance(v, list) and len(v) == 0  # pyright: ignore[reportUnknownArgumentType]
        )
        empty_strs = sum(
            1 for _, v in result.items() if isinstance(v, str) and v in ("", "Unknown")
        )
        return empty_lists >= 2 or (empty_lists >= 1 and empty_strs >= 2)

    @staticmethod
    def _is_insufficient_jd(result: dict[str, Any]) -> bool:
        """Return True if regex parsing returned too little data."""
        empty_lists = sum(
            1
            for v in result.values()
            if isinstance(v, list) and len(v) == 0  # pyright: ignore[reportUnknownArgumentType]
        )
        return empty_lists >= 2

    # ------------------------------------------------------------------
    # LLM fallback helpers
    # ------------------------------------------------------------------

    async def _llm_parse_resume(
        self, content: str
    ) -> dict[str, str | list[str]] | None:
        """Use an LLM to extract structured resume fields.

        Returns a dict of parsed fields, or `None` on failure.
        """
        prompt = (
            "Extract structured data from this resume. "
            "Return a JSON object with keys: name, title, summary, "
            "skills, experience, education, certifications. "
            "Skills, experience, and certifications must be lists. "
            "Return only valid JSON."
        )
        if self.client is None:
            return None
        try:
            raw = await self.client.chat(
                purpose="Resume parsing agent",
                prompt=prompt,
                output=[
                    "name",
                    "title",
                    "summary",
                    "skills",
                    "experience",
                    "education",
                    "certifications",
                ],
                rules=["Return only valid JSON", "Do not infer missing information"],
                inputs=[content],
            )
            return self._safe_json(raw)
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception("LLM resume parsing failed")
            return None

    async def _llm_parse_job_description(
        self, content: str
    ) -> dict[str, str | list[str]] | None:
        """Use an LLM to extract structured JD fields.

        Returns a dict of parsed fields, or `None` on failure.
        """
        prompt = (
            "Extract structured data from this job description. "
            "Return a JSON object with keys: title, responsibilities, "
            "requirements, nice_to_have. "
            "responsibilities, requirements, and nice_to_have must be lists. "
            "Return only valid JSON."
        )
        if self.client is None:
            return None
        try:
            raw = await self.client.chat(
                purpose="Job description parsing agent",
                prompt=prompt,
                output=["title", "responsibilities", "requirements", "nice_to_have"],
                rules=[
                    "Return only valid JSON",
                    "Do not add information not present in the JD",
                ],
                inputs=[content],
            )
            return self._safe_json(raw)
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception("LLM JD parsing failed")
            return None

    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from an LLM response.

        Handles responses wrapped in markdown fences (```json ... ```).
        """
        text = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            parsed: dict[str, Any] = json.loads(text)
            return parsed
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return None
