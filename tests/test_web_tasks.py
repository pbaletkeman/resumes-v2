"""Phase 7.4.3 web tests: ``TaskRegistry`` unit + tasks route.

``TaskRegistry`` is exercised directly (no network, no event loop), and the
``GET /api/tasks/{id}`` route is checked via ``TestClient`` for the unknown-id
``404`` path. The route reads the app's module-level registry; a random hex id
is used so the check never collides with a live task.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main as app_module
from app.tasks import TaskRegistry


@pytest.fixture
def registry() -> TaskRegistry:
    return TaskRegistry()


@pytest.fixture(scope="module")
def client() -> Any:
    """TestClient with the app lifespan entered (runner built on startup)."""
    with TestClient(app_module.app) as test_client:
        yield test_client


class TestTaskRegistryCreate:
    """``create()``: unique ids + initial record shape."""

    def test_create_returns_unique_ids(self, registry: TaskRegistry) -> None:
        first = registry.create()
        second = registry.create()

        assert first != second
        assert isinstance(first, str)
        assert first
        assert second

    def test_create_initializes_pending_record(self, registry: TaskRegistry) -> None:
        task_id = registry.create()
        record = registry.get(task_id)

        assert record is not None
        assert record["status"] == "pending"
        assert record["result"] is None
        assert record["error"] is None
        assert record["created_at"] is not None
        assert record["completed_at"] is None


class TestTaskRegistryUpdateGet:
    """``update()/get()`` round-trip + copy semantics."""

    def test_update_and_get_round_trip_fields(self, registry: TaskRegistry) -> None:
        task_id = registry.create()
        registry.update(task_id, status="running", note="background")

        record = registry.get(task_id)
        assert record is not None
        assert record["status"] == "running"
        assert record["note"] == "background"

    def test_get_returns_a_copy(self, registry: TaskRegistry) -> None:
        task_id = registry.create()
        record = registry.get(task_id)
        assert record is not None

        record["status"] = "tampered"
        record["extra"] = "not stored"

        fresh = registry.get(task_id)
        assert fresh is not None
        assert fresh["status"] == "pending"
        assert "extra" not in fresh

    def test_update_unknown_id_is_noop(self, registry: TaskRegistry) -> None:
        registry.update("does-not-exist", status="running")

        assert registry.get("does-not-exist") is None

    def test_get_unknown_id_returns_none(self, registry: TaskRegistry) -> None:
        assert registry.get("does-not-exist") is None


class TestTaskRegistryLifecycle:
    """``set_result()``/``set_error()`` terminal transitions."""

    def test_set_result_marks_completed(self, registry: TaskRegistry) -> None:
        task_id = registry.create()
        result = {"polished_resume": "done"}

        registry.set_result(task_id, result)

        record = registry.get(task_id)
        assert record is not None
        assert record["status"] == "completed"
        assert record["result"] == result
        assert record["completed_at"] is not None
        assert record["error"] is None

    def test_set_error_marks_failed(self, registry: TaskRegistry) -> None:
        task_id = registry.create()

        registry.set_error(task_id, "boom")

        record = registry.get(task_id)
        assert record is not None
        assert record["status"] == "failed"
        assert record["error"] == "boom"
        assert record["completed_at"] is not None
        assert record["result"] is None


class TestTaskRoutes:
    """Task route behaviour via TestClient."""

    def test_get_unknown_task_returns_404(self, client: Any) -> None:
        response = client.get("/api/tasks/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"detail": "Unknown task id"}
