# Resume Pipeline — Remaining Work

**Status:** ✅ ALL DONE (2026-08-08) — nothing left to implement.

Everything that was once on this list has been completed and archived in [resume-done.md](resume-done.md). The archive now includes the full Phase 7 (Testing & Docs) work: the live end-to-end test, the per-agent + pipeline test coverage, the web API tests, and the four doc guides.

## What was completed here (archive link)

| Section | Summary | Archived to |
|---------|---------|-------------|
| Verification bugs (V1 event-loop, V2 `_extract_field`) | Fixed during live verification runs | See `resume-done.md` §Phase 9 & `resume-todo.md` history below |
| **7.1** `test_real_files.py` | Live E2E integration test (requires Ollama; `RUN_LIVE_PIPELINE` guard) | `resume-done.md` §7.1 |
| **7.2.1** Agent contract tests | 55 tests across 7 files, `FakeClient` in `conftest.py` | `resume-done.md` §7.2.1 |
| **7.2.2** `tests/test_pipeline.py` | 17 orchestration tests with stub agents | `resume-done.md` §7.2.2 |
| **7.3** Docs | `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md` | `resume-done.md` §7.3 |
| **7.4** Web API tests | 43 tests across 6 files (`test_web_health/pipeline/tasks/outputs/files/upload`) | `resume-done.md` §7.4 |

## Final verification state

- `uv run pytest` → **477 passed** (23 test files, up from 362/9).
- `uv run ruff check .` → clean.
- `uv run ruff format --check .` → clean.
- `uv run pyright` (strict) → **0 errors, 0 warnings, 0 informations**.
- Live pipeline: `uv run python test_real_files.py` (Ollama required).

---

## Historical record

> For traceability, the two live-run bugs fixed during `resume-verify.md` are described below. Both were resolved and merged into the codebase long ago; they are kept as a reference for how event-loop and dict-vs-model handling bugs surface only under a live LLM.

### Verification bugs (fixed 2026-08-06 during `resume-verify.md` live runs)

#### V1 — Event-loop lifecycle: `RuntimeError: Event loop is closed` — ✅ FIXED

`AgentRunner.run_agent()` wrapped each of the 7 agents in its own `asyncio.run()`, opening+closing a fresh event loop per agent. The dedicated agent classes share a single `ollama.AsyncClient` bound to the first loop, so agent 1 (`jd_parsing_agent`) succeeded but agent 2 (`resume_parsing_agent`) and later failed with `RuntimeError: Event loop is closed`.

**Fix:** added `AgentRunner.run_agent_async()` (async dispatch) and made sync `run_agent()` delegate via one `asyncio.run()`. `run_resume_pipeline()` now runs all 7 agents under a single event loop through a new `_run_pipeline_core()` coroutine, wrapped once in `asyncio.run()`.

#### V2 — `_extract_field` returns whole model instead of named field — ✅ FIXED

`pipeline._extract_field()` only handled `dict` results, so when a dedicated agent returned a Pydantic model it returned the entire model rather than its named field. With ATS this passed an `ATSComplianceOutput` object into `tone_polishing_agent`, which raised `TypeError: object of type 'ATSComplianceOutput' has no len()`.

**Fix:** added a `getattr` branch so model results yield their named field (e.g. `final_resume`, `cover_letter`) before falling back to the object itself.

---

## Web API workstreams

The web API layer (`app/`) was tracked in separate work logs: `resume-web-todo.md` (API routes) and `web-files-todo.md` (file-management endpoints). Both are complete. The test coverage for the web layer is archived in `resume-done.md` §7.4.