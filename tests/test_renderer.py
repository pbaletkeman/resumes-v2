"""Tests for client/templates/renderer.py ResumeRenderer.

Shared ``RewriteOutput`` / ``CoverLetterOutput`` fixtures come from
``tests/conftest.py`` (``rewrite_output`` / ``cover_letter_output``).
"""

from pathlib import Path

import pytest

from client.models import CoverLetterOutput, RewriteOutput
from client.templates.renderer import ResumeRenderer


def test_renderer_instantiates() -> None:
    """A ResumeRenderer can be built without triggering any runtime import."""
    renderer = ResumeRenderer()
    assert isinstance(renderer, ResumeRenderer)


# ===================================================================
# render_plaintext
# ===================================================================


def test_plaintext_contains_header(rewrite_output: RewriteOutput) -> None:
    """The plaintext header includes the candidate name and title."""
    rendered = ResumeRenderer().render_plaintext(
        rewrite_output, name="Jane Doe", title="Staff Engineer"
    )
    assert "Jane Doe" in rendered
    assert "Staff Engineer" in rendered


def test_plaintext_contains_sections(rewrite_output: RewriteOutput) -> None:
    """All expected sections render with their content."""
    rendered = ResumeRenderer().render_plaintext(rewrite_output)
    assert "Senior engineer with 10+ years experience." in rendered
    assert "Python" in rendered
    assert "Rust" in rendered
    assert "Kubernetes" in rendered
    assert "Led platform team" in rendered
    assert "Reduced costs 40%" in rendered
    assert "$2M annual savings" in rendered
    assert "Open-source CLI tool" in rendered
    assert "AWS Solutions Architect" in rendered
    assert "B.Sc. Computer Science, U of T" in rendered


def test_plaintext_section_order(rewrite_output: RewriteOutput) -> None:
    """Sections appear in the template order (SUMMARY, SKILLS, EXPERIENCE, ...)."""
    rendered = ResumeRenderer().render_plaintext(rewrite_output)
    assert rendered.index("SUMMARY") < rendered.index("SKILLS")
    assert rendered.index("SKILLS") < rendered.index("EXPERIENCE")
    assert rendered.index("EXPERIENCE") < rendered.index("EDUCATION")


def test_plaintext_omits_optional_sections_when_empty() -> None:
    """Empty certifications/projects are omitted entirely."""
    resume = RewriteOutput(
        summary="Just a summary.",
        skills=[],
        experience=[],
        projects=[],
        certifications=[],
        education=["MIT"],
    )
    rendered = ResumeRenderer().render_plaintext(resume)
    assert "CERTIFICATIONS" not in rendered
    assert "PROJECTS" not in rendered
    assert "EDUCATION" in rendered


def test_plaintext_unknown_template_raises(rewrite_output: RewriteOutput) -> None:
    """An unknown template key raises KeyError."""
    with pytest.raises(KeyError):
        ResumeRenderer().render_plaintext(rewrite_output, template="does-not-exist")


# ===================================================================
# render_markdown
# ===================================================================


def test_markdown_contains_header(rewrite_output: RewriteOutput) -> None:
    """The Markdown header includes the candidate name and title."""
    rendered = ResumeRenderer().render_markdown(
        rewrite_output, name="Jane Doe", title="Staff Engineer"
    )
    assert "# Jane Doe" in rendered
    assert "Staff Engineer" in rendered


def test_markdown_contains_sections(rewrite_output: RewriteOutput) -> None:
    """All expected sections render with their content."""
    rendered = ResumeRenderer().render_markdown(rewrite_output)
    assert "## Summary" in rendered
    assert "## Skills" in rendered
    assert "## Experience" in rendered
    assert "## Education" in rendered
    assert "Senior engineer with 10+ years experience." in rendered
    assert "- Python" in rendered
    assert "Led platform team" in rendered
    assert "- Open-source CLI tool" in rendered
    assert "- AWS Solutions Architect" in rendered


def test_markdown_section_order(rewrite_output: RewriteOutput) -> None:
    """Markdown sections appear in the template order."""
    rendered = ResumeRenderer().render_markdown(rewrite_output)
    assert rendered.index("## Summary") < rendered.index("## Skills")
    assert rendered.index("## Skills") < rendered.index("## Experience")
    assert rendered.index("## Experience") < rendered.index("## Education")


def test_markdown_unknown_template_raises(rewrite_output: RewriteOutput) -> None:
    """An unknown template key raises KeyError."""
    with pytest.raises(KeyError):
        ResumeRenderer().render_markdown(rewrite_output, template="does-not-exist")


# ===================================================================
# Template loading
# ===================================================================


@pytest.mark.parametrize("template", ["modern", "classic", "minimal"])
def test_all_templates_render(rewrite_output: RewriteOutput, template: str) -> None:
    """Every built-in template renders both formats without error."""
    renderer = ResumeRenderer()
    plain = renderer.render_plaintext(rewrite_output, template=template)
    md = renderer.render_markdown(rewrite_output, template=template)
    assert "Senior engineer" in plain
    assert "Senior engineer" in md


# ===================================================================
# _clean_output
# ===================================================================


def test_clean_output_collapses_blank_lines() -> None:
    """Consecutive blank lines are collapsed to a single one."""
    cleaned = ResumeRenderer._clean_output("a\n\n\n\nb")
    assert cleaned == "a\n\nb"


def test_clean_output_strips_outer_whitespace() -> None:
    """Leading/trailing blank lines are removed and the result is stripped."""
    cleaned = ResumeRenderer._clean_output("\n\n  hello  \n\n")
    assert cleaned == "hello"


def test_clean_output_keeps_single_blank_line() -> None:
    """A single blank line between content lines is preserved."""
    cleaned = ResumeRenderer._clean_output("a\n\nb")
    assert cleaned == "a\n\nb"


# ===================================================================
# render_cover_letter_plaintext / render_cover_letter_markdown
# ===================================================================


def test_cover_letter_plaintext_contains_body(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The plaintext letter includes the body text."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "I am excited to apply for the role." in rendered


def test_cover_letter_plaintext_contains_salutation(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The plaintext letter opens with a salutation."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "Dear Hiring Manager," in rendered


def test_cover_letter_plaintext_contains_signature(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The plaintext letter ends with the candidate's signature."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "Sincerely," in rendered
    assert "Jane Doe" in rendered


def test_cover_letter_markdown_contains_body(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The Markdown letter includes the body text."""
    rendered = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "I am excited to apply for the role." in rendered


def test_cover_letter_markdown_contains_salutation(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The Markdown letter opens with a salutation."""
    rendered = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "Dear Hiring Manager," in rendered


def test_cover_letter_markdown_contains_signature(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The Markdown letter ends with the candidate's signature."""
    rendered = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert "Sincerely," in rendered
    assert "Jane Doe" in rendered


def test_cover_letter_plaintext_uses_date(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The letter renders today's date in a month-name format."""
    from datetime import date

    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe", company="Acme Corp"
    )
    assert date.today().strftime("%B %d, %Y") in rendered


def test_cover_letter_plaintext_includes_contact_line(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The plaintext letter header includes the provided contact details."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output,
        name="Jane Doe",
        phone="555-1234",
        email="jane@example.com",
        linkedin="https://linkedin.com/in/jane",
        github="https://github.com/jane",
    )
    assert "555-1234 | jane@example.com" in rendered
    assert "https://linkedin.com/in/jane" in rendered
    assert "https://github.com/jane" in rendered


def test_cover_letter_markdown_includes_contact_line(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The Markdown letter header includes the provided contact details."""
    rendered = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output,
        name="Jane Doe",
        email="jane@example.com",
        linkedin="https://linkedin.com/in/jane",
    )
    assert "*jane@example.com | https://linkedin.com/in/jane*" in rendered


def test_cover_letter_omits_contact_line_when_empty(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """Empty contact fields do not render an empty contact line."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe"
    )
    assert " | " not in rendered
    rendered_md = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output, name="Jane Doe"
    )
    assert " | " not in rendered_md


def test_cover_letter_no_blank_line_between_name_and_date(
    cover_letter_output: CoverLetterOutput,
) -> None:
    """The name and date are adjacent lines when no contact info is present."""
    rendered = ResumeRenderer().render_cover_letter_plaintext(
        cover_letter_output, name="Jane Doe"
    )
    assert "Jane Doe\n" in rendered
    assert "Jane Doe\n\n" not in rendered
    rendered_md = ResumeRenderer().render_cover_letter_markdown(
        cover_letter_output, name="Jane Doe"
    )
    assert "Jane Doe\n" in rendered_md
    assert "Jane Doe\n\n" not in rendered_md


# ===================================================================
# build_output_path
# ===================================================================


def test_build_output_path_naming_pattern(tmp_path) -> None:
    """Path follows {dir}/{YYYYMMDD_HHMM}_{candidate}_{company}_{type}.{ext}."""
    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=tmp_path,
        ext=".docx",
    )
    assert path.parent == tmp_path
    assert path.suffix == ".docx"
    assert "jane-doe" in path.name
    assert "acme-corp" in path.name
    assert "resume" in path.name


def test_build_output_path_date_format(tmp_path) -> None:
    """The filename carries a YYYYMMDD_HHMM timestamp prefix."""
    from datetime import datetime

    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="Jane",
        company_name="Acme",
        output_dir=tmp_path,
    )
    parts = path.name.split("_")
    assert len(parts) >= 2
    timestamp = f"{parts[0]}_{parts[1]}"
    datetime.strptime(timestamp, "%Y%m%d_%H%M")  # raises if malformed


def test_build_output_path_slugifies(tmp_path) -> None:
    """Candidate/company segments are lowercase with runs hyphenated."""
    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="Jane  Doe!!!",
        company_name="Acme_Corp",
        output_dir=tmp_path,
    )
    # timestamp prefix ends at the first two underscore-separated parts
    body = "_".join(path.name.split("_")[2:])
    assert "jane-doe" in body
    assert "acme-corp" in body
    assert "!" not in body and "!!!" not in body


def test_build_output_path_ascii_slugify(tmp_path) -> None:
    """Non-ASCII characters are stripped by _slugify."""
    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="café",
        company_name="Acme",
        output_dir=tmp_path,
    )
    body = "_".join(path.name.split("_")[2:])
    assert "caf" in body
    assert not any(ord(c) > 127 for c in body)
    assert "é" not in body


def test_build_output_path_empty_names(tmp_path) -> None:
    """Empty candidate/company yield empty filename segments but a valid path."""
    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="",
        company_name="",
        output_dir=tmp_path,
    )
    assert "__" in path.name.replace(path.name.split("_")[0], "", 1)
    assert path.suffix == ".txt"  # default ext for an unmapped document type


def test_build_output_path_extension_defaults(tmp_path) -> None:
    """Extension defaults map known document types to the right suffix."""
    renderer = ResumeRenderer
    assert (
        renderer.build_output_path(
            "resume_docx", candidate_name="A", company_name="B", output_dir=tmp_path
        ).suffix
        == ".docx"
    )
    assert (
        renderer.build_output_path(
            "resume_pdf", candidate_name="A", company_name="B", output_dir=tmp_path
        ).suffix
        == ".pdf"
    )
    assert (
        renderer.build_output_path(
            "markdown", candidate_name="A", company_name="B", output_dir=tmp_path
        ).suffix
        == ".md"
    )


def test_build_output_path_unknown_type_defaults_to_txt(tmp_path) -> None:
    """An unrecognized document type falls back to .txt."""
    path = ResumeRenderer.build_output_path(
        "mystery", candidate_name="A", company_name="B", output_dir=tmp_path
    )
    assert path.suffix == ".txt"


def test_build_output_path_ext_normalized(tmp_path) -> None:
    """A dotless extension gets a leading dot added."""
    path = ResumeRenderer.build_output_path(
        "resume",
        candidate_name="A",
        company_name="B",
        output_dir=tmp_path,
        ext="docx",
    )
    assert path.suffix == ".docx"


# ===================================================================
# render_all
# ===================================================================


def test_render_all_returns_six_keys(
    rewrite_output: RewriteOutput,
    cover_letter_output: CoverLetterOutput,
    tmp_path,
    monkeypatch,
) -> None:
    """render_all returns all 6 format keys when a cover letter is present."""
    renderer = ResumeRenderer()
    monkeypatch.setattr(renderer, "render_plaintext", lambda *a, **k: "plain")
    monkeypatch.setattr(renderer, "render_markdown", lambda *a, **k: "md")
    monkeypatch.setattr(renderer, "render_docx", lambda *a, **k: Path("d.docx"))
    monkeypatch.setattr(renderer, "render_pdf", lambda *a, **k: Path("d.pdf"))
    monkeypatch.setattr(
        renderer, "render_cover_letter_plaintext", lambda *a, **k: "clp"
    )
    monkeypatch.setattr(renderer, "render_cover_letter_markdown", lambda *a, **k: "clm")

    paths = renderer.render_all(
        rewrite_output,
        cover_letter_output,
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=tmp_path,
    )
    assert set(paths.keys()) == {
        "resume_plaintext",
        "resume_markdown",
        "resume_docx",
        "resume_pdf",
        "cover_letter_plaintext",
        "cover_letter_markdown",
    }
    assert all(isinstance(p, Path) for p in paths.values())


def test_render_all_skips_letter_without_cover_letter(
    rewrite_output: RewriteOutput,
    tmp_path,
    monkeypatch,
) -> None:
    """When cover_letter is None the two letter keys are absent."""
    renderer = ResumeRenderer()
    monkeypatch.setattr(renderer, "render_plaintext", lambda *a, **k: "plain")
    monkeypatch.setattr(renderer, "render_markdown", lambda *a, **k: "md")
    monkeypatch.setattr(renderer, "render_docx", lambda *a, **k: Path("d.docx"))
    monkeypatch.setattr(renderer, "render_pdf", lambda *a, **k: Path("d.pdf"))

    paths = renderer.render_all(
        rewrite_output,
        None,
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=tmp_path,
    )
    assert set(paths.keys()) == {
        "resume_plaintext",
        "resume_markdown",
        "resume_docx",
        "resume_pdf",
    }


def test_render_all_creates_output_dir(
    rewrite_output: RewriteOutput,
    tmp_path,
    monkeypatch,
) -> None:
    """render_all creates the output directory before writing."""
    nested = tmp_path / "a" / "b"
    renderer = ResumeRenderer()
    monkeypatch.setattr(renderer, "render_plaintext", lambda *a, **k: "plain")
    monkeypatch.setattr(renderer, "render_markdown", lambda *a, **k: "md")
    monkeypatch.setattr(renderer, "render_docx", lambda *a, **k: Path("d.docx"))
    monkeypatch.setattr(renderer, "render_pdf", lambda *a, **k: Path("d.pdf"))

    renderer.render_all(
        rewrite_output,
        None,
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=nested,
    )
    assert nested.is_dir()


def test_render_all_writes_timestamped_files(
    rewrite_output: RewriteOutput,
    cover_letter_output: CoverLetterOutput,
    tmp_path,
    monkeypatch,
) -> None:
    """render_all writes real text files with the expected naming pattern."""
    renderer = ResumeRenderer()
    monkeypatch.setattr(renderer, "render_plaintext", lambda *a, **k: "hello world")
    monkeypatch.setattr(renderer, "render_markdown", lambda *a, **k: "md body")
    monkeypatch.setattr(renderer, "render_docx", lambda *a, **k: Path("d.docx"))
    monkeypatch.setattr(renderer, "render_pdf", lambda *a, **k: Path("d.pdf"))
    monkeypatch.setattr(
        renderer, "render_cover_letter_plaintext", lambda *a, **k: "cl plain"
    )
    monkeypatch.setattr(
        renderer, "render_cover_letter_markdown", lambda *a, **k: "cl md"
    )

    paths = renderer.render_all(
        rewrite_output,
        cover_letter_output,
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=tmp_path,
    )
    resume_txt = paths["resume_plaintext"]
    assert resume_txt.parent == tmp_path
    assert resume_txt.suffix == ".txt"
    assert "jane-doe" in resume_txt.name
    assert "acme-corp" in resume_txt.name
    assert resume_txt.read_text() == "hello world"

    md_file = paths["resume_markdown"]
    assert md_file.suffix == ".md"
    assert md_file.read_text() == "md body"

    letter_txt = paths["cover_letter_plaintext"]
    assert letter_txt.suffix == ".txt"
    assert letter_txt.read_text() == "cl plain"


def test_render_all_renders_with_empty_segments(
    rewrite_output: RewriteOutput,
    cover_letter_output: CoverLetterOutput,
    tmp_path,
    monkeypatch,
) -> None:
    """render_all renders files even with empty candidate/company segments."""
    renderer = ResumeRenderer()
    monkeypatch.setattr(renderer, "render_plaintext", lambda *a, **k: "plain")
    monkeypatch.setattr(renderer, "render_markdown", lambda *a, **k: "md")
    monkeypatch.setattr(renderer, "render_docx", lambda *a, **k: Path("d.docx"))
    monkeypatch.setattr(renderer, "render_pdf", lambda *a, **k: Path("d.pdf"))

    paths = renderer.render_all(
        rewrite_output,
        cover_letter_output,
        candidate_name="",
        company_name="",
        output_dir=tmp_path,
    )
    assert set(paths.keys()) == {
        "resume_plaintext",
        "resume_markdown",
        "resume_docx",
        "resume_pdf",
        "cover_letter_plaintext",
        "cover_letter_markdown",
    }


def test_render_all_cover_letter_files_include_contact_info(
    rewrite_output: RewriteOutput,
    cover_letter_output: CoverLetterOutput,
    tmp_path,
) -> None:
    """Contact info passes through render_all into the written letter files."""
    paths = ResumeRenderer().render_all(
        rewrite_output,
        cover_letter_output,
        candidate_name="Jane Doe",
        company_name="Acme Corp",
        output_dir=tmp_path,
        phone="555-1234",
        email="jane@example.com",
        linkedin="https://linkedin.com/in/jane",
        github="https://github.com/jane",
    )
    contact_line = "555-1234 | jane@example.com | https://linkedin.com/in/jane | https://github.com/jane"
    for key in ("cover_letter_plaintext", "cover_letter_markdown"):
        text = paths[key].read_text(encoding="utf-8")
        assert contact_line in text


# ===================================================================
# DOCX / PDF smoke tests
# ===================================================================


def test_render_docx_produces_nonempty_file(
    rewrite_output: RewriteOutput, tmp_path
) -> None:
    """render_docx writes a non-empty .docx file."""
    pytest.importorskip("docx")
    out = tmp_path / "resume.docx"
    path = ResumeRenderer().render_docx(
        rewrite_output, name="Jane Doe", output_path=out
    )
    assert path == out
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.suffix == ".docx"


def test_render_pdf_produces_nonempty_file(
    rewrite_output: RewriteOutput, tmp_path
) -> None:
    """render_pdf writes a non-empty PDF file."""
    pytest.importorskip("reportlab")
    out = tmp_path / "resume.pdf"
    path = ResumeRenderer().render_pdf(rewrite_output, name="Jane Doe", output_path=out)
    assert path == out
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes().startswith(b"%PDF")
