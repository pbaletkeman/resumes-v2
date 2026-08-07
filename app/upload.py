"""Text extraction from uploaded files for the resume web API."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from starlette.datastructures import UploadFile

logger = logging.getLogger(__name__)

_TXT_MIME = "text/plain"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME = "application/pdf"

_VALID_MIMES = frozenset({_TXT_MIME, _DOCX_MIME, _PDF_MIME})


def extract_text(file: UploadFile, *, mime: str) -> str:
    """Extract plain text from a pasted file.

    ``mime`` is matched against known types; unsupported types raise ``400``.
    """
    if mime not in _VALID_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime!r}. Use .txt, .docx, or .pdf.",
        )

    data = _read_bytes(file)
    if mime == _TXT_MIME:
        return _decode_txt(data)
    if mime == _DOCX_MIME:
        return _extract_docx(data)
    return _extract_pdf(data)


def _read_bytes(file: UploadFile) -> bytes:
    try:
        return file.file.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail="Could not read uploaded file."
        ) from exc


def _decode_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 never fails; fall back defensively.
    return data.decode("latin-1", errors="replace")


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document

        doc = Document(BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail="Could not parse .docx file."
        ) from exc
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail="Could not parse .pdf file."
        ) from exc
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages)
