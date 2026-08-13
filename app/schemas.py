"""Pydantic request/response schemas for the resume web API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    """Inputs for a pipeline run (multipart form fields)."""

    job_description: str | None = Field(
        default=None, description="Raw pasted JD text (text wins over job_file)."
    )
    resume: str | None = Field(
        default=None, description="Raw pasted resume text (text wins over resume_file)."
    )
    candidate_name: str = Field(default="", description="Candidate name for rendering.")
    company_name: str = Field(
        default="", description="Target company for the cover letter."
    )
    resume_template: str = Field(
        default="modern",
        description=(
            "Resume layout template to render: modern, classic, minimal, or "
            "all (renders every layout)."
        ),
    )


class PipelineRunResponse(BaseModel):
    """Full pipeline result: 7 agent keys + rendered output file paths."""

    parsed_job_description: Any
    parsed_resume: Any
    tailoring_strategy: Any
    rewritten_resume: Any
    ats_optimized_resume: Any
    polished_resume: Any
    cover_letter: Any
    output_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of format name to rendered file path.",
    )


class TaskCreated(BaseModel):
    """Response to a background pipeline launch."""

    task_id: str = Field(description="Unique id used to poll task status.")


class TaskStatus(BaseModel):
    """Status of an async pipeline task."""

    status: Literal["pending", "running", "completed", "failed"] = Field(
        description="Lifecycle state of the task."
    )
    result: dict[str, Any] | None = Field(
        default=None, description="Serialized pipeline result when completed."
    )
    error: str | None = Field(
        default=None, description="Error message when the task failed."
    )
    created_at: float | None = Field(
        default=None, description="Monotonic timestamp when the task was created."
    )
    completed_at: float | None = Field(
        default=None, description="Monotonic timestamp when the task finished."
    )


class FileMeta(BaseModel):
    """Metadata for a single generated or uploaded file."""

    name: str = Field(description="Filename without the directory prefix.")
    size: int = Field(description="File size in bytes.")
    modified: datetime = Field(description="Last modification time (UTC).")
    type: str = Field(description="Lowercase extension without the dot (e.g. pdf).")
    path: str = Field(description="Dir-qualified key, e.g. uploads/resume.pdf.")


class PagedFile(BaseModel):
    """A filtered + paginated page of file metadata."""

    items: list[FileMeta] = Field(description="Metadata for files on this page.")
    page: int = Field(description="1-based page number.")
    page_size: int = Field(description="Requested page size.")
    total: int = Field(description="Total matching files across all pages.")
    total_pages: int = Field(description="Total number of pages.")


class DeleteFilesRequest(BaseModel):
    """Body for batch-deleting files by their ``path`` keys."""

    files: list[str] = Field(description="Dir-qualified path keys to delete.")


class DeleteFilesResponse(BaseModel):
    """Outcome of a batch delete."""

    deleted: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ModelSummaryRow(BaseModel):
    """One agent's model configuration as shown on the Models page.

    Mirrors one row of ``config.agents.get_model_summary()``: the effective
    provider/model (after any persisted override), the environment defaults
    the agent would fall back to, and whether a persisted override is active.
    """

    agent: str = Field(description="Pipeline agent name, e.g. cover_letter_agent.")
    provider: str = Field(description="Effective provider (ollama or openai).")
    model: str = Field(description="Effective model name.")
    default_provider: str = Field(
        description="Provider without any persisted override."
    )
    default_model: str = Field(description="Model without any persisted override.")
    is_overridden: bool = Field(
        description="Whether a persisted provider/model override is active."
    )


class AgentOverrideUpdate(BaseModel):
    """Body for ``PATCH /api/models/{agent}``: edit provider and/or model."""

    provider: str | None = Field(
        default=None,
        description="Provider name (ollama or openai); None leaves it unchanged.",
    )
    model: str | None = Field(
        default=None, description="Model name; None leaves it unchanged."
    )
