"""Tests for FormatDetector regex parsing (no LLM)."""

import pytest

from client.format_detector import FormatDetector


class TestExtractName:
    def test_markdown_h1(self) -> None:
        assert FormatDetector._extract_name("# John Smith\nOther text") == "John Smith"

    def test_no_h1_returns_unknown(self) -> None:
        assert FormatDetector._extract_name("No heading here") == "Unknown"

    def test_empty_string(self) -> None:
        assert FormatDetector._extract_name("") == "Unknown"

    def test_h1_with_extra_whitespace(self) -> None:
        assert FormatDetector._extract_name("#  Jane Doe  \nStuff") == "Jane Doe"


class TestExtractTitle:
    def test_first_h2_in_first_five_lines(self) -> None:
        content = "# Name\n## Senior Developer\nStuff"
        assert FormatDetector._extract_title(content) == "Senior Developer"

    def test_no_h2_returns_unknown(self) -> None:
        content = "# Name\nNo subheadings here"
        assert FormatDetector._extract_title(content) == "Unknown"

    def test_h2_beyond_five_lines_ignored(self) -> None:
        lines = ["# Name"] + [""] * 5 + ["## Too Late"]
        assert FormatDetector._extract_title("\n".join(lines)) == "Unknown"


class TestExtractJobTitle:
    def test_first_non_empty_non_heading_line(self) -> None:
        content = "\nSenior Engineer\nSome description"
        assert FormatDetector._extract_job_title(content) == "Senior Engineer"

    def test_short_line_skipped(self) -> None:
        content = "\nHi\nSenior Engineer"
        assert FormatDetector._extract_job_title(content) == "Senior Engineer"

    def test_returns_position_when_empty(self) -> None:
        assert FormatDetector._extract_job_title("") == "Position"


class TestExtractSection:
    def test_extracts_between_headings(self) -> None:
        content = "## Summary\nHello world\n## Experience\nStuff"
        assert (
            FormatDetector._extract_section(content, r"##\s*Summary") == "Hello world"
        )

    def test_section_at_end_of_file(self) -> None:
        content = "## Skills\nPython\nJavaScript"
        assert (
            FormatDetector._extract_section(content, r"##\s*Skills")
            == "Python\nJavaScript"
        )

    def test_missing_section_returns_empty(self) -> None:
        content = "## Summary\nHello"
        assert FormatDetector._extract_section(content, r"##\s*Skills") == ""


class TestExtractListSection:
    def test_bullets_from_section(self) -> None:
        content = "## Skills\n- Python\n- JavaScript\n- SQL"
        result = FormatDetector._extract_list_section(content, r"##\s*Skills")
        assert result == ["Python", "JavaScript", "SQL"]

    def test_star_bullets(self) -> None:
        content = "## Skills\n* Python\n* JavaScript"
        result = FormatDetector._extract_list_section(content, r"##\s*Skills")
        assert result == ["Python", "JavaScript"]

    def test_empty_section(self) -> None:
        content = "## Skills\nNo bullets here"
        result = FormatDetector._extract_list_section(content, r"##\s*Skills")
        assert result == []

    def test_missing_section(self) -> None:
        content = "## Summary\nHello"
        result = FormatDetector._extract_list_section(content, r"##\s*Skills")
        assert result == []


class TestExtractBulletPoints:
    def test_bullets_after_keyword(self) -> None:
        content = "Requirements\n- Python\n- SQL\n- Git\n"
        result = FormatDetector._extract_bullet_points(content, "requirements")
        assert result == ["Python", "SQL", "Git"]

    def test_no_match(self) -> None:
        content = "Some random text\n- bullet"
        result = FormatDetector._extract_bullet_points(content, "requirements")
        assert result == []

    def test_case_insensitive(self) -> None:
        content = "QUALIFICATIONS\n- Python\n- SQL\n"
        result = FormatDetector._extract_bullet_points(content, "qualifications")
        assert result == ["Python", "SQL"]


class TestSafeJson:
    def test_plain_json(self) -> None:
        raw = '{"key": "value"}'
        assert FormatDetector._safe_json(raw) == {"key": "value"}

    def test_json_in_markdown_fences(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        assert FormatDetector._safe_json(raw) == {"key": "value"}

    def test_json_in_plain_fences(self) -> None:
        raw = '```\n{"key": "value"}\n```'
        assert FormatDetector._safe_json(raw) == {"key": "value"}

    def test_invalid_json_returns_none(self) -> None:
        assert FormatDetector._safe_json("not json at all") is None


class TestInsufficientChecks:
    def test_insufficient_resume_two_empty_lists(self) -> None:
        data = {"skills": [], "experience": [], "education": ["B.S."]}
        assert FormatDetector._is_insufficient_resume(data) is True

    def test_sufficient_resume(self) -> None:
        data = {"skills": ["Python"], "experience": ["Dev"], "education": ["B.S."]}
        assert FormatDetector._is_insufficient_resume(data) is False

    def test_insufficient_jd_two_empty_lists(self) -> None:
        data = {"responsibilities": [], "requirements": [], "nice_to_have": []}
        assert FormatDetector._is_insufficient_jd(data) is True

    def test_sufficient_jd(self) -> None:
        data = {
            "responsibilities": ["Build things"],
            "requirements": ["Python"],
            "nice_to_have": [],
        }
        assert FormatDetector._is_insufficient_jd(data) is False


@pytest.mark.asyncio
class TestParseResumeRegex:
    async def test_full_markdown_resume(self, markdown_resume: str) -> None:
        fd = FormatDetector(client=None)
        result = await fd.parse_resume(markdown_resume)
        assert result.name == "Jane Doe"
        assert result.title == "Summary"
        assert "Python" in result.skills
        assert len(result.experience) == 2
        assert len(result.education) == 1

    async def test_real_sample_resume(self, sample_resume: str) -> None:
        fd = FormatDetector(client=None)
        result = await fd.parse_resume(sample_resume)
        assert result.name == "Unknown"  # sample doesn't use # Name heading
        assert result.title == "Unknown"  # sample doesn't use ## Title heading
        assert isinstance(result.skills, list)
        assert isinstance(result.experience, list)
        assert isinstance(result.education, list)


@pytest.mark.asyncio
class TestParseJobDescriptionRegex:
    async def test_full_markdown_jd(self, markdown_jd: str) -> None:
        fd = FormatDetector(client=None)
        result = await fd.parse_job_description(markdown_jd)
        assert result.title == "Senior Backend Engineer"
        assert len(result.requirements) == 3
        assert len(result.responsibilities) == 3
        assert len(result.nice_to_have) == 2

    async def test_real_sample_jd(self, sample_jd: str) -> None:
        fd = FormatDetector(client=None)
        result = await fd.parse_job_description(sample_jd)
        assert result.title  # title is extracted (first non-empty line)
        assert isinstance(result.requirements, list)
        assert isinstance(result.responsibilities, list)
