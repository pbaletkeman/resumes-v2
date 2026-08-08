# Frontend Plan: React + PrimeReact UI for the Resume API

Decisions locked in:

- TypeScript (Vite `react-ts` template)
- TanStack Query (React Query) for data fetching
- Async pipeline runs with task-id polling
- `ui/` lives in this repo; FastAPI serves the built SPA in production; Vite proxy in dev (no CORS needed)

## 1. Backend prep - `app/main.py` (small, typecheck-clean)

- After the API routes, serve the built SPA when it exists:
  - Mount `/assets` via `StaticFiles`, plus a catch-all `GET /{path:path}` (excluding `/api`, `/health`, dotfiles) returning `index.html`, so React Router deep links like `/files` work on refresh.
  - Keep this guarded so running without a build keeps the current pure-API behavior.
  - No CORS middleware needed - dev uses a Vite proxy.
- Existing pytest suite must stay green (tests hit `/api/*` only).

## 2. Scaffold `ui/` (Vite + React + TS)

- `npm create vite@latest ui -- --template react-ts`
- `npm i primereact primeicons react-router-dom @tanstack/react-query`
- `.gitignore`: add `ui/node_modules`, `ui/dist`
- PrimeReact default theme (`lara-light-blue`) imported in `src/main.tsx`. No Tailwind.

## 3. `vite.config.ts`

- `react()` plugin + `server.proxy: { "/api": "http://localhost:8000" }`.
- Dev on :5173 talks to :8000 with zero CORS.

## 4. `src/api/` - typed client + hooks

- `types.ts` - TS mirrors of `PipelineRunResponse`, `PagedFile`, `FileMeta`, `TaskStatus`, model summary.
- `client.ts` - thin `fetch` wrapper; run pipeline posts `FormData` (text wins, matching `_read_text_input`): `job_description`, `resume`, `job_file`, `resume_file`, `candidate_name`, `company_name`.
- `hooks.ts` - React Query:
  - `useModels`
  - `useInvokePipeline` (mutation `POST /api/pipeline/async`)
  - `usePollTask(taskId, refetchInterval)` polling `GET /api/tasks/{id}` until `completed|failed`
  - `useFiles(kind, params)` for listing
  - `useDeleteFiles` mutation
- `download.ts` - build download links to `/api/outputs/{name}` for `output_files` and file rows.

## 5. Views (PrimeReact)

- `App.tsx` - `Menubar` (Run | Files | Models) + `Outlet`.
- **Run** - `FileUpload` + `TextArea` for JD & resume (paste or file), optional candidate/company `InputText`; `Button` starts async run; `ProgressSpinner` + live status while running; results in a `TabView`:
  - Parsed JD (chip tags for skills)
  - Gap Analysis (tagged lists)
  - Rewritten / ATS (score via `Tag` + issues list)
  - Polished
  - Cover Letter
  - Downloads row linking the `output_files`
- **Files** - two `DataTable`s (generated / uploaded) with `Paginator`, `q` + `file_type` filters, download links, row `Checkbox` batch delete with `ConfirmDialog` -> `DELETE /api/files`.
- **Models** - `DataTable` of `agent/provider/model` from `GET /api/models`.

## 5b. ASCII preview

Wireframe of the shell shared by every page (`Menubar` + content area):

```plaintext
+------------------------------------------------------------------------------+
| [r] Resume Optimizer        Run | Files | Models                  [health ok]|
+------------------------------------------------------------------------------+
|                                                                              |
|                          <- page content below ->                            |
|                                                                              |
+------------------------------------------------------------------------------+
```

**Run page** (launch + status + tabbed results):

```plaintext
+------------------------------------------------------------------------------+
| RUN PIPELINE                                                                 |
+------------------------------------------------------------------------------+
| +----------------------------------+ +----------------------------------+    |
| | Job Description                  | | Resume                           |    |
| | [ TextArea: paste raw JD....]    | | [ TextArea: paste raw resume]    |    |
| |  or                              | |  or                              |    |
| | [Choose] job_file.pdf    drop    | | [Choose] resume.docx    drop     |    |
| +----------------------------------+ +----------------------------------+    |
|                                                                              |
| Candidate name [____________________]  Company name [____________________]   |
|                                                                              |
|                              [ Run Pipeline ]                                |
|                                                                              |
|  Status: [o=o=o=o=o spinner]  running `task #a1b2c3` ...  (polls /tasks/id) |
+------------------------------------------------------------------------------+
|  [v] Parsed JD   [v] Gap   [v] Rewrite   [v] ATS   [v] Polished   [v] Cover  |
+------------------------------------------------------------------------------+
|  Active tab: ATS Compliance                                                  |
|   +-----------+  ATS Score: 85   Badge: [ Good ]                            |
|   | Missing   |  > Python   > SQL   > Docker                               |
|   | keywords: |                                                             |
|   +-----------+  Formatting issues:  - none                                  |
|                  Recommended fixes:  - add quantified metrics               |
|                  Downloads: [AT S_optimized.docx] [.pdf] [.md] [.plain.txt]  |
+------------------------------------------------------------------------------+
```

**Files page** (generated/uploaded tables with paging + batch delete):

```plaintext
+------------------------------------------------------------------------------+
| FILES                                                                        |
+------------------------------------------------------------------------------+
| [ Generated ] [ Uploaded ]                                          [ + New ] |
| Search [__________________]  Type [All v]                                     |
+------------------------------------------------------------------------------+
| [x] | Name                    | Type | Modified          | Size    | Links    |
| [x] | 1712_..._resume.pdf     | pdf  | 2026-08-08 12:00  | 24 KB   | [dl]     |
| [ ] | polished_resume.txt     | txt  | 2026-08-07 09:15  | 4 KB    | [dl]     |
| [ ] | cover_letter.pdf        | pdf  | 2026-08-07 09:15  | 18 KB   | [dl]     |
+------------------------------------------------------------------------------+
| < 1 2 3 ... 9 >   20 per page                                                 |
|                              [ Delete selected (2) ]  (ConfirmDialog)        |
+------------------------------------------------------------------------------+
```

**Models page**:

```plaintext
+------------------------------------------------------------------------------+
| MODELS                                                                       |
+------------------------------------------------------------------------------+
| Agent                  | Provider | Model               |
| jd_parsing_agent       | ollama   | qwen2.5:7b-instruct |
| resume_parsing_agent   | ollama   | qwen2.5:7b-instruct |
| gap_analysis_agent     | ollama   | qwen2.5:7b-instruct |
| ...                    |          | tons more agents    |
| (loaded live from GET /api/models)                                        |
+------------------------------------------------------------------------------+
```

## 6. Verification

- `uv run ruff check .` and `uv run pyright` (app/main.py change must stay strict-clean).
- `uv run pytest` (backend suite must stay green).
- `npm run build` + `npm run lint` in `ui/`.
- Manual: start backend, `npm run dev`, run a pipeline against `sample/jobs/` + `sample/resume/`, confirm results + downloads.

## 7. Docs (optional)

- Add a "UI" section to `AGENTS.md` with the two-terminal quickstart and `npm` commands.

## Known limitations

- Async task results live only in memory (lost on restart) - fine for single-user use.
- PrimeReact base themes are free; the paid theme-designer packs are deliberately avoided.

## Dev workflow

- Terminal 1: `uv run uvicorn app.main:app --reload` (port 8000)
- Terminal 2: `npm install && npm run dev` in `ui/` (port 5173), proxied to 8000.
