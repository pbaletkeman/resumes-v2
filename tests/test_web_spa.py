"""Task 1.3 web tests: built-SPA serving + catch-all fallback.

``mount_spa()`` mounts a Vite build's ``/assets`` directory and registers a
catch-all ``GET /{full_path:path}`` route that serves ``index.html`` for
non-API, non-health, non-dotfile paths. The ``app/main.py`` module wires it
in at import time, guarded by ``ui/dist/index.html`` existing.

Tests:
- ``mount_spa`` against a purpose-built app with a fake ``dist`` under
  ``tmp_path``: deep links return the SPA html, API/health routes are not
  shadowed, dotfile and unknown-API paths are 404.
- The module-level guard via ``importlib.reload`` with a real
  ``ui/dist/index.html`` present (created/removed around the test).

The real ``output/``/``uploads/`` dirs are never touched.
"""

from __future__ import annotations

import importlib
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main as app_module

SPA_HTML = "<html><body>SPA fallback</body></html>"


def _build_dist(dist: Path) -> Path:
    """Populate *dist* with ``index.html`` + an ``assets/`` file."""
    assets = dist / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(SPA_HTML, encoding="utf-8")
    (assets / "app.js").write_text("// build asset", encoding="utf-8")
    return dist


def _build_app() -> FastAPI:
    """A minimal app mirroring the real API routes used in the tests."""
    app = FastAPI()

    @app.get("/api/models")
    async def list_models() -> list[dict[str, str]]:
        return [{"agent": "jd_parsing_agent", "provider": "ollama", "model": "m"}]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
def spa_client(tmp_path: Path) -> Any:
    """TestClient for an app with the SPA mounted from a fake dist."""
    dist = _build_dist(tmp_path / "dist")
    app = _build_app()
    app_module.mount_spa(app, dist)
    with TestClient(app) as client:
        yield client


class TestMountSpa:
    """mount_spa() behaviour with a built SPA present."""

    def test_deep_links_return_index_html(self, spa_client: Any) -> None:
        for path in ("/", "/files", "/models", "/some/deep/link"):
            response = spa_client.get(path)
            assert response.status_code == 200
            assert SPA_HTML in response.text

    def test_api_route_not_shadowed(self, spa_client: Any) -> None:
        response = spa_client.get("/api/models")
        assert response.status_code == 200
        assert response.json()[0]["agent"] == "jd_parsing_agent"

    def test_health_route_not_shadowed(self, spa_client: Any) -> None:
        response = spa_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_assets_served_from_static_mount(self, spa_client: Any) -> None:
        response = spa_client.get("/assets/app.js")
        assert response.status_code == 200
        assert response.text == "// build asset"

    def test_dotfile_path_returns_404(self, spa_client: Any) -> None:
        for path in ("/file.txt", "/resume.pdf", "/.hidden"):
            assert spa_client.get(path).status_code == 404

    def test_unknown_api_path_returns_404(self, spa_client: Any) -> None:
        response = spa_client.get("/api/nope")
        assert response.status_code == 404


class TestModuleGuard:
    """Module-level wiring: SPA routes only registered when dist exists.

    ``app/main.py`` reads ``UI_DIST`` at import time and mounts the SPA when
    ``ui/dist/index.html`` exists. Each test stages/removes the dist and
    reloads ``app.main`` so the import-time guard is exercised for real, and
    always restores the module to its no-build (API-only) state.
    """

    def test_build_present_wires_spa(self) -> None:
        dist = Path("ui") / "dist"
        _build_dist(dist)
        try:
            refreshed = importlib.reload(app_module)
            with TestClient(refreshed.app) as client:
                response = client.get("/files")
                assert response.status_code == 200
                assert SPA_HTML in response.text
                assert client.get("/api/models").status_code == 200
                assert client.get("/health").status_code == 200
        finally:
            _remove_dist(dist)
            importlib.reload(app_module)

    def test_no_build_keeps_api_only(self) -> None:
        # No dist present: reloading reproduces the API-only app, so unknown
        # non-API GETs are plain 404s and API/health routes still work.
        dist = Path("ui") / "dist"
        _remove_dist(dist)
        try:
            refreshed = importlib.reload(app_module)
            with TestClient(refreshed.app) as client:
                assert client.get("/files").status_code == 404
                assert client.get("/api/models").status_code == 200
        finally:
            importlib.reload(app_module)


def _remove_dist(dist: Path) -> None:
    """Best-effort removal of the ``ui/dist`` tree."""
    index = dist / "index.html"
    if index.is_file():
        index.unlink()
    assets = dist / "assets"
    for child in assets.iterdir() if assets.is_dir() else ():
        child.unlink()
    if assets.is_dir():
        assets.rmdir()
    with suppress(OSError):
        dist.rmdir()
