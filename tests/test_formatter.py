"""Tests for client/formatter.py formatting helpers."""

from client.formatter import (
    _fix_encoding,
    format_cover_letter,
    format_resume_markdown,
    format_resume_plain,
)
from client.models import CoverLetterOutput, ExperienceEntry, RewriteOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _full_resume() -> RewriteOutput:
    """A RewriteOutput populated with every section."""
    return RewriteOutput(
        summary="Senior engineer with 10+ years experience.",
        skills=["Python", "Rust", "Kubernetes"],
        experience=[
            ExperienceEntry(
                title="Staff Engineer",
                company="Acme Corp",
                dates="2020-2024",
                responsibilities=["Led platform team"],
                achievements=["Reduced costs 40%"],
                metrics=["$2M annual savings"],
            ),
            ExperienceEntry(
                title="Senior Engineer",
                company="Globex",
                dates="2016-2020",
                responsibilities=["Built microservices"],
            ),
        ],
        projects=["Open-source CLI tool"],
        certifications=["AWS Solutions Architect"],
        education=["B.Sc. Computer Science, U of T"],
    )


def _empty_resume() -> RewriteOutput:
    """A completely empty RewriteOutput."""
    return RewriteOutput()


# ===================================================================
# format_resume_markdown
# ===================================================================


class TestFormatResumeMarkdown:
    def test_empty_resume(self) -> None:
        result = format_resume_markdown(_empty_resume())
        assert result == ""

    def test_header_with_name_and_title(self) -> None:
        result = format_resume_markdown(_empty_resume(), name="Jane Doe", title="SRE")
        assert result.startswith("# Jane Doe")
        assert "**SRE**" in result

    def test_header_name_only(self) -> None:
        result = format_resume_markdown(_empty_resume(), name="Jane Doe")
        assert "# Jane Doe" in result
        # Title line should not appear
        assert "**" not in result.split("\n")[2:]

    def test_summary_section(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Summary" in result
        assert "Senior engineer with 10+ years" in result

    def test_skills_bullets(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Skills" in result
        for skill in ["Python", "Rust", "Kubernetes"]:
            assert f"- {skill}" in result

    def test_experience_header_and_bullets(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Experience" in result
        assert "### **Staff Engineer** at **Acme Corp** (2020-2024)" in result
        assert "- Led platform team" in result
        assert "- Reduced costs 40%" in result
        assert "- $2M annual savings" in result

    def test_experience_second_job(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "### **Senior Engineer** at **Globex** (2016-2020)" in result

    def test_certifications_section(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Certifications" in result
        assert "- AWS Solutions Architect" in result

    def test_projects_section(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Projects" in result
        assert "- Open-source CLI tool" in result

    def test_education_section(self) -> None:
        result = format_resume_markdown(_full_resume())
        assert "## Education" in result
        assert "- B.Sc. Computer Science, U of T" in result

    def test_full_output_order(self) -> None:
        """Sections should appear in a consistent order."""
        result = format_resume_markdown(_full_resume(), name="X", title="Y")
        lines = result.split("\n")
        summary_i = next(i for i, ln in enumerate(lines) if "## Summary" in ln)
        skills_i = next(i for i, ln in enumerate(lines) if "## Skills" in ln)
        experience_i = next(i for i, ln in enumerate(lines) if "## Experience" in ln)
        certs_i = next(i for i, ln in enumerate(lines) if "## Certifications" in ln)
        projects_i = next(i for i, ln in enumerate(lines) if "## Projects" in ln)
        edu_i = next(i for i, ln in enumerate(lines) if "## Education" in ln)
        assert summary_i < skills_i < experience_i < certs_i < projects_i < edu_i

    def test_experience_no_company(self) -> None:
        resume = RewriteOutput(
            experience=[ExperienceEntry(title="Dev", responsibilities=["Shipped code"])]
        )
        result = format_resume_markdown(resume)
        assert "### **Dev**" in result
        # No " at " since company is empty
        assert " at " not in result

    def test_experience_no_dates(self) -> None:
        resume = RewriteOutput(
            experience=[
                ExperienceEntry(title="Dev", company="Co", responsibilities=["Work"])
            ]
        )
        result = format_resume_markdown(resume)
        assert "### **Dev** at **Co**" in result
        # No parentheses since dates is empty
        assert "(" not in result.split("###")[1]


# ===================================================================
# format_resume_plain
# ===================================================================


class TestFormatResumePlain:
    def test_empty_resume(self) -> None:
        result = format_resume_plain(_empty_resume())
        assert result == ""

    def test_header(self) -> None:
        result = format_resume_plain(_empty_resume(), name="Jane Doe", title="SRE")
        assert result.startswith("Jane Doe")
        # No markdown syntax
        assert "#" not in result

    def test_summary_heading(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "SUMMARY" in result

    def test_skills_heading_and_indent(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "SKILLS" in result
        for skill in ["Python", "Rust", "Kubernetes"]:
            assert f"  {skill}" in result

    def test_experience_heading(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "EXPERIENCE" in result
        # No markdown syntax
        assert "###" not in result

    def test_experience_job_header(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "Staff Engineer at Acme Corp (2020-2024)" in result

    def test_experience_bullets_indent(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "  - Led platform team" in result
        assert "  - Reduced costs 40%" in result

    def test_certifications_heading(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "CERTIFICATIONS" in result
        assert "  AWS Solutions Architect" in result

    def test_projects_heading(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "PROJECTS" in result
        assert "  Open-source CLI tool" in result

    def test_education_heading(self) -> None:
        result = format_resume_plain(_full_resume())
        assert "EDUCATION" in result
        assert "  B.Sc. Computer Science, U of T" in result

    def test_no_markdown_syntax_in_full_output(self) -> None:
        result = format_resume_plain(_full_resume(), name="Jane", title="Eng")
        for md_char in ["#", "*", "_", "`"]:
            assert md_char not in result

    def test_full_output_order(self) -> None:
        result = format_resume_plain(_full_resume())
        lines = result.split("\n")
        summary_i = next(i for i, ln in enumerate(lines) if ln == "SUMMARY")
        skills_i = next(i for i, ln in enumerate(lines) if ln == "SKILLS")
        exp_i = next(i for i, ln in enumerate(lines) if ln == "EXPERIENCE")
        certs_i = next(i for i, ln in enumerate(lines) if ln == "CERTIFICATIONS")
        proj_i = next(i for i, ln in enumerate(lines) if ln == "PROJECTS")
        edu_i = next(i for i, ln in enumerate(lines) if ln == "EDUCATION")
        assert summary_i < skills_i < exp_i < certs_i < proj_i < edu_i


# ===================================================================
# format_cover_letter
# ===================================================================


class TestFormatCoverLetter:
    def test_with_model(self) -> None:
        model = CoverLetterOutput(cover_letter="  Hello world.  ")
        result = format_cover_letter(model)
        assert result == "Hello world."

    def test_with_raw_string(self) -> None:
        result = format_cover_letter("  Dear Hiring Manager,\n")
        assert result == "Dear Hiring Manager,"

    def test_collapses_consecutive_blank_lines(self) -> None:
        text = "Paragraph one.\n\n\n\nParagraph two."
        result = format_cover_letter(text)
        assert "\n\n\n" not in result
        assert "Paragraph one." in result
        assert "Paragraph two." in result

    def test_strips_leading_trailing_whitespace(self) -> None:
        result = format_cover_letter("   \n  Hello  \n  ")
        assert result == "Hello"

    def test_normalizes_internal_whitespace(self) -> None:
        result = format_cover_letter("Hello   world\t\tthere")
        assert result == "Hello world there"

    def test_empty_string(self) -> None:
        result = format_cover_letter("")
        assert result == ""

    def test_encoding_smart_quotes(self) -> None:
        text = "He said \u201chello\u201d and \u2018bye\u2019"
        result = format_cover_letter(text)
        # Smart quotes replaced with ASCII equivalents
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert "\u2018" not in result
        assert "\u2019" not in result
        assert '"hello"' in result
        assert "'bye'" in result

    def test_encoding_dashes(self) -> None:
        text = "A\u2013B and C\u2014D"
        result = format_cover_letter(text)
        assert "A-B" in result
        assert "C-D" in result

    def test_encoding_ellipsis(self) -> None:
        result = format_cover_letter("Wait\u2026")
        assert result == "Wait..."

    def test_encoding_nonbreaking_space(self) -> None:
        result = format_cover_letter("Hello\u00a0world")
        assert result == "Hello world"

    def test_encoding_arrows(self) -> None:
        result = format_cover_letter("Use \u2192 and \u2190")
        assert "Use -> and <-" in result

    def test_multiple_paragraphs_preserved(self) -> None:
        text = "Para one.\n\nPara two.\n\nPara three."
        result = format_cover_letter(text)
        lines = result.split("\n")
        assert "Para one." in lines
        assert "Para two." in lines
        assert "Para three." in lines

    def test_model_with_empty_string(self) -> None:
        model = CoverLetterOutput(cover_letter="")
        result = format_cover_letter(model)
        assert result == ""


# ===================================================================
# _fix_encoding (private helper)
# ===================================================================


class TestFixEncoding:
    def test_all_replacements(self) -> None:
        text = "\u2018a\u2019 \u201cb\u201d \u2013 \u2014 \u2026 \u00a0 \u2192 \u2190"
        result = _fix_encoding(text)
        assert result == "'a' \"b\" - - ...   -> <-"

    def test_no_op_when_clean(self) -> None:
        text = "Plain ASCII text."
        assert _fix_encoding(text) == text

    def test_empty_string(self) -> None:
        assert _fix_encoding("") == ""
