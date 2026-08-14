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


def _record_parity_calls(
    client: Any,
    monkeypatch: Any,
    tmp_path: Any,
    *,
    candidate_name: str,
    company_name: str,
    template: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Capture the pipeline-core kwargs from the CLI and the sync web route.

    Both entry points must forward the exact same parameters (runner aside)
    for identical user inputs; otherwise identical inputs can produce
    different output.
    """
    import pipeline

    recorded: list[dict[str, Any]] = []

    async def recording_core(
        runner: Any, job_description: str, resume: str, **kwargs: Any
    ) -> dict[str, Any]:
        recorded.append(
            {"job_description": job_description, "resume": resume, **kwargs}
        )
        return _canned_result()

    monkeypatch.setattr(pipeline, "_run_pipeline_core", recording_core)
    monkeypatch.setattr(app_module, "_run_pipeline_core", recording_core)
    monkeypatch.setattr(pipeline, "create_runner_from_config", lambda *a, **k: object())

    resume_file = tmp_path / "resume.txt"
    resume_file.write_text(RES_TEXT, encoding="utf-8")
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text(JD_TEXT, encoding="utf-8")

    cli_args = ["--resume", str(resume_file), "--job-description", str(jd_file)]
    if candidate_name:
        cli_args += ["--candidate-name", candidate_name]
    if company_name:
        cli_args += ["--company-name", company_name]
    if template:
        cli_args += ["--template", template]

    exit_code = pipeline.main(cli_args)
    assert exit_code == 0

    web_data: dict[str, str] = {"job_description": JD_TEXT, "resume": RES_TEXT}
    if candidate_name:
        web_data["candidate_name"] = candidate_name
    if company_name:
        web_data["company_name"] = company_name
    if template:
        web_data["resume_template"] = template

    response = client.post("/api/pipeline", data=web_data)
    assert response.status_code == 200
    assert len(recorded) == 2
    return recorded[0], recorded[1]


def _effective(call: dict[str, Any]) -> dict[str, Any]:
    """Reduce a core call to its effective template semantics.

    ``run_resume_pipeline`` always forwards ``resume_templates`` (``None``
    when not requested) while the web route omits the key entirely; both mean
    "render the single ``resume_template``".  When ``resume_templates`` is
    set it takes precedence over ``resume_template`` in
    ``ResumeRenderer.render_all``, so the trailing default
    ``resume_template="modern"`` the CLI still forwards is dropped too.
    """
    effective = {k: v for k, v in call.items() if v is not None}
    if effective.get("resume_templates") is not None:
        effective.pop("resume_template", None)
    return effective


class TestEntryPointParity:
    """CLI and web API forward identical parameters to the pipeline core.

    The CLI (``pipeline.main`` -> ``run_resume_pipeline``) and the web route
    (``POST /api/pipeline``) both funnel through ``_run_pipeline_core``; with
    the same inputs and the same effective model configuration they produce
    the same output.  These tests lock the parameter-forwarding contract.
    """

    def test_cli_and_web_forward_identical_core_kwargs(
        self, client: Any, monkeypatch, tmp_path
    ) -> None:
        cli_call, web_call = _record_parity_calls(
            client,
            monkeypatch,
            tmp_path,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
            template="classic",
        )
        assert _effective(cli_call) == _effective(web_call)
        assert cli_call["resume_template"] == "classic"

    def test_cli_and_web_template_all_match(
        self, client: Any, monkeypatch, tmp_path
    ) -> None:
        cli_call, web_call = _record_parity_calls(
            client,
            monkeypatch,
            tmp_path,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
            template="all",
        )
        assert _effective(cli_call) == _effective(web_call)
        assert cli_call["resume_templates"] == ["modern", "classic", "minimal"]

    def test_cli_and_web_defaults_match(
        self, client: Any, monkeypatch, tmp_path
    ) -> None:
        cli_call, web_call = _record_parity_calls(
            client,
            monkeypatch,
            tmp_path,
            candidate_name="",
            company_name="",
            template="",
        )
        assert _effective(cli_call) == _effective(web_call)
        assert cli_call["candidate_name"] == ""
        assert cli_call["company_name"] == ""
        assert cli_call["resume_template"] == "modern"
