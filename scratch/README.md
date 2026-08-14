# Scratch — Working Logs, Plans & Archives

- [Scratch — Working Logs, Plans \& Archives](#scratch--working-logs-plans--archives)
  - [Index](#index)
  - [Conventions](#conventions)

This directory holds the repo's working notes: planning documents, task logs,
verification records, and completed-work archives for the resume optimization
pipeline. The `scratch/*.md` files are tracked in git for provenance but are
**not part of the shipped product** — the authoritative, maintained references
live in `docs/` (`docs/README.md` is the hub), `AGENTS.md`, and `ui/README.md`.

Most notes carry a `STATUS: ARCHIVED` header and are kept purely for the
decisions, wireframes, and build history they record. The only currently
actionable item in the whole directory is the manual E2E verification in
`frontend-tasks.md` (§7.3).

## Index

| File | Status | What it is |
| --- | --- | --- |
| [`bots.md`](bots.md) | Archived | Original 7-agent design spec (per-agent prompts + output fields). Superseded by `docs/agents.md`. |
| [`simple.md`](simple.md) | Complete | Simplification-plan progress log. All phases done; records moved to `simple-done.md`. |
| [`simple-done.md`](simple-done.md) | Archive | Completed-phases archive of the inspect-and-simplify effort (phases 1-23, incl. docs consolidation). |
| [`resume-done.md`](resume-done.md) | Archive | Completed-work archive for the pipeline (phases 1-10, 8.x, 9). |
| [`resume-todo.md`](resume-todo.md) | Complete | Remaining-work log — all done (2026-08-08); points to `resume-done.md`. |
| [`resume-verify.md`](resume-verify.md) | Archived | Verification plan + results record (2026-08-06), incl. two `pipeline.py` bugs found and fixed. |
| [`resume-web-todo.md`](resume-web-todo.md) | Archived | FastAPI web-layer plan (`app/`), incl. the `_run_pipeline_core` vs `run_resume_pipeline` constraint. |
| [`web-files-todo.md`](web-files-todo.md) | Archived | File-management endpoints plan (`GET/DELETE /api/files`). |
| [`frontend-plan.md`](frontend-plan.md) | Archived | Frontend plan (Vite + React + PrimeReact) with wireframes. Implemented in `ui/`. |
| [`frontend-tasks.md`](frontend-tasks.md) | Actionable | Frontend implementation tasks — **one item left** (§7.3 manual E2E). |
| [`frontend-tasks-done.md`](frontend-tasks-done.md) | Archive | Frontend completed-tasks archive (scaffold, theming, pages, hooks, tests). |

## Conventions

- A file with a `> STATUS: ARCHIVED` header is historical — do not edit it to
  chase new work; record new work elsewhere.
- Completed tasks are moved from a `*tasks.md` / `*.md` log into the matching
  `*-done.md` archive, keeping the live log short.
- Stale hard-coded counts (test totals, line numbers) should be refreshed in
  the docs (`AGENTS.md`, `docs/`, `README.md`) rather than left diverging from
  the code.
- All files here pass `markdownlint-cli2` (see `.markdownlint-cli2.jsonc`).
