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

    task_id: str


class TaskStatus(BaseModel):
    """Status of an async pipeline task."""

    status: Literal["pending", "running", "completed", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float | None = None
    completed_at: float | None = None


class FileMeta(BaseModel):
    """Metadata for a single generated or uploaded file."""

    name: str
    size: int
    modified: datetime
    type: str
    path: str


class PagedFile(BaseModel):
    """A filtered + paginated page of file metadata."""

    items: list[FileMeta]
    page: int
    page_size: int
    total: int
    total_pages: int


class DeleteFilesRequest(BaseModel):
    """Body for batch-deleting files by their ``path`` keys."""

    files: list[str]


class DeleteFilesResponse(BaseModel):
    """Outcome of a batch delete."""

    deleted: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
