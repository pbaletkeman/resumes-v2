# Frontend Implementation — Completed Tasks

Archive of tasks from `frontend-tasks.md` as they are completed. See [frontend-tasks.md](frontend-tasks.md) for the full breakdown and [frontend-plan.md](frontend-plan.md) for the overall plan.

## Overview

The React + PrimeReact UI will live in `ui/`. During development it talks to the backend through a Vite proxy; in production FastAPI serves the built SPA from `ui/dist`. Task 1.1 added the backend helper that serves the SPA; task 1.2 wires it in, guarded by build presence; task 1.3 (backed tests) is still pending.

## Completed

### 1.1 Add a static-mount helper in `app/main.py` — DONE

Added `mount_spa(app_instance, ui_dist)` in `app/main.py`.

- `app/main.py:41` — `mount_spa()`:
  - Mounts `/assets` via `StaticFiles` when `ui_dist/assets` exists (registration order ensures the mount wins over the catch-all).
  - Registers a catch-all `GET /{full_path:path}` route (`add_api_route`, `include_in_schema=False`) that:
    - returns 404 for `/api`/`/health` paths (preserving API precedence),
    - returns 404 for dotfile/dotted segment paths,
    - serves `ui_dist/index.html` for everything else (SPA fallback for deep links like `/files`).
  - Pure function of app + paths; no imports of frontend code.
- New imports: `HTMLResponse` from `fastapi.responses`, `StaticFiles` from `fastapi.staticfiles` (`app/main.py:15-16`).

#### Verification

- `uv run ruff check .` — All checks passed.
- `uv run pyright` (strict, no path arg) — 0 errors, 0 warnings, 0 informations.
- `uv run pytest` — 477 passed.
- Manual smoke (temporary script, removed after): `mount_spa` against a temp SPA confirmed `/` and `/files` return `index.html`, `/assets/*.js` serves the file, `/api/models` and `/health` stay JSON, `/api/nope` and `/file.txt` are 404.

### 1.2 Wire the mount in `app/main.py`, guarded by build presence — DONE

- Added `UI_DIST = Path("ui") / "dist"` constant (`app/main.py:38`).
- At the end of module scope, after all API routes/docs are registered, added:
  - `if (UI_DIST / "index.html").is_file(): mount_spa(app, UI_DIST)` (`app/main.py:322-324`).
  - Route registration order keeps the explicit `/api/*`, `/health`, and `/docs` routes ahead of the catch-all, so they always win.
- Without a build, the guard is False and app behavior is unchanged (API-only).
- Verified both branches:
  - **No build present** (`ui/dist` absent): `ruff` clean, `pyright` 0 errors, `pytest` 477 passed.
  - **Build present** (temp `ui/dist/index.html` + `ui/dist/assets/app.js`, removed after): `/` and `/files` served SPA html, `/api/models` + `/health` JSON, `/api/nope` and `/file.txt` 404, `/assets/app.js` 200, `/docs` 200.

#### Verification

- `uv run ruff check .` — All checks passed.
- `uv run pyright` (strict, no path arg) — 0 errors, 0 warnings, 0 informations.
- `uv run pytest` — 477 passed.