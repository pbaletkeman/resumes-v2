"""Phase 7.4.6 web tests: text extraction unit.

``app.upload.extract_text`` is exercised directly with in-memory files
(BytesIO-backed ``UploadFile``). Covers txt decoding (utf-8 / utf-8-sig /
latin-1 fallback), real docx/pdf parsing via python-docx/pypdf, the
unsupported-MIME ``400``, and malformed docx/pdf bytes raising ``400``.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.upload import extract_text

TXT_MIME = "text/plain"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


def _upload(data: bytes, *, filename: str = "file.txt") -> UploadFile:
    return UploadFile(file=BytesIO(data), filename=filename)


class TestTxtDecoding:
    """``.txt`` decodes across utf-8 / utf-8-sig / latin-1."""

    def test_utf8(self) -> None:
        text = extract_text(_upload("résumé ✓".encode()), mime=TXT_MIME)

        assert text == "résumé ✓"

    def test_utf8_sig_decodes_via_utf8(self) -> None:
        raw = b"\xef\xbb\xbfHello with BOM"
        text = extract_text(_upload(raw), mime=TXT_MIME)

        assert "Hello with BOM" in text

    def test_latin1_fallback(self) -> None:
        raw = "café".encode("latin-1")
        text = extract_text(_upload(raw), mime=TXT_MIME)

        assert text == "café"


class TestDocxExtraction:
    """``.docx`` via python-docx."""

    def _make_docx(self, *paragraphs: str) -> bytes:
        from docx import Document

        buffer = BytesIO()
        doc = Document()
        for paragraph in paragraphs:
            doc.add_paragraph(paragraph)
        doc.save(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_parses_paragraphs(self) -> None:
        data = self._make_docx("Hello", "World")
        text = extract_text(_upload(data, filename="resume.docx"), mime=DOCX_MIME)

        assert text == "Hello\nWorld"

    def test_malformed_docx_raises_400(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            extract_text(_upload(b"not a docx"), mime=DOCX_MIME)

        assert excinfo.value.status_code == 400
        assert "Could not parse .docx file." in excinfo.value.detail


class TestPdfExtraction:
    """``.pdf`` via pypdf (minimal in-memory PDF)."""

    def test_parses_pdf_text(self) -> None:
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        page = canvas.Canvas(buffer)
        page.drawString(72, 720, "Hello PDF")
        page.save()
        buffer.seek(0)

        text = extract_text(
            _upload(buffer.read(), filename="resume.pdf"), mime=PDF_MIME
        )

        assert "Hello PDF" in text

    def test_malformed_pdf_raises_400(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            extract_text(_upload(b"%PDF-not-real"), mime=PDF_MIME)

        assert excinfo.value.status_code == 400
        assert "Could not parse .pdf file." in excinfo.value.detail


class TestUnsupportedMime:
    """Unrecognized MIME types raise ``400``."""

    def test_unknown_mime_raises_400(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            extract_text(_upload(b"whatever"), mime="application/octet-stream")

        assert excinfo.value.status_code == 400
        assert "Unsupported file type" in excinfo.value.detail

    def test_empty_mime_raises_400(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            extract_text(_upload(b"whatever"), mime="")

        assert excinfo.value.status_code == 400
        assert "Unsupported file type" in excinfo.value.detail
