# Simplification Plan: Inspect & Simplify Every File, Method, Module

## Purpose

Go through the entire codebase — backend (Python) and frontend (React/TypeScript) — file by file, method by method, module by module, and:

1. **Simplify** the code.
2. **Prefer verbose, easy-to-follow code** over short, clever, or dense code.
3. **Update or improve documentation** for every file, module, class, method, and function we touch.

This is a *working plan*: each phase is small, reviewable, and keeps the test suites green. Do one phase at a time. Do not mix phases.

---

## Guiding Rules

These rules apply to every phase. Read them once here; each phase references them.

### Simplification rules (how we change code)

- **Readability beats cleverness.** If a one-liner is hard to parse, write it as 3-4 obvious lines with clear names. Verbose is welcome; complex is not.
- **Prefer named helper functions** over deep inline expressions. A helper like `_is_task_active(status)` is easier to read than a repeated 3-way boolean expression.
- **Break up "wall of logic" functions.** Any method over ~50 lines of dense logic should be split into smaller, named, single-purpose helpers.
- **Name things by intent.** Rename ambiguous variables (`data`, `raw`, `obj`, `value`) toward meaning (`parsed_json`, `llm_response_text`, `paged_file`).
- **Kill duplication by extraction, not abstraction.** If the same guarded block (e.g., `try: json.loads(...) except ...`) genuinely repeats, extract one shared helper with a clear docstring. Do not build micro-frameworks.
- **Remove dead weight.** Stale docstring claims, unused imports, commented-out code, and unreachable branches are removed (or the bug is fixed).
- **Keep behavior byte-for-byte identical** unless the phase explicitly says the change may alter output. The output shape of the 7-agent pipeline and the API contract must not change.
- **Standardize the Python 3.14 `except A, B:` style** (see Phase 4) so code does not read like Python 2.

### Documentation rules (how we improve docs)

- Every file we touch gets:
  - A **module docstring** that says *what* the module does, *why* it exists, and (where useful) *how* the pieces fit.
  - A **docstring on every class, method, and non-trivial function**: one line for *what*, a sentence for *why/edge cases*, plus `Args:`/`Returns:`/`Raises:` where relevant.
  - **In-code comments** explaining the *why* behind non-obvious decisions (never just restating the code).
- Update **stale documentation** we discover along the way (docstrings that no longer match reality, outdated file headers, wrong command examples).
- Frontend components get a short header comment describing their purpose and the data they render; helper util functions keep JSDoc.
- Documentation lives **next to the code** (docstrings) first, and in `docs/*.md` / `AGENTS.md` / `README.md` only in the final consolidation phase.

### Guardrails (every phase)

- **Baseline must stay green.** Commands (run at repo root unless noted):
  - Backend: `uv run pytest` (currently **485 passed**), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
  - Frontend (from `ui/`): `npm test -- --run` (currently **45 passed**), `npm run lint`, `npx tsc -b`
- **Never change tests to make the code pass.** If a simplification is blocked by a test, the phase is too big - split it further.
- Type-check at the end of each backend phase (`uv run pyright`) and each frontend phase (`npx tsc -b`).
- Commit small, per-phase. Commit message mentions the phase, e.g. `simplify: jd_parsing agent - split run() helpers + docstrings`.

### Per-file checklist (use in every phase)

- [ ] Read the file fully.
- [ ] List every class, method, and module-level function in the file.
- [ ] Simplify per the rules, one logical concern at a time.
- [ ] Update/add docstrings (module, class, method, function).
- [ ] Fix any stale documentation found.
- [ ] `uv run ruff check .` + `uv run ruff format .` (backend) or `npm run lint` (frontend).
- [ ] `uv run pyright` (backend) / `npx tsc -b` (frontend).
- [ ] `uv run pytest` / `npm test -- --run` green.
- [ ] Commit with a phase-tagged message.

---

## File Inventory (what we are covering)

### Backend - core pipeline (`client/`)

| File | Lines | Phase |
|---|---|---|
| `client/agents/cover_letter.py` | 968 | 6 |
| `client/templates/renderer.py` | 890 | 7 |
| `client/format_detector.py` | 756 | 3 |
| `client/agents/resume_rewrite.py` | 621 | 5 |
| `client/agents/resume_parsing.py` | 282 | 3 |
| `client/agents/ats_compliance.py` | 273 | 4 |
| `client/agents/jd_parsing.py` | 272 | 3 |
| `client/agents/gap_analysis.py` | 262 | 4 |
| `client/models.py` | 281 | 2 |
| `client/formatter.py` | 254 | 7 |
| `client/model_registry.py` | 209 | 1 |
| `client/open_ai_client.py` | 209 | 1 |
| `client/ollama_client.py` | 179 | 1 |
| `client/agents/tone_polishing.py` | 189 | 4 |
| `client/json_utils.py` | 121 | 1 |
| `client/skills/normalizer.py` | 110 | 8 |
| `client/model_client.py` | 54 | 1 |
| `client/errors.py` | 20 | 1 |
| `client/templates/modern.py`, `classic.py`, `minimal.py`, `cover_letter.py` | 84/120/70/39 | 7 |
| `client/templates/__init__.py`, `client/skills/__init__.py`, `client/__init__.py` | small | 8 |

### Backend - orchestration, CLI, config

| File | Lines | Phase |
|---|---|---|
| `pipeline.py` | 623 | 9 |
| `config/agents.py` | 173 | 1 |
| `logging_config.py` | ~50 | 1 |
| `basic.py` | small | 9 |
| `test_real_files.py` | small | 11 |

### Backend - web API (`app/`)

| File | Lines | Phase |
|---|---|---|
| `app/main.py` | 327 | 10 |
| `app/schemas.py` | 88 | 10 |
| `app/files.py` | 114 | 10 |
| `app/upload.py` | 83 | 10 |
| `app/tasks.py` | 66 | 10 |
| `app/__init__.py` | 0 | 10 |

### Backend - tests & scratch

| File | Phase |
|---|---|
| `tests/*.py` (23 files, 485 tests) | 11 |
| `wip_testing/*.py` (7 files) | 11 |

### Frontend (`ui/src/`)

| File | Lines | Phase |
|---|---|---|
| `api/client.ts`, `api/hooks.ts`, `api/types.ts`, `api/download.ts` | 94/87/125/9 | 12 |
| `api/client.test.ts`, `api/hooks.test.ts` | 219/146 | 18 |
| `pages/results/coerce.ts`, `parts.tsx` | 136/137 | 13 |
| `pages/results/*Tab.tsx` (8 files) | ~350 total | 14 |
| `pages/RunPage.tsx`, `pages/runForm.ts` | 224/43 | 15 |
| `pages/FilesPage.tsx` | 238 | 16 |
| `pages/ModelsPage.tsx`, `App.tsx`, `main.tsx`, `index.css` | 41/74/14 | 17 |
| `theme/*`, `toast/*`, `test/*` | ~250 | 17 |

### Docs

| File | Phase |
|---|---|
| `AGENTS.md`, `README.md`, `ui/README.md` | 19 |
| `docs/*.md` (8 guides) | 19 |
| Root scratch notes (`frontend-plan.md`, `frontend-tasks*.md`, `web-files-todo.md`, `resume-web-todo.md`, `resume-verify.md`, `bots.md`, `resume-todo.md`, `resume-done.md`) | 19 |

---

## Phase 0 - Baseline snapshot & conventions

**Goal:** Record where we start so every phase can be verified against it.

1. Run and record baseline output:
   - Backend: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
   - Frontend (in `ui/`): `npm test -- --run`, `npm run lint`, `npx tsc -b`
2. Save current counts (485 backend tests, 45 frontend tests) next to each phase's verify list.
3. Confirm the repo state is clean: `git status`, `git log --oneline -5`, note the branch.
4. Agree on the commit-message convention and the per-file checklist above.

**Exit criteria:** baseline commands run, snapshot documented, checklist in use.

---

## Part A - Backend (Python)

## Phase 1 - Foundation: config, logging, errors, LLM clients, JSON utils  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `config/agents.py`, `logging_config.py`, `client/errors.py`, `client/model_client.py`, `client/json_utils.py`, `client/ollama_client.py`, `client/open_ai_client.py`, `client/model_registry.py`

This is the shared "plumbing" layer every other module uses. Simplifying here is high leverage.

**Inspect for:**

- `config/agents.py`: environment-variable reading (provider/model defaults, per-agent overrides such as `COVER_LETTER_AGENT_MODEL`, `OPENAI_API_KEY`). Is every branch reachable and are variable names self-explanatory?
- `logging_config.py`: is `LOG_LEVEL` handling verbose enough to follow? Are the hard-coded logger-level decisions commented?
- `client/errors.py` (20 lines): confirm the 3 exception types plus base clearly document *when* each is raised.
- `client/model_client.py` (54 lines): the `chat()` ABC. The `response_format` / `json_schema` contract text should say *exactly* what providers must implement.
- `client/json_utils.py` (121): `parse_json_response()` (fence stripping + `json.loads`) and `model_to_json_schema()`. These two are the cornerstones every agent uses.
- `client/ollama_client.py` / `client/open_ai_client.py`: timeouts, `response_format`, and any duplicated send/format logic between them. Worth a docstring per method documenting provider-specific behavior.
- `client/model_registry.py` (209): per-agent registry; clarify how fallback `MODEL_PROVIDER`/`MODEL_NAME` interacts with per-agent overrides.

**Simplify toward:**

- Spell out inline one-liners that pack too much (e.g., complex ternaries in config resolution).
- If the two clients duplicate `json.loads` + error handling, route both through one shared "safe JSON decode" helper in `json_utils.py`.
- Rename short/mysterious module-level variables to intent-revealing names.
- Add a short "how agents use this file" comment at the top of `json_utils.py` and `model_client.py`.

**Documentation:** module + class + method docstrings (many exist already - verify each is accurate). Especially document the `response_format="json"` + optional `json_schema=` contract on `ModelClient.chat`.

**Verify:** ruff + pyright + `uv run pytest` (watch `tests/test_model_clients.py`, `tests/test_json_utils.py`).

---

## Phase 2 - Pydantic models & coercion  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/models.py`

Holds every agent output model plus the coercion validators (`_coerce_str_list`, `_coerce_tone_guidance`, `_coerce_final_resume`, etc.) that forgive LLMs returning dicts where strings/lists are expected.

**Inspect for:**

- Does every model and every field have a description written for a human (what the LLM populates) rather than restating the field name?
- The coercion validators: are they written in clear multi-step logic or terse `dict.get` chains? Are the edge cases (empty dict, `None`, list of dicts) explicit?

**Simplify toward:**

- Break any validator longer than ~25 lines into named helper functions (`_to_str_list`, `_to_str`, `_to_str_list_from_dict_value`).
- Use explicit `if/else` over complex boolean expressions so a reader can trace each fallback.
- Add a short comment at the top of the file explaining the *reason* coercion exists (LLMs produce inconsistent shapes; we forgive at the model boundary).
- Keep `model_dump`/`model_validate` output shapes identical - the pipeline and API depend on them.

**Documentation:** field descriptions on every field of every output model (`JDParsingOutput`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`, and the `Parsed*` format-detector models). Cross-check with `docs/models.md` (consolidated in Phase 19).

**Verify:** ruff + pyright + `uv run pytest` (watch `tests/test_cover_letter_validation.py`, `tests/test_resume_rewrite_validation.py`).

---

## Phase 3 - Parsing agents & the format detector  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/jd_parsing.py`, `client/agents/resume_parsing.py`, `client/format_detector.py`

These three are the "input parsers" shared by the pipeline and the regex fallbacks.

**Inspect for:**

- `jd_parsing.py`: `_extract_company_name` and the three compiled regexes (`_COMPANY_LABEL_RE`, `_COMPANY_FIRST_SENTENCE_RE`, `_COMPANY_AT_RE`) are dense. `_sync_company_name` is a good small pure helper - make sure it has a full docstring.
- `resume_parsing.py`: same structure (LLM attempt -> retry -> regex fallback). Verify the fallback path mirrors JD parsing and both read cleanly.
- `format_detector.py` (756 lines): the largest parser. Many private static helpers (`_extract_name`, `_extract_title`, `_extract_section`, `_extract_list_section`, ...). Check the big parse methods for chained one-liners and the LLM fallback for a duplicated retry loop.

**Simplify toward:**

- Introduce (or document) a shared, named "attempt LLM twice, then fall back" loop so each agent reads the same way. Do not abstract the whole agent - just the loop scaffolding.
- Build regex pattern strings piece by piece with named variables (as `_COMPANY_TOKEN` etc. already do - extend that style to other patterns).
- Break large helpers into small steps with `# 1. ...`, `# 2. ...` comments.
- Rename regex variables to state *what they match* (`_heading_pattern`, `_bullet_item_pattern`).

**Documentation:** every private helper gets `Args:`/`Returns:` docstrings. Add a file-top note explaining "regex first, LLM only if sparse" and *why* (deterministic fallback, offline-safe).

**Verify:** watch `tests/test_format_detector.py`, `tests/test_jd_parsing.py`, `tests/test_agent_jd_parsing.py`, `tests/test_agent_resume_parsing.py`.

---

## Phase 4 - LLM-only agents: Gap Analysis, ATS Compliance, Tone Polishing + shared validation cleanup  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/gap_analysis.py`, `client/agents/ats_compliance.py`, `client/agents/tone_polishing.py`

**Inspect for:**

- `ats_compliance.py` (and its siblings in Phases 5-6) use the `except json.JSONDecodeError, TypeError:` form. This is valid Python 3.14 (PEP 758) but reads like Python 2 and is confusing. Standardize to the explicit tuple form `except (json.JSONDecodeError, TypeError):` **and** route each guard through one shared helper (below) so the intent is obvious.
- The three agents' `_try_llm` methods are near-identical (prompt, rules, chat, parse, validate). Note the *small* differences (output shape, prompt strings) - keep those, de-duplicate only the scaffolding.
- `tone_polishing.py`: tone guidance coercion; verify it is as clearly written as the equivalent in `models.py`.

**Simplify toward:**

- Add one shared helper - likely in `client/json_utils.py` or a new `client/agents/_validation.py` - called something like `load_json_safe(text) -> dict | None`, and have every `_validate_*` helper use it. This is the single highest-value de-duplication on the backend: the guarded `json.loads` pattern currently appears 12+ times across `resume_rewrite.py`, `cover_letter.py`, and `ats_compliance.py`.
- Ensure each `_validate_*` function is a self-contained, clearly documented predicate: `Returns True when ...`.

**Documentation:** write the module docstring to explain the "LLM only, deterministic fallback" role of these three agents. Note which output model each produces and what happens on total failure (empty model vs. pass-through).

**Verify:** watch `tests/test_agent_gap_analysis.py`, `tests/test_agent_ats_compliance.py`, `tests/test_agent_tone_polishing.py`.

---

## Phase 5 - Resume Rewrite agent + post-validation  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/resume_rewrite.py`

621 lines: `run()` -> `_try_llm()` -> 6 post-validation helpers, plus fallback tailoring (`_parsed_to_rewrite`, `_tailor_skills`, `_as_dict`, `_read_str_list`, `_is_ascii`) and skill matching (`_sanitize_skills`, `_skill_matches`, `_normalize_skill`, `_load_str_list`).

**Inspect for:**

- `_validate_experience_count`, `_validate_certifications`, `_validate_companies` share the same `json.loads` guard (standardize via the Phase 4 helper).
- `_ensure_chronological` and `_sanitize_skills` use `model_copy` (never mutate in place) - confirm the docstrings explain that contract.
- `_tailor_skills`: two deterministic transformations are already well-commented; verify the loops read step-by-step.

**Simplify toward:**

- Re-order the file: public class first, then its methods, then module-level helpers grouped by purpose (validation -> tailoring -> skill matching).
- Give each post-validation helper a full `Args:`/`Returns:` docstring and a one-line "why" (guarding against LLM fabrication).
- Convert dense conditionals in `_skill_matches` into a few named boolean helpers (`_exact_match`, `_substring_match`, `_token_match`), each with a one-line docstring.

**Documentation:** module docstring should explain the full correctness story: LLM -> Pydantic -> *deterministic post-validation* -> chronological ordering -> skill sanitization -> deterministic fallback. Cross-check with `docs/agents.md`.

**Verify:** watch `tests/test_resume_rewrite_validation.py` (63 tests) - the heaviest safety net - plus `tests/test_agent_resume_rewrite.py`.

---

## Phase 6 - Cover Letter agent (largest file)  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/cover_letter.py`

968 lines. Highest-impact simplification target on the backend.

**Inspect for:**

- Seven occurrences of the `json.loads` guard (the Phase 4 helper removes them all).
- The chain of `_validate_*` / `_apply_company_name` / `_apply_candidate_name` post-processors - list every module-level function and assign each a clear intent.
- Where does the file switch from LLM output handling to HTML/plain rendering helpers? That split should become visible in the file structure.

**Simplify toward:**

- Split the file's helpers into named sections with banner comments (`# --- validation ---`, `# --- deterministic post-processors ---`, `# --- rendering/formatting ---`).
- Break any method over ~50 lines into smaller named steps.
- Standardize the placeholder-token handling (`[Company Name]`, `[Your Name]`) so every substitution is one obvious path with a comment.

**Documentation:** module docstring covering the agent contract (inputs from which prior agents, output model, fallback behavior, the two deterministic post-processors). This is *the* file to document thoroughly because it is the largest.

**Verify:** watch `tests/test_agent_cover_letter.py` + `tests/test_cover_letter_validation.py` (109 tests).

---

## Phase 7 - Renderer, templates, formatter  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/templates/renderer.py`, `client/templates/modern.py`, `classic.py`, `minimal.py`, `cover_letter.py`, `client/templates/__init__.py`, `client/formatter.py`

**Inspect for:**

- `renderer.py` (890): the module docstring says *"DOCX/PDF support will be added in subsequent phases"*, but DOCX/PDF rendering already exists (`render_all`, docx/pdf writers). **This stale claim must be fixed.**
- The big public methods (`render_plaintext`, `render_markdown`, `render_cover_letter`, `render_docx`, `render_pdf`, `render_all`, `_clean_output`) - check each for inlined format-specific logic that belongs in a named private method.
- `modern.py`/`classic.py`/`minimal.py`: dict templates with `plaintext`/`markdown` keys - verify the Jinja string templates are readable and each has a docstring naming its style.
- `formatter.py`: `format_resume_markdown`/`plain`/`format_cover_letter` - the "other" rendering path; document how it differs from `ResumeRenderer`.

**Simplify toward:**

- Fix the stale header. Document the two rendering paths (template-based renderer vs. formatter helpers) at the top of each module.
- Break the repeated "build context -> render -> clean output" sequence into one private `_render(template_key, context)` helper used by each public method.
- Give every template dict an explicit docstring of what it contains and which outputs it drives.

**Documentation:** full class/method docstrings; add `Args:`/`Returns:`/`Raises:` to `render_all`. Keep output byte-identical - `tests/test_renderer.py` (43 tests) and `tests/test_formatter.py` (41 tests) guard this.

**Verify:** watch `tests/test_renderer.py`, `tests/test_formatter.py`.

---

## Phase 8 - Skill taxonomy & normalization  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/skills/normalizer.py`, `client/skills/__init__.py`, `docs/skill-taxonomy.md` (read-only reference for this phase)

**Inspect for:**

- `SkillNormalizer` public surface (`normalize`, `normalize_list`, `match_skills`, ...), the canonical taxonomy loading, localization, and the `match_skills` return dict.
- Every method docstring should reference how it treats unknown skills and case.

**Simplify toward:**

- Make the internal lookup logic read step-by-step (`# 1. exact canonical match, # 2. variant lookup ...`).
- Rename any single-letter or ambiguous locals.

**Documentation:** module docstring explaining "canonical skill taxonomy -> normalized forms" and when to prefer `normalize_list` vs `match_skills`. Verify `docs/skill-taxonomy.md` matches code (consolidate in Phase 19 if it drifts).

**Verify:** watch `tests/test_skill_normalizer.py` (15 tests).

---

## Phase 9 - Pipeline orchestration + CLI  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `pipeline.py`, `basic.py`

**Inspect for:**

- `_run_pipeline_core`: seven near-identical `runner.run_agent_async(...)` blocks (steps 1-7). Each differs only by agent name, prompt, output key, rules, and context inputs. Extract one small helper `_run_stage(runner, agent_name, *, prompt, output, rules, **context)` that returns the resolved field via `_extract_field` - more verbose per call, far easier to read as a chain.
- `AgentRunner.run_agent_async`: the long protective docstring is good; verify the instantiate-on-first-use logic is clearly commented.
- `PipelineAgent` (generic wrapper): confirm the docstring explains it exists for backward compatibility with the dedicated classes.
- CLI in `main()`: file validation + sample-mode branching - keep the flow in plain sequential steps.

**Simplify toward:**

- The stage call-sites in `_run_pipeline_core` become one-line calls into `_run_stage` with a `# 1. JD Parsing` ... `# 7. Cover Letter` comment above each. This makes the order obvious.
- Keep `create_runner_from_config`, `DEFAULT_AGENT_CLASSES` behavior unchanged; improve their docstrings.

**Documentation:** extend the pipeline module docstring with a stage table (agent -> output key -> consumed by). Keep the shared event-loop rationale in `run_agent_async` accurate.

**Verify:** watch `tests/test_pipeline.py` (17 tests). CLI still works: `uv run python pipeline.py` (sample mode) and with `--resume`/`--job-description`.

---

## Phase 10 - Web API layer  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `app/main.py`, `app/schemas.py`, `app/files.py`, `app/upload.py`, `app/tasks.py`, `app/__init__.py`

**Inspect for:**

- `main.py`: duplicated `list_generated`/`list_uploaded` handlers (same query params, different dir) - extract one shared handler or document the parallel clearly. `_read_text_input` double-checks file size (already done in `_persist_upload`) - remove the redundant check with a comment.
- `files.py` (114): `list_files()` filter/sort/paginate pipeline is clear; verify `safe_dir_path`/`safe_delete_path` docstrings explain the traversal defense.
- `upload.py`: `extract_text()` text extraction for txt/docx/pdf - document each format path.
- `tasks.py`: in-memory `TaskRegistry`; small, verify thread/loop-safety notes.
- `schemas.py`: request/response models; ensure field descriptions.

**Simplify toward:**

- Keep endpoint bodies readable: the small helper functions (`_read_text_input`, `_to_response`, `_require_runner`) are already good. Expand their `Args`/`Returns`/`Raises`.
- The multipart form signature is duplicated between the sync and async pipeline endpoints (6 params). Extract one shared signature object only if it reads simpler; otherwise document the parallel.

**Documentation:** module docstring for `main.py` listing every route and its purpose. Note the SPA mount comment is already good.

**Verify:** watch `tests/test_web_health.py`, `test_web_pipeline.py`, `test_web_tasks.py`, `test_web_outputs.py`, `test_web_files.py`, `test_web_upload.py`, `test_web_spa.py`.

---

## Phase 11 - Backend tests & scratch scripts  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `tests/*.py` (23 files), `wip_testing/*.py` (7 files), `test_real_files.py`

**Inspect for:**

- `tests/conftest.py` (190): fixtures for the mocked `ModelClient` - verify fixture names read clearly and are documented.
- Per-agent contract tests: do they assert *behavior* rather than *implementation*, so the simplifications in Phases 3-6 do not churn them?
- `wip_testing/`: manual chained demos. Confirm each has a header comment stating which agents it exercises and how to run it.
- `test_real_files.py`: the live E2E guarded by `RUN_LIVE_PIPELINE`; verify the guard is documented.

**Simplify toward:**

- Add docstrings/header comments to any test file lacking them.
- Rename unclear test helpers; leave the test cases themselves mostly alone.

**Documentation:** file-top comments for every test file stating what it covers and the key fixture/hook it relies on.

**Verify:** `uv run pytest` full suite green (485 passed), `uv run ruff check .`.

---

## Part B - Frontend (React / TypeScript)

## Phase 12 - API layer: client, hooks, types, download  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/api/client.ts`, `ui/src/api/hooks.ts`, `ui/src/api/types.ts`, `ui/src/api/download.ts`

**Inspect for:**

- `client.ts`: `apiFetch` + `parseErrorDetail` - the error-parsing chain (string detail vs. array of `{msg}`) is subtle; make each step a named, documented branch.
- `hooks.ts`: `usePollTask` wraps `useTask` with a `useEffect` that invalidates `files` and fires `onDone`. Document *why* the files query is invalidated and *when* `onDone` fires. The `refetchInterval` predicate on `useTask` should be documented too.
- `types.ts`: TS mirrors of the backend response models - add comments mapping each type to its FastAPI schema (e.g., `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`) so drift is easy to spot.
- `download.ts` (9 lines): document the URL it builds.

**Simplify toward:**

- Extract the busy `parseErrorDetail` body into one or two small helpers (`_detailString(detail)`, `_detailArray(detail)`), each with a JSDoc line.
- Keep hooks one-per-concern; expand the top-of-file comment in `hooks.ts` describing the polling lifecycle.

**Documentation:** JSDoc on every exported function and hook. Header comment per file stating what it does and how it is used by pages.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `api/client.test.ts`, `api/hooks.test.ts`).

---

## Phase 13 - Result data coercion + shared result parts  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/pages/results/coerce.ts`, `ui/src/pages/results/parts.tsx`

**Inspect for:**

- `coerce.ts` (136): the `as*`/`pick*` helpers are already well-named. Verify each handles its edge cases explicitly and document them (`asString` drops empty strings, `pickNumber` parses numeric strings, etc.).
- `parts.tsx` (137): shared Tag/Chip/List renderers used across the result tabs - confirm props and behavior are documented so tab components read as declarative data.

**Simplify toward:**

- Add one-line JSDoc to every exported helper in `coerce.ts` stating exactly what it tolerates and returns.
- If any `pick*` helper composes two others in a dense one-liner, expand it into a couple of obvious lines.

**Documentation:** module header explaining "the backend result dicts are loosely typed; these helpers coerce unknown shapes safely".

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run`.

---

## Phase 14 - Results tabs (8 components)  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/pages/results/ParsedJDTab.tsx`, `ParsedResumeTab.tsx`, `GapAnalysisTab.tsx`, `RewrittenResumeTab.tsx`, `ATSTab.tsx`, `PolishedTab.tsx`, `CoverLetterTab.tsx`, `ResultsTabView.tsx`

**Inspect for:**

- `ResultsTabView.tsx`: the tab map (`TAB_KEYS`, `TAB_HEADERS`, `renderTabBody` switch) is clean. Add a comment that tab order mirrors pipeline output keys.
- Each tab: what data shape does it expect? Does it use the `coerce.ts` helpers or inline its own `as*` logic?
- Any tab rendering an HTML string (e.g., polished/cover letter) - document the trust boundary (content came from our own pipeline).

**Simplify toward:**

- Keep each tab a thin "read data via `pick*`, render via `parts.tsx`" component. Move repeated row/label markup into `parts.tsx` when it appears in 2+ tabs.
- Give every tab a one-line header comment (what it shows + which pipeline field it renders).

**Documentation:** per-component docstrings plus a note in `ResultsTabView.tsx` tying tab keys to the 7-agent output keys.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch the tab tests: `ATSTab.test.tsx`, `DownloadsRow.test.tsx`).

---

## Phase 15 - Run page & form helpers

**Files:** `ui/src/pages/RunPage.tsx`, `ui/src/pages/runForm.ts`

**Inspect for:**

- `RunPage.tsx` (224): the "active" status expression appears twice (`status === undefined || status === 'pending' || status === 'running'`). Extract an `isTaskActive(status)` helper (or a derived boolean) and reuse it in the button `disabled`, `label`, the status panel, and any other spot.
- `FileChosen`: the upload/remove toggle; document the `customUpload` PrimeReact behavior it relies on.
- `runForm.ts`: `validateRunInputs` + `buildRunFormData` - verify the "text wins over file" rule matches backend `_read_text_input` (AGENTS.md convention). Document it.

**Simplify toward:**

- Extract `isTaskActive`, `taskStatusLabel`, and the status-severity map next to `STATUS_SEVERITY`.
- Expand `handleSubmit` into 2-3 obvious steps with comments (validate -> show toast -> mutate -> capture task id).
- Give `FileChosen` and `RunPage` header comments describing the page flow (submit -> poll -> results + downloads).

**Documentation:** JSDoc on `validateRunInputs`/`buildRunFormData` and the file-vs-text precedence rule.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `RunPage.test.tsx`).

---

## Phase 16 - Files page

**Files:** `ui/src/pages/FilesPage.tsx`

238 lines - the largest page component.

**Inspect for:**

- The filter / sort / pagination param object passed to `useFiles(kind, params)`; the delete flow (selection state -> `useDeleteFiles` -> confirm dialog -> invalidate).
- Any repeated `asStringMap`/type coercion for file rows.

**Simplify toward:**

- Split the page into named sections: file-table config, filter bar, delete selection, toolbar. Extract a small `FileTable` component or at least add banner comments for each section.
- Name the state variables by intent (`selectedKeys`, `fileTypeFilter`, `searchQuery`, `page`).
- Add a header comment explaining the generated-vs-uploaded toggle and how downloads/delete map to the two listing kinds.

**Documentation:** JSDoc/header comment on every helper and callback.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `FilesPage.test.tsx`).

---

## Phase 17 - Models page, App shell, theme, toast, entry

**Files:** `ui/src/pages/ModelsPage.tsx`, `ui/src/App.tsx`, `ui/src/main.tsx`, `ui/src/index.css`, `ui/src/theme/*`, `ui/src/toast/*`, `ui/src/test/*`

**Inspect for:**

- `App.tsx`: `Shell` + nav items + routes - compact but clear; add a header comment walking the routing tree.
- `ModelsPage.tsx` (41): the models table; small, but get a header comment.
- `theme/useTheme.ts` + `ThemeToggle.tsx`: the persisted-theme hook; document storage key and initial-state fallback.
- `toast/ToastProvider.tsx` + `ToastContext.ts`: small context wrapper; document the `show` contract.
- `main.tsx`: PrimeReact theme import + mount; document the PrimeReact dependency and stylesheet.
- `test/setup.ts`, `test/utils.tsx`: the shared render helper; document what it provides (router/provider wrappers).

**Simplify toward:**

- Expand short files where a reader would have to guess (one-line JSDoc on each export is enough).
- Do not over-engineer; these files are already simple - this phase is mostly documentation.

**Documentation:** header/component comments for all of the above.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `theme/useTheme.test.ts`, `ThemeToggle.test.tsx`).

---

## Phase 18 - Frontend tests

**Files:** `ui/src/**/*.test.ts(x)` (9 files, 45 tests)

**Inspect for:**

- Do tests assert behavior over implementation? (Keeps Phases 12-17 low-churn.)
- Are test names readable as sentences? Rename only where meaning is unclear.
- Missing coverage for newly extracted helpers (e.g., `isTaskActive` if introduced in Phase 15) - add small focused tests there.

**Simplify toward:**

- Add file-top comment to each test file stating the unit under test.
- Extract repeated test setup (mocked fetch responses, wrapped renders) into `test/utils.tsx` when it appears in 2+ files.

**Documentation:** header comments only; behavior unchanged.

**Verify:** `npm test -- --run` green (45 passed).

---

## Part C - Closing

## Phase 19 - Repo-wide documentation consolidation

**Files:** `AGENTS.md`, `README.md`, `ui/README.md`, `docs/*.md` (8 guides), root scratch notes

**Inspect for:**

- `AGENTS.md`: verify the file/architecture map still matches after Phases 1-11 (new helper names, moved functions). Update the quick-command table and conventions (e.g., note the shared `load_json_safe` helper, the `_run_stage` pipeline helper).
- `README.md` / `ui/README.md`: quickstart accuracy.
- `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`, `docs/models.md`, `docs/TESTING.md`, `docs/logging-info.md`, `docs/skill-taxonomy.md`: check each against the code; fix drift found during Phases 1-18.
- Root scratch notes (`frontend-plan.md`, `frontend-tasks*.md`, `web-files-todo.md`, `resume-web-todo.md`, `resume-verify.md`, `bots.md`, `resume-todo.md`, `resume-done.md`): decide which are historical archives vs. still-actionable. Do not delete without the user's OK - recommend a `scratch/` move or a "completed" note in the text.

**Simplify toward:**

- Keep doc text consistent with the new, more verbose code names.
- Remove outdated "TODO/Phase X remains" lines whose work is already complete.

**Verify:** re-read each doc against the relevant module; no command examples broken.

---

## Phase 20 - Final verification & regression

**Goal:** prove nothing regressed after all phases.

1. Backend: `uv run pytest` (expect >= 485 passed), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`.
2. Frontend: `npm test -- --run` (expect >= 45 passed), `npm run lint`, `npx tsc -b`.
3. Manual smoke:
   - `uv run python basic.py`
   - `uv run python pipeline.py` (sample mode)
   - Web API up: `uv run uvicorn app.main:app` then `GET /health`, `GET /api/models`, `POST /api/pipeline/async` with the sample files, `GET /api/tasks/{id}` until complete, verify `output_files`.
   - Live E2E (Ollama running): `uv run python test_real_files.py`.
   - UI dev server: `npm run dev` from `ui/`, load Run page, run a pipeline, check tabs + downloads.
4. Diff review: `git diff` across all phases = documentation + readability only, no behavior change (spot-check output of rendered files before/after if desired).

**Exit criteria:** all suites green, manual smoke passes, `git status` clean after final commit, `simple.md` updated with a short "progress log" section listing which phases are done.

---

## Remaining Work Breakdown (Phases 4-20)

Phases 1-3 are complete (records in `simple-done.md`). The remaining work is
split into sub-tasks below. Work one phase at a time; commit per phase with a
phase-tagged message. Check each sub-task off in place as it is completed.

### Phase 4 - LLM-only agents + shared validation cleanup ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 4.1 Add `load_json_safe(text) -> dict | None` shared helper in `client/json_utils.py` with docstring explaining fence-stripping + guard. ✅ See `simple-done.md`.
- [x] 4.2 Standardize the `except json.JSONDecodeError, TypeError:` sites. Resolution: ruff 0.16 + `target-version = "py314"` auto-canonicalizes the parenthesized form to the PEP 758 comma form (`except A, B:`) with no formatter opt-out, so the tuple form is not enforceable in this repo's toolchain. All 13 sites across `json_utils.py`, `ats_compliance.py`, `cover_letter.py`, `resume_rewrite.py` already use the canonical form (verified via `ruff format --check` + git-clean diff). These guards get routed through `load_json_safe` in 4.4-4.6 anyway. ✅ See `simple-done.md`.
- [x] 4.3 `gap_analysis.py`: dedupe `_try_llm` scaffolding, verify module docstring ("LLM only, deterministic fallback", output model, failure = empty model). ✅ See `simple-done.md`.
- [x] 4.4 `ats_compliance.py`: route its `_validate_*` helpers through `load_json_safe`, expand `Returns True when ...` docstrings. ✅ See `simple-done.md`.
- [x] 4.5 `tone_polishing.py`: verify tone-guidance coercion is as clear as `models.py`; expand docstrings. ✅ See `simple-done.md`.
- [x] 4.6 Guardrails: `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`, `uv run pytest` (watch `tests/test_agent_gap_analysis.py`, `test_agent_ats_compliance.py`, `test_agent_tone_polishing.py`).
- [x] 4.7 Move Phase 4 to `simple-done.md`, mark complete in `simple.md`, commit.

### Phase 5 - Resume Rewrite agent + post-validation ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 5.1 Re-order file: public class first, then module helpers grouped (validation -> tailoring -> skill matching) with banner comments. ✅ See `simple-done.md`.
- [x] 5.2 Route `_validate_experience_count`, `_validate_certifications`, `_validate_companies` guards through `load_json_safe`. ✅ See `simple-done.md`.
- [x] 5.3 Full `Args:`/`Returns:` + one-line "why" on every post-validation helper. ✅ See `simple-done.md`.
- [x] 5.4 Convert dense `_skill_matches` conditionals into named helpers (`_exact_match`, `_substring_match`, `_token_match`). ✅ See `simple-done.md`.
- [x] 5.5 Verify `_ensure_chronological` / `_sanitize_skills` docstrings explain the `model_copy` never-mutate contract; `_tailor_skills` reads step-by-step. ✅ See `simple-done.md`.
- [x] 5.6 Module docstring: LLM -> Pydantic -> post-validation -> chronological -> sanitize -> fallback story. ✅ See `simple-done.md`.
- [x] 5.7 Guardrails (watch `tests/test_resume_rewrite_validation.py` 63 + `test_agent_resume_rewrite.py`), move to `simple-done.md`, commit.

### Phase 6 - Cover Letter agent (largest file) ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 6.1 Split helpers into banner sections: `# --- validation ---`, `# --- deterministic post-processors ---`, `# --- rendering/formatting ---`. ✅ See `simple-done.md`.
- [x] 6.2 Replace all seven `json.loads` guards with `load_json_safe`. ✅ See `simple-done.md`.
- [x] 6.3 Break any method over ~50 lines into named steps with `# 1.`/`# 2.` comments. ✅ See `simple-done.md`.
- [x] 6.4 Standardize placeholder-token handling (`[Company Name]`, `[Your Name]`) - every substitution one obvious path with comment. ✅ See `simple-done.md`.
- [x] 6.5 Module docstring covering agent contract (inputs, output model, fallback, two deterministic post-processors). ✅ See `simple-done.md`.
- [x] 6.6 Guardrails (watch `tests/test_agent_cover_letter.py` + `test_cover_letter_validation.py` 109), move to `simple-done.md`, commit.

### Phase 7 - Renderer, templates, formatter ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 7.1 Fix stale renderer.py header ("DOCX/PDF will be added in subsequent phases" -> they already exist). ✅ See `simple-done.md`.
- [x] 7.2 Document the two rendering paths (template-based `ResumeRenderer` vs `formatter.py` helpers) at top of each module. ✅ See `simple-done.md`.
- [x] 7.3 Extract one private `_render(template_key, context)` helper for the repeated "build context -> render -> clean output" sequence. ✅ See `simple-done.md`.
- [x] 7.4 Docstring per template dict (modern/classic/minimal/cover_letter) naming its style and which outputs it drives. ✅ See `simple-done.md`.
- [x] 7.5 Full class/method docstrings + `Args:`/`Returns:`/`Raises:` on `render_all`. ✅ See `simple-done.md`.
- [x] 7.6 Guardrails (keep output byte-identical; watch `tests/test_renderer.py` 43 + `test_formatter.py` 41), move to `simple-done.md`, commit.

### Phase 8 - Skill taxonomy & normalization ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 8.1 Make internal lookup read step-by-step (`# 1. exact canonical match`, `# 2. variant lookup`, ...). ✅ See `simple-done.md`.
- [x] 8.2 Rename single-letter/ambiguous locals; every method docstring covers unknown-skill + case handling. ✅ See `simple-done.md`.
- [x] 8.3 Module docstring: canonical taxonomy -> normalized forms; when to prefer `normalize_list` vs `match_skills`; cross-check `docs/skill-taxonomy.md`. ✅ See `simple-done.md`.
- [x] 8.4 Guardrails (watch `tests/test_skill_normalizer.py` 15), move to `simple-done.md`, commit.

### Phase 9 - Pipeline orchestration + CLI ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 9.1 Extract `_run_stage(runner, agent_name, *, prompt, output, rules, **context)` helper returning the resolved field. ✅ See `simple-done.md`.
- [x] 9.2 Convert the seven near-identical blocks in `_run_pipeline_core` to one-line `_run_stage` calls with `# 1. JD Parsing` ... `# 7. Cover Letter` comments. ✅ See `simple-done.md`.
- [x] 9.3 Verify `run_agent_async` instantiate-on-first-use comments + shared-event-loop rationale; `PipelineAgent` backward-compat docstring. ✅ See `simple-done.md`.
- [x] 9.4 Pipeline module docstring: stage table (agent -> output key -> consumed by); CLI `main()` plain sequential steps. ✅ See `simple-done.md`.
- [x] 9.5 Guardrails (watch `tests/test_pipeline.py` 17) + CLI smoke: `uv run python pipeline.py` (sample + with `--resume`/`--job-description`). ✅ See `simple-done.md`.

### Phase 10 - Web API layer ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 10.1 `main.py` module docstring listing every route + purpose; decide/document `list_generated` vs `list_uploaded` parallel. ✅ See `simple-done.md`.
- [x] 10.2 Remove redundant size double-check in `_read_text_input` (already in `_persist_upload`) with comment; expand `_read_text_input`/`_to_response`/`_require_runner` `Args`/`Returns`/`Raises`. ✅ See `simple-done.md`.
- [x] 10.3 `files.py`: verify `safe_dir_path`/`safe_delete_path` docstrings explain traversal defense. ✅ See `simple-done.md`.
- [x] 10.4 `upload.py`: document each extraction path (.txt/.docx/.pdf). ✅ See `simple-done.md`.
- [x] 10.5 `tasks.py`: thread/loop-safety notes; `schemas.py`: field descriptions. ✅ See `simple-done.md`.
- [x] 10.6 Guardrails (watch all `test_web_*.py`), move to `simple-done.md`, commit. ✅ See `simple-done.md`.

### Phase 11 - Backend tests & scratch scripts ✅ COMPLETED

- [x] 11.1 `tests/conftest.py` (190): fixture names read clearly, documented.
- [x] 11.2 Audit per-agent contract tests assert behavior over implementation.
- [x] 11.3 `wip_testing/*.py`: header comment per file (which agents, how to run).
- [x] 11.4 `test_real_files.py`: document `RUN_LIVE_PIPELINE` guard.
- [x] 11.5 File-top comment per test file (what it covers, key fixture/hook).
- [x] 11.6 Guardrails: full `uv run pytest` green + `uv run ruff check .`, move to `simple-done.md`, commit.

### Phase 12 - Frontend API layer ✅ COMPLETED

- [x] 12.1 `client.ts`: extract `_detailString(detail)` / `_detailArray(detail)` from `parseErrorDetail` with JSDoc.
- [x] 12.2 `hooks.ts`: document polling lifecycle, why files query invalidates, when `onDone` fires, `refetchInterval` predicate.
- [x] 12.3 `types.ts`: comment mapping each type to its FastAPI schema (e.g. `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`).
- [x] 12.4 `download.ts`: document the URL it builds.
- [x] 12.5 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `api/client.test.ts`, `api/hooks.test.ts`).

### Phase 13 - Result data coercion + shared result parts ✅ COMPLETED

- [x] 13.1 `coerce.ts`: one-line JSDoc on every export (what it tolerates/returns); expand dense `pick*` one-liners.
- [x] 13.2 `parts.tsx`: document props/behavior of each shared renderer.
- [x] 13.3 Module header: "backend result dicts are loosely typed; these helpers coerce unknown shapes safely".
- [x] 13.4 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`.

### Phase 14 - Results tabs (8 components) ✅ COMPLETED

- [x] 14.1 `ResultsTabView.tsx`: comment tying `TAB_KEYS` to the 7-agent output keys/order.
- [x] 14.2 Each tab: one-line header (what it shows + which pipeline field); consistent use of `coerce.ts` helpers.
- [x] 14.3 HTML-string tabs (polished/cover letter): document trust boundary (content from our own pipeline).
- [x] 14.4 Extract repeated row/label markup into `parts.tsx` when it appears in 2+ tabs.
- [x] 14.5 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `ATSTab.test.tsx`, `DownloadsRow.test.tsx`).

### Phase 15 - Run page & form helpers ✅ COMPLETED

- [x] 15.1 Extract `isTaskActive(status)` and reuse in button `disabled`/`label`, status panel, etc.
- [x] 15.2 Extract `taskStatusLabel` + status-severity map next to `STATUS_SEVERITY`.
- [x] 15.3 Expand `handleSubmit` into 2-3 obvious steps with comments (validate -> toast -> mutate -> capture task id).
- [x] 15.4 `FileChosen`: document `customUpload` behavior; header comments for the page flow (submit -> poll -> results + downloads).
- [x] 15.5 `runForm.ts`: JSDoc on `validateRunInputs`/`buildRunFormData`; document "text wins over file" matches backend `_read_text_input`.
- [x] 15.6 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `RunPage.test.tsx`).

### Phase 16 - Files page ✅ COMPLETED

- [x] 16.1 Split into named sections (file-table config, filter bar, delete selection, toolbar) via banner comments or a `FileTable` component.
- [x] 16.2 Name state by intent (`selectedKeys`, `fileTypeFilter`, `searchQuery`, `page`).
- [x] 16.3 Header comment: generated-vs-uploaded toggle; how downloads/delete map to the two listing kinds.
- [x] 16.4 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `FilesPage.test.tsx`).

### Phase 17 - Models page, App shell, theme, toast, entry ✅ COMPLETED

- [x] 17.1 `App.tsx`: header comment walking the routing tree (Shell + nav + routes).
- [x] 17.2 `ModelsPage.tsx`: header comment.
- [x] 17.3 `theme/useTheme.ts` + `ThemeToggle.tsx`: document storage key + initial-state fallback.
- [x] 17.4 `toast/ToastProvider.tsx` + `ToastContext.ts`: document the `show` contract.
- [x] 17.5 `main.tsx`: document PrimeReact theme import + stylesheet dependency.
- [x] 17.6 `test/setup.ts` + `test/utils.tsx`: document the shared render helper (router/provider wrappers).
- [x] 17.7 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`.

### Phase 18 - Frontend tests ✅ COMPLETED

- [x] 18.1 File-top comment per test file stating the unit under test.
- [x] 18.2 Extract repeated setup (mocked fetch, wrapped renders) into `test/utils.tsx` where it appears in 2+ files.
- [x] 18.3 Add focused tests for newly extracted helpers (e.g. `isTaskActive`) from Phase 15.
- [x] 18.4 Guardrails: `npm test -- --run` green.

### Phase 19 - Repo-wide documentation consolidation

- [x] 19.1 `AGENTS.md`: verify file/architecture map after Phases 1-11 (new helpers `load_json_safe`, `_run_stage`); update quick-command table + conventions. ✅ See `simple-done.md`.
- [ ] 19.2 `README.md` / `ui/README.md`: quickstart accuracy.
- [ ] 19.3 Cross-check `docs/*.md` (8 guides) against code; fix drift found during Phases 1-18.
- [ ] 19.4 Root scratch notes: classify archive vs actionable; recommend `scratch/` move or "completed" note (no deletion without user OK).
- [ ] 19.5 Remove outdated "TODO/Phase X remains" lines for completed work.

### Phase 20 - Final verification & regression

- [ ] 20.1 Backend: `uv run pytest` (>=485), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`.
- [ ] 20.2 Frontend: `npm test -- --run` (>=45), `npm run lint`, `npx tsc -b`.
- [ ] 20.3 Manual smoke: `basic.py`, `pipeline.py` sample mode, web API health/models/pipeline/tasks, live E2E (`test_real_files.py` with Ollama), `npm run dev` UI run.
- [ ] 20.4 Diff review spot-check rendered output before/after; `git status` clean after final commit.
- [ ] 20.5 Add a short "progress log" section to `simple.md` listing completed phases (archive the full plan in `simple-done.md`).

### Phase 21 - Documentation Cleanup

- [ ] 21.1 Move all markdown files to a single directory named docs
- [ ] 21.2 Root README.md needs to be less than 500 lines with a quickstart section that explains to to get started in 10 minutes or less and links to detailed README.md file
- [ ] 21.3 Create a more expansive/detailed README.md in the docs directory which contains:
  - [ ] 21.3.1 Detailed instructions on how to get started
  - [ ] 21.3.2 Detailed examples on all command line switches/options
  - [ ] 21.3.3 Common issues and fixes
- [ ] 21.4 Make sure that there is a README.md in the root UI/frontend directory
- [ ] 21.5 Make sure that there is a README.md in the root directory
- [ ] 21.6 All markdown files should link to previous and next file, sorted alphabetically with a link docs/README.md file
- [ ] 21.7 Ensure all markdown files are up to date.
- [ ] 21.8 No markdown linting errros in any of the markdown files
