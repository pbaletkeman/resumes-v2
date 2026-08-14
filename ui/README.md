# resumes-v2 Frontend (`ui/`)

React 19 + TypeScript + Vite single-page app for the multi-agent resume
optimization pipeline. It talks to the FastAPI backend (`app/`, served on
`localhost:8000`): you paste a job description + resume (or upload files),
optionally give a candidate/company name, run the 7-agent pipeline, then browse
the seven result tabs and download the rendered output files.

The pages use **PrimeReact** for components, **React Query** for server state
and polling, and **React Router** for navigation.

## Quickstart

Dev mode uses two terminals — the Vite dev server proxies `/api` and `/health`
to the backend on `localhost:8000`, so point the browser at the Vite URL
(printed by `npm run dev`).

```text
# terminal 1 — backend (from the repo root)
uv run uvicorn app.main:app --reload

# terminal 2 — frontend (from this directory)
npm install
npm run dev
```

Open the Vite URL (defaults to `http://localhost:5173`), go to the **Run**
page, and submit a pipeline. Watch the background task on the same page; when
it completes, the result tabs and the download row appear.

In production, the backend serves the built SPA itself: FastAPI mounts `ui/dist`
and falls back to `index.html` for non-API routes when `ui/dist/index.html`
exists. So `npm run build` in this directory is all that is needed to ship the
UI through the FastAPI server.

## Commands

| What | Command |
| --- | --- |
| Dev server (proxies `/api` + `/health` to `localhost:8000`) | `npm run dev` |
| Build SPA to `../ui/dist` (runs `tsc -b && vite build`) | `npm run build` |
| Lint (oxlint) | `npm run lint` |
| Typecheck | `npx tsc -b` |
| Unit tests (Vitest + Testing Library) | `npm test` |
| Tests (watch) | `npm run test:watch` |

Run the frontend test suite from this directory: `npm test`. All other
repo-level commands (backend tests, ruff, pyright) are documented in
`../README.md` and `../AGENTS.md`.

## Routes

| Path | Page | Purpose |
| --- | --- | --- |
| `/` | RunPage | Input form (JD + resume text/files) and the pipeline task lifecycle (submit -> poll -> results + downloads) |
| `/files` | FilesPage | Browse / filter / delete generated (`output/`) and uploaded (`uploads/`) files |
| `/models` | ModelsPage | Per-agent model/provider table with inline editing and reset-to-defaults (SQLite-persisted overrides) |

Routing is set up in `src/App.tsx` (a `Menubar` shell wrapping the routed pages
with a theme toggle). The Run page's task-status helpers live in `src/pages/`:
`runStatus.ts` (pure `isTaskActive` / `taskStatusLabel` helpers) and `runForm.ts`
(`validateRunInputs` / `buildRunFormData`, text-wins-over-file matching the
backend's `_read_text_input`).

## Source layout

```plaintext
src/
  main.tsx              # Mount point: PrimeReact themes + app CSS + <App />
  App.tsx               # Shell + routing tree (/, /files, /models)
  api/
    client.ts           # apiFetch wrapper + error-detail parsing
    hooks.ts            # React Query hooks: useModels, useFiles, useDeleteFiles,
                        #   usePollTask (polls + invalidates files on completion)
    types.ts            # TS mirrors of the FastAPI response models
    download.ts         # Builds the /api/outputs/<filename> download URL
  pages/
    RunPage.tsx         # Pipeline input form + task poll + result tabs
    runForm.ts          # Build/validate the multipart run form
    runStatus.ts        # Task-status label + active helpers (pure)
    FilesPage.tsx       # Generated/uploaded file listing + delete
    ModelsPage.tsx      # Per-agent model table
    results/            # coerce.ts (loosely-typed result coercion), parts.tsx
                        #   (shared renderers), the 7 result tabs, DownloadsRow,
                        #   ResultsTabView (tab order mirrors pipeline output)
  theme/useTheme.ts     # Persisted light/dark/system theme (localStorage "theme")
  theme/ThemeToggle.tsx # Menu toggle for the theme mode
  toast/ToastProvider.tsx + ToastContext.ts  # Global toast context
  test/setup.ts, test/utils.tsx               # Shared Vitest setup + render helper
```

Result tabs render the pipeline's seven outputs in order — `parsed_job_description`
… `cover_letter` — matching the backend result keys (see `src/pages/results/ResultsTabView.tsx`,
whose `TAB_KEYS` order mirrors the 7-agent chain, for the exact mapping).

## Theme note

The PrimeReact dark theme (`lara-dark-blue`) is scoped to `html[data-theme='dark']`
by `vite.config.ts`; `useTheme.ts` flips that one attribute so the whole app
switches schemes. The chosen mode is persisted under the `theme` localStorage key.
