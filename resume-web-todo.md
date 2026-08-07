# Resume Web API — Plan (FastAPI)

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

## Verification

- `uv sync`; `uv run uvicorn app.main:app`
- Smoke: `/health`, `/api/models`
- Live: `POST /api/pipeline` with `sample/jobs/3Pillar.txt` + `sample/resume/Peter-Letkeman-Resume.txt` (Ollama must be up), then background + poll + output download
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`

## Known limitations (documented, not solved)

- One shared `AgentRunner` → concurrent requests share the same LLM clients (fine for Ollama, but note it)
- In-memory task store → lost on restart; no auth/CORS by default
- No `.env` handling — config stays env-var driven

## Out of scope (this pass)

No API tests, no `test_pipeline.py`, no Phase 7 docs files, no `AGENTS.md`/`docs/` edits. Those remain in `resume-todo.md` Phase 7 for a later pass.
