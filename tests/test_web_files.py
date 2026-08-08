"""Phase 7.4.5 web tests: file listing + deletion routes.

``GET /api/files/generated`` / ``GET /api/files/uploaded`` list files from
``OUTPUT_DIR`` / ``UPLOADS_DIR`` (with filtering/sorting/paging); ``DELETE
/api/files`` batch-deletes by ``path`` key. Both dirs are monkeypatched to
``tmp_path`` subdirs named ``output``/``uploads`` so ``build_file_meta``
emits the same `path` prefixes the real dirs would, and nothing touches the
real ``output/``/``uploads/``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main as app_module


@pytest.fixture
def file_dirs(tmp_path: Path) -> dict[str, Path]:
    """Fresh ``output/`` and ``uploads/`` dirs under tmp_path."""
    output = tmp_path / "output"
    uploads = tmp_path / "uploads"
    output.mkdir()
    uploads.mkdir()
    return {"output": output, "uploads": uploads}


def _write(dir_path: Path, name: str, mtime: float | None = None) -> None:
    """Write a tiny file (optionally with a controlled mtime)."""
    target = dir_path / name
    target.write_bytes(b"x")
    if mtime is not None:
        os.utime(target, (mtime, mtime))


@pytest.fixture(scope="module")
def client() -> Any:
    """TestClient with the app lifespan entered (runner built on startup)."""
    with TestClient(app_module.app) as test_client:
        yield test_client


class TestListGenerated:
    """7.4.5.1-7.4.5.4: ``GET /api/files/generated``."""

    def test_returns_paged_file_shape(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "resume.pdf")
        _write(file_dirs["output"], "cover.txt")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        response = client.get("/api/files/generated")

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"items", "page", "page_size", "total", "total_pages"}
        assert payload["total"] == 2
        assert payload["total_pages"] == 1
        names = {item["name"] for item in payload["items"]}
        assert names == {"resume.pdf", "cover.txt"}

    def test_file_type_filter_narrows_results(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "resume.pdf")
        _write(file_dirs["output"], "notes.pdf")
        _write(file_dirs["output"], "cover.txt")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        response = client.get("/api/files/generated", params={"file_type": "pdf"})

        assert response.status_code == 200
        payload = response.json()
        names = {item["name"] for item in payload["items"]}
        assert names == {"resume.pdf", "notes.pdf"}
        assert payload["total"] == 2

    def test_query_filter_narrows_results(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "resume.pdf")
        _write(file_dirs["output"], "notes.txt")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        response = client.get("/api/files/generated", params={"q": "resume"})

        assert response.status_code == 200
        payload = response.json()
        names = {item["name"] for item in payload["items"]}
        assert names == {"resume.pdf"}

    def test_sort_modes(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "bravo.txt", mtime=100)
        _write(file_dirs["output"], "alpha.pdf", mtime=300)
        _write(file_dirs["output"], "charlie.md", mtime=200)
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        newest = client.get("/api/files/generated", params={"sort": "newest"}).json()
        oldest = client.get("/api/files/generated", params={"sort": "oldest"}).json()
        name_asc = client.get(
            "/api/files/generated", params={"sort": "name_asc"}
        ).json()
        name_desc = client.get(
            "/api/files/generated", params={"sort": "name_desc"}
        ).json()

        assert [item["name"] for item in newest["items"]] == [
            "alpha.pdf",
            "charlie.md",
            "bravo.txt",
        ]
        assert [item["name"] for item in oldest["items"]] == [
            "bravo.txt",
            "charlie.md",
            "alpha.pdf",
        ]
        assert [item["name"] for item in name_asc["items"]] == [
            "alpha.pdf",
            "bravo.txt",
            "charlie.md",
        ]
        assert [item["name"] for item in name_desc["items"]] == [
            "charlie.md",
            "bravo.txt",
            "alpha.pdf",
        ]

    def test_unknown_sort_returns_400(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "resume.pdf")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        response = client.get("/api/files/generated", params={"sort": "bogus"})

        assert response.status_code == 400

    def test_paging(self, client: Any, monkeypatch, file_dirs: dict[str, Path]) -> None:
        _write(file_dirs["output"], "a.txt")
        _write(file_dirs["output"], "b.txt")
        _write(file_dirs["output"], "c.txt")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        first_page = client.get(
            "/api/files/generated", params={"page": 1, "page_size": 2}
        ).json()
        second_page = client.get(
            "/api/files/generated", params={"page": 2, "page_size": 2}
        ).json()

        assert len(first_page["items"]) == 2
        assert first_page["page"] == 1
        assert len(second_page["items"]) == 1
        assert second_page["page"] == 2
        assert second_page["total"] == 3

    def test_page_below_one_returns_400(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "a.txt")
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])

        response = client.get("/api/files/generated", params={"page": 0})

        assert response.status_code == 400


class TestListUploaded:
    """7.4.5.5: ``GET /api/files/uploaded`` mirrors on ``uploads/``."""

    def test_lists_uploaded_files(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["uploads"], "job.txt")
        _write(file_dirs["uploads"], "resume.docx")
        monkeypatch.setattr(app_module, "UPLOADS_DIR", file_dirs["uploads"])

        response = client.get("/api/files/uploaded")

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"items", "page", "page_size", "total", "total_pages"}
        assert payload["total"] == 2
        names = {item["name"] for item in payload["items"]}
        assert names == {"job.txt", "resume.docx"}


class TestDeleteFiles:
    """7.4.5.6-7.4.5.8: ``DELETE /api/files``."""

    def _patch_dirs(
        self,
        monkeypatch,
        file_dirs: dict[str, Path],
    ) -> None:
        monkeypatch.setattr(app_module, "OUTPUT_DIR", file_dirs["output"])
        monkeypatch.setattr(app_module, "UPLOADS_DIR", file_dirs["uploads"])

    def test_deleted_and_missing_split(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["output"], "existing.pdf")
        self._patch_dirs(monkeypatch, file_dirs)

        response = client.request(
            "DELETE", "/api/files", json={"files": ["existing.pdf", "missing.pdf"]}
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] == ["existing.pdf"]
        assert payload["missing"] == ["missing.pdf"]
        assert not (file_dirs["output"] / "existing.pdf").exists()
        assert not (file_dirs["output"] / "missing.pdf").exists()

    def test_dir_qualified_keys_resolve(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        _write(file_dirs["uploads"], "foo.txt")
        _write(file_dirs["output"], "bar.pdf")
        self._patch_dirs(monkeypatch, file_dirs)

        response = client.request(
            "DELETE",
            "/api/files",
            json={"files": ["uploads/foo.txt", "output/bar.pdf"]},
        )

        assert response.status_code == 200
        payload = response.json()
        assert sorted(payload["deleted"]) == ["output/bar.pdf", "uploads/foo.txt"]
        assert payload["missing"] == []
        assert not (file_dirs["uploads"] / "foo.txt").exists()
        assert not (file_dirs["output"] / "bar.pdf").exists()

    def test_path_traversal_never_deletes_outside_dir(
        self, client: Any, monkeypatch, file_dirs: dict[str, Path]
    ) -> None:
        decoy = file_dirs["output"].parent / "secret.txt"
        decoy.write_text("must survive")
        self._patch_dirs(monkeypatch, file_dirs)

        response = client.request(
            "DELETE", "/api/files", json={"files": ["../../secret.txt"]}
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["deleted"] == []
        assert payload["missing"] == ["../../secret.txt"]
        assert decoy.is_file()
        assert decoy.read_text() == "must survive"
