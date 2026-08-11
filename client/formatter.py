"""
formatter.py
Output formatting utilities for pipeline results.

Converts structured Pydantic models into clean Markdown, plain text, and
cover letter strings suitable for downstream rendering or ATS upload.

Rendering path: these helpers are the *simpler* of the two rendering
paths.  They build output strings directly (no Jinja2 templates) and
support only single-format text output.  The alternative, template-based
path is ``client/templates/renderer.py`` (``ResumeRenderer``), which
renders the same models as plaintext, Markdown, DOCX, and PDF from one
shared context.  Prefer ``ResumeRenderer`` for multi-format output; use
these helpers when you need a single plain/markdown string without the
template machinery (e.g. quick previews or simple serialization).
"""

from client.models import CoverLetterOutput, RewriteOutput


def format_resume_markdown(
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
) -> str:
    """Convert a ``RewriteOutput`` to clean Markdown.

    Args:
        resume: Structured resume data from the Resume Rewrite Agent.
        name: Candidate name for the header (optional).
        title: Candidate title for the header (optional).

    Returns:
        A Markdown-formatted resume string.
    """
    parts: list[str] = []

    # Header
    if name:
        parts.append(f"# {name}")
        parts.append("")
    if title:
        parts.append(f"**{title}**")
        parts.append("")

    # Summary
    if resume.summary:
        parts.append("## Summary")
        parts.append("")
        parts.append(resume.summary)
        parts.append("")

    # Skills
    if resume.skills:
        parts.append("## Skills")
        parts.append("")
        for skill in resume.skills:
            parts.append(f"- {skill}")
        parts.append("")

    # Experience
    if resume.experience:
        parts.append("## Experience")
        parts.append("")
        for job in resume.experience:
            header = f"### **{job.title}**"
            if job.company:
                header += f" at **{job.company}**"
            if job.dates:
                header += f" ({job.dates})"
            parts.append(header)
            parts.append("")
            for r in job.responsibilities:
                parts.append(f"- {r}")
            for a in job.achievements:
                parts.append(f"- {a}")
            for m in job.metrics:
                parts.append(f"- {m}")
            parts.append("")

    # Certifications
    if resume.certifications:
        parts.append("## Certifications")
        parts.append("")
        for cert in resume.certifications:
            parts.append(f"- {cert}")
        parts.append("")

    # Projects
    if resume.projects:
        parts.append("## Projects")
        parts.append("")
        for project in resume.projects:
            parts.append(f"- {project}")
        parts.append("")

    # Education
    if resume.education:
        parts.append("## Education")
        parts.append("")
        for edu in resume.education:
            parts.append(f"- {edu}")
        parts.append("")

    return "\n".join(parts)


def format_resume_plain(
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
) -> str:
    """Convert a ``RewriteOutput`` to plain-text ATS-friendly format.

    Produces clean text with no Markdown syntax, no special characters,
    and no decorative elements.  Suitable for ATS upload and as input
    to DOCX/PDF rendering pipelines.

    Args:
        resume: Structured resume data from the Resume Rewrite Agent.
        name: Candidate name for the header (optional).
        title: Candidate title for the header (optional).

    Returns:
        A plain-text resume string.
    """
    parts: list[str] = []

    # Header
    if name:
        parts.append(name)
        parts.append("")
    if title:
        parts.append(title)
        parts.append("")

    # Summary
    if resume.summary:
        parts.append("SUMMARY")
        parts.append("")
        parts.append(resume.summary)
        parts.append("")

    # Skills
    if resume.skills:
        parts.append("SKILLS")
        parts.append("")
        for skill in resume.skills:
            parts.append(f"  {skill}")
        parts.append("")

    # Experience
    if resume.experience:
        parts.append("EXPERIENCE")
        parts.append("")
        for job in resume.experience:
            header = job.title
            if job.company:
                header += f" at {job.company}"
            if job.dates:
                header += f" ({job.dates})"
            parts.append(header)
            parts.append("")
            for r in job.responsibilities:
                parts.append(f"  - {r}")
            for a in job.achievements:
                parts.append(f"  - {a}")
            for m in job.metrics:
                parts.append(f"  - {m}")
            parts.append("")

    # Certifications
    if resume.certifications:
        parts.append("CERTIFICATIONS")
        parts.append("")
        for cert in resume.certifications:
            parts.append(f"  {cert}")
        parts.append("")

    # Projects
    if resume.projects:
        parts.append("PROJECTS")
        parts.append("")
        for project in resume.projects:
            parts.append(f"  {project}")
        parts.append("")

    # Education
    if resume.education:
        parts.append("EDUCATION")
        parts.append("")
        for edu in resume.education:
            parts.append(f"  {edu}")
        parts.append("")

    return "\n".join(parts)


def format_cover_letter(
    letter: CoverLetterOutput | str,
) -> str:
    """Clean up cover letter text for output.

    Normalizes whitespace, fixes common encoding artifacts, and ensures
    consistent paragraph spacing (single blank line between paragraphs).

    Args:
        letter: A ``CoverLetterOutput`` model or a raw cover letter string.

    Returns:
        A cleaned cover letter string.
    """
    content: str = (
        letter.cover_letter if isinstance(letter, CoverLetterOutput) else letter
    )

    # Strip leading/trailing whitespace from the whole text
    content = content.strip()

    # Fix common encoding artifacts
    content = _fix_encoding(content)

    # Normalize whitespace within lines (collapse runs of spaces/tabs)
    lines: list[str] = []
    for line in content.split("\n"):
        lines.append(" ".join(line.split()))

    # Rebuild with consistent paragraph spacing:
    # collapse consecutive blank lines into a single blank line
    normalized: list[str] = []
    prev_blank: bool = False
    for line in lines:
        is_blank: bool = line == ""
        if is_blank and prev_blank:
            continue
        normalized.append(line)
        prev_blank = is_blank

    return "\n".join(normalized).strip()


# Common Unicode-to-ASCII replacements for encoding artifacts
_ENCODING_FIXES: list[tuple[str, str]] = [
    ("\u2018", "'"),  # left single quote
    ("\u2019", "'"),  # right single quote
    ("\u201c", '"'),  # left double quote
    ("\u201d", '"'),  # right double quote
    ("\u2013", "-"),  # en dash
    ("\u2014", "-"),  # em dash
    ("\u2026", "..."),  # ellipsis
    ("\u00a0", " "),  # non-breaking space
    ("\u2192", "->"),  # right arrow
    ("\u2190", "<-"),  # left arrow
]


def _fix_encoding(text: str) -> str:
    """Replace common Unicode encoding artifacts with ASCII equivalents."""
    for bad, good in _ENCODING_FIXES:
        text = text.replace(bad, good)
    return text
