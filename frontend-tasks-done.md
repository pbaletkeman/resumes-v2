# Frontend Implementation — Completed Tasks

Archive of tasks from `frontend-tasks.md` as they are completed. See [frontend-tasks.md](frontend-tasks.md) for the full breakdown and [frontend-plan.md](frontend-plan.md) for the overall plan.

## Overview

The React + PrimeReact UI will live in `ui/`. During development it talks to the backend through a Vite proxy; in production FastAPI serves the built SPA from `ui/dist`. Tasks 1.1 (SPA-serving helper), 1.2 (guarded wiring), 1.3 (backend SPA fallback tests), 2.1 (Vite scaffold), 2.2 (dependencies), 2.3 (gitignore + boilerplate prune), 2.4 (PrimeReact light/dark themes wired), and 2.5 (theme state: system default + manual override) are complete.

> **Version note (PrimeReact v10, not v11):** task 2.2 originally installed `primereact@11.1.0`, which turned out to be a new "unstyled primitives" line with no `resources/themes/*.css`, no classic component suite (`TabView`/`Menubar`/`FileUpload`/`SegmentedButton`/`ConfirmDialog`), and a different design-token theming runtime (`@primeuix/themes`). Tasks 2.4 and 5.x are written for the classic v10 API, so I pinned `ui/` to **`primereact@10.9.8`** (the officially tagged `v10-stable`, React 19 compatible) and removed the v11-only `@primeuix/themes` dependency. All theme/component work below uses the classic API as the plan specifies.

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

### 1.3 Add a backend test for the SPA fallback — DONE

New file `tests/test_web_spa.py` (8 tests).

- **`TestMountSpa`** (6 tests) — exercises `mount_spa()` directly against a purpose-built app whose fake `dist/` lives under `tmp_path`:
  - deep links (`/`, `/files`, `/models`, `/some/deep/link`) return `index.html`;
  - `/api/models` and `/health` are not shadowed (still JSON 200);
  - `/assets/app.js` is served from the `StaticFiles` mount;
  - dotfile/dotted paths (`/file.txt`, `/resume.pdf`, `/.hidden`) are 404;
  - unknown API paths (`/api/nope`) are 404.
- **`TestModuleGuard`** (2 tests) — exercises the real import-time wiring in `app/main.py` by staging/removing `ui/dist/index.html` and reloading the module with `importlib.reload`, always restoring the no-build state afterward:
  - build present → `/files` serves SPA html while API/static routes stay intact;
  - build absent → unknown non-API GET is a plain 404, API still works.

#### Verification

- `uv run ruff check .` — All checks passed.
- `uv run pyright` (strict, no path arg) — 0 errors, 0 warnings, 0 informations.
- `uv run pytest tests/test_web_spa.py -v` — 8 passed.
- `uv run pytest` — **485 passed** (477 + 8 new).
- Confirmed no `ui/dist` artifacts are leaked by the module-reload tests.

### 2.1 Create the Vite project — DONE

Scaffolded `ui/` with `npm create vite@latest ui -- --template react-ts` (create-vite 9.1.2, Vite 8 / React 19 / TypeScript ~6.0).

- `ui/` contains: `index.html`, `src/main.tsx`, `src/App.tsx`, `tsconfig.json` + `tsconfig.app.json` + `tsconfig.node.json`, `vite.config.ts`, `package.json`, `public/`, plus scaffold extras (`.oxlintrc.json`, `.gitignore`, `README.md`).
- `npm install` — 27 packages, 0 vulnerabilities.

#### Verification

- `npm install` — succeeded.
- `npm run dev` — started dev server; `GET http://localhost:5173/` returned 200 with the Vite root `#root` div + `<title>`.
- `npm run build` — succeeded, emits `ui/dist/` (assets under `dist/assets/`).
- Backend integration sanity: with the built `ui/dist` present, the task 1.2 guard now fires and serves the SPA; `uv run pytest tests/test_web_spa.py` still 8 passed (module-guard tests stage/remove their own dist and restore the no-build state), `uv run ruff check .` clean, `uv run pyright` 0 errors.
- `git status` — `ui/` shows as an untracked single dir (gitignore for `node_modules`/`dist` lands in task 2.3).

### 2.2 Install dependencies — DONE

Installed both dep groups in `ui/`.

- Runtime: `npm i primereact primeicons react-router-dom @tanstack/react-query` → `primereact@11.1.0`, `primeicons@8.0.0`, `react-router-dom@7.18.2`, `@tanstack/react-query@5.101.4`.
- Dev/test: `npm i -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom vite-tsconfig-paths` → `vitest@4.1.10`, `@testing-library/react@16.3.2`, `@testing-library/user-event@14.6.3`, `@testing-library/jest-dom@7.0.0`, `jsdom@30.0.1`, `vite-tsconfig-paths@6.1.1`.
- Only transient note: `npm warn deprecated tsconfck@3.1.6` (unmaintained) — a transitive dep pulled in by a `vite-tsconfig-paths` peer; harmless (TypeScript 6 / Vite 8 still resolve paths via it).

#### Verification

- `npm ls` — all packages resolved, no missing deps (complete tree: react/router/query/primereact/primeicons + vitest + jsdom + testing-library set + vite-tsconfig-paths + existing template deps).
- Both installs reported 0 vulnerabilities.

### 2.3 Gitignore + prune scaffold boilerplate — DONE

- Root `.gitignore` gained a `### Frontend (ui/) ###` block: `ui/node_modules/` and `ui/dist/`.
- Pruned the Vite demo: deleted `ui/src/App.css`, `ui/src/assets/` (react.svg, vite.svg, hero.png), `ui/public/icons.svg`.
- Replaced the demo `App.tsx` with a minimal clean component (`<main><h1>Resume Optimizer</h1></main>`), and trimmed `index.css` to a minimal reset (`:root` font + light/dark `color-scheme`, `#root` flex column, `body { margin: 0 }`).

#### Verification

- `git status` shows only intended additions; `git add -A --dry-run ui` lists exactly: `ui/.gitignore`, `.oxlintrc.json`, `index.html`, `package.json`, `package-lock.json`, `public/favicon.svg`, `README.md`, `src/App.tsx`, `src/index.css`, `src/main.tsx`, `tsconfig*.json`, `vite.config.ts` — no `node_modules/`, no `dist/`.
- `npm run build` — passes (index.html 0.45 kB, `index-*.js` 190.41 kB, `index-*.css` 0.39 kB); `dist/` remains ignored.

### 2.4 Wire PrimeReact themes (light + dark) — DONE

Note: this task assumed PrimeReact v10-classic (`resources/themes/*`). See the v10 note in the Overview. Also note that 2.4 + 2.5 are interleaved — the theme-toggling UI (attribute flipping) is owned by 2.5; 2.4 wires both theme stylesheets so attribute flipping works; 2.4 is done now.

- `ui/src/main.tsx` (rewritten, `main.tsx:1-19`):
  - Imports **both** themes — `primereact/resources/themes/lara-light-blue/theme.css` and `primereact/resources/themes/lara-dark-blue/theme.css`.
  - Also `primereact/resources/primereact.min.css` and `primeicons/primeicons.css`.
  - Removed the v11-only imports (`@primereact/core`'s `PrimeReactProvider`, `@primeuix/themes/lara`); app renders `<App />` directly under `StrictMode`.
- `ui/vite.config.ts` (new `scopeDarkThemeCss` plugin, `vite.config.ts:1-33`):
  - Applies a postcss transform to the **dark** theme file (`lara-dark-blue/theme.css`) that scopes **every** selector under `html[data-theme='dark']` — `:root` blocks are rewritten to the attribute selector itself and component rules are prefixed with `${scope} ${sel}` — so both stylesheets coexist in one bundle and flip by attribute without a reload.
  - Rule walk skips `@keyframes` bodies (they'd otherwise be prefixed into invalid selectors). Light theme is left unscoped — it wins the cascade when the attribute is absent.
  - `enforce: 'pre'` so Vite's normal CSS processing (url rebasing for the Inter/primeicons fonts, minification) applies afterward.
- `ui/src/App.tsx`: kept the minimal shell with a `Button` that toggles `document.documentElement.dataset.theme` between `light`/`dark` (used to verify the flip; hard split "severity" props match the v10 Button type).
- `ui/src/index.css`: unchanged minimal reset (independent of theme).

#### Verification

- `npm run build` — passes (dist CSS ~416 kB: ~1900 dark-scoped rules + unscoped light).
- Build inspection of `dist/assets/index-*.css`: `html[data-theme='dark'] { ... }` blocks (2, carrying `color-scheme: dark`), `html[data-theme='dark'] .p-*` selectors (1904), plus unscoped `.p-*` light rules (112) with the light palette (`--color: #3b82f6` intact on light).
- Dev server smoke: GET `http://localhost:5199/` serves `index.html`; GET of the dark theme CSS through Vite returns content scoped under `html[data-theme='dark']`.
- `npm run lint` (oxlint) — clean; `npx tsc --noEmit` — clean; `npm run build` (tsc -b + vite) — clean.
- Cleanup: removed temp v11 investigation files (`ui/src/theme.smoke.test.tsx`, `ui/src/theme.dump.test.tsx`, `ui/probe-theme.mjs`) and leftover empty `@primereact`/`@primeuix` dirs.
- PrimeReact downgrade: `npm i primereact@10.9.8`, `npm uninstall @primeuix/themes`; `npm ls` clean, no missing deps, 0 vulns.

### 2.5 Theme state — default to system, allow manual override — DONE

- `ui/src/theme/useTheme.ts` (new) — `useTheme()` hook returning `{ mode, resolved, setTheme, clearOverride }`:
  - `mode: ThemeMode` = `'light' | 'dark' | 'system'`. Initial value = `localStorage` override if present (`STORE_KEY='theme'`), else `'system'`.
  - `resolved`: resolves `'system'` → `window.matchMedia('(prefers-color-scheme: dark)')` (implemented via exported `getSystemTheme()`/`resolveTheme()` pure helpers so tests can target them).
  - Applies the resolved theme by setting `document.documentElement.dataset.theme` on init and on every `mode` change; subscribes a `change` listener to the `prefers-color-scheme` media query that re-applies (and flips live) only while `mode === 'system'`.
  - `setTheme(next)` persists the manual choice to `localStorage`; `clearOverride()` removes it and returns to `'system'` (the "system" reset option).
- `ui/src/theme/ThemeToggle.tsx` (new) — a three-way `SelectButton` (System | Light | Dark) driven by `useTheme`; the toggle is wired into `ui/src/App.tsx` alongside the demo Buttons.
- `ui/index.html` (new inline script in `<head>`) — pre-paint `data-theme` setter: reads the `localStorage` override (`'theme'` key), else falls back to `prefers-color-scheme: dark`; sets `document.documentElement.dataset.theme` before first paint to avoid a flash of the wrong theme.

#### Verification

- `npm run build` — succeeds; TypeScript clean (`tsc -b`), dist JS 296 kB.
- `npm run lint` (oxlint) — clean; `npx tsc --noEmit` — 0 errors.
- Dev-server smoke on :5199 — served `index.html` contains the inline pre-paint script (`localStorage.getItem('theme')`, `prefers-color-scheme: dark`, `dataset.theme` assignment); Vite transforms dev theme CSS as in 2.4.
- `git add -A --dry-run ui` — lists only intended files (`src/theme/useTheme.ts`, `src/theme/ThemeToggle.tsx` added; no `node_modules`, no `dist`).