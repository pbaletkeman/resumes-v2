"""Phase 7.4.2 web tests: sync + async pipeline routes.

Covers ``POST /api/pipeline`` (text/file inputs, validation, serialization)
and ``POST /api/pipeline/async`` (background task lifecycle). ``_run_pipeline_core``
is patched with an ``AsyncMock`` so no LLM is invoked; requests exercise the
routes, form parsing, validation, and the task registry instead.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import main as app_module

JD_TEXT = "Senior Backend Engineer at Acme Corp"
RES_TEXT = "Jane Doe, senior engineer with 10 years of experience."

STAGE_KEYS = (
    "parsed_job_description",
    "parsed_resume",
    "tailoring_strategy",
    "rewritten_resume",
    "ats_optimized_resume",
    "polished_resume",
    "cover_letter",
)


def _canned_result() -> dict[str, Any]:
    """A pipeline core result with JSON-serializable stage values."""
    return {
        "parsed_job_description": {"role_title": "Senior Backend Engineer"},
        "parsed_resume": {"name": "Jane Doe"},
        "tailoring_strategy": {"missing_skills": ["Kubernetes"]},
        "rewritten_resume": "Rewritten resume.",
        "ats_optimized_resume": "ATS optimized resume.",
        "polished_resume": "Polished resume.",
        "cover_letter": "Cover letter body.",
        "output_files": {"resume_pdf": "output/resume.pdf"},
    }


def _wait_for_task(client: Any, task_id: str, timeout: float = 5.0) -> dict[str, Any]:
    """Poll ``GET /api/tasks/{id}`` until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in ("completed", "failed"):
            return payload
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} did not finish within {timeout}s")


@pytest.fixture(scope="module")
def client() -> Any:
    """TestClient with the app lifespan entered (runner built on startup)."""
    with TestClient(app_module.app) as test_client:
        yield test_client


class TestRunPipelineSync:
    """7.4.2.1-7.4.2.6: sync route behaviour."""

    def test_text_inputs_return_full_result_shape(
        self, client: Any, monkeypatch
    ) -> None:
        core_mock = AsyncMock(return_value=_canned_result())
        monkeypatch.setattr(app_module, "_run_pipeline_core", core_mock)

        response = client.post(
            "/api/pipeline",
            data={"job_description": JD_TEXT, "resume": RES_TEXT},
        )

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {*STAGE_KEYS, "output_files"}
        assert payload["output_files"] == {"resume_pdf": "output/resume.pdf"}
        core_mock.assert_called_once()

    def test_text_wins_over_uploaded_file(self, client: Any, monkeypatch) -> None:
        core_mock = AsyncMock(return_value=_canned_result())
        monkeypatch.setattr(app_module, "_run_pipeline_core", core_mock)

        response = client.post(
            "/api/pipeline",
            data={
                "job_description": JD_TEXT,
                "resume": RES_TEXT,
                "candidate_name": "Jane Doe",
                "company_name": "Acme Corp",
            },
            files={"job_file": ("job.txt", b"FILE TEXT SHOULD NOT WIN", "text/plain")},
        )

        assert response.status_code == 200
        call = core_mock.call_args
        assert call is not None
        assert call.args[1] == JD_TEXT
        assert call.args[2] == RES_TEXT
        assert call.kwargs["candidate_name"] == "Jane Doe"
        assert call.kwargs["company_name"] == "Acme Corp"

    def test_resume_template_classic_forwarded(self, client: Any, monkeypatch) -> None:
        core_mock = AsyncMock(return_value=_canned_result())
        monkeypatch.setattr(app_module, "_run_pipeline_core", core_mock)

        response = client.post(
            "/api/pipeline",
            data={
                "job_description": JD_TEXT,
                "resume": RES_TEXT,
                "resume_template": "classic",
            },
        )

        assert response.status_code == 200
        call = core_mock.call_args
        assert call is not None
        assert call.kwargs["resume_template"] == "classic"
        assert "resume_templates" not in call.kwargs

    def test_resume_template_all_forwarded(self, client: Any, monkeypatch) -> None:
        core_mock = AsyncMock(return_value=_canned_result())
        monkeypatch.setattr(app_module, "_run_pipeline_core", core_mock)

        response = client.post(
            "/api/pipeline",
            data={
                "job_description": JD_TEXT,
                "resume": RES_TEXT,
                "resume_template": "all",
            },
        )

        assert response.status_code == 200
        call = core_mock.call_args
        assert call is not None
        assert call.kwargs["resume_templates"] == ["modern", "classic", "minimal"]
        assert "resume_template" not in call.kwargs

    def test_invalid_resume_template_returns_400(self, client: Any) -> None:
        response = client.post(
            "/api/pipeline",
            data={
                "job_description": JD_TEXT,
                "resume": RES_TEXT,
                "resume_template": "banana",
            },
        )

        assert response.status_code == 400
        assert "Unknown resume template" in response.json()["detail"]

    def test_missing_both_inputs_returns_400(self, client: Any) -> None:
        response = client.post("/api/pipeline", data={})

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Provide job description as pasted text or an uploaded file."
        )

    def test_empty_text_and_no_file_returns_400(self, client: Any) -> None:
        response = client.post(
            "/api/pipeline",
            data={"job_description": "   ", "resume": RES_TEXT},
        )

        assert response.status_code == 400
        assert "must not be empty" in response.json()["detail"]

    def test_unsupported_file_type_returns_400(
        self, client: Any, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(app_module, "UPLOADS_DIR", tmp_path)

        response = client.post(
            "/api/pipeline",
            data={"resume": RES_TEXT},
            files={"job_file": ("jobs.exe", b"%PDF-shim", "application/octet-stream")},
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_oversized_file_returns_400(
        self, client: Any, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr(app_module, "UPLOADS_DIR", tmp_path)
        monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 4)

        response = client.post(
            "/api/pipeline",
            data={"resume": RES_TEXT},
            files={"job_file": ("jobs.txt", b"longer than four bytes", "text/plain")},
        )

        assert response.status_code == 400
        assert "too large" in response.json()["detail"]


class TestRunPipelineAsync:
    """7.4.2.7-7.4.2.9: background task routes."""

    def test_async_launch_returns_task_id(self, client: Any, monkeypatch) -> None:
        monkeypatch.setattr(
            app_module, "_run_pipeline_core", AsyncMock(return_value=_canned_result())
        )

        response = client.post(
            "/api/pipeline/async",
            data={"job_description": JD_TEXT, "resume": RES_TEXT},
        )

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"task_id"}
        assert payload["task_id"]

    def test_async_task_lifecycle_completes(self, client: Any, monkeypatch) -> None:
        monkeypatch.setattr(
            app_module, "_run_pipeline_core", AsyncMock(return_value=_canned_result())
        )

        launch = client.post(
            "/api/pipeline/async",
            data={"job_description": JD_TEXT, "resume": RES_TEXT},
        )
        task_id = launch.json()["task_id"]
        payload = _wait_for_task(client, task_id)

        assert payload["status"] == "completed"
        assert payload["completed_at"] is not None
        assert set(payload["result"]) == {*STAGE_KEYS, "output_files"}

    def test_async_task_failure_records_error(self, client: Any, monkeypatch) -> None:
        async def _explode(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

        monkeypatch.setattr(app_module, "_run_pipeline_core", _explode)

        launch = client.post(
            "/api/pipeline/async",
            data={"job_description": JD_TEXT, "resume": RES_TEXT},
        )
        task_id = launch.json()["task_id"]
        payload = _wait_for_task(client, task_id)

        assert payload["status"] == "failed"
        assert payload["error"] == "boom"
        assert payload["result"] is None

    def test_async_resume_template_all_forwarded(
        self, client: Any, monkeypatch
    ) -> None:
        core_mock = AsyncMock(return_value=_canned_result())
        monkeypatch.setattr(app_module, "_run_pipeline_core", core_mock)

        launch = client.post(
            "/api/pipeline/async",
            data={
                "job_description": JD_TEXT,
                "resume": RES_TEXT,
                "resume_template": "all",
            },
        )
        task_id = launch.json()["task_id"]
        payload = _wait_for_task(client, task_id)

        assert payload["status"] == "completed"
        call = core_mock.call_args
        assert call is not None
        assert call.kwargs["resume_templates"] == ["modern", "classic", "minimal"]
