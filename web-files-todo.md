# File Management Endpoints — Plan (FastAPI)

> **STATUS: ARCHIVED — completed plan, no longer actionable.** The
> file-management endpoints described here are implemented in `app/files.py` +
> `app/main.py`; every task checkbox below is done. Coverage lives in
> `tests/test_web_files.py` + `tests/test_web_upload.py`; docs in `docs/api.md`.
> Kept for the listing/delete design rationale (safe-path guard, paging).

Add file-management capabilities to the existing FastAPI app in `app/`:

1. **List generated files** (from the `output/` dir) with metadata + filtering + paging.
2. **List uploaded files** (from a new `uploads/` dir) with the same list contract.
3. **Delete files** selected from either listing.

## Current state

- Generated files are written to `output/` by `ResumeRenderer.render_all()` (`pipeline.py:439`); served by `GET /api/outputs/{filename}` (`app/main.py:179`).
- Uploaded files are **never persisted** — `_read_text_input` (`app/main.py:63`) reads the `UploadFile` bytes in memory, extracts text, and discards the original. So today there is **no way to list uploaded files**; we must persist them first.
- Line limits in pyright `strict` mode; ruff `E/F/I/UP/B/SIM`, line length 88; `B008` avoided via `Annotated[...]` defaults (see `app/main.py`).

## Design

### Shared file-metadata model & listing helpers

New module `app/files.py` (keeps `main.py` route-thin, mirrors how `upload.py`/`tasks.py` are split out):

- `FileMeta` (Pydantic) — `name: str`, `size: int`, `modified: datetime`, `type: str` (e.g. `"docx"`, `"pdf"`, `"txt"`, `"md"` derived from suffix), `path: str` (dir-qualified key, e.g. `output/foo.pdf` or `uploads/bar.docx`). Serialize via `model_dump(mode="json")` (ISO-8601 datetime).
- `list_files(directory: Path, *, file_type: str | None, q: str | None, page: int, page_size: int) -> FilePage` — scans `directory`, yields `FileMeta` sorted `modified` desc, applies filters, slices to page.
- `PagedFileList` (Pydantic) response: `items: list[FileMeta]`, `page`, `page_size`, `total`, `total_pages`.

**Filtering**: `file_type` filters by lowercase suffix (`docx`/`pdf`/`txt`/`md`); `q` substring-matches `name` (case-insensitive) and, matching the resume domain, also matches `type`. Optional `sort` param (`name_asc`/`name_desc`/`newest`/`oldest`, default `newest`).

**Paging**: 1-indexed `page` (default 1), `page_size` (default 20, max 100, min 1). Query params, validated → `400` on invalid values.

### Persisting uploads

- New `UPLOADS_DIR = Path("uploads")` in `app/main.py` (mirrors `OUTPUT_DIR`).
- In `_read_text_input`/pipeline endpoints, when a `*_file` is supplied, **write the bytes to `UPLOADS_DIR`** before/after text extraction. Store under a deduplicated name (prefix with a short timestamp/id to avoid collisions, e.g. `20260807_1456_original-name.pdf`). Only the supplied upload is persisted (text-paste path writes nothing).
- Decide: persist upload even if text extraction later fails? **Yes** — the uploaded artifact is the thing we list/delete; extraction failure is separate. But note the pipeline still 400s on empty extraction.

### Endpoints (all in `app/main.py`)

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/files/generated` | List `output/` files (filter + paged) → `PagedFile` |
| `GET` | `/api/files/uploaded` | List `uploads/` files (filter + paged) → `PagedFile` |
| `DELETE` | `/api/files` | Delete selected files by `path` key (JSON body `{"paths": [...]}`) → `{deleted: [...], missing: [...]}` |

**Delete semantics**: accepting JSON body of `{"files": ["output/a.pdf", "uploads/b.docx"]}`. Each path is resolved relative to the repo root and must:

- resolve via a validated allowlist of directories (`output/` or `uploads/`) — prevents path traversal beyond them (reuse the same `.resolve()` + `base in parents` guard as `get_output` at `app/main.py:195`);
- actually exist → otherwise added to `missing` and not `404` (bulk idempotency).
Returns the list of deleted `path`s and the `missing` ones so the client can reconcile. `400` when body path escapes an allowed dir. `204`/`200` decision: return `200` with `{deleted, missing}` so callers see per-file outcomes.

**Reuse**: `list_files` is shared by both list endpoints (only the `directory` differs) — no duplication. Delete also verifies against both dirs so a `path` from either listing is acceptable.

## Schemas (`app/schemas.py`)

- `FileMeta` (also used in `app/files.py`; define once in `schemas.py` to avoid double definition, importing into `files.py`).
- `PagedFile` response.
- `DeleteFilesRequest` = `files: list[str]` (path keys).
- `DeleteFilesResponse` = `deleted: list[str]`, `missing: list[str]`.

## Files to create / modify

| File | Change |
| --- | --- |
| `app/files.py` | **new** — `FileMeta`-to-listing helpers, `list_files()`, safe-path resolution |
| `app/schemas.py` | add `FileMeta`, `PagedFile`, `DeleteFilesRequest`, `DeleteFilesResponse` |
| `app/main.py` | add `UPLOADS_DIR`, persist `*_file` uploads, add the 3 routes, wire `list_files` |

## Task breakdown

### 1. Schemas (`app/schemas.py`)

- [x] `FileMeta` — `name`, `size`, `modified`, `type`, `path`
- [x] `PagedFile` — `items`, `page`, `page_size`, `total`, `page_pages`
- [x] `DeleteFilesRequest` — `files: list[str]`
- [x] `DeleteFilesResponse` — `deleted`, `missing`

### 2. `app/files.py` helpers

- [x] `safe_dir_path(base: Path, name: str) -> Path` — resolve + allowlist guard (traversal-safe)
- [x] `build_file_meta(entry: Path, kind: str) -> FileMeta` — name/size/modified/type/path
- [x] `list_files(directory, *, file_type, q, page, page_size, sort) -> PagedFile` — filter, sort, paginate
- [x] Validate/clamp paging params → `400`

### 3. `app/main.py` — persist uploads

- [x] `UPLOADS_DIR = Path("uploads")` constant
- [x] Persist `*_File` uploads into `UP_LOADS_DIR` (dedup name) inside the pipeline endpoints — via `_persist_upload()` called from `_read_text_input`
- [x] Ensure `uploads/` and `output/` dirs exist at startup (lifespan `mkdir`)

### 4. `app/main.py` — routes

- [x] `GET /api/files/generated` → `list_files(OUTPUT_DIR, ...)`
- [x] `GET /api/files/uploaded` → `list_files(UPLOADS_DIR, ...)`
- [x] `DELETE /api/files` → bulk delete with allowlist + `deleted`/`missing` response

### 5. Manual smoke + verification

- [x] `uv run uvicorn app.main:app` boots — verified via `import app.main` + `TestClient` (no import/boot errors)
- [x] `GET /api/files/generated` lists existing `output/` files; `page`/`page_size`/`file_type=pdf`/`q=` behave — verified filter (pdf→2), page_size=3→total_pages=4, q=resume→8, page=0→400, bad sort→400
- [x] `GET /api/files/uploaded` lists persisted uploads after a `*_file` pipeline call — uploads persisted + listed
- [x] `DELETE /api/files` removes a chosen file (and reports `missing` for unknowns; rejects traversal) — verified upload/generated delete, `missing`, and `../` traversal rejection
- [x] `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`

## Known limitations / notes

- In-memory listing = filesystem scan per request (fine for small dirs; no index).
- Uploads persist to `uploads/` only going forward; existing pre-change uploads (none) N/A.
- No auth/ACL; deletion is unauthenticated like the rest of the API.

## Out of scope (this pass)

- No API tests / no `tests/` additions (matches `resume-web-todo.md` rule: "API layer only ... no API tests").
- Not integrating into the frontend; purely new endpoints + persistence.
