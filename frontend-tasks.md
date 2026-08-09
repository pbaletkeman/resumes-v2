# Frontend Implementation Tasks

Detailed breakdown of `frontend-plan.md` into actionable, verifiable tasks. Each task lists the deliverable, its acceptance check(s), and how to verify. Assumed environment: Node v24/npm on Windows, backend on `localhost:8000` (`uv run uvicorn app.main:app --reload`).

Conventions:

- All `ui/` commands run with `ui/` as the working directory.
- Python checks run from the repo root.
- Follow `AGENTS.md` conventions (ruff/pyright strict, no comments unless asked).

---

## 2. Scaffold `ui/` (Vite + React + TS)

---

## 4. `src/api/` — typed client + React Query hooks

### 4.3 `src/api/download.ts`

- `outputDownloadUrl(name: string)` → `/api/outputs/{name}` (encode name).
- `fileDownloadUrl(path: string)` → same, extracting basename from `path` keys like `uploads/foo.pdf`.
- **Verify:** typecheck; manual link click downloads a real file.

### 4.4 `src/api/hooks.ts` — React Query hooks

- `useModels()` — `useQuery(['models'], fetchModels)`.
- `useInvokePipeline()` — `useMutation(runPipelineAsync)` returning `taskId`.
- `useTask(id)` — `useQuery(['task', id], getTask, { refetchInterval: query.state.status in running/pending ? 2000 : false })`, plus a `usePollTask(id, onDone)` helper that stops polling at `completed`/`failed` and invalidates related queries (e.g. `['files']`).
- `useFiles(kind, params)` — `useQuery(['files', kind, params], ...)`, keepPreviousData for paging.
- `useDeleteFiles()` — mutation; onSuccess invalidate `['files', ...]`.
- **Verify:** typecheck; manual run shows polling then settled state.

---

## 5. Views (PrimeReact)

### 5.1 App shell — `src/App.tsx`

- `BrowserRouter` + `Menubar` (logo/title, items: Run `/`, Files `/files`, Models `/models`) + `<Outlet/>`.
- Add a theme switch to the end of the `Menubar`: a `ToggleButton` (sun/moon icons) that flips light↔dark via the `useTheme` hook from 2.5; optionally a three-way dropdown ("System | Light | Dark").
- Small `Toast` ref provided via context for messages.
- **Verify:** navigate between three routes; Menubar highlights active; the theme toggle flips the whole app in place without a reload.

### 5.2 Run page — form (paste or upload)

- JD & resume columns: `TextArea` for paste + `FileUpload` (choose mode, single file, accept `.txt,.docx,.pdf`) for upload. Text wins when non-empty.
- Optional `InputText` for candidate/company name.
- `Button` "Run Pipeline" disabled while a run is active.
- Validation: at least one of paste/file per input (reuse the API's error `detail` on failure).
- **Verify:** both input paths build valid `FormData` (inspect via network tab).

### 5.3 Run page — async status

- On submit: `useInvokePipeline` → show task id + `ProgressSpinner`; `usePollTask` updates a status `Tag` (pending/running/completed/failed) and surfaces `error` via Toast on failure.
- **Verify:** with Ollama running, status transitions running → completed; without Ollama it surfaces a failure message.

### 5.4 Run page — results `TabView`

- After `completed`, render result tabs:
  - **Parsed JD** — role/company/seniority; `Tag`s for required/preferred skills, keywords, industry terms; responsibilities list; company_signals table.
  - **Parsed Resume** — summary, skills tags, experience entries (title/company/dates + responsibilities/achievements/metrics), projects/certs/education, contact line.
  - **Gap Analysis** — tag lists for missing/weak/strong, emphasis, keyword strategy, bullet plan; tone guidance text.
  - **Rewritten Resume** — structured summary + experience.
  - **ATS** — `Tag` score (colored by band: <50 red, <80 orange, else green), missing keywords, issues, fixes, auto-fixes; `final_resume` in a `pre`/textarea.
  - **Polished** — `polished_resume` text.
  - **Cover Letter** — `cover_letter` text.
  - Handle string-vs-object keys defensively (`polished_resume`/`cover_letter` may arrive as plain strings).
- **Verify:** manual pipeline run populates every tab; empty agents show "no data" placeholders.

### 5.5 Run page — downloads row

- From `output_files` (keys: `resume_plaintext`, `resume_markdown`, `resume_docx`, `resume_pdf`, `cover_letter_plaintext`, `cover_letter_markdown`), render `Button`s (link) to `/api/outputs/{basename}` via `download.ts`.
- **Verify:** each button downloads a non-empty file from `output/`.

### 5.6 Files page

- Toggle between generated/uploaded (`SegmentedButton` or `TabMenu`) → `useFiles(kind, ...)`.
- `DataTable` columns: checkbox, name, type, modified, size, link. `Paginator` wired to page/page_size; `q` input + `file_type` dropdown; sort selector.
- Selection state → "Delete selected (n)" `Button` → `ConfirmDialog` → `useDeleteFiles` → Toast with `deleted`/`missing`; refetch.
- **Verify:** paging/filter/sort round-trip against `/api/files/*`; delete removes rows (check `output/` and `uploads/`).

### 5.7 Models page

- `DataTable` of `useModels()`: agent / provider / model. Empty state message if fetch fails.
- **Verify:** matches `uv run python -c "from config.agents import get_model_summary; ..."` output.

---

## 6. Frontend unit tests (Vitest + Testing Library)

### 6.1 Configure Vitest

- Add a `test` block to `ui/vite.config.ts`: `environment: 'jsdom'`, `globals: true`, `setupFiles: './src/test/setup.ts'`, and a `ui/tsconfig` type entry for Vitest globals + jest-dom matchers.
- Create `ui/src/test/setup.ts` importing `@testing-library/jest-dom` (and, if needed, a PrimeReact CSS stub so theme imports don't break jsdom).
- Add `"test": "vitest run"` (and `"test:watch": "vitest"`) to `ui/package.json` scripts.
- **Accept:** `npm test` runs a trivial passing test.
- **Verify:** run `npm test` in `ui/`.

### 6.2 Test the API client (`src/api/client.ts`)

- Mock `global.fetch` (or `vi.stubGlobal`) in each test; cover:
  - `runPipelineAsync` builds the expected `FormData` — text fields present, empty text omitted.
  - `getTask`/`listFiles`/`deleteFiles` hit the correct URLs+methods and parse JSON.
  - Non-2xx responses throw with the backend `detail` message surfaced.
  - Download URLs produce the expected `/api/outputs/...` paths.
- **Verify:** `npm test` in `ui/`.

### 6.3 Test React Query hooks (`src/api/hooks.ts`)

- Wrap components in `QueryClientProvider` (fresh `QueryClient` per test, e.g. via a `renderWithClient` helper that also flushes pending queries).
- Cover: `useModels` renders data on success; `useFiles` passes page params through and keeps previous data while refetching; `useDeleteFiles` onSuccess invalidates the `['files', ...]` queries.
- **Verify:** `npm test` in `ui/`.

### 6.4 Test the theme hook (`useTheme`)

- Mock `matchMedia` (jsdom doesn't implement it) to simulate `prefers-color-scheme: dark` and its `change` event.
- Cover: defaults to the system scheme when no `localStorage` override exists; respects a stored `light`/`dark` override; toggling persists the choice; setting "system" removes the override and re-follows OS changes; `data-theme` is set/removed on `document.documentElement`.
- **Verify:** `npm test` in `ui/`.

### 6.5 Test components

- **ThemeToggle** — clicking flips light↔dark and calls the theme hook's setter.
- **Run page form** — paste text + uploaded file: text wins in the submitted `FormData`; the "Run Pipeline" button is disabled while a run is active; validation surfaces a message when both inputs are empty.
- **Downloads row** — renders one link per `output_files` entry and points at the correct `/api/outputs/{name}` URL.
- **Files page** — renders rows from a stubbed `PagedFile`, fires the delete mutation with the selected `path`s, shows the `ConfirmDialog`, and surfaces the delete result via Toast.
- **Models page** — renders agent/provider/model rows; shows the empty-state message on fetch failure.
- **ATS tab** — `Tag` severity maps score bands (<50 red, <80 orange, else green).
- **Verify:** `npm test` in `ui/`; all pass.

### 6.6 Run the full suite

- **Accept:** `npm run lint` and `npm test` are both clean in `ui/`, alongside `npm run build` / `npx tsc --noEmit`.
- **Verify:** `npm test` in `ui/` ends with a green summary.

---

## 7. Verification (whole app)

### 7.1 Backend checks

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pyright` (strict, no path arg)
- `uv run pytest`
- **Accept:** all clean/green.

### 7.2 Frontend checks

- In `ui/`: `npm run lint`, `npm test`, `npm run build`, `npx tsc --noEmit`.
- **Accept:** no errors/warnings, all tests green.

### 7.3 Manual E2E

- Backend up (`uv run uvicorn app.main:app --reload`), `npm run dev` in `ui/`.
- Run pipeline with `sample/jobs/*` + `sample/resume/*` (paste a sample text or upload the file).
- Confirm: async status polling, all result tabs populated, all download buttons work.
- Confirm theming: match OS theme on load, instant light↔dark toggle from the Menubar, preference survives refresh, "system" mode follows a live OS theme change.
- Confirm SPA fallback: `npm run build`, then restart backend and visit `/files` directly (refresh works).

---

## 8. Docs (optional)

### 7.1 Update `AGENTS.md`

- Add a "UI" section: two-terminal quickstart (`uv run uvicorn app.main:app --reload` + `cd ui && npm run dev`), build command (`npm run build`), and note that production serves `ui/dist` from FastAPI.
- **Accept:** commands in the doc match reality.
