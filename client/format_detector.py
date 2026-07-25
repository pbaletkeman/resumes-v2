"""
format_detector.py
Regex-based document parser for job descriptions and resumes.

Extracts structured fields (skills, experience, requirements, etc.) from
plain-text or Markdown documents without requiring an LLM call.
"""

import re


class FormatDetector:
    """Parses resumes and job descriptions into structured dictionaries.

    All methods are static — no instance state is required. Detection
    relies on Markdown heading patterns (``## Section Name``) and
    bullet-point markers (``-``, ``*``).
    """

    @staticmethod
    def parse_resume(content: str) -> dict[str, str | list[str]]:
        """Parse a resume into structured fields.

        Extracts name, title, summary, skills, experience, and education
        sections using Markdown heading detection.

        Args:
            content: Raw resume text (Markdown or plain text).

        Returns:
            Dictionary with keys: ``name``, ``title``, ``summary``,
            ``skills``, ``experience``, ``education``, ``raw``.
        """
        return {
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
            "raw": content,
        }

    @staticmethod
    def parse_job_description(content: str) -> dict[str, str | list[str]]:
        """Parse a job description into structured fields.

        Extracts title, responsibilities, requirements, and nice-to-have
        items by matching common JD section keywords.

        Args:
            content: Raw job description text.

        Returns:
            Dictionary with keys: ``title``, ``responsibilities``,
            ``requirements``, ``nice_to_have``, ``raw``.
        """
        return {
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

    @staticmethod
    def _extract_name(content: str) -> str:
        """Extract the person's name from a resume.

        Looks for a top-level Markdown heading (``# Name``) as the first
        meaningful line.

        Args:
            content: Raw resume text.

        Returns:
            The extracted name, or ``"Unknown"`` if not found.
        """
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# ") and len(line) > 2:
                return line[2:].strip()
        return "Unknown"

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract the job title from a resume.

        Looks for the first ``##`` heading within the first 5 lines.

        Args:
            content: Raw resume text.

        Returns:
            The extracted title, or ``"Unknown"`` if not found.
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
            The extracted title, or ``"Position"`` if not found.
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

        Finds the section matching ``pattern``, then extracts all lines
        starting with ``-`` or ``*``.

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
                ``"requirements|qualifications"``).

        Returns:
            List of extracted bullet-point strings.
        """
        safe_keyword = re.escape(keyword)
        pattern = rf"(?i){safe_keyword}.*?\n((?:[-*]\s+.+?\n)*)"
        match = re.search(pattern, content)
        if not match:
            return []

        bullets_text = match.group(1)
        if not bullets_text:
            return []
        bullets = re.findall(r"^[-*]\s+(.+?)$", bullets_text, re.MULTILINE)
        return [b.strip() for b in bullets if b.strip()]
