"""
renderer.py
Template-based multi-format resume renderer.

Renders ``RewriteOutput`` and ``CoverLetterOutput`` models against
Jinja2 templates to produce plaintext and Markdown output.  DOCX/PDF
support will be added in subsequent phases.
"""

import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast
from xml.sax.saxutils import escape

from docx import Document as create_document
from docx.document import Document as DocumentType
from docx.shared import Inches, Pt
from docx.styles.style import ParagraphStyle
from jinja2 import BaseLoader, Environment, StrictUndefined

try:
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle as PdfParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Flowable,
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ReportLab is required for PDF rendering. Install it with "
        "`uv sync` (adds `reportlab>=4.0` to the project dependencies)."
    ) from exc

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
        phone: str = "",
        email: str = "",
        linkedin: str = "",
        github: str = "",
    ) -> str:
        """Render *cover_letter* as clean plaintext.

        Args:
            cover_letter: Structured letter data from the Cover Letter Agent.
            name: Candidate name for the signature and header.
            company: Target company name (reserved for context).
            phone: Candidate phone number for the header.
            email: Candidate email address for the header.
            linkedin: Candidate LinkedIn profile URL for the header.
            github: Candidate GitHub profile URL for the header.

        Returns:
            A rendered plaintext letter string.

        Raises:
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_source = COVER_LETTER["plaintext"]

        context = self._build_cover_letter_context(
            cover_letter,
            name=name,
            company=company,
            phone=phone,
            email=email,
            linkedin=linkedin,
            github=github,
        )
        rendered = self._env.from_string(tpl_source).render(**context)
        return self._clean_output(rendered)

    def render_cover_letter_markdown(
        self,
        cover_letter: CoverLetterOutput,
        *,
        name: str = "",
        company: str = "",
        phone: str = "",
        email: str = "",
        linkedin: str = "",
        github: str = "",
    ) -> str:
        """Render *cover_letter* as Markdown.

        Args:
            cover_letter: Structured data from the Cover Letter Agent.
            name: Candidate name for the signature and header.
            company: Target company name (reserved for context).
            phone: Candidate phone number for the header.
            email: Candidate email address for the header.
            linkedin: Candidate LinkedIn profile URL for the header.
            github: Candidate GitHub profile URL for the header.

        Returns:
            A rendered Markdown letter string.

        Raises:
            jinja2.UndefinedError: If the template references a variable
                that is not provided.
        """
        tpl_source = COVER_LETTER["markdown"]

        context = self._build_cover_letter_context(
            cover_letter,
            name=name,
            company=company,
            phone=phone,
            email=email,
            linkedin=linkedin,
            github=github,
        )
        rendered = self._env.from_string(tpl_source).render(**context)
        return self._clean_output(rendered)

    def render_docx(
        self,
        resume: RewriteOutput,
        *,
        name: str = "",
        title: str = "",
        template: str = "modern",
        output_path: str | Path | None = None,
    ) -> Path:
        """Render *resume* as a professionally styled ``.docx`` document.

        The document uses letter-size pages with 1-inch margins, Calibri
        11pt body text, and the name rendered large and bold.  When
        *output_path* is ``None`` a temporary path is used.

        Args:
            resume: Structured resume data from the Resume Rewrite Agent.
            name: Candidate name for the header.
            title: Candidate title for the header.
            template: Accepted for API consistency (styling is fixed).
            output_path: Destination file. Defaults to a temp file.

        Returns:
            The ``Path`` the document was written to.
        """
        doc: DocumentType = create_document()

        for section in doc.sections:
            section.page_width = Inches(8.5)
            section.page_height = Inches(11)
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        normal = cast(ParagraphStyle, doc.styles["Normal"])
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)

        context = self._build_context(resume, name=name, title=title)
        self._populate_docx_paragraphs(doc, context)

        path = Path(output_path) if output_path is not None else _temp_docx_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(path))
        return path

    def render_pdf(
        self,
        resume: RewriteOutput,
        *,
        name: str = "",
        title: str = "",
        template: str = "modern",
        output_path: str | Path | None = None,
    ) -> Path:
        """Render *resume* as a professionally styled PDF document.

        ReportLab builds the PDF directly with Platypus (no HTML/Markdown
        intermediate).  Letter-size pages with 1-inch margins and the
        shared :meth:`_pdf_styles` styling.  When *output_path* is ``None``
        a temporary path is used.

        Args:
            resume: Structured resume data from the Resume Rewrite Agent.
            name: Candidate name for the header.
            title: Candidate title for the header.
            template: Accepted for API consistency (styling is fixed).
            output_path: Destination file. Defaults to a temp file.

        Returns:
            The ``Path`` the document was written to.
        """
        path = Path(output_path) if output_path is not None else _temp_pdf_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        context = self._build_context(resume, name=name, title=title)
        flowables = self._populate_pdf_flowables(context, self._pdf_styles())
        doc.build(flowables)
        return path

    def render_all(
        self,
        resume: RewriteOutput,
        cover_letter: CoverLetterOutput | None,
        *,
        candidate_name: str,
        company_name: str,
        output_dir: str | Path,
        resume_template: str = "modern",
        phone: str = "",
        email: str = "",
        linkedin: str = "",
        github: str = "",
    ) -> dict[str, Path]:
        """Render *resume* and, when available, *cover_letter* into formats.

        Produces the four resume formats (plaintext, Markdown, DOCX, PDF).
        When *cover_letter* is provided and non-empty, the two cover letter
        formats (plaintext, Markdown) are produced as well; otherwise they
        are skipped.  Each file is written to *output_dir* under a
        timestamped, slugified filename built by :meth:`build_output_path`.

        Args:
            resume: Structured resume data from the Resume Rewrite Agent.
            cover_letter: Structured letter data from the Cover Letter Agent,
                or ``None`` to skip the letter formats.
            candidate_name: Candidate name for headers and filenames.
            company_name: Target company name for filenames.
            output_dir: Directory the rendered files are written to.
            resume_template: Template key for the resume text formats.
            phone: Candidate phone number for cover letter headers.
            email: Candidate email address for cover letter headers.
            linkedin: Candidate LinkedIn profile URL for cover letter headers.
            github: Candidate GitHub profile URL for cover letter headers.

        Returns:
            Mapping of format name to the written ``Path``.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        resume_plain = self.render_plaintext(
            resume, name=candidate_name, template=resume_template
        )
        resume_md = self.render_markdown(
            resume, name=candidate_name, template=resume_template
        )
        resume_docx = self.render_docx(
            resume,
            name=candidate_name,
            template=resume_template,
            output_path=self.build_output_path(
                "resume",
                candidate_name=candidate_name,
                company_name=company_name,
                output_dir=output_dir,
                ext=".docx",
            ),
        )
        resume_pdf = self.render_pdf(
            resume,
            name=candidate_name,
            template=resume_template,
            output_path=self.build_output_path(
                "resume",
                candidate_name=candidate_name,
                company_name=company_name,
                output_dir=output_dir,
                ext=".pdf",
            ),
        )

        paths = {
            "resume_plaintext": self._write_text(
                resume_plain,
                "resume",
                candidate_name,
                company_name,
                output_dir,
                ".txt",
            ),
            "resume_markdown": self._write_text(
                resume_md,
                "resume",
                candidate_name,
                company_name,
                output_dir,
                ".md",
            ),
            "resume_docx": resume_docx,
            "resume_pdf": resume_pdf,
        }

        if cover_letter is not None and cover_letter.cover_letter.strip():
            letter_plain = self.render_cover_letter_plaintext(
                cover_letter,
                name=candidate_name,
                company=company_name,
                phone=phone,
                email=email,
                linkedin=linkedin,
                github=github,
            )
            letter_md = self.render_cover_letter_markdown(
                cover_letter,
                name=candidate_name,
                company=company_name,
                phone=phone,
                email=email,
                linkedin=linkedin,
                github=github,
            )
            paths["cover_letter_plaintext"] = self._write_text(
                letter_plain,
                "cover_letter",
                candidate_name,
                company_name,
                output_dir,
                ".txt",
            )
            paths["cover_letter_markdown"] = self._write_text(
                letter_md,
                "cover_letter",
                candidate_name,
                company_name,
                output_dir,
                ".md",
            )

        return paths

    @staticmethod
    def _write_text(
        content: str,
        document_type: str,
        candidate_name: str,
        company_name: str,
        output_dir: Path,
        ext: str,
    ) -> Path:
        """Write *content* to a timestamped output file and return its path."""
        path = ResumeRenderer.build_output_path(
            document_type,
            candidate_name=candidate_name,
            company_name=company_name,
            output_dir=output_dir,
            ext=ext,
        )
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def build_output_path(
        document_type: str,
        *,
        candidate_name: str,
        company_name: str,
        output_dir: str | Path,
        ext: str | None = None,
    ) -> Path:
        """Build a timestamped output file path for *document_type*.

        The returned path has the form::

            {output_dir}/{YYYYMMDD_HHMM}_{candidate}_{company}_{document_type}.{ext}

        Names are slugified (see :meth:`_slugify`) so the result is safe
        to write on any filesystem.  Pure path logic -- no file I/O.

        Args:
            document_type: Type of document, e.g. ``"resume"`` or
                ``"cover_letter"``.
            candidate_name: Candidate name for the path segment.
            company_name: Company name for the path segment.
            output_dir: Directory the file will live in.
            ext: File extension including the leading dot.  When ``None``,
                a default is chosen per *document_type*.

        Returns:
            The resolved ``Path`` under *output_dir*.
        """
        resolved_ext = ext or _default_extension(document_type)
        if not resolved_ext.startswith("."):
            resolved_ext = f".{resolved_ext}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        slug_candidate = ResumeRenderer._slugify(candidate_name)
        slug_company = ResumeRenderer._slugify(company_name)
        slug_type = ResumeRenderer._slugify(document_type) or "output"

        filename = (
            f"{timestamp}_{slug_candidate}_{slug_company}_{slug_type}{resolved_ext}"
        )
        return Path(output_dir) / filename

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(text: str) -> str:
        """Normalize *text* to a filename-safe ASCII token.

        Lowercases the input, replaces runs of non-alphanumeric characters
        with a single ``-``, and strips leading/trailing hyphens.  Returns
        an empty string when nothing usable remains.
        """
        ascii_text = text.encode("ascii", errors="ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
        return slug

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
        phone: str = "",
        email: str = "",
        linkedin: str = "",
        github: str = "",
    ) -> dict[str, object]:
        """Convert a ``CoverLetterOutput`` into a Jinja2 context dict.

        The ``COVER_LETTER`` template expects ``candidate_name``, ``date``,
        ``opening_paragraph``, ``body_paragraph``, and ``closing_paragraph``.
        The letter body is split on blank lines into up to three logical
        paragraphs (opening / middle / closing).  ``contact_line`` holds the
        non-empty contact details joined on `` | `` for the header.
        """
        paragraphs = _split_paragraphs(cover_letter.cover_letter)
        opening = paragraphs[0] if paragraphs else ""
        closing = paragraphs[-1] if len(paragraphs) > 1 else ""
        body = "\n\n".join(paragraphs[1:-1]) if len(paragraphs) > 2 else ""
        contact_parts = [p for p in (phone, email, linkedin, github) if p]
        return {
            "candidate_name": name,
            "company": company,
            "phone": phone,
            "email": email,
            "linkedin": linkedin,
            "github": github,
            "contact_line": " | ".join(contact_parts),
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

    @staticmethod
    def _docx_heading(doc: DocumentType, text: str) -> None:
        """Add a bold section heading paragraph to *doc*.

        Encapsulates the heading run styling so every section header
        shares the same font size and weight.
        """
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(12)

    @staticmethod
    def _docx_bullet(doc: DocumentType, text: str) -> None:
        """Add a bulleted paragraph to *doc* using the ``List Bullet`` style.

        Encapsulates the bullet list styling so all list content shares
        the same paragraph style.
        """
        para = doc.add_paragraph(style="List Bullet")
        para.add_run(text)

    @staticmethod
    def _pdf_styles() -> dict[str, PdfParagraphStyle]:
        """Return the shared set of ReportLab ``ParagraphStyle`` objects.

        Uses Helvetica / Helvetica-Bold (Type-1 base-14 fonts), a 14pt bold
        name, bold section headings, and 10.5pt single-spaced body text --
        matching the professional DOCX layout.  Base-14 fonts cannot render
        Unicode/emoji, which is fine given the project's ASCII-only rule.
        """
        return {
            "name": PdfParagraphStyle(
                name="ResumeName",
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                spaceAfter=2,
                alignment=TA_LEFT,
            ),
            "title": PdfParagraphStyle(
                name="ResumeTitle",
                fontName="Helvetica",
                fontSize=11,
                leading=14,
                spaceAfter=8,
                alignment=TA_LEFT,
            ),
            "heading": PdfParagraphStyle(
                name="SectionHeading",
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=15,
                spaceBefore=10,
                spaceAfter=4,
                alignment=TA_LEFT,
            ),
            "body": PdfParagraphStyle(
                name="Body",
                fontName="Helvetica",
                fontSize=10.5,
                leading=13,
                spaceAfter=4,
                alignment=TA_LEFT,
            ),
            "bullet": PdfParagraphStyle(
                name="Bullet",
                fontName="Helvetica",
                fontSize=10.5,
                leading=13,
                leftIndent=14,
                spaceAfter=2,
                alignment=TA_LEFT,
            ),
        }

    @staticmethod
    def _populate_pdf_flowables(
        context: dict[str, object], styles: dict[str, PdfParagraphStyle]
    ) -> list[Flowable]:
        """Build the Platypus flowables for the resume body in *context*.

        Mirrors :meth:`_populate_docx_paragraphs`: a name/title header,
        summary paragraph, skills line, per-experience blocks, and bulleted
        projects / certifications / education.  Text is XML-escaped for
        ReportLab's ``Paragraph`` markup parser.
        """
        flowables: list[Flowable] = []
        name = str(context.get("name", ""))
        title = str(context.get("title", ""))

        if name:
            flowables.append(Paragraph(escape(name), styles["name"]))
        if title:
            flowables.append(Paragraph(escape(title), styles["title"]))

        summary = str(context.get("summary", "")).strip()
        if summary:
            flowables.append(Paragraph("Summary", styles["heading"]))
            flowables.append(Paragraph(escape(summary), styles["body"]))

        skills = cast(list[str], context.get("skills", []))
        if skills:
            flowables.append(Paragraph("Skills", styles["heading"]))
            flowables.append(Paragraph(escape(", ".join(skills)), styles["body"]))

        experience = cast(list[dict[str, object]], context.get("experience", []))
        if experience:
            flowables.append(Paragraph("Experience", styles["heading"]))
            for job in experience:
                job_title = str(job.get("title", ""))
                company = str(job.get("company", ""))
                dates = str(job.get("dates", ""))

                header_parts = [part for part in (job_title, company, dates) if part]
                if header_parts:
                    joined = escape(" - ".join(header_parts))
                    flowables.append(Paragraph(joined, styles["body"]))

                for key in ("responsibilities", "achievements", "metrics"):
                    items = cast(list[str], job.get(key, []))
                    if items:
                        flowables.append(_bullet_list([text for text in items], styles))
                flowables.append(Spacer(1, 6))

        for section, label in (
            ("projects", "Projects"),
            ("certifications", "Certifications"),
            ("education", "Education"),
        ):
            items = cast(list[str], context.get(section, []))
            if items:
                flowables.append(Paragraph(label, styles["heading"]))
                flowables.append(_bullet_list(items, styles))

        return flowables

    @staticmethod
    def _populate_docx_paragraphs(
        doc: DocumentType, context: dict[str, object]
    ) -> None:
        """Populate *doc* with the resume content in *context*.

        *context* is the dict produced by :meth:`_build_context`.  The
        candidate name is rendered at 14pt bold; section headings are bold;
        experience is rendered as blocks of a bold title plus company/dates
        and bulleted responsibilities, achievements, and metrics.
        """
        name = str(context.get("name", ""))
        title = str(context.get("title", ""))

        if name:
            name_para = doc.add_paragraph()
            name_run = name_para.add_run(name)
            name_run.bold = True
            name_run.font.size = Pt(14)
        if title:
            title_para = doc.add_paragraph()
            title_para.add_run(title)

        summary = str(context.get("summary", "")).strip()
        if summary:
            ResumeRenderer._docx_heading(doc, "Summary")
            doc.add_paragraph(summary)

        skills = cast(list[str], context.get("skills", []))
        if skills:
            ResumeRenderer._docx_heading(doc, "Skills")
            doc.add_paragraph(", ".join(skills))

        experience = cast(list[dict[str, object]], context.get("experience", []))
        if experience:
            ResumeRenderer._docx_heading(doc, "Experience")
            for job in experience:
                job_title = str(job.get("title", ""))
                company = str(job.get("company", ""))
                dates = str(job.get("dates", ""))

                header_parts = [part for part in (job_title, company, dates) if part]
                if header_parts:
                    header = doc.add_paragraph()
                    if job_title:
                        title_run = header.add_run(job_title)
                        title_run.bold = True
                    meta = " - ".join(part for part in (company, dates) if part)
                    if meta:
                        header.add_run(f" - {meta}")

                for key in ("responsibilities", "achievements", "metrics"):
                    for item in cast(list[str], job.get(key, [])):
                        ResumeRenderer._docx_bullet(doc, item)

        projects = cast(list[str], context.get("projects", []))
        if projects:
            ResumeRenderer._docx_heading(doc, "Projects")
            for item in projects:
                ResumeRenderer._docx_bullet(doc, item)

        certifications = cast(list[str], context.get("certifications", []))
        if certifications:
            ResumeRenderer._docx_heading(doc, "Certifications")
            for item in certifications:
                ResumeRenderer._docx_bullet(doc, item)

        education = cast(list[str], context.get("education", []))
        if education:
            ResumeRenderer._docx_heading(doc, "Education")
            for item in education:
                ResumeRenderer._docx_bullet(doc, item)


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

_DEFAULT_EXTENSIONS: dict[str, str] = {
    "resume_plaintext": ".txt",
    "resume_markdown": ".md",
    "resume_docx": ".docx",
    "resume_pdf": ".pdf",
    "cover_letter_plaintext": ".txt",
    "cover_letter_markdown": ".md",
    "plaintext": ".txt",
    "markdown": ".md",
    "docx": ".docx",
    "pdf": ".pdf",
}


def _default_extension(document_type: str) -> str:
    """Return the default file extension for *document_type*."""
    return _DEFAULT_EXTENSIONS.get(document_type, ".txt")


def _temp_docx_path() -> Path:
    """Return a fresh temporary ``.docx`` path not tied to the workspace."""
    fd, name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    return Path(name)


def _temp_pdf_path() -> Path:
    """Return a fresh temporary ``.pdf`` path not tied to the workspace."""
    fd, name = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    return Path(name)


def _bullet_list(items: list[str], styles: dict[str, PdfParagraphStyle]) -> Flowable:
    """Build a bulleted ``ListFlowable`` from *items* using *styles*."""
    flowables = [ListItem(Paragraph(escape(item), styles["bullet"])) for item in items]
    return ListFlowable(cast(Any, flowables), bulletType="bullet")


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
