"""File listing + deletion helpers for the resume web API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from app.schemas import FileMeta, PagedFile

_DEFAULT_PAGE = 1
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


def _validate_page(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > _MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=400, detail=f"page_size must be 1..{_MAX_PAGE_SIZE}"
        )
    return page, page_size


def _file_type(suffix: str) -> str:
    return suffix.lstrip(".").lower() if suffix else ""


def safe_dir_path(base: Path, name: str) -> Path:
    """Resolve ``base/name`` and guard against path traversal.

    Raises:
        ValueError: when ``name`` escapes ``base``.
    """
    base_resolved = base.resolve()
    target = (base / name).resolve()
    if base_resolved not in target.parents and target != base_resolved:
        raise ValueError(f"Path escapes allowed directory: {name!r}")
    return target


def safe_delete_path(base: Path, name: str) -> Path:
    """Resolve ``base/name``, guarding against traversal and directory targets."""
    target = safe_dir_path(base, name)
    if not target.is_file():
        raise ValueError(f"Not a regular file: {name!r}")
    return target


def build_file_meta(entry: Path, kind: str) -> FileMeta:
    """Build ``FileMeta`` from a filesystem entry within ``kind`` dir."""
    stat = entry.stat()
    return FileMeta(
        name=entry.name,
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        type=_file_type(entry.suffix),
        path=f"{kind}/{entry.name}",
    )


def list_files(
    directory: Path,
    *,
    file_type: str | None = None,
    q: str | None = None,
    page: int = _DEFAULT_PAGE,
    page_size: int = _DEFAULT_PAGE_SIZE,
    sort: str = "newest",
) -> PagedFile:
    """List, filter, sort, and paginate ``directory``'s files.

    Raises:
        HTTPException(400): on invalid paging/sort params.
    """
    page, page_size = _validate_page(page, page_size)
    if sort not in {"newest", "oldest", "name_asc", "name_desc"}:
        raise HTTPException(status_code=400, detail=f"Unknown sort: {sort!r}")

    needle = q.lower() if q else None
    type_filter = file_type.lower() if file_type else None

    metas: list[FileMeta] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        meta = build_file_meta(entry, directory.name)
        if type_filter and meta.type != type_filter:
            continue
        if needle and needle not in meta.name.lower() and needle not in meta.type:
            continue
        metas.append(meta)

    if sort == "newest":
        metas.sort(key=lambda m: m.modified, reverse=True)
    elif sort == "oldest":
        metas.sort(key=lambda m: m.modified)
    elif sort == "name_asc":
        metas.sort(key=lambda m: m.name.lower())
    else:
        metas.sort(key=lambda m: m.name.lower(), reverse=True)

    total = len(metas)
    start = (page - 1) * page_size
    items = metas[start : start + page_size]
    return PagedFile(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=((total + page_size - 1) // page_size) if total else 0,
    )
