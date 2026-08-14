# Resume Web API — Plan (FastAPI)

> **STATUS: ARCHIVED — completed plan, no longer actionable.** The FastAPI web
> layer described here is implemented in `app/` (`main.py`, `schemas.py`,
> `tasks.py`, `upload.py`); every task checkbox below is done. Coverage lives in
> `tests/test_web_*.py`; docs in `docs/api.md`; quickstart in `README.md`. Kept
> for the architectural-constraint rationale (`_run_pipeline_core` vs
> `run_resume_pipeline`).

Turn the existing 7-agent CLI pipeline into a FastAPI application. **API layer only** in this pass — no API tests, no `test_pipeline.py`, no Phase 7 docs, no `AGENTS.md`/`docs/` edits.

## Key architectural constraint

`run_resume_pipeline()` (`pipeline.py:313`) wraps the chain in `asyncio.run()` — **cannot be called from inside FastAPI's running event loop** (would raise `RuntimeError: event loop already running`).

The API calls `_run_pipeline_core()` (`pipeline.py:324`) directly with `await`. The shared `AgentRunner` (holding clients bound to one loop) is built once at startup via `create_runner_from_config()` and reused on the single app loop; both sync and background modes share that loop, so no "Event loop is closed" failures.

## Design

- **App package**: `app/` with `main.py`, `schemas.py`, `tasks.py`, `upload.py`.
- **Lifecycle**: `lifespan` builds one `AgentRunner` via `create_runner_from_config()` and stores it on `app.state.runner`. Both endpoint styles reuse it on the single app loop.
- **Sync endpoint** `await`s `_run_pipeline_core(runner, jd, resume, candidate_name=..., company_name=...)` directly — the same coroutine `run_resume_pipeline` uses (`pipeline.py:324`). Never call `run_resume_pipeline()` itself (`pipeline.py:313`).
- **Background endpoint** spawns `asyncio.create_task(_run_pipeline_core(...))`, records status/result in an in-memory registry in `app/tasks.py`.

## Files to create

| File | Content |
| --- | --- |
| `app/__init__.py` | package marker |
| `app/schemas.py` | `PipelineRunRequest`, `PipelineRunResponse`, `TaskCreated`, `TaskStatus` (Pydantic models; result payload serialized via `model_dump(mode="json")`) |
| `app/upload.py` | `extract_text(file, *, mime) -> str`: `.txt` decode, `.docx` via `python-docx`, `.pdf` via `pypdf`, else `HTTPException(400)` |
| `app/tasks.py` | `TaskRegistry` dataclass/dict: `create() -> task_id`, `update()`, `get()`, `set_result`/`set_error` |
| `app/main.py` | FastAPI app + lifespan, all routes below |

## Routes

- `GET /health` → `{"status": "ok"}`
- `GET /api/models` → `get_model_summary()` from `config.agents`
- `POST /api/pipeline` (sync) — multipart fields: `job_description`, `resume` (raw pasted text), optional `job_file`/`resume_file` (`UploadFile`), optional `candidate_name`/`company_name`; one of text-or-file required per input; returns full 7-key result + `output_files` (string paths)
- `POST /api/pipeline/async` — same inputs, returns `{"task_id": ...}`

**Copied-and-pasted input is a first-class, supported path:** the caller sends the resume and/or job description straight in the `resume` and `job_description` text fields (plain text, no upload needed). Text fields and file uploads are each optional per input; exactly one of the two (text field or `*_file`) is required for each of resume and job description. When both are supplied for a given input, the text field wins (or return `400` — decide in `upload.py`).

- `GET /api/tasks/{task_id}` → `{status, result?, error?, created_at?, completed_at?}`
- `GET /api/outputs/{filename}` → `FileResponse` from the `output/` dir (renderer writes there, `pipeline.py:444`)

## Config changes (`pyproject.toml`)

- deps: `fastapi>=0.115`, `uvicorn>=0.30`, `python-multipart>=0.0.9`, `pypdf>=4.0`
- `[tool.ruff.lint.isort] known-first-party`: add `"app"`
- `[tool.pyright] include`: add `"app"` (so new code is typechecked in strict mode)

## Task breakdown

### 1. Dependencies & config (`pyproject.toml`)

- [x] `uv add fastapi>=0.115 uvicorn>=0.30 python-multipart>=0.0.9 pypdf>=4.0` (or edit deps list) — added to `dependencies` in `pyproject.toml`
- [x] `[tool.ruff.lint.isort] known-first-party`: add `"app"` — `["app", "client", "config"]`
- [x] `[tool.pyright] include`: add `"app"` so new code is typechecked in strict mode — `["app", "client", "config", "pipeline.py", "basic.py"]`
- [x] `uv sync` to lock/install — fastapi 0.141.1, uvicorn 0.52.1, python-multipart 0.0.32, pypdf 6.15.0

### 2. Package scaffold

- [x] Create `app/__init__.py` package marker

### 3. `app/schemas.py` — Pydantic models

- [x] `PipelineRunRequest` — validated request shape for pipeline inputs
- [x] `PipelineRunResponse` — 7-key result + `output_files` (string paths); serialize via `model_dump(mode="json")`
- [x] `TaskCreated` — `{task_id}` response
- [x] `TaskStatus` — `{status, result?, error?, created_at?, completed_at?}`
- [x] Confirm serialization helpers for nested result dicts — verified `model_dump(mode="json")` round-trips nested dicts/`Any` fields

### 4. `app/upload.py` — text extraction + 400 handling

- [x] `extract_text(file, *, mime) -> str` signature + dispatch — on `mime`, dispatches to `_decode_txt` / `_extract_docx` / `_extract_pdf`
- [x] `.txt` decode branch — `_decode_txt`: tries `utf-8` → `utf-8-sig` → `latin-1`, falls back to `latin-1` with `replace`
- [x] `.docx` branch via `python-docx` — `Document(BytesIO(data))`, joins paragraph text with `\n`
- [x] `.pdf` branch via `pypdf` — `PdfReader(BytesIO(data))`, joins page text with `\n`
- [x] else → `HTTPException(400)` — unsupported MIME raises `400` with a `.txt/.docx/.pdf` hint
- [x] Empty-text guard (return 400 vs pass-through — decide) — `extract_text` returns the extracted text as-is (empty allowed); the empty-vs-400 decision is delegated to `main.py`
- [x] Decide text-field-vs-file precedence (text wins, or 400 for both) — text field wins (see todo line 35); enforcement delegated to `main.py` which only calls `extract_text` when no text was supplied

### 5. `app/tasks.py` — in-memory task registry

- [x] `TaskRegistry` container (dataclass or dict-backed) — class backed by `dict[str, dict[str, Any]]` with a `threading.Lock`
- [x] `create() -> task_id` (unique id generation + initial status/created_at) — `uuid.uuid4().hex`; initializes `status="pending"`, `result/error=None`, `created_at=monotonic()`, `completed_at=None`
- [x] `update()` and `get()` — `update()` merges fields (no-op for unknown id); `get()` returns a copy or `None`
- [x] `set_result()` / `set_error()` (complete + completed_at) — set `status="completed"/"failed"`, store `result`/`error`, stamp `completed_at`

### 6. `app/main.py` — FastAPI app + routes

- [x] `lifespan` builds one `AgentRunner` via `create_runner_from_config()`, stores on `app.state.runner` — `@asynccontextmanager lifespan` builds once, sets `app.state.runner`; routes access it via `Depends(_require_runner)`
- [x] `GET /health` → `{"status": "ok"}`
- [x] `GET /api/models` → `get_model_summary()` from `config.agents`
- [x] `POST /api/pipeline` (sync): multipart fields `job_description`, `resume`, optional `job_file`/`resume_file`, optional `candidate_name`/`company_name`; parse inputs via `upload.py`; call `_run_pipeline_core(runner, jd, resume, candidate_name=, company_name=)` with `await` (via `pipeline.py:324`); return 7-key result + `output_files`
- [x] `POST /api/pipeline/async`: same inputs → `asyncio.create_task(_run_pipeline_core(...))`, record in `TaskRegistry`, return `TaskCreated`
- [x] `GET /api/tasks/{task_id}` → `TaskStatus` (404 if unknown)
- [x] `GET /api/outputs/{filename}` → `FileResponse` from `output/` dir
- [x] Ensure main only ever calls `_run_pipeline_core`, never `run_resume_pipeline` (avoid `asyncio.run` re-entry) — only `_run_pipeline_core` is awaited; `run_resume_pipeline` (which wraps in `asyncio.run`) is never referenced

### 7. Manual smoke + live verification

- [x] `uv run uvicorn app.main:app` boots without import errors — verified via `TestClient` (boot, import, routes)
- [x] Smoke: `GET /health` → `{"status": "ok"}`
- [x] Smoke: `GET /api/models` lists models — 7 models
- [x] Live: `POST /api/pipeline` with `sample/jobs/3Pillar.txt` + `sample/resume/Peter-Letkeman-Resume.txt` (Ollama up) → 7-key result + `output_files` — verified sync run + rendered files
- [x] Background: `POST /api/pipeline/async` → poll `GET /api/tasks/{task_id}` → completed with result — verified wait→completed with all 7 keys
- [x] Verify `GET /api/outputs/{filename}` downloads rendered file — returned `200` for `.pdf`/`.md`; traversal rejected
- [x] `uv run ruff check .`
- [x] `uv run ruff format --check .`
- [x] `uv run pyright` (no path arg)

## Notes / follow-ups implemented after this plan

- **File management endpoints** were added after this pass; see `web-files-todo.md` for the list/uploaded/delete work (`GET /api/files/generated`, `GET /api/files/uploaded`, `DELETE /api/files`).
- Uploaded `*_file` inputs are now persisted to `uploads/` (git-ignored) so they can be listed/deleted.
- `app/files.py` was added (moved outside `main.py`). The "Files to create" table does not list `app/files.py` (added in the later file-management pass).

## Known limitations (documented, not solved)

- One shared `AgentRunner` → concurrent requests share the same LLM clients (fine for Ollama, but note it)
- In-memory task store → lost on restart; no auth/CORS by default
- No `.env` handling — config stays env-var driven

## Out of scope (this pass)

No API tests, no `test_pipeline.py`, no Phase 7 docs files. Those remain in `resume-todo.md` Phase 7 for a later pass. (The plan's "no `AGENTS.md`/`docs/` edits" rule was later relaxed — `AGENTS.md` and `README.md` were updated in subsequent passes.)
