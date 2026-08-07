"""In-memory task registry for background pipeline runs."""

from __future__ import annotations

import logging
import threading
import uuid
from time import monotonic
from typing import Any

logger = logging.getLogger(__name__)


class TaskRegistry:
    """Thread-safe, in-memory store of background pipeline task state."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        """Allocate a unique task id with initial status/created_at."""
        task_id = uuid.uuid4().hex
        with self._lock:
            self._store[task_id] = {
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": monotonic(),
                "completed_at": None,
            }
        logger.debug("Created task %s", task_id)
        return task_id

    def update(self, task_id: str, **fields: Any) -> None:
        """Merge ``fields`` into the task record (no-op if unknown id)."""
        with self._lock:
            record = self._store.get(task_id)
            if record is None:
                logger.debug("update() unknown task %s (ignored)", task_id)
                return
            record.update(fields)

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Return a copy of the task record, or None if unknown."""
        with self._lock:
            record = self._store.get(task_id)
            return dict(record) if record is not None else None

    def set_result(self, task_id: str, result: dict[str, Any]) -> None:
        """Mark complete with a result and completed_at."""
        self.update(
            task_id,
            status="completed",
            result=result,
            completed_at=monotonic(),
        )

    def set_error(self, task_id: str, error: str) -> None:
        """Mark failed with an error message and completed_at."""
        self.update(
            task_id,
            status="failed",
            error=error,
            completed_at=monotonic(),
        )
