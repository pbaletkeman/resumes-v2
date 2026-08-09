# Frontend Implementation — Completed Tasks

Archive of tasks from `frontend-tasks.md` as they are completed. See [frontend-tasks.md](frontend-tasks.md) for the full breakdown and [frontend-plan.md](frontend-plan.md) for the overall plan.

## Overview

The React + PrimeReact UI will live in `ui/`. During development it talks to the backend through a Vite proxy; in production FastAPI serves the built SPA from `ui/dist`. Tasks 1.1 (SPA-serving helper), 1.2 (guarded wiring), 1.3 (backend SPA fallback tests), 2.1 (Vite scaffold), 2.2 (dependencies), 2.3 (gitignore + boilerplate prune), 2.4 (PrimeReact light/dark themes wired), and 2.5 (theme state: system default + manual override) are complete. The results `TabView` (5.4) is complete with all 7 tabs (5.4.1–5.4.7) — see the records below.

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

### 3.1 Add the `/api` dev proxy — DONE

`ui/vite.config.ts` gained a `server.proxy` block (Vite 8 config, `vite.config.ts:39-46`) proxying both `/api` and `/health` to the local backend:

```ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/health': 'http://localhost:8000',
  },
},
```

- Browser fetches from the Vite dev server (:5173) hit the backend (:8000) directly, so no CORS errors occur during development. Keys are unprefixed (no trailing `/`) per Vite proxy convention.
- The `scopeDarkThemeCss` plugin (task 2.4) is untouched; the proxy is additive.

#### Verification

- `npx tsc --noEmit` — 0 errors (in `ui/`).
- `npm run lint` (oxlint) — clean.
- End-to-end proxy smoke: backend via `uv run uvicorn app.main:app --port 8000`, dev server via `npm run dev -- --port 5173 --strictPort`; `GET http://localhost:5173/api/models` returned 200 with the 7-agent model summary JSON, and `GET http://localhost:5173/health` returned 200 `{"status":"ok"}`.

### 4.1 `src/api/types.ts` — backend schema types — DONE

New file `ui/src/api/types.ts`.

- Mirrors `app/schemas.py` exactly: `ModelSummary`, `TaskStatus` (with `TaskStatusName` status union `'pending'|'running'|'completed'|'failed'` and optional `result?`/`error?`/`created_at?`/`completed_at?`), `FileMeta`, `PagedFile`, `DeleteFilesResponse`.
- `PipelineRunResponse` with all 7 result keys + `output_files: Record<string, string>`. Each result key is typed as `StageResult<T> = T | Record<string, unknown> | null` — a typed agent-output shape unioned with a loose `Record<string, unknown>` so unknown/variant backend payloads (the API uses `Any`) don't break the type.
- Agent output shapes copied from the field lists in `client/models.py`: `ExperienceEntry`, `JDParsingOutput` (includes `company_signals: Record<string, string>`), `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`.

#### Verification

- `npx tsc --noEmit` — 0 errors (in `ui/`).

### 4.2 `src/api/client.ts` — fetch wrappers — DONE

New file `ui/src/api/client.ts`.

- `API_BASE = '/api'` with a private `apiFetch<T>(path, init)` helper that prepends the base, parses JSON, and surfaces backend errors: on non-2xx it throws an `Error` carrying the FastAPI `detail` (string, or FastAPI's list-of-`{msg}` validation errors joined with `'; '`), falling back to a status message. `parseErrorDetail` is a separate helper so the 6.x unit tests can target it.
- Wrappers, matching `app/main.py` routes exactly:
  - `fetchModels()` → `GET /api/models` → `ModelSummary[]`.
  - `runPipelineAsync(formData)` → `POST /api/pipeline/async` with the caller-supplied `FormData` (field names follow `_read_text_input`: `job_description`, `resume`, `job_file`, `resume_file`, `candidate_name`, `company_name`) → `TaskCreated`.
  - `getTask(taskId)` → `GET /api/tasks/{id}` (id `encodeURIComponent`-encoded) → `TaskStatus`.
  - `listFiles(kind: 'generated'|'uploaded', params)` → `GET /api/files/{kind}` building a query string from `file_type`, `q`, `page`, `page_size`, `sort` (undefined values omitted) → `PagedFile`.
  - `deleteFiles(files)` → `DELETE /api/files` with JSON body `{ files }` → `DeleteFilesResponse`.
- `FileListParams` type exported. Added `TaskCreated { task_id }` to `types.ts` (mirrors `app/schemas.py:42-45`, needed by `runPipelineAsync`).
- Also added `buildQuery` helper (query-string builder used by `listFiles`).

#### Verification

- `npx tsc --noEmit` — 0 errors (in `ui/`).
- Live spot-checks against the running backend (`uv run uvicorn app.main:app --port 8000`), matching each wrapper's URL/method/body:
  - `GET /api/models` → 200, 7 agents.
  - `POST /api/pipeline/async` (multipart with `job_description` + `resume` text) → 200 `{ task_id }`.
  - `GET /api/tasks/{id}` → 200 `{ status: 'running', created_at, result: null }`; a bogus id surfaces 404.
  - `GET /api/files/generated?page=1&page_size=5&sort=newest` → 200 `PagedFile` (23 total in `output/`).
  - `DELETE /api/files` with `{ files: ["nonexistent.pdf"] }` → 200 `{ deleted: [], missing: ["nonexistent.pdf"] }`.

### 4.3 `src/api/download.ts` — download URL helpers — DONE

New file `ui/src/api/download.ts`.

- `outputDownloadUrl(name)` → `/api/outputs/{encodeURIComponent(name)}` — encodes the basename so spaces/`&`/etc. survive the URL.
- `fileDownloadUrl(path)` → same, normalizing backslashes (`\` → `/`) then extracting the basename via `split('/').pop()` from dir-qualified `path` keys like `uploads/foo.pdf` / `output/foo.pdf`.

#### Verification

- `npx tsc --noEmit` — 0 errors (in `ui/`).
- URL logic spot-checked (node): `my resume v2.pdf` → `/api/outputs/my%20resume%20v2.pdf`; `uploads/foo.pdf` → `/api/outputs/foo.pdf`; `output/a b&c.txt` → `/api/outputs/a%20b%26c.txt`.
- Live download: listed `output/` via `/api/files/generated`, then `GET /api/outputs/{name}` returned 200 with 2523 bytes (`text/markdown`).

### 4.4 `src/api/hooks.ts` — React Query hooks — DONE

New file `ui/src/api/hooks.ts` (server-rendered for TanStack Query v5 — `^5.101.4` installed).

- `useModels()` — `useQuery(['models'], fetchModels)`.
- `useInvokePipeline()` — `useMutation(runPipelineAsync)`; `.data` carries the `TaskCreated.task_id`.
- `useTask(taskId)` — `useQuery(['task', taskId], …)` disabled when `taskId` is null; `refetchInterval={(query) => query.state.data?.status is pending/running ? 2000 : false}` so polling auto-stops once settled.
- `usePollTask(taskId, onDone)` — wraps `useTask`; a `useEffect` fires `queryClient.invalidateQueries(['files'])` and calls `onDone(status)` exactly when the task enters `completed`/`failed`.
- `useFiles(kind, params)` — `useQuery(['files', kind, params], …)` with `placeholderData: keepPreviousData` for paging continuity.
- `useDeleteFiles()` — `useMutation(deleteFiles)` whose `onSuccess` invalidates `['files', …]` queries, so listings refetch after a delete.
- Re-exports the `ModelSummary`/`PagedFile` types for consumer convenience.

#### Verification

- `npx tsc --noEmit` — 0 errors (in `ui/`).
- `npm run lint` (oxlint) — clean.
- Query-client wiring (manual `started → polling → settled` run) is exercised end-to-end by the Run page tasks (5.2/5.3) and task 6.3 unit tests, once those land. Hooks themselves typecheck and are validated by the package's v5 API (`keepPreviousData` confirmed present at runtime).

### 5.1 App shell — `src/App.tsx` — DONE

Restructured the entrypoint into a routed shell.

- `ui/src/App.tsx` (rewritten) — `QueryClient`/`QueryClientProvider` (covers the 4.x hooks) → `BrowserRouter` → `ToastProvider` → `Routes` with a layout route (`<Shell />` holding the `Menubar` + `<Outlet/>`) and three children: `index` → RunPage, `/files` → FilesPage, `/models` → ModelsPage.
  - `Menubar` `start` slot = brand (`pi pi-briefcase` + "Resume Optimizer"); `model` items built from `NAV_ITEMS` (Run `/`, Files `/files`, Models `/models`) each using an item **template** that renders a `NavLink` (`end` on `/`) with base class `p-menuitem-link` plus ` p-menuitem-link-active` when `isActive` — Menubar highlighting comes from React Router, no command/state needed.
  - `Menubar` `end` slot = the existing three-way `ThemeToggle` (System | Light | Dark from 2.5) — satisfies the theme switch; flips via `useTheme` by setting `data-theme` on `<html>` with no reload.
- `ui/src/pages/RunPage.tsx`, `FilesPage.tsx`, `ModelsPage.tsx` (new) — minimal placeholder pages (headers only); filled in by 5.2–5.7.
- `ui/src/toast/ToastContext.ts` + `ui/src/toast/ToastProvider.tsx` (new) — `ToastContext.Provider` owns one `Toast` ref; `useToast()` returns `{ show(message), clear() }` (throws outside the provider). Pages call `useToast().show({ severity, summary, detail })`.
- `ui/src/index.css` — `.app-shell`/`.app-content` layout + active-link highlight rule (`var(--primary-300)` background, rounded).

#### Verification

- `npx tsc --noEmit` — 0 lines (caught & fixed a **4.2-era bug**: `FileListParams` declared as an `interface` isn't assignable to `Record<string, string|number|undefined>` under `tsc -b`; converted to a `type` alias → build green).
- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes; dist 411 kB JS / 416 kB CSS (theme scoping intact).
- Dev-server smoke on :5173 — `/`, `/files`, `/models` all return 200 serving the SPA `index.html` (mount div + pre-paint theme script present); backend `/health` on :8000 returns 200.
- Route navigation, active-link highlight, and the live theme flip are browser-interactive; covered manually in 7.3 and by the 6.x unit tests once Vitest lands.

### 5.2 Run page — form (paste or upload) — DONE

Built the Run page form + FormData construction.

- `ui/src/pages/runForm.ts` (new) — pure, testable helpers:
  - `RunInputs` type; `validateRunInputs()` returns a warning message when either JD or resume lacks both text and file.
  - `buildRunFormData()` — appends `job_description`/`resume` when the pasted text is non-empty, else `job_file`/`resume_file` (text wins, matching backend `_read_text_input`); appends `candidate_name`/`company_name` only when non-empty.
- `ui/src/pages/RunPage.tsx` (rewritten) — two-column grid (`run-grid`):
  - **Job Description** / **Resume** columns each get an `InputTextarea` for paste + a `FileChosen` control: `FileUpload` (`mode="basic"`, single file, `accept=".txt,.docx,.pdf"`, `auto={false}` + `customUpload` so nothing posts until submit) shown when no file is chosen; once chosen, replaced by the file name + a text "Remove" `Button` (clears via `FileUpload.clear()` ref + state).
  - Optional `candidateName`/`companyName` `InputText` fields rendered PrimeReact `p-float-label` style.
  - "Run Pipeline" `Button` (pi pi-play) disabled while `useInvokePipeline().isPending` (run active).
  - `handleSubmit()`: `validateRunInputs` short-circuit → Toast warn on missing input; otherwise `invokePipeline.mutate(formData, { onError })` → Toast error reusing the API's `detail` (surfaced by `client.ts`'s `parseErrorDetail`).
- CSS: `.run-page`, `.run-grid` (1fr/1fr, responsive-safe column stack via grid gap), `.run-column`, `.run-file`, `.run-file-name`, `.run-options`.

#### Verification

- `npx tsc --noEmit` — 0 errors; `npm run lint` (oxlint) — clean; `npm run build` (`tsc -b && vite build`) — passes (472 kB JS).
- FormData semantics node-checked: text-only → `['job_description','resume']`; file-only → `['job_file','resume_file','candidate_name','company_name']`; text+wins omits files (`['job_description','resume']`).
- Dev-server smoke: `GET /src/pages/RunPage.tsx` through Vite transforms cleanly (200).
- Live backend check: POST `/api/pipeline/async` with `job_description` + `resume` form fields → 200 `{ task_id }`, confirming the exact field names/contract (`_read_text_input`, `app/main.py:130`).
- Interactive verify (both input paths via network tab + disabled-while-running) is browser-manual; the async status UI on top is task 5.3.

### 5.3 Run page — async status — DONE

Added live async status tracking to `ui/src/pages/RunPage.tsx`.

- On submit success, stores the `task_id` from `useInvokePipeline()`'s mutation data (`onSuccess: (data) => setTaskId(data.task_id)`); the button stays disabled through polling.
- Polls via `usePollTask(taskId, handleTaskDone)` (polling at 2 s while `pending`/`running`, auto-stops on `completed`/`failed`, invalidates `['files']`).
- `handleTaskDone` (stable via `useCallback([show])`) surfaces a `failed` task's `error` string through a Toast (`severity: 'error'`), falling back to "Unknown pipeline error".
- Status panel (`run-status` block, visible when `taskId !== null`):
  - Task id rendered as `code`.
  - While `undefined`/`pending`/`running`: `ProgressSpinner` (`2rem`, `strokeWidth=4`) + a status `Tag` (`info`).
  - Settled: `Tag` with `STATUS_SEVERITY` map (`completed` → `success`, `failed` → `danger`).
  - On `failed`: inline `run-status-error` text with `taskError`.
- Button label reflects state (`Starting...`/`Running...` with a spinning icon while active), plus a secondary "Reset" button that clears the task id (`disabled={active}`).
- CSS: `.run-actions`, `.run-status`, `.run-status-label`, `.run-status-active`, `.run-status-error`.

#### Verification

- `npx tsc --noEmit` — 0 errors; `npm run lint` (oxlint) — clean; `npm run build` — passes (488 kB JS).
- **Live success path** (Ollama up, port 8000): POST `/api/pipeline/async` → polled `/api/tasks/{id}` → `running` × 4 → `completed`; result carries all 7 keys (`parsed_job_description` … `cover_letter`) + `output_files`. Status transition running → completed confirmed.
- **Live failure path** (`OLLAMA_HOST` → dead port 1, backend on 8001): POST → first poll already `status=failed`, `error` = "Failed to connect to Ollama. Please check that Ollama is downloaded, running and accessible." — proves the Toast path surfaces the message end-to-end.

### 5.4.1 Results container + Parsed JD tab — DONE

Built the shared results tab container + defensive extraction, with the Parsed JD tab fully implemented.

- `ui/src/pages/results/coerce.ts` (new) — pure defensive-extraction helpers over `unknown` values pulled from the loose `TaskStatus.result`:
  - `asRecord()` (object-and-not-array → `Record<string, unknown>`, else `null`), `asString()`, `asStringList()`, `asStringMap()` (record → `Record<string, string>`, dropping non-string values),
  - `pickString()`/`pickList()`/`pickMap()` conveniences for reading a key off a `Record<string, unknown> | null`.
- `ui/src/pages/results/parts.tsx` (new) — small shared render atoms used by later tabs:
  - `NoData` (italic "no data" placeholder), `TagSection` (`Tag`s for a `string[]`), `BulletSection` (`<ul>` list), `KeyValueTable` (key→value `<table>` for maps like `company_signals`). Sections render `null` when their list/map is empty; the whole-tab fallback is `NoData`.
- `ui/src/pages/results/ParsedJDTab.tsx` (new) — takes `value: unknown`, coerces to a record via `pick*` helpers, and renders: role/company/seniority (Role section), required/preferred skills + keywords + industry terms as `Tag`s, responsibilities as bullets, company_signals as a key→value table. Non-object value → `NoData`.
- `ui/src/pages/results/ResultsTabView.tsx` (new) — `ResultsTabView({ result })` renders a `TabView` with all 7 result tabs in order (keys `parsed_job_description` … `cover_letter`, headers Parsed JD / Parsed Resume / Gap Analysis / Rewritten Resume / ATS / Polished / Cover Letter). `renderTabBody()` delegates by key; non-JD tabs currently fall through to `NoData` (filled by 5.4.2–5.4.7). Null/undefined result → renders nothing.
- `ui/src/pages/RunPage.tsx` — `{status === 'completed' && <ResultsTabView result={taskQuery.data?.result ?? null} />}` appended after the status panel.
- `ui/src/index.css` — `.run-results`, `.results-panel`, `.results-section`, `.results-tags`, `.results-bullets`, `.results-table`, `.results-no-data` styles.

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (507 kB JS / 418 kB CSS).
- JD tab render correctness is browser-manual (needs a completed live run); container + coercion are fully typed and unit-testable for the 6.x suite.

### 5.4.2 Parsed Resume tab — DONE

Built the Parsed Resume result tab.

- `ui/src/pages/results/ParsedResumeTab.tsx` (new) — takes `value: unknown` (whole-resume non-object → `NoData`) and renders:
  - **Summary** and **Contact** as always-visible `Section`s (label + content or `NoData` placeholder), contact line = non-empty `name`/`phone`/`email`/`linkedin`/`github` joined with ` · `.
  - **Skills** via `TagSection` (`emptyText="No data"`).
  - **Experience** via per-entry `ExperienceEntryView`: head row (title · company · dates, dates right-aligned) + Responsibilities/Achievements/Metrics `BulletSection`s; entries come from the new `pickObjectList` coercion (array-of-objects; string items dropped). Empty list → `NoData`.
  - **Projects** / **Certifications** / **Education** via `BulletSection` (`emptyText="No data"`).
- `ui/src/pages/results/coerce.ts` — added `asObjectList()` + `pickObjectList()` for experience entries (object arrays within `Record<string, unknown>`).
- `ui/src/pages/results/parts.tsx` — `TagSection`/`BulletSection`/`KeyValueTable` gained an optional `emptyText` prop: when set, empty sections render `<h3>` + `NoData` instead of returning `null` (JD tab behavior unchanged).
- `ui/src/pages/results/ResultsTabView.tsx` — `parsed_resume` case now renders `<ParsedResumeTab />`.
- `ui/src/index.css` — `.results-experiences`, `.results-experience*` (bordered card, head row, right-aligned dates).

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (510 kB JS / 418 kB CSS).
- Tab render correctness is browser-manual (needs a completed live run).

### 5.4.3 Gap Analysis tab — DONE

Built the Gap Analysis result tab.

- `ui/src/pages/results/GapAnalysisTab.tsx` (new) — takes `value: unknown` (non-object → `NoData`) and renders the tailoring strategy: Missing skills / Weak skills / Strong matches / Recommended emphasis / Keyword strategy / Bullet plan via `TagSection` (`emptyText="No data"`), plus `tone_guidance` as a `results-text` paragraph when present.
- `ui/src/pages/results/coerce.ts` — added `pickText()`: reads a text field from a `Record<string, unknown> | null` that may arrive as a plain string, an array (joined `, `), or an object (`k: v` pairs joined `, `, empty values skipped) — mirrors the backend `_coerce_tone_guidance` in `client/models.py:206`.
- `ui/src/pages/results/ResultsTabView.tsx` — `tailoring_strategy` case now renders `<GapAnalysisTab />`.
- `ui/src/index.css` — `.results-text` (pre-wrap paragraph for guidance text).

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (511 kB JS / 418 kB CSS).
- Tab render correctness is browser-manual (needs a completed live run).

### 5.4.4 Rewritten Resume tab — DONE

Built the Rewritten Resume result tab.

- `ui/src/pages/results/RewrittenResumeTab.tsx` (new) — takes `value: unknown` (non-object → `NoData`) and renders the rewritten resume: summary `Section`, skills `TagSection`, experience via shared `ExperienceEntryView` cards, plus projects/certifications/education `BulletSection`s (`emptyText="No data"`).
- `ui/src/pages/results/parts.tsx` — moved `Section` (label + content-or-`NoData` wrapper) and `ExperienceEntryView` (title/company/dates head + Responsibilities/Achievements/Metrics subsection cards) out of `ParsedResumeTab.tsx` into shared parts so 5.4.2 and 5.4.4 reuse them. `parts.tsx` now imports `pickList`/`pickString` from `coerce.ts`.
- `ui/src/pages/results/ParsedResumeTab.tsx` — refactored to import the shared `Section`/`ExperienceEntryView`; no behavior change.
- `ui/src/pages/results/ResultsTabView.tsx` — `rewritten_resume` case now renders `<RewrittenResumeTab />`.

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (512 kB JS / 418 kB CSS).
- Tab render correctness is browser-manual (needs a completed live run).

### 5.4.5 ATS tab — DONE

Built the ATS Compliance result tab.

- `ui/src/pages/results/ATSTab.tsx` (new) — takes `value: unknown` (non-object → `NoData`) and renders:
  - **Score** `Section` with a `Tag` colored by band via `scoreSeverity()` (`<50` danger/red, `<80` warning/orange, else success/green). Missing score (null) → no chip (section still shows `NoData` label).
  - **Missing keywords** via `TagSection`; **Formatting issues** / **Clarity issues** / **Recommended fixes** / **Auto-fixes applied** via `BulletSection` (all `emptyText="No data"`).
  - **Final resume** as a read-only `<pre>` block (`results-pre`), fed by `pickText` (tolerates string/array/object payloads from backend `_coerce_final_resume`).
- `ui/src/pages/results/coerce.ts` — added `pickNumber()` (parses number-or-numeric-string values from a record, `NaN`/empty → `null`).
- `ui/src/pages/results/ResultsTabView.tsx` — `ats_optimized_resume` case now renders `<ATSTab />`.
- `ui/src/index.css` — `.results-pre` (border, `surface-100` background, `pre-wrap` + `word-break`).

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (513 kB JS / 418 kB CSS).
- Tab render correctness is browser-manual (needs a completed live run).

### 5.4.6 Polished tab — DONE

Built the Polished result tab with string-vs-object tolerance.

- `ui/src/pages/results/PolishedTab.tsx` (new) — takes `value: unknown` and coerces `polished_resume` via `textFromValue(value, ['polished_resume', 'text'])`, so the value may arrive as a plain string OR an object whose `polished_resume`/`text` field holds the text. Non-text value → `NoData`; otherwise renders a `Section` with the text in a `<pre>` (`results-pre`).
- `ui/src/pages/results/coerce.ts` — added `textFromValue(value, keys)`: whole-value coercion for the string-vs-object keys — plain string → itself (trimmed); object → first non-empty via `pickText` across the given `keys`; else `null`.
- `ui/src/pages/results/ResultsTabView.tsx` — `polished_resume` case now renders `<PolishedTab />`.

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes.
- Tab render correctness is browser-manual (needs a completed live run).

### 5.4.7 Cover Letter tab — DONE

Built the Cover Letter result tab with string-vs-object tolerance; completes the 5.4 tab series.

- `ui/src/pages/results/CoverLetterTab.tsx` (new) — counterpoint to `PolishedTab`: coerces `cover_letter` via `textFromValue(value, ['cover_letter', 'text'])` (plain string OR object text field). Non-text value → `NoData`; otherwise a `Section` with the text in a `<pre>`.
- `ui/src/pages/results/ResultsTabView.tsx` — `cover_letter` case now renders `<CoverLetterTab />`; all 7 result keys now have real tab components, so the `default: <NoData />` fallback in `renderTabBody()` was removed (and the now-unused `NoData` import dropped).

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (514 kB JS / 418 kB CSS).
- Tab render correctness is browser-manual (needs a completed live run); the series' whole-task verify (every tab populated, empty agents show "no data") belongs to 7.3.

### 5.4 Run page — results `TabView` — DONE

Whole task complete — all 7 tab sub-tasks (5.4.1–5.4.7) are archived individually above.

- Results render in a 7-tab `TabView` after a run reaches `completed`, fed by the settled `TaskStatus.result`.
- Every result key has a dedicated tab component: Parsed JD (`ParsedJDTab`), Parsed Resume (`ParsedResumeTab`), Gap Analysis (`GapAnalysisTab`), Rewritten Resume (`RewrittenResumeTab`), ATS (`ATSTab`), Polished (`PolishedTab`), Cover Letter (`CoverLetterTab`).
- Shared plumbing under `ui/src/pages/results/`: `ResultsTabView.tsx` (container + key→tab dispatch), `coerce.ts` (defensive extractors incl. string-vs-object `pickText`/`textFromValue`), `parts.tsx` (shared `NoData`/`Section`/`TagSection`/`BulletSection`/`KeyValueTable`/`ExperienceEntryView`), CSS in `ui/src/index.css`.

#### Verification

- Whole-task verify (manual pipeline run populates every tab; empty agents show "no data" placeholders) is browser-manual and belongs to task 7.3; per-tab `tsc`/lint/build cleanliness was verified in each sub-task record.

### 5.5 Run page — downloads row — DONE

Built the downloads row under the Run page results.

- `ui/src/pages/results/DownloadsRow.tsx` (new) — `DownloadsRow({ outputFiles })` takes the `output_files` map and renders one download link per known format key:
  - `DOWNLOAD_LABELS` maps the backend's 6 keys (`resume_plaintext`/`resume_markdown`/`resume_docx`/`resume_pdf`/`cover_letter_plaintext`/`cover_letter_markdown` — confirmed against `client/templates/renderer.py:381` and its cover-letter counterparts) to display labels.
  - Entries with unknown keys are dropped; empty/null map → component renders `null`.
  - Each link is an `<a>` carrying the PrimeReact button classes (`p-button p-button-secondary p-button-outlined` + `pi-download` icon) so it looks like `Button`s (v10 `Button` has no `href`/`as` prop) and points at `fileDownloadUrl(path)` from `download.ts` → `/api/outputs/{basename}` (path values are `output/...` — basename extracted).
- `ui/src/pages/RunPage.tsx` — on `completed`, renders `<DownloadsRow outputFiles={asStringMap(taskQuery.data?.result?.output_files)} />` above `<ResultsTabView />`; new `asStringMap` import from `results/coerce.ts`.
- `ui/src/index.css` — `.run-downloads` (wrap row, gap) + `.run-downloads .p-button { text-decoration: none }`.

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (515 kB JS / 418 kB CSS).
- Live backend spot-check (uvicorn on :8000): `GET /api/outputs/20260809_1417_test-user_test-co_resume.md` → 200 with 91 bytes (`text/markdown`), confirming the download URL scheme (`fileDownloadUrl` → `/api/outputs/{basename}`) serves output files from `output/`. Non-existent names → 404 as expected.

### 5.6 Files page — DONE

Built the Files page with listing/filtering/deletion.

- `ui/src/pages/FilesPage.tsx` (rewritten) —
  - **Kind toggle** via `TabMenu` (Generated/Uploaded; v10.9.8 has no `SegmentedButton`, `TabMenu` is the plan's alternative). Switching resets page + selection.
  - **Filters row**: `q` search `InputText` (Enter applies; applied value lives separate from typing state so only committed searches refetch), `file_type` `Dropdown` (All types/txt/md/docx/pdf) and `sort` `Dropdown` (newest/oldest/name_asc/name_desc) — both reset to page 1 on change.
  - **DataTable**: `dataKey="path"`, checkbox selection (`selectionMode="checkbox"`, `selectionPageOnly`), lazy + `Paginator` (`rows`, `first`, `totalRecords`, `rowsPerPageOptions`, `onPage` maps `first/rows + 1` → page). Columns: selection, Name, Type, Modified (locale string), Size (`formatSize` B/KB/MB), Link (download `p-button` anchor via `fileDownloadUrl(row.path)`). `emptyMessage` switches between Loading…/No files found.
  - **Delete**: `useDeleteFiles` mutation (invalidates `['files']` on success via the hook) → ConfirmDialog (accept = delete, clears selection; Toast success on `deleted` count, warn on `missing`, error on mutation failure). Button disabled when nothing selected or while pending, label reflects `Delete selected (n)`.
- `ui/src/index.css` — `.files-page`, `.files-toolbar`, `.files-filters`, `.files-filter-type`, `.files-filter-sort`, `.files-actions`, `.files-name`.

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (840 kB JS / 419 kB CSS; DataTable/TabMenu/ConfirmDialog pulled in).
- Live backend round-trip on :8000 (uvicorn): paging (`page=2&page_size=5` returns a different first file than page 1), sort (`oldest` first = 20260806 file, `newest` = 20260809), `q=cover` returns only cover-letter names, `file_type=pdf` returns only PDFs — all matching `GET /api/files/*`.
- Delete round-trip: created `uploads/__deleteme_test.txt`, `DELETE /api/files` with `{"files":["uploads/__deleteme_test.txt"]}` → `{deleted:[...], missing:[]}`; confirmed the file is removed from disk and from a follow-up listing.

### 5.7 Models page — DONE

Built the Models page.

- `ui/src/pages/ModelsPage.tsx` (rewritten) — `DataTable` fed by `useModels()` with columns Agent / Provider / Model (all `sortable`, `dataKey="agent"`):
  - Provider rendered as a `Tag` (openai → `info`, ollama → `success`, anything else → `warning`).
  - `loading={isLoading}`; `emptyMessage` flips to "Failed to load models. Is the backend running?" when the fetch errors (isError), else "No models found".
  - Paginator enabled only when more than 10 rows.
- `ui/src/index.css` — `.models-page` (column layout, gap).

#### Verification

- `npm run lint` (oxlint) — clean.
- `npm run build` (`tsc -b && vite build`) — passes (840 kB JS / 419 kB CSS).
- Live match check: `GET /api/models` (uvicorn on :8000) returns exactly `[{'agent': 'jd_parsing_agent', 'provider': 'ollama', 'model': 'qwen2.5:7b-instruct'}, …]` for all 7 agents, identical to `uv run python -c "from config.agents import get_model_summary; …"` — the task verify.