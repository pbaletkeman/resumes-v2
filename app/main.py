"""FastAPI application exposing the 7-agent resume pipeline as an API."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.files import list_files, safe_delete_path
from app.schemas import (
    DeleteFilesRequest,
    DeleteFilesResponse,
    PagedFile,
    PipelineRunResponse,
    TaskCreated,
    TaskStatus,
)
from app.tasks import TaskRegistry
from app.upload import extract_text
from config.agents import get_model_summary
from pipeline import (
    _run_pipeline_core,  # pyright: ignore[reportPrivateUsage]
    create_runner_from_config,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
UPLOADS_DIR = Path("uploads")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None]:
    """Build one shared AgentRunner on the app loop at startup."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    runner = create_runner_from_config()
    app_instance.state.runner = runner
    logger.info("Agent runner built; agents: %s", ", ".join(runner.agents))
    yield
    logger.info("Agent runner context exit")


app = FastAPI(title="Resume Web API", lifespan=lifespan)
registry = TaskRegistry()


def _require_runner() -> Any:
    runner = getattr(app.state, "runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Pipeline runner not initialized")
    return runner


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

    Raises:
        HTTPException(400) when neither resolves to non-empty text.
    """
    if text and text.strip():
        return text
    if file is not None:
        _persist_upload(file, name)
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail=f"{name} file is too large.")
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
    """Serialize the pipeline core result into the response model."""
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


@app.get("/api/models")
async def list_models() -> list[dict[str, str]]:
    return get_model_summary()


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
    """Run the full pipeline synchronously (multipart form inputs)."""
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
    """Launch a background pipeline run; returns a task id."""
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
    """List generated files from the ``output/`` dir."""
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
    """List uploaded files from the ``uploads/`` dir."""
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
