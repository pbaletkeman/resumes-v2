"""
renderer.py
Template-based multi-format resume renderer.

Renders ``RewriteOutput`` models against Jinja2 templates to produce
plaintext and Markdown output.  DOCX/PDF support will be added in
subsequent phases.
"""

from pathlib import Path

from jinja2 import BaseLoader, Environment, StrictUndefined

from client.models import RewriteOutput
from client.templates import TEMPLATES


class ResumeRenderer:
    """Renders resume data using Jinja2 templates.

    Templates are loaded from the ``client.templates`` package by default.
    Pass *template_dir* to load from a custom directory instead.

    Args:
        template_dir: Optional directory to load ``.j2`` template files from.
            When ``None`` (the default), uses the built-in template dicts
            from ``client.templates``.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        self._template_dir = template_dir
        self._env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        # Built-in templates from the package
        self._templates: dict[str, dict[str, str]] = dict(TEMPLATES)

    def render_plaintext(
        self,
        resume: RewriteOutput,
        *,
        name: str = "",
        title: str = "",
        template: str = "modern",
    ) -> str:
        """Render *resume* as clean plaintext using the named template.

        Args:
            resume: Structured resume data from the Resume Rewrite Agent.
            name: Candidate name for the header.
            title: Candidate title for the header.
            template: Template key (``"modern"``, ``"classic"``, or
                ``"minimal"``).

        Returns:
            A rendered plaintext string.

        Raises:
            KeyError: If *template* is not found.
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_dict = self._templates[template]
        tpl_source = tpl_dict["plaintext"]

        context = self._build_context(resume, name=name, title=title)
        rendered = self._env.from_string(tpl_source).render(**context)
        return self._clean_output(rendered)

    def render_markdown(
        self,
        resume: RewriteOutput,
        *,
        name: str = "",
        title: str = "",
        template: str = "modern",
    ) -> str:
        """Render *resume* as Markdown using the named template.

        Args:
            resume: Structured resume data from the Resume Rewrite Agent.
            name: Candidate name for the header.
            title: Candidate title for the header.
            template: Template key (``"modern"``, ``"classic"``, or
                ``"minimal"``).

        Returns:
            A rendered Markdown string.

        Raises:
            KeyError: If *template* is not found.
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_dict = self._templates[template]
        tpl_source = tpl_dict["markdown"]

        context = self._build_context(resume, name=name, title=title)
        rendered = self._env.from_string(tpl_source).render(**context)
        return self._clean_output(rendered)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(
        resume: RewriteOutput,
        *,
        name: str = "",
        title: str = "",
    ) -> dict[str, object]:
        """Convert a ``RewriteOutput`` into a Jinja2 template context dict."""
        return {
            "name": name,
            "title": title,
            "summary": resume.summary,
            "skills": resume.skills,
            "experience": [
                {
                    "title": job.title,
                    "company": job.company,
                    "dates": job.dates,
                    "responsibilities": job.responsibilities,
                    "achievements": job.achievements,
                    "metrics": job.metrics,
                }
                for job in resume.experience
            ],
            "projects": resume.projects,
            "certifications": resume.certifications,
            "education": resume.education,
        }

    @staticmethod
    def _clean_output(text: str) -> str:
        """Collapse excessive blank lines produced by Jinja2 templates."""
        lines = text.split("\n")
        cleaned: list[str] = []
        prev_blank = False
        for line in lines:
            stripped = line.rstrip()
            is_blank = stripped == ""
            if is_blank and prev_blank:
                continue
            cleaned.append(stripped)
            prev_blank = is_blank
        return "\n".join(cleaned).strip()
