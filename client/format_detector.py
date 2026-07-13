"""
format_detector.py
Detects and normalizes job descriptions and resumes into structured format.
"""

import json
import re


class FormatDetector:
    """Detects document format (Markdown, plain text, etc.) and extracts sections."""

    @staticmethod
    def parse_resume(content: str) -> dict:
        """Parse resume and extract structured fields."""
        return {
            "name": FormatDetector._extract_name(content),
            "title": FormatDetector._extract_title(content),
            "summary": FormatDetector._extract_section(content, r"##\s*Summary|##\s*Professional Summary"),
            "skills": FormatDetector._extract_list_section(content, r"##\s*Skills"),
            "experience": FormatDetector._extract_list_section(content, r"##\s*Experience"),
            "education": FormatDetector._extract_list_section(content, r"##\s*Education"),
            "raw": content,
        }

    @staticmethod
    def parse_job_description(content: str) -> dict:
        """Parse job description and extract structured fields."""
        return {
            "title": FormatDetector._extract_job_title(content),
            "responsibilities": FormatDetector._extract_bullet_points(content, "responsibility|responsibility|day look|work"),
            "requirements": FormatDetector._extract_bullet_points(content, "qualifications|requirements|experience|requirements look for"),
            "nice_to_have": FormatDetector._extract_bullet_points(content, "nice to have"),
            "raw": content,
        }

    @staticmethod
    def _extract_name(content: str) -> str:
        """Extract person name from resume."""
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# ") and len(line) > 2:
                return line[2:].strip()
        return "Unknown"

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract job title from resume."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## ") and i < 5:
                return line[3:].strip()
        return "Unknown"

    @staticmethod
    def _extract_job_title(content: str) -> str:
        """Extract job title from JD."""
        lines = content.split("\n")
        for line in lines[:5]:
            if len(line) > 5 and not line.startswith("#"):
                return line.strip()
        return "Position"

    @staticmethod
    def _extract_section(content: str, pattern: str) -> str:
        """Extract section content by header pattern."""
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            return ""

        start = match.end()
        next_header = re.search(r"^##\s+", content[start:], re.MULTILINE)
        end = start + next_header.start() if next_header else len(content)
        return content[start:end].strip()

    @staticmethod
    def _extract_list_section(content: str, pattern: str) -> list:
        """Extract bullet-pointed list from section."""
        section = FormatDetector._extract_section(content, pattern)
        if not section:
            return []

        bullets = re.findall(r"^[•\-\*]\s+(.+?)$", section, re.MULTILINE)
        return [b.strip() for b in bullets if b.strip()]

    @staticmethod
    def _extract_bullet_points(content: str, keyword: str) -> list:
        """Extract bullet points near keyword."""
        pattern = rf"(?i){keyword}.*?\n((?:[•\-\*]\s+.+?\n)*)"
        match = re.search(pattern, content)
        if not match:
            return []

        bullets_text = match.group(1)
        if not bullets_text:
            return []
        bullets = re.findall(r"^[•\-\*]\s+(.+?)$", bullets_text, re.MULTILINE)
        return [b.strip() for b in bullets if b.strip()]
