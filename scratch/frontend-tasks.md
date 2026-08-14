# Frontend Implementation Tasks

> **STATUS: ACTIONABLE — one item left.** This is the only still-open root
> scratch note. Every completed task lives in `scratch/frontend-tasks-done.md`
> (sections 1.1-2.5, 5.x, 6, 7.1/7.2, 8.1 are all done; the empty section
> headers 2/4/5 below are stubs pointing there). The single remaining item is
> **§7.3 Manual E2E** below: run the built app against the backend and confirm
> status polling, all result tabs, downloads, theming, and the SPA fallback.

- [Frontend Implementation Tasks](#frontend-implementation-tasks)
  - [2. Scaffold `ui/` (Vite + React + TS)](#2-scaffold-ui-vite--react--ts)
  - [4. `src/api/` — typed client + React Query hooks](#4-srcapi--typed-client--react-query-hooks)
  - [5. Views (PrimeReact)](#5-views-primereact)
  - [7. Verification (whole app)](#7-verification-whole-app)
    - [7.3 Manual E2E](#73-manual-e2e)
  - [8. Docs (optional)](#8-docs-optional)


Detailed breakdown of `scratch/frontend-plan.md` into actionable, verifiable tasks. Each task lists the deliverable, its acceptance check(s), and how to verify. Assumed environment: Node v24/npm on Windows, backend on `localhost:8000` (`uv run uvicorn app.main:app --reload`).

Conventions:

- All `ui/` commands run with `ui/` as the working directory.
- Python checks run from the repo root.
- Follow `AGENTS.md` conventions (ruff/pyright strict, no comments unless asked).

---

## 2. Scaffold `ui/` (Vite + React + TS)

---

## 4. `src/api/` — typed client + React Query hooks

---

## 5. Views (PrimeReact)

---

## 7. Verification (whole app)

### 7.3 Manual E2E

- Backend up (`uv run uvicorn app.main:app --reload`), `npm run dev` in `ui/`.
- Run pipeline with `sample/jobs/*` + `sample/resume/*` (paste a sample text or upload the file).
- Confirm: async status polling, all result tabs populated, all download buttons work.
- Confirm theming: match OS theme on load, instant light↔dark toggle from the Menubar, preference survives refresh, "system" mode follows a live OS theme change.
- Confirm SPA fallback: `npm run build`, then restart backend and visit `/files` directly (refresh works).

---

## 8. Docs (optional)

Complete — see `scratch/frontend-tasks-done.md`.
