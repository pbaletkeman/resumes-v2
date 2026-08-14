# Simplification Plan — Progress Log

> This is the working log for the inspect-and-simplify plan. Completed phases
> are recorded in `simple-done.md`; the full plan (guiding rules, file
> inventory, per-phase specs, and work-breakdown checklists) is archived there
> under "Archive: Full Simplification Plan". This file keeps only the progress
> table and the remaining work.

- [Simplification Plan — Progress Log](#simplification-plan--progress-log)
  - [Progress log](#progress-log)
  - [Remaining work](#remaining-work)
    - [Phase 23 - Formatting](#phase-23---formatting)
    - [Phase 21 - Documentation Cleanup](#phase-21---documentation-cleanup)

## Progress log

| Phase | Status | Record |
| --- | --- | --- |
| 1 — Foundation: config, logging, errors, LLM clients, JSON utils | ✅ Completed | `simple-done.md` |
| 2 — Pydantic models & coercion | ✅ Completed | `simple-done.md` |
| 3 — Parsing agents & the format detector | ✅ Completed | `simple-done.md` |
| 4 — LLM-only agents: Gap Analysis, ATS Compliance, Tone Polishing + shared validation cleanup | ✅ Completed | `simple-done.md` |
| 5 — Resume Rewrite agent + post-validation | ✅ Completed | `simple-done.md` |
| 6 — Cover Letter agent (largest file) | ✅ Completed | `simple-done.md` |
| 7 — Renderer, templates, formatter | ✅ Completed | `simple-done.md` |
| 8 — Skill taxonomy & normalization | ✅ Completed | `simple-done.md` |
| 9 — Pipeline orchestration + CLI | ✅ Completed | `simple-done.md` |
| 10 — Web API layer | ✅ Completed | `simple-done.md` |
| 11 — Backend tests & scratch scripts | ✅ Completed | `simple-done.md` |
| 12 — Frontend API layer (client, hooks, types, download) | ✅ Completed | `simple-done.md` |
| 13 — Result data coercion + shared result parts | ✅ Completed | `simple-done.md` |
| 14 — Results tabs (8 components) | ✅ Completed | `simple-done.md` |
| 15 — Run page & form helpers | ✅ Completed | `simple-done.md` |
| 16 — Files page | ✅ Completed | `simple-done.md` |
| 17 — Models page, App shell, theme, toast, entry | ✅ Completed | `simple-done.md` |
| 18 — Frontend tests | ✅ Completed | `simple-done.md` |
| 19 — Repo-wide documentation consolidation | ✅ Completed | `simple-done.md` |
| 20 — Final verification & regression (20.1-20.5) | ✅ Completed | `simple-done.md` |
| 22 — Model editing (SQLite overrides + Models page editing) | ✅ Completed | `simple-done.md` |
| 23 — Formatting (23.1-23.4 done) | ✅ Completed | `simple-done.md` |

Phase 20 verification: backend green (`pytest` 493 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings), frontend green
(`npm test -- --run` 48 passed, `npm run lint`, `npx tsc -b`), CLI + web API +
live E2E smoke passed, and the diff review / final commit left the working tree
clean.

Phase 22 verification: backend green (`pytest` 518 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings), frontend green
(`npm test` 57 passed, `npm run lint`, `npm run build`).

Phase 23.1 verification: backend green (`pytest` 520 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings), frontend green
(`npm test` 57 passed, `npm run lint`, `npm run build`).

Phase 23.2 verification: backend green (`pytest` 526 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings). Backend-only change
(renderer templates + tests), no frontend impact.

Phase 23.3 verification: backend green (`pytest` 537 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings), frontend green
(`npm test` 61 passed, `npm run lint`, `npm run build`).

Phase 23.4 verification: backend green (`pytest` 542 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings). Backend-only change
(renderer cover letter signature handling + tests), no frontend impact.

Phase 21.2 verification: `docs/README.md` audited against the current code and
refreshed (pytest count 542, Vitest count 61 — confirmed by `npm test -- --run`
9 files/61 tests). Markdown-only change, no source touched.

Phase 21.3 verification: pipeline-flow ASCII diagram replaced with Mermaid in
`AGENTS.md`, `docs/agents.md`, `docs/architecture.md`, and `docs/README.md`;
no `↓`/`←`/box-drawing ASCII diagrams remain in the docs. Markdown-only change.

Phase 21.4 verification: all 8 docs guides now carry a `## Related` footer with
alphabetical Previous/Next links (agents → api → architecture → logging-info →
models → skill-taxonomy → TESTING → usage) plus a link to `docs/README.md`; the
`docs/README.md` documentation index was re-sorted alphabetically. Markdown-only
change.

Phase 21.5 verification: all markdown docs audited against the code —
`_split_paragraphs` → `_split_letter_body` in `docs/api.md`, `pipeline.py`
line refs refreshed (432/330), ModelsPage no longer "read-only" in
`ui/README.md`, rendering-gate claims updated for the parsed-resume-name
fallback (commit `eab20e2`), and the test census refreshed to **550 passed**
(`test_renderer.py` 66, `test_pipeline.py` 22). Markdown-only change.

## Remaining work

### Phase 23 - Formatting

- [x] 23.1 The Cover letter is never transformed into a DOCX file or a PDF file. ✅ See `simple-done.md`.
- [x] 23.2 The line breaks in the generated files are not correct. In Markdown you need two line breaks in a row to have one of then display correctly. ✅ See `simple-done.md`.
- [x] 23.3 Provide a way to generate all three layout formats of the resume templates. ✅ See `simple-done.md`.
- [x] 23.4 The closing salulation for the cover letters is repeated. ✅ See `simple-done.md`.

### Phase 21 - Documentation Cleanup

- [x] 21.1 Root README.md needs to be less than 500 lines with a quickstart section that explains to to get started in 10 minutes or less and links to detailed README.md file ✅ See `simple-done.md`.
- [x] 21.2 Create a more expansive/detailed README.md in the docs directory which contains:
  - [x] 21.2.1 Detailed instructions on how to get started ✅ See `simple-done.md`.
  - [x] 21.2.2 Detailed examples on all command line switches/options ✅ See `simple-done.md`.
  - [x] 21.2.3 Common issues and fixes ✅ See `simple-done.md`.
- [x] 21.3 Replace all ASCII diagrams with Mermaid Markdown diagrams ✅ See `simple-done.md`.
- [x] 21.4 All markdown files should link to previous and next file, sorted alphabetically with a link docs/README.md file ✅ See `simple-done.md`.
- [x] 21.5 Ensure all markdown files are up to date ✅ See `simple-done.md`.
- [x] 21.6 No markdown linting errors in any of the markdown files ✅ See `simple-done.md`.

Phase 21.6 verification: all git-tracked markdown files (root `*.md`,
`docs/*.md`, `scratch/*.md`, `ui/README.md`) pass `npx markdownlint-cli2`
with a new repo `.markdownlint-cli2.jsonc` config — 0 issues. The config
tracks the project style (long prose lines, compact tables) and scopes
`MD025` off for `simple-done.md` only, which embeds the archived original
plan as a standalone historical document with its own top-level heading.
Auto-fixable spacing/trailing-newline issues were fixed via
`markdownlint-cli2 --fix`; bare fences gained `text`/`bash`/`powershell`
languages; a `docs/README.md` table cell containing `(resume|cover[-_]letter)`
was reworded (the `|` inside the code span split the row). Markdown-only
change.
