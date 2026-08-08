"""Phase 7.4.4 web tests: output file serving.

``GET /api/outputs/{filename}`` serves files out of ``OUTPUT_DIR``.
``OUTPUT_DIR`` is monkeypatched to ``tmp_path`` per test so the real
``output/`` dir is never touched. Covers an existing file streaming its
bytes (7.4.4.1), a missing file (7.4.4.2), and a path-traversal attempt
that must not escape the directory (7.4.4.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main as app_module

OUTPUT_FILENAME = "resume.pdf"
OUTPUT_BYTES = b"%PDF-1.4 fake resume content"


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """A fresh empty output dir + ``OUTPUT_DIR`` monkeypatch."""
    return tmp_path


@pytest.fixture(scope="module")
def client() -> Any:
    """TestClient with the app lifespan entered (runner built on startup)."""
    with TestClient(app_module.app) as test_client:
        yield test_client


class TestOutputServing:
    """7.4.4: ``GET /api/outputs/{filename}`` behaviour."""

    def test_existing_file_streams_bytes(
        self, client: Any, monkeypatch, output_dir: Path
    ) -> None:
        (output_dir / OUTPUT_FILENAME).write_bytes(OUTPUT_BYTES)
        monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)

        response = client.get(f"/api/outputs/{OUTPUT_FILENAME}")

        assert response.status_code == 200
        assert response.content == OUTPUT_BYTES
        assert response.headers["content-type"].startswith("application/pdf")

    def test_missing_file_returns_404(
        self, client: Any, monkeypatch, output_dir: Path
    ) -> None:
        monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)

        response = client.get("/api/outputs/missing.pdf")

        assert response.status_code == 404

    def test_path_traversal_does_not_escape_output_dir(
        self, client: Any, monkeypatch, output_dir: Path
    ) -> None:
        outside = output_dir.parent / "secret.txt"
        outside.write_text("should never be served")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)

        response = client.get("/api/outputs/../secret.txt")

        assert response.status_code == 404
