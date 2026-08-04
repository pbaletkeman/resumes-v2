"""
formatter.py
Output formatting utilities for pipeline results.

Converts structured Pydantic models into clean Markdown, plain text, and
cover letter strings suitable for downstream rendering or ATS upload.
"""

from client.models import RewriteOutput


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
