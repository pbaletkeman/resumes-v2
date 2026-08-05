"""
renderer.py
Template-based multi-format resume renderer.

Renders ``RewriteOutput`` and ``CoverLetterOutput`` models against
Jinja2 templates to produce plaintext and Markdown output.  DOCX/PDF
support will be added in subsequent phases.
"""

from datetime import date
from pathlib import Path

from jinja2 import BaseLoader, Environment, StrictUndefined

from client.models import CoverLetterOutput, RewriteOutput
from client.templates import TEMPLATES
from client.templates.cover_letter import COVER_LETTER


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

    def render_cover_letter_plaintext(
        self,
        cover_letter: CoverLetterOutput,
        *,
        name: str = "",
        company: str = "",
    ) -> str:
        """Render *cover_letter* as clean plaintext.

        Args:
            cover_letter: Structured letter data from the Cover Letter Agent.
            name: Candidate name for the signature and header.
            company: Target company name (reserved for context).

        Returns:
            A rendered plaintext letter string.

        Raises:
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_source = COVER_LETTER["plaintext"]

        context = self._build_cover_letter_context(
            cover_letter, name=name, company=company
        )
        rendered = self._env.from_string(tpl_source).render(**context)
        return self._clean_output(rendered)

    def render_cover_letter_markdown(
        self,
        cover_letter: CoverLetterOutput,
        *,
        name: str = "",
        company: str = "",
    ) -> str:
        """Render *cover_letter* as Markdown.

        Args:
            cover_letter: Structured data from the Cover Letter Agent.
            name: Candidate name for the signature and header.
            company: Target company name (reserved for context).

        Returns:
            A rendered Markdown letter string.

        Raises:
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_source = COVER_LETTER["markdown"]

        context = self._build_cover_letter_context(
            cover_letter, name=name, company=company
        )
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
    def _build_cover_letter_context(
        cover_letter: CoverLetterOutput,
        *,
        name: str = "",
        company: str = "",
    ) -> dict[str, object]:
        """Convert a ``CoverLetterOutput`` into a Jinja2 context dict.

        The ``COVER_LETTER`` template expects ``candidate_name``, ``date``,
        ``opening_paragraph``, ``body_paragraph``, and ``closing_paragraph``.
        The letter body is split on blank lines into up to three logical
        paragraphs (opening / middle / closing).
        """
        paragraphs = _split_paragraphs(cover_letter.cover_letter)
        opening = paragraphs[0] if paragraphs else ""
        closing = paragraphs[-1] if len(paragraphs) > 1 else ""
        body = "\n\n".join(paragraphs[1:-1]) if len(paragraphs) > 2 else ""
        return {
            "candidate_name": name,
            "company": company,
            "date": date.today().strftime("%B %d, %Y"),
            "opening_paragraph": opening,
            "body_paragraph": body,
            "closing_paragraph": closing,
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


_SALUTATION_PREFIXES = ("dear", "to whom it may concern", "hello", "hi")
_SIGNATURE_PREFIXES = (
    "sincerely",
    "best regards",
    "kind regards",
    "warm regards",
    "regards",
    "yours truly",
    "yours sincerely",
    "respectfully",
)


def _split_paragraphs(text: str) -> list[str]:
    """Split letter text into paragraphs, dropping template-supplied parts.

    The ``COVER_LETTER`` template renders its own salutation and signature,
    so a leading ``Dear ...`` line and a trailing ``Sincerely, ...`` block
    are stripped from the letter body to avoid duplication.
    """
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        return parts
    if _is_salutation(parts[0]):
        parts = parts[1:]
    if parts and _is_signature(parts[-1]):
        parts = parts[:-1]
    return parts


def _is_salutation(paragraph: str) -> bool:
    """Return True when *paragraph* is a standalone greeting line."""
    first_line = paragraph.splitlines()[0].strip().rstrip(",").lower()
    return len(paragraph) < 80 and first_line.startswith(_SALUTATION_PREFIXES)


def _is_signature(paragraph: str) -> bool:
    """Return True when *paragraph* is a standalone closing block."""
    first_line = paragraph.splitlines()[0].strip().rstrip(",").lower()
    return len(paragraph) < 80 and first_line.startswith(_SIGNATURE_PREFIXES)
