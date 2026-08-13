"""FastAPI application exposing the 7-agent resume pipeline as an API.

Routes:
    GET  /health                       service liveness probe
    GET  /api/models                   per-agent model summary
    PATCH /api/models/{agent}          edit an agent's model/provider
    DELETE /api/models/{agent}         reset an agent's model/provider to defaults
    POST /api/pipeline                 run the pipeline synchronously (multipart)
    POST /api/pipeline/async           launch a background pipeline run
    GET  /api/tasks/{task_id}          poll a background task
    GET  /api/outputs/{filename}       download a rendered output file
    GET  /api/files/generated          list files in ``output/``
    GET  /api/files/uploaded           list files in ``uploads/``
    DELETE /api/files                  batch-delete files by path key
    GET  /{full_path:path}             SPA fallback (serves ``ui/dist`` when built)

``/api/files/generated`` and ``/api/files/uploaded`` are intentionally
parallel: identical query params (``file_type``, ``q``, ``page``,
``page_size``, ``sort``), differing only in the directory they list
(``OUTPUT_DIR`` vs ``UPLOADS_DIR``).  Both delegate to ``app.files.list_files``.

Model edits (``PATCH``/``DELETE /api/models/{agent}``) are persisted in a
SQLite database (``app.model_store.ModelStore``) and, on each change, the
shared ``AgentRunner`` is rebuilt from the environment defaults plus the
persisted overrides so the running pipeline picks up the new model/provider.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError

from app.files import list_files, safe_delete_path
from app.model_store import ModelStore
from app.schemas import (
    AgentOverrideUpdate,
    DeleteFilesRequest,
    DeleteFilesResponse,
    ModelSummaryRow,
    PagedFile,
    PipelineRunResponse,
    TaskCreated,
    TaskStatus,
)
from app.tasks import TaskRegistry
from app.upload import extract_text
from config.agents import AGENT_NAMES, get_model_summary
from pipeline import (
    _run_pipeline_core,  # pyright: ignore[reportPrivateUsage]
    create_runner_from_config,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
UPLOADS_DIR = Path("uploads")
UI_DIST = Path("ui") / "dist"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def mount_spa(app_instance: FastAPI, ui_dist: Path) -> None:
    """Serve a built Vite SPA from ``ui_dist`` with a client-side fallback.

    Registers a ``StaticFiles`` mount for the ``/assets`` directory and a
    catch-all ``GET /{full_path:path}`` route that serves ``index.html``.
    The catch-all only fires for non-``/api``, non-``/health``, non-dotfile
    paths, so deep links such as ``/files`` return the SPA on refresh while
    API and health routes keep precedence.

    Args:
        app_instance: The FastAPI app to attach the static routes to.
        ui_dist: Directory containing the built SPA (``index.html`` + ``assets/``).
    """
    assets_dir = ui_dist / "assets"
    if assets_dir.is_dir():
        app_instance.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    async def spa_fallback(full_path: str) -> HTMLResponse:
        if full_path.startswith(("api/", "health/")) or full_path in {"api", "health"}:
            raise HTTPException(status_code=404, detail="Not found")
        last_segment = full_path.rsplit("/", 1)[-1]
        if last_segment.startswith(".") or "." in last_segment:
            raise HTTPException(status_code=404, detail="Not found")
        index_html = ui_dist / "index.html"
        if not index_html.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return HTMLResponse(content=index_html.read_text(encoding="utf-8"))

    app_instance.add_api_route(
        "/{full_path:path}", spa_fallback, methods=["GET"], include_in_schema=False
    )


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None]:
    """Build one shared AgentRunner on the app loop at startup.

    Creates the SQLite ``ModelStore`` and builds the runner from the
    environment defaults plus any persisted model/provider overrides, so a
    restart keeps the model choices made on the Models page.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    store = ModelStore()
    app_instance.state.model_store = store
    runner = create_runner_from_config(overrides=store.all_overrides())
    app_instance.state.runner = runner
    logger.info("Agent runner built; agents: %s", ", ".join(runner.agents))
    yield
    logger.info("Agent runner context exit")


app = FastAPI(title="Resume Web API", lifespan=lifespan)
registry = TaskRegistry()


def _require_runner() -> Any:
    """Return the lifespan-built ``AgentRunner`` for dependency injection.

    The runner is created once in :func:`lifespan` and stored on
    ``app.state.runner``; this dependency fetches it for route handlers.

    Returns:
        The shared ``AgentRunner`` instance.

    Raises:
        HTTPException(503): when the app is not fully started (no runner).
    """
    runner = getattr(app.state, "runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Pipeline runner not initialized")
    return runner


def _require_store() -> ModelStore:
    """Return the lifespan-built ``ModelStore`` for the model routes.

    Returns:
        The shared ``ModelStore`` instance.

    Raises:
        HTTPException(503): when the app is not fully started (no store).
    """
    store = getattr(app.state, "model_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Model store not initialized")
    return store


def _rebuild_runner() -> None:
    """Rebuild ``app.state.runner`` from the persisted model overrides.

    Called after every model edit so the running pipeline uses the new
    provider/model.  The rebuilt ``AgentRunner`` starts with agent *classes*
    again, which are lazily instantiated on the current event loop on first
    dispatch (see ``AgentRunner.run_agent_async``), so the new clients bind
    cleanly to the app loop.
    """
    store = _require_store()
    overrides = store.all_overrides()
    app.state.runner = create_runner_from_config(overrides=overrides)
    logger.info("Rebuilt agent runner with %d model override(s)", len(overrides))


def _agent_or_404(agent: str) -> None:
    """Reject requests for an unknown agent name with a 404."""
    if agent not in AGENT_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'")


def _summary_row(agent: str) -> dict[str, Any]:
    """Return the summary row for one agent, matching ``GET /api/models``."""
    _agent_or_404(agent)
    rows = get_model_summary(_require_store().all_overrides())
    for row in rows:
        if row["agent"] == agent:
            return cast(dict[str, Any], row)
    raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'")


def _mime_for(filename: str) -> str:
    """Map a filename to its MIME type (empty string when unrecognized)."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "txt": "text/plain",
        "docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "pdf": "application/pdf",
    }.get(suffix, "")


def _persist_upload(file: UploadFile, name: str) -> None:
    """Persist an uploaded file to ``UPLOADS_DIR`` under a deduped name."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"{name} file is too large.")
    original = file.filename or name
    stem, _, suffix = original.rpartition(".")
    suffix = f".{suffix}" if suffix else ""
    target = UPLOADS_DIR / f"{int(time.time())}_{stem or 'upload'}{suffix}"
    try:
        file.file.seek(0)
        data = file.file.read()
        target.write_bytes(data)
        file.file.seek(0)
        logger.info("Persisted upload %s -> %s", original, target.name)
    except OSError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Could not save {name} file."
        ) from exc


def _read_text_input(text: str | None, file: UploadFile | None, name: str) -> str:
    """Resolve a pasted-text-vs-uploaded-file input (text wins).

    Uploaded files are persisted to ``UPLOADS_DIR`` regardless of whether
    text extraction succeeds, so they can be listed/deleted later.

    Args:
        text: Pasted text from the multipart form, or ``None``.
        file: Uploaded file from the multipart form, or ``None``.
        name: Human-readable input name used in error messages
            (e.g. ``"resume"``).

    Returns:
        Non-empty text ready for the pipeline.

    Raises:
        HTTPException(400): when neither input yields non-empty text.
    """
    if text and text.strip():
        return text
    if file is not None:
        _persist_upload(file, name)  # also enforces MAX_UPLOAD_BYTES
        extracted = extract_text(file, mime=_mime_for(file.filename or ""))
        if extracted.strip():
            return extracted
        raise HTTPException(
            status_code=400, detail=f"{name} is empty after extraction."
        )
    if text is not None:
        raise HTTPException(status_code=400, detail=f"{name} must not be empty.")
    raise HTTPException(
        status_code=400, detail=f"Provide {name} as pasted text or an uploaded file."
    )


def _to_response(result: dict[str, Any]) -> PipelineRunResponse:
    """Serialize the pipeline core result into the response model.

    Args:
        result: The dict returned by ``_run_pipeline_core`` (7 stage keys
            plus ``output_files`` mapping format names to ``Path`` values).

    Returns:
        A ``PipelineRunResponse`` with stringified output file paths.
    """
    raw_files = result.get("output_files", {})
    raw_dict = cast(dict[str, Any], raw_files) if isinstance(raw_files, dict) else {}
    files = {str(k): str(v) for k, v in raw_dict.items()}
    return PipelineRunResponse(
        parsed_job_description=result["parsed_job_description"],
        parsed_resume=result["parsed_resume"],
        tailoring_strategy=result["tailoring_strategy"],
        rewritten_resume=result["rewritten_resume"],
        ats_optimized_resume=result["ats_optimized_resume"],
        polished_resume=result["polished_resume"],
        cover_letter=result["cover_letter"],
        output_files=files,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/models", response_model=list[ModelSummaryRow])
async def list_models() -> list[dict[str, Any]]:
    """List the effective provider/model for each agent.

    Rows report the effective values after any persisted override, plus the
    environment defaults the agent would fall back to (see
    ``config.agents.get_model_summary``).
    """
    return get_model_summary(_require_store().all_overrides())


@app.patch("/api/models/{agent}", response_model=ModelSummaryRow)
async def update_agent_model(agent: str, body: AgentOverrideUpdate) -> dict[str, Any]:
    """Edit the model and/or provider used by one agent.

    Persists the override in SQLite and rebuilds the shared runner so the
    change takes effect on the next pipeline run.  A ``None`` field leaves
    that dimension inheriting the environment default.  When the rebuild
    fails (e.g. switching to OpenAI without an API key set) the change is
    rolled back and a 400 is returned.

    Raises:
        HTTPException(400): when both fields are unset, the provider is
            unknown, the model is empty, or the runner cannot be rebuilt.
        HTTPException(404): when the agent name is unknown.
    """
    _agent_or_404(agent)
    if body.provider is None and body.model is None:
        raise HTTPException(
            status_code=400, detail="Provide at least one of provider or model."
        )
    if body.provider is not None and body.provider not in ("ollama", "openai"):
        raise HTTPException(
            status_code=400,
            detail="Unknown provider. Supported: ollama, openai",
        )
    model = body.model.strip() if body.model is not None else None
    if body.model is not None and not model:
        raise HTTPException(status_code=400, detail="Model must not be empty.")

    store = _require_store()
    store.set_override(agent, body.provider, model)
    try:
        _rebuild_runner()
    except Exception as exc:  # noqa: BLE001
        store.clear(agent)
        logger.error(
            "Runner rebuild failed after model update for %s; change rolled back",
            agent,
            exc_info=True,
        )
        if isinstance(exc, OpenAIError):
            raise HTTPException(
                status_code=400,
                detail="Switching an agent to OpenAI requires OPENAI_API_KEY "
                "to be set in the server environment.",
            ) from exc
        raise HTTPException(
            status_code=400, detail=f"Could not apply the model change: {exc}"
        ) from exc

    logger.info(
        "Updated model config for %s: provider=%s model=%s",
        agent,
        body.provider,
        model,
    )
    return _summary_row(agent)


@app.delete("/api/models/{agent}", response_model=ModelSummaryRow)
async def reset_agent_model(agent: str) -> dict[str, Any]:
    """Reset one agent's model and provider back to the environment defaults.

    Removes the persisted override (SQLite row) and rebuilds the shared
    runner so the next pipeline run uses the default configuration.

    Raises:
        HTTPException(404): when the agent name is unknown.
    """
    _agent_or_404(agent)
    store = _require_store()
    store.clear(agent)
    _rebuild_runner()
    logger.info("Reset model config for %s to defaults", agent)
    return _summary_row(agent)


@app.post("/api/pipeline", response_model=PipelineRunResponse)
async def run_pipeline(
    job_description: Annotated[str | None, Form()] = None,
    resume: Annotated[str | None, Form()] = None,
    job_file: Annotated[UploadFile | None, File()] = None,
    resume_file: Annotated[UploadFile | None, File()] = None,
    candidate_name: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    runner: Annotated[Any, Depends(_require_runner)] = None,
) -> PipelineRunResponse:
    """Run the full pipeline synchronously (multipart form inputs).

    Mirrors the multipart signature of ``run_pipeline_async``; this route
    blocks until the pipeline finishes and returns the full result.
    """
    jd = _read_text_input(job_description, job_file, "job description")
    rsv = _read_text_input(resume, resume_file, "resume")
    result = await _run_pipeline_core(
        runner,
        jd,
        rsv,
        candidate_name=candidate_name,
        company_name=company_name,
    )
    return _to_response(result)


@app.post("/api/pipeline/async", response_model=TaskCreated)
async def run_pipeline_async(
    job_description: Annotated[str | None, Form()] = None,
    resume: Annotated[str | None, Form()] = None,
    job_file: Annotated[UploadFile | None, File()] = None,
    resume_file: Annotated[UploadFile | None, File()] = None,
    candidate_name: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    runner: Annotated[Any, Depends(_require_runner)] = None,
) -> TaskCreated:
    """Launch a background pipeline run; returns a task id.

    Mirrors the multipart signature of ``run_pipeline``; the pipeline runs
    in a background task and progress is polled via ``GET /api/tasks/{id}``.
    """
    jd = _read_text_input(job_description, job_file, "job_description")
    rsv = _read_text_input(resume, resume_file, "resume")
    task_id = registry.create()
    registry.update(task_id, status="running")

    async def _execute() -> None:
        try:
            result = await _run_pipeline_core(
                runner,
                jd,
                rsv,
                candidate_name=candidate_name,
                company_name=company_name,
            )
            registry.set_result(task_id, _to_response(result).model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            logger.error("Async pipeline task %s failed", task_id, exc_info=True)
            registry.set_error(task_id, str(exc))

    asyncio.create_task(_execute())
    return TaskCreated(task_id=task_id)


@app.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task(task_id: str) -> TaskStatus:
    record = registry.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown task id")
    return TaskStatus(**record)


@app.get("/api/outputs/{filename}")
async def get_output(filename: str) -> FileResponse:
    base = OUTPUT_DIR.resolve()
    target = (OUTPUT_DIR / filename).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(target)


@app.get("/api/files/generated", response_model=PagedFile)
async def list_generated(
    file_type: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
    page_size: Annotated[int, Query()] = 20,
    sort: Annotated[str, Query()] = "newest",
) -> PagedFile:
    """List generated files from the ``output/`` dir.

    Parallel of ``list_uploaded_files``: same query params (``file_type``,
    ``q``, ``page``, ``page_size``, ``sort``), only the directory differs.
    """
    return list_files(
        OUTPUT_DIR,
        file_type=file_type,
        q=q,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@app.get("/api/files/uploaded", response_model=PagedFile)
async def list_uploaded_files(
    file_type: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
    page_size: Annotated[int, Query()] = 20,
    sort: Annotated[str, Query()] = "newest",
) -> PagedFile:
    """List uploaded files from the ``uploads/`` dir.

    Parallel of ``list_generated``: same query params (``file_type``, ``q``,
    ``page``, ``page_size``, ``sort``), only the directory differs.
    """
    return list_files(
        UPLOADS_DIR,
        file_type=file_type,
        q=q,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@app.delete("/api/files", response_model=DeleteFilesResponse)
async def delete_files(body: DeleteFilesRequest) -> DeleteFilesResponse:
    """Delete selected files (path keys from either listing)."""
    allowed = (OUTPUT_DIR, UPLOADS_DIR)
    deleted: list[str] = []
    missing: list[str] = []
    for key in body.files:
        resolved: Path | None = None
        for base in allowed:
            # ``path`` keys are dir-qualified (e.g. ``uploads/foo.pdf``);
            # strip the matching dir prefix if present.
            name = key
            if key.startswith(f"{base.name}/"):
                name = key[len(base.name) + 1 :]
            try:
                resolved = safe_delete_path(base, name)
                break
            except ValueError:
                resolved = None
        if resolved is None or not resolved.is_file():
            missing.append(key)
            continue
        resolved.unlink()
        deleted.append(key)
    return DeleteFilesResponse(deleted=deleted, missing=missing)


# Serve the built SPA when present. Registered last so the explicit API,
# health, and docs routes keep precedence over the catch-all fallback.
if (UI_DIST / "index.html").is_file():
    mount_spa(app, UI_DIST)
