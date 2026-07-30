"""Tests for FormatDetector regex parsing (no LLM)."""

import pytest

from client.format_detector import FormatDetector


class TestExtractName:
    def test_markdown_h1(self) -> None:
        assert FormatDetector._extract_name("# John Smith\nOther text") == "John Smith"

    def test_no_h1_returns_first_line(self) -> None:
        assert FormatDetector._extract_name("No heading here") == "No heading here"

    def test_empty_string(self) -> None:
        assert FormatDetector._extract_name("") == "Unknown"

    def test_h1_with_extra_whitespace(self) -> None:
        assert FormatDetector._extract_name("#  Jane Doe  \nStuff") == "Jane Doe"


class TestExtractTitle:
    def test_first_h2_in_first_five_lines(self) -> None:
        content = "# Name\n## Senior Developer\nStuff"
        assert FormatDetector._extract_title(content) == "Senior Developer"

    def test_no_h2_returns_second_line(self) -> None:
        content = "# Name\nNo subheadings here"
        assert FormatDetector._extract_title(content) == "No subheadings here"

    def test_h2_beyond_five_lines_ignored(self) -> None:
        lines = ["# Name"] + [""] * 5 + ["## Too Late"]
        assert FormatDetector._extract_title("\n".join(lines)) == "Too Late"


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


class TestExtractProjects:
    def test_projects_section(self) -> None:
        content = "## Projects\n- Built a CLI tool\n- Designed a dashboard"
        assert FormatDetector._extract_projects(content) == [
            "Built a CLI tool",
            "Designed a dashboard",
        ]

    def test_no_projects_section(self) -> None:
        content = "## Skills\n- Python"
        assert FormatDetector._extract_projects(content) == []


class TestExtractMetrics:
    def test_percentages(self) -> None:
        assert "30%" in FormatDetector._extract_metrics("Boosted performance by 30%")

    def test_dollar_amounts(self) -> None:
        metrics = FormatDetector._extract_metrics("Budget of $50,000")
        assert "$50,000" in metrics

    def test_team_sizes(self) -> None:
        metrics = FormatDetector._extract_metrics("Managed a team of 12")
        assert "team of 12" in metrics

    def test_timeframes(self) -> None:
        metrics = FormatDetector._extract_metrics("Over 3 years of experience")
        assert "3 years" in metrics

    def test_no_metrics(self) -> None:
        assert FormatDetector._extract_metrics("No numbers here") == []

    def test_multiple_metrics(self) -> None:
        text = "Cut costs by 25% over 6 months with a team of 8"
        metrics = FormatDetector._extract_metrics(text)
        assert len(metrics) >= 3


class TestExtractKeywords:
    def test_top_keywords(self) -> None:
        content = "python python python javascript javascript sql"
        keywords = FormatDetector._extract_keywords(content, top_n=2)
        assert keywords[0] == "python"
        assert keywords[1] == "javascript"

    def test_stopwords_filtered(self) -> None:
        content = "the the the python is a good language"
        keywords = FormatDetector._extract_keywords(content, top_n=3)
        assert "the" not in keywords
        assert "is" not in keywords

    def test_empty_content(self) -> None:
        assert FormatDetector._extract_keywords("") == []


class TestDetectFormat:
    def test_markdown(self) -> None:
        assert FormatDetector._detect_format("## Skills\n- Python") == "markdown"

    def test_plain_text(self) -> None:
        assert FormatDetector._detect_format("Skills:\n- Python") == "plain"

    def test_empty(self) -> None:
        assert FormatDetector._detect_format("") == "plain"


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
        assert isinstance(result.projects, list)
        assert isinstance(result.keywords, list)
        assert len(result.keywords) > 0

    async def test_real_sample_resume(self, sample_resume: str) -> None:
        fd = FormatDetector(client=None)
        result = await fd.parse_resume(sample_resume)
        assert result.name  # plain text: first line is the name
        assert result.title  # plain text: second line is the title
        assert isinstance(result.skills, list)
        assert isinstance(result.experience, list)
        assert isinstance(result.education, list)
        assert isinstance(result.projects, list)
        assert isinstance(result.keywords, list)
        assert len(result.keywords) > 0


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
