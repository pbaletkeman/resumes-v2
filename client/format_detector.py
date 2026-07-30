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
from collections import Counter
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

    @staticmethod
    def _section_pattern(name: str) -> str:
        """Build a regex that matches a heading in Markdown or plain-text form.

        Matches ``## Name`` (Markdown) or ``Name:`` (plain text).

        Args:
            name: The heading label (e.g. ``"Skills"``).

        Returns:
            Regex pattern string.
        """
        escaped = re.escape(name)
        return rf"(?:##\s*{escaped}|{escaped}\s*:)"

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
                content,
                FormatDetector._section_pattern("Summary")
                + r"|"
                + FormatDetector._section_pattern("Professional Summary"),
            ),
            "skills": FormatDetector._extract_list_section(
                content, FormatDetector._section_pattern("Skills")
            ),
            "experience": FormatDetector._extract_list_section(
                content, FormatDetector._section_pattern("Experience")
            ),
            "projects": FormatDetector._extract_projects(content),
            "education": FormatDetector._extract_list_section(
                content, FormatDetector._section_pattern("Education")
            ),
            "certifications": FormatDetector._extract_list_section(
                content,
                FormatDetector._section_pattern("Certifications")
                + r"|"
                + FormatDetector._section_pattern("Certification"),
            ),
            "keywords": FormatDetector.extract_keywords(content),
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
                "responsibilities|responsibility|day to day|what you'll do"
                "|key responsibilities|what the role involves",
            ),
            "requirements": FormatDetector._extract_bullet_points(
                content,
                "qualifications|requirements|what we're looking for|what you'll bring"
                "|must have|minimum qualifications|required skills|required experience",
            ),
            "nice_to_have": FormatDetector._extract_bullet_points(
                content,
                "nice to have|additional experience desired|preferred qualifications"
                "|bonus|nice-to-have|optional|desirable",
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
        meaningful line, or falls back to the first non-empty line for
        plain-text resumes.

        Args:
            content: Raw resume text.

        Returns:
            The extracted name, or `"Unknown"` if not found.
        """
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip().lstrip("\ufeff\xef\xbb\xbf")
            if not stripped:
                continue
            if stripped.startswith("# ") and len(stripped) > 2:
                return stripped[2:].strip()
            return stripped
        return "Unknown"

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract the job title from a resume.

        Looks for the first `##` heading within the first 5 lines, or
        the second non-empty line for plain-text resumes.

        Args:
            content: Raw resume text.

        Returns:
            The extracted title, or `"Unknown"` if not found.
        """
        lines = content.split("\n")
        non_empty = [line.strip() for line in lines if line.strip()]
        for i, line in enumerate(non_empty[:5]):
            if line.startswith("## ") and i < 5:
                return line[3:].strip()
        if len(non_empty) >= 2:
            return non_empty[1]
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

        Handles both Markdown headings (``## Name``) and plain-text
        headings (``Name:``) as section boundaries.

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
        # Match the next Markdown heading OR the next plain-text heading
        # (a line starting with a Capitalised word/phrase followed by a colon).
        next_header = re.search(
            r"^(?:##\s+|[A-Z][\w\s/]*:\s*$)",
            content[start:],
            re.MULTILINE,
        )
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
        """Extract bullet points or content lines following a keyword-matching line.

        Searches for a line containing any of the pipe-separated keywords,
        then collects the bullet points or non-empty content lines that follow.
        Handles both ``- item`` / ``* item`` bullet markers and plain text
        lines.

        Args:
            content: Full document text.
            keyword: Pipe-separated keywords to search for (e.g.
                `"requirements|qualifications"`).

        Returns:
            List of extracted item strings.
        """
        safe_keyword = "|".join(re.escape(p) for p in keyword.split("|"))
        # Find the keyword heading line - the keyword must be the main
        # content of the line (not just a word in a sentence).
        heading_re = re.compile(
            rf"(?i)^\s*(?:{safe_keyword})\s*[.:]?\s*$", re.MULTILINE
        )
        match = heading_re.search(content)
        if not match:
            return []

        start = match.end()
        # Collect lines after the heading, skipping blank lines, stopping
        # at the next heading-like line (starts with a capital letter and
        # ends with nothing or a colon, or matches ## Markdown heading).
        lines = content[start:].split("\n")
        items: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if items:
                    break  # blank line after content = end of section
                continue
            # Stop if we hit another section heading
            if re.match(r"^(?:##\s+|[A-Z][\w\s/]*:\s*$)", stripped):
                break
            # Strip bullet markers
            cleaned = re.sub(r"^[-*]\s+", "", stripped)
            if cleaned:
                items.append(cleaned)
        return items

    # ------------------------------------------------------------------
    # Extended extraction (Phase 2.1)
    # ------------------------------------------------------------------

    _STOPWORDS: set[str] = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "this",
        "that",
        "these",
        "those",
        "i",
        "we",
        "you",
        "he",
        "she",
        "it",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "where",
        "when",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "again",
        "also",
        "am",
        "any",
        "because",
        "before",
        "below",
        "between",
        "into",
        "through",
        "during",
        "out",
        "off",
        "over",
        "under",
        "further",
        "then",
        "once",
        "here",
        "there",
        "if",
        "nor",
        "while",
        "up",
        "down",
    }

    @staticmethod
    def _extract_projects(content: str) -> list[str]:
        """Extract bullet-point items from a Projects section.

        Args:
            content: Raw resume text.

        Returns:
            List of project description strings.
        """
        return FormatDetector._extract_list_section(
            content, FormatDetector._section_pattern("Projects")
        )

    @staticmethod
    def _extract_metrics(text: str) -> list[str]:
        """Extract quantifiable metrics from text.

        Finds percentages, dollar amounts, team sizes, and timeframes.

        Args:
            text: Text to search for metrics.

        Returns:
            List of metric strings found in the text.
        """
        patterns = [
            r"\d+(?:\.\d+)?%",  # percentages
            r"\$[\d,]+(?:\.\d+)?(?:[KMB])?",  # dollar amounts
            r"team of \d+",  # team sizes
            r"\d+ (?:months?|years?|weeks?)",  # timeframes
        ]
        metrics: list[str] = []
        for pat in patterns:
            metrics.extend(re.findall(pat, text, re.IGNORECASE))
        return metrics

    @staticmethod
    def extract_keywords(content: str, top_n: int = 20) -> list[str]:
        """Extract top frequency-based keywords from content.

        Splits on whitespace and punctuation, filters stopwords, and
        returns the most frequent meaningful terms.

        Args:
            content: Full document text.
            top_n: Number of top keywords to return.

        Returns:
            List of the most frequent non-stopword terms.
        """
        words = re.findall(r"[a-zA-Z0-9#+.]+", content.lower())
        filtered = [
            w for w in words if w not in FormatDetector._STOPWORDS and len(w) > 1
        ]
        counts = Counter(filtered)
        return [word for word, _ in counts.most_common(top_n)]

    @staticmethod
    def _detect_format(content: str) -> str:
        """Detect whether content is Markdown or plain text.

        Args:
            content: Raw document text.

        Returns:
            ``"markdown"`` if Markdown patterns are found, else ``"plain"``.
        """
        if re.search(r"^##\s+", content, re.MULTILINE):
            return "markdown"
        return "plain"

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
            "skills, experience, projects, education, certifications, keywords. "
            "Every value must be a string or a list of flat strings. "
            "For experience, each item must be a single descriptive string. "
            "For projects and education, each item must be a single string. "
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
                    "projects",
                    "education",
                    "certifications",
                    "keywords",
                ],
                rules=["Return only valid JSON", "Do not infer missing information"],
                inputs=[content],
            )
            result = self._safe_json(raw)
            if result is not None:
                result = self._normalize_list_fields(result)
            return result
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
    def _normalize_list_fields(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten list values that contain dicts into flat strings.

        LLM responses sometimes return structured dicts for fields like
        ``experience`` or ``education``.  This converts each dict to a
        readable string so the result fits ``list[str]`` fields.
        """
        list_keys = ("experience", "projects", "education", "certifications")
        for key in list_keys:
            if key not in data or not isinstance(data[key], list):
                continue
            flat: list[str] = []
            for item in data[key]:
                if isinstance(item, str):
                    flat.append(item)
                elif isinstance(item, dict):
                    # Join all values into a single descriptive string
                    flat.append(" - ".join(str(v) for v in item.values() if v))
            data[key] = flat
        return data

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
