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

---

## 5. Views (PrimeReact)

### 5.4 Run page — results `TabView`

Split into 7 sub-tasks, one per result tab. 5.4.1 also scaffolds the shared `TabView` container and result-extraction helpers; 5.4.6/5.4.7 handle the string-vs-object tolerance.

- **Verify (whole):** manual pipeline run populates every tab; empty agents show "no data" placeholders.

#### 5.4.1 Results container + Parsed JD tab

- `src/pages/results/ResultsTabView.tsx` (new) — after `completed`, renders a `TabView` of result tabs, fed by the settled `TaskStatus.result`. Extract the 7 result keys defensively (each `parsed_*` key may be an object, plain string, or null).
- Parsed JD tab: role/company/seniority; `Tag`s for required skills / preferred skills / keywords / industry terms; responsibilities list; company_signals key→value table.
- Empty value → "no data" placeholder text in the tab body.
- **Verify:** tsc/lint clean; JD tab renders from a completed run.

#### 5.4.2 Parsed Resume tab

- Tab that renders parsed resume: summary text; skills `Tag`s; experience entries (title/company/dates + responsibilities/achievements/metrics); projects, certifications, education; contact line.
- Empty/missing sections → per-section "no data" placeholders.
- **Verify:** tsc/lint clean; tab renders from a completed run.

#### 5.4.3 Gap Analysis tab

- Tab that renders tailoring strategy: tag lists for missing/weak/strong skills, emphasis area, keyword strategy, bullet plan; tone-guidance text (may arrive as string or object — coerce defensively).
- Empty → "no data" placeholder.
- **Verify:** tsc/lint clean; tab renders from a completed run.

#### 5.4.4 Rewritten Resume tab

- Tab that renders rewritten resume: structured summary + experience (title/company/dates + responsibilities/achievements/metrics).
- Empty → "no data" placeholder.
- **Verify:** tsc/lint clean; tab renders from a completed run.

#### 5.4.5 ATS tab

- Tab that renders ATS compliance: `Tag` score colored by band (<50 red, <80 orange, else green); missing keywords list; issues list; fixes list; auto-fixes list; `final_resume` body in a read-only `Textarea`/`pre`.
- Empty → "no data" placeholder; missing score → no score chip.
- **Verify:** tsc/lint clean; tab renders from a completed run.

#### 5.4.6 Polished tab

- Tab that renders `polished_resume`, tolerating it arriving as a plain string OR an object with a text field (coerce defensively).
- Empty → "no data" placeholder.
- **Verify:** tsc/lint clean; tab renders from a completed run.

#### 5.4.7 Cover Letter tab

- Tab that renders `cover_letter`, tolerating it arriving as a plain string OR an object with a text field (coerce defensively).
- Empty → "no data" placeholder.
- **Verify:** tsc/lint clean; tab renders from a completed run.

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
