# Resume Pipeline — Remaining Work

**Status:** ✅ ALL DONE (2026-08-08) — nothing left to implement.

Everything that was once on this list has been completed and archived in [resume-done.md](resume-done.md):

- **Verification bugs (V1 event-loop, V2 `_extract_field`)** → `resume-done.md` §"Verification Bugs"
- **Phase 7.1** `test_real_files.py` live E2E test → `resume-done.md` §7.1
- **Phase 7.2.1** agent contract tests (55 tests, `FakeClient` in `conftest.py`) → `resume-done.md` §7.2.1
- **Phase 7.2.2** `tests/test_pipeline.py` (17 tests) → `resume-done.md` §7.2.2
- **Phase 7.3** docs (`architecture.md`, `agents.md`, `usage.md`, `api.md`) → `resume-done.md` §7.3
- **Phase 7.4** web API tests (43 tests across 6 files) → `resume-done.md` §7.4

## Final verification state

- `uv run pytest` → **477 passed** (23 test files).
- `uv run ruff check .` → clean.
- `uv run ruff format --check .` → clean.
- `uv run pyright` (strict) → **0 errors, 0 warnings, 0 informations**.
- Live pipeline: `uv run python test_real_files.py` (Ollama required).

---

## Web API workstreams

The web API layer (`app/`) was tracked in separate work logs: `resume-web-todo.md` (API routes) and `web-files-todo.md` (file-management endpoints). Both are complete. Their build/test history is archived in `resume-done.md` (Phase 10 + §7.4).