# Simplification Plan — Progress Log

> This is the working log for the inspect-and-simplify plan. Completed phases
> are recorded in `simple-done.md`; the full plan (guiding rules, file
> inventory, per-phase specs, and work-breakdown checklists) is archived there
> under "Archive: Full Simplification Plan". This file keeps only the progress
> table and the remaining work.

## Progress log

| Phase | Status | Record |
|---|---|---|
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

Phase 20 verification: backend green (`pytest` 493 passed, `ruff check .`,
`ruff format --check .`, `pyright` 0 errors/warnings), frontend green
(`npm test -- --run` 48 passed, `npm run lint`, `npx tsc -b`), CLI + web API +
live E2E smoke passed, and the diff review / final commit left the working tree
clean.

## Remaining work

### Phase 21 - Documentation Cleanup

- [x] 21.1 Root README.md needs to be less than 500 lines with a quickstart section that explains to to get started in 10 minutes or less and links to detailed README.md file ✅ See `simple-done.md`.
- [ ] 21.2 Create a more expansive/detailed README.md in the docs directory which contains:
  - [ ] 21.2.1 Detailed instructions on how to get started
  - [ ] 21.2.2 Detailed examples on all command line switches/options
  - [ ] 21.2.3 Common issues and fixes
- [ ] 21.3 All markdown files should link to previous and next file, sorted alphabetically with a link docs/README.md file
- [ ] 21.4 Ensure all markdown files are up to date.
- [ ] 21.5 No markdown linting errros in any of the markdown files