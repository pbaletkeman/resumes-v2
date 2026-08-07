# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

> Note: the FastAPI web API layer (`app/`) is a separate workstream from the core pipeline. Its work log lives in `resume-web-todo.md` (API routes) and `web-files-todo.md` (file-management endpoints), not here.

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), Phase 4.3 (post-validation for rewrite/cover letter, fallback templates, logging, prompt strengthening, `company_name` — see `resume-done.md`), Phase 5.2 (pipeline wiring — all 7 dedicated classes wired), Phase 6.A (output formatting helpers), Phase 6.B (template renderer: `render_all()`, DOCX/PDF — see `resume-done.md`), Phase 8-contact info, Phase 8.5 (skill normalization & canonical taxonomy), Phase 9 (cover letter creation fixes — see `resume-done.md`), and 362 unit tests. The items below are what remains.

---

## Verification bugs (fixed 2026-08-06 during `resume-verify.md` live runs)

Two `pipeline.py` bugs surfaced only under a live Ollama run and were fixed as
part of the verification plan; both are recorded here for traceability.

### V1 — Event-loop lifecycle: `RuntimeError: Event loop is closed` — ✅ FIXED

`AgentRunner.run_agent()` wrapped each of the 7 agents in its own
`asyncio.run()`, opening+closing a fresh event loop per agent. The dedicated
agent classes share a single `ollama.AsyncClient` bound to the first loop, so
agent 1 (`jd_parsing_agent`) succeeded but agent 2 (`resume_parsing_agent`)
and later failed with `RuntimeError: Event loop is closed`.

**Fix:** added `AgentRunner.run_agent_async()` (async dispatch) and made sync
`run_agent()` delegate via one `asyncio.run()`. `run_resume_pipeline()` now
runs all 7 agents under a single event loop through a new `_run_pipeline_core()`
coroutine, wrapped once in `asyncio.run()`.

### V2 — `_extract_field` returns whole model instead of named field — ✅ FIXED

`pipeline._extract_field()` only handled `dict` results, so when a dedicated
agent returned a Pydantic model it returned the entire model rather than its
named field. With ATS this passed an `ATSComplianceOutput` object into
`tone_polishing_agent`, which raised
`TypeError: object of type 'ATSComplianceOutput' has no len()`.

**Fix:** added a `getattr` branch so model results yield their named field
(e.g. `final_resume`, `cover_letter`) before falling back to the object itself.

---

## Phase 7: Testing & Docs

### 7.1 Create `test_real_files.py`

**Status:** ❌ NOT done

A single end-to-end integration test that runs the full 7-agent pipeline against the real sample files. It is deliberately **not** in `tests/` (which runs under pyright's excluded directory and the deterministic suite) — it depends on a live Ollama, so it is run manually via `uv run python test_real_files.py` (or `uv run pytest test_real_files.py`) and exercises the true agent chain rather than mocks. If Ollama is down, the test should raise a clear `LLMConnectionError`-driven skip/failure message rather than silently pass.

**Depends on:** 6.B.8 (`pipeline.py` wired with `candidate_name`/`company_name` + `render_all()`), 7.2 `test_pipeline.py` for the mocked-agent coverage already in place.

**Sub-tasks:**

- **7.1.1** Create `test_real_files.py` at repo root.
  - [ ] Create `test_real_files.py` at repo root (outside `tests/`).
  - [ ] Add `main()`-style entry (`if __name__ == "__main__":`) so it doubles as runnable script + pytest module.
  - [ ] Call `configure_logging()` at import/module scope.
- **7.1.2** Add a file-loading helper.
  - [ ] Add `_load_job()`/`_load_resume()` (or inline `Path(...).read_text(...)`).
  - [ ] Read `sample/jobs/3Pillar.txt` and `sample/resume/Peter-Letkeman-Resume.txt`.
  - [ ] Assert both files exist first with a clear `FileNotFoundError` message.
- **7.1.3** Run the pipeline.
  - [ ] Call `run_resume_pipeline(job_description, resume_text)` with both texts.
  - [ ] Capture the returned result dict.
- **7.1.4** Structure-existence assertions.
  - [ ] Assert all 7 agent output keys present: `parsed_job_description`, `parsed_resume`, `tailoring_strategy`, `rewritten_resume`, `ats_compliance`, `polished_resume`, `cover_letter`.
- **7.1.5** JD parsing assertions.
  - [ ] Assert `result["parsed_job_description"]["role_title"]` is non-empty.
  - [ ] Assert `result["parsed_job_description"]["required_skills"]` is a non-empty list.
- **7.1.6** Resume parsing assertions.
  - [ ] Assert `result["parsed_resume"]["experience"]` is a list (and non-empty).
  - [ ] Assert the parsed name matches/corresponds to the input file.
- **7.1.7** Gap analysis assertions.
  - [ ] Assert `result["tailoring_strategy"]["missing_skills"]` exists (list, ≥1 entry on a normal 3Pillar run).
- **7.1.8** Rewrite/ATS/polish assertions.
  - [ ] Assert `ats_optimized_resume` and `polished_resume` are truthy non-empty (accept a dict, NOT a string).
- **7.1.9** Cover letter word-count assertion.
  - [ ] Assert the `cover_letter` output is 450–600 words.
  - [ ] Compute word count on text content (strip Markdown).
  - [ ] Log the computed count.
- **7.1.10** Chronological ordering assertion.
  - [ ] Assert `parsed_resume.experience` ordered most-recent-first by comparing parsed date ranges.
  - [ ] Log the ordering it found.
- **7.1.11** No-added-experience assertion.
  - [ ] Compare the set of company/role titles in input resume vs. rewritten/polished output.
  - [ ] Assert nothing new was introduced (no fabricated experience).
- **7.1.12** Certification-preservation assertion.
  - [ ] Assert every certification in the input resume text still appears in the output (compare normalized lowercase names).
- **7.1.13** Output-file assertions.
  - [ ] Second call (or reuse) with `candidate_name="..."` and `company_name="..."` so `render_all()` writes files.
  - [ ] Assert the returned `output_files` dict has the 6 expected keys.
  - [ ] Assert each written `Path` exists and is non-empty.
- **7.1.14** Naming-pattern assertion.
  - [ ] Assert each output filename matches `{YYYYMMDD_HHMM}_{slug(candidate)}_{slug(company)}_{doc_type}.{ext}` (e.g. regex `^\d{8}_\d{4}_.+$`).
  - [ ] Exercises `build_output_path()` format for real files.
- **7.1.15** Summary print.
  - [ ] `print()` a compact summary table (per-agent non-empty ✓/✗, cover letter word count, output file list, total elapsed time).
- **7.1.16** Deterministic guard.
  - [ ] Add env-var/module flag (e.g. `RUN_LIVE_PIPELINE`) so the test is skipped (not failed) under deterministic `pytest` run when live Ollama is unavailable.

**Files changed:** new file `test_real_files.py`

---

### 7.2 Add unit tests (`tests/`) — remaining

**Status:** ⚠️ PARTIAL — existing deterministic tests are done; agent + pipeline tests remain

**What exists now:** 362 tests across 9 files:

- `tests/test_format_detector.py` — 46 tests covering all `FormatDetector` static extraction methods + regex-only parse flows
- `tests/test_jd_parsing.py` — 19 tests (`_extract_company_name` + `_sync_company_name`)
- `tests/test_resume_rewrite_validation.py` — 63 tests (§4.3.A checks + §C skill tailoring + §D fallback logging + Phase 9 `_ensure_chronological` ordering)
- `tests/test_cover_letter_validation.py` — 109 tests (§4.3.B checks + §C fallback builder + §D fallback logging + Phase 8 contact-info post-processing + Phase 9 `_apply_company_name`/`_apply_candidate_name`)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 15 tests (shared parser + JSON Schema helpers)
- `tests/test_formatter.py` — 41 tests (Phase 6.A formatting helpers)
- `tests/test_renderer.py` — 43 tests (Phase 6.B renderer + Phase 8 contact-line rendering — archived in `resume-done.md` §6.3 and §8)
- `tests/test_skill_normalizer.py` — 15 tests (Phase 8.5 SkillNormalizer canonical taxonomy — archived in `resume-done.md` §8.5)

**Still needed:**

- `tests/test_agents.py` — mock `ModelClient`, verify prompts and JSON validation
- `tests/test_pipeline.py` — end-to-end with mocked agents

#### 7.2.1 Agent unit tests — per-agent behaviour with a mocked `ModelClient`

**Status:** ❌ NOT done

Verify each dedicated agent runs its `run()` → `_try_llm()` → `_parse_json()` → validation → fallback contract against a fake client that injects canned responses, with **no real LLM**. Because the built-in structured outputs enforce provider JSON, some of these are the only place the parse/validation layer is exercised off-network.

**Pre-requisites.** Define a `FakeClient` (or reuse a `StubModel` from `tests/conftest.py`).
- [ ] Create a `FakeClient`/`StubModel` whose `chat()` returns a fixed payload from a fixture map keyed by `purpose`.
- [ ] Record the call args so each test can assert `json_schema`/`response_format`/`purpose`/`output` as specified in AGENTS.md.
- [ ] Add `FakeClient` fixture to `tests/conftest.py` (if none exists).

- **7.2.1.1** Create `tests/test_agent_jd_parsing.py`.
  - [ ] Test: valid JSON → `JDParsingOutput`.
  - [ ] Test: malformed JSON → fallback.
  - [ ] Test: `LLMConnectionError` → fallback.
  - [ ] Test: `strict=True` retry round on second exception.
- **7.2.1.2** Create `tests/test_agent_resume_parsing.py`.
  - [ ] Test: valid parse.
  - [ ] Test: malformed JSON → fallback.
  - [ ] Test: missing `experience` key → fallback.
  - [ ] Test: dict-where-list coercion via `_coerce_str_list`.
- **7.2.1.3** Create `tests/test_agent_gap_analysis.py`.
  - [ ] Test: LLM happy path.
  - [ ] Test: LLM returning `None` → deterministic missing-skills fallback.
  - [ ] Test: prompt receives `missing_skills`.
- **7.2.1.4** Create `tests/test_agent_resume_rewrite.py`.
  - [ ] Test: post-validation path (§4.3.A) applies.
  - [ ] Test: strict-mode retry toggles.
  - [ ] Test: invalid-date / empty-tone coercion.
- **7.2.1.5** Create `tests/test_agent_ats_compliance.py`.
  - [ ] Test: compliance checks run on a non-compliant payload and return fix suggestions.
  - [ ] Test: fallback when the frame is absent.
- **7.2.1.6** Create `tests/test_agent_tone_polishing.py`.
  - [ ] Test: `tone_guidance` dict→string coercion (`_coerce_tone_guidance`).
  - [ ] Test: fallback when LLM fails.
- **7.2.1.7** Create `tests/test_agent_cover_letter.py`.
  - [ ] Test: uses `_sync_company_name`-style verification.
  - [ ] Test: word-count / fallback-builder.
  - [ ] Test: `CoverLetterOutput` fill.

**(Alternate, factored layout)** — If preferred, one slim `tests/test_agents.py` module with parametrized fixtures that cover items 7.2.1.1–7.2.1.7 above, rather than 7 separate files; the AGENTS.md convention favors function-specific modules, so pick the one that matches `tests/test_jd_parsing.py`/`tests/test_formatter.py` style.

#### 7.2.2 `tests/test_pipeline.py` — pipeline wiring with mocked agents

**Status:** ⚠️ NOT done

**What it covers:** `AgentRunner` and `run_resume_pipeline()` orchestration (not the real LLM). Because the real agents are instantiated by the runner via `DEFAULT_AGENT_CLASSES`, the cleanest seam is to either (a) patch the agent classes in the module, or (b) swap `DEFAULT_AGENT_CLASSES` with a list of minimal fakes. This validates ordering, input/output threading, and the `output_files` dict without touching Ollama.

- **7.2.2.1 — async end-to-end.**
  - [ ] `async` test that runs `run_resume_pipeline(jd, resume, candidate_name=..., company_name=...)` with stub agents returning fixed `ParsedJDOutput`/`ParsedResumeOutput`/etc.
  - [ ] Assert the 7 keys + `output_files` (6 keys) are present.
- **7.2.2.2 — dependency threading.**
  - [ ] Test that each agent in the chain receives the preceding agent's output.
  - [ ] Assert via stub `run()` that records its `inputs` argument.
- **7.2.2.3 — error propagation.**
  - [ ] Stub an agent that raises `LLMConnectionError`.
  - [ ] Assert `run_resume_pipeline()` surfaces/logs the failure and does not hallucinate a missing output key.
- **7.2.2.4 — `company`/`candidate` passthrough.**
  - [ ] Verify the `name`/`company` args reach the renderer call and `render_all()`.
  - [ ] Assert an empty `candidate_name` skips rendering (no `output_files`).
- **7.2.2.5 — `AgentRunner` unit.**
  - [ ] `AgentRunner.run(..)` calls the right agent.
  - [ ] It carries `purpose`/`inputs`/`output`/`response_format`/`json_schema`.
  - [ ] It maps LLM failures to the documented error-type handling.

**Files changed:** new files `tests/test_agents.py` (+7 split files per layout), `tests/test_pipeline.py`, plus `tests/conftest.py` if no `FakeClient` fixture exists yet.

---

### 7.3 Populate `docs/`

**Status:** ❌ NOT done

`docs/` directory has 3 existing files: `TESTING.md`, `models.md`, `logging-info.md`. Add four new guides. Each docs file should end with a `## References` section pointing at the relevant `client/*.py` and `resume-*.md` files it documents.

#### 7.3.1 (`docs/architecture.md`)

- **7.3.1.1** Write a **system overview**.
  - [ ] Describe the 7-agent chain (JD→Resume Parsing→Gap Analysis→Resume Rewrite→ATS→Tone→Cover).
  - [ ] Describe the two provider backends (Ollama / OpenAI).
  - [ ] Describe the renderer/formatter layers.
- **7.3.1.2** Add a **data-flow diagram** (ASCII or Mermaid).
  - [ ] Show input files.
  - [ ] Show agent order.
  - [ ] Show intermediate Pydantic models.
  - [ ] Show output artifacts (`output_files`).
- **7.3.1.3** Describe the **agent chain** and each transition's input/output contract.
  - [ ] Mirror the pipeline-flow block in `AGENTS.md`.
  - [ ] Note where `ResumeRenderer` hooks in.
  - [ ] End file with a `## References` section.

#### 7.3.2 (`docs/agents.md`)

- **7.3.2.1** For each of the 7 agents add **purpose**, the **prompt** it sends, and **input/output schema**.
  - [ ] Reference `client/models.py` model names (e.g. `JDParsingOutput`, `RewriteOutput`).
- **7.3.2.2** Note the **fallback path** per agent.
  - [ ] Regex fallback for parsing agents.
  - [ ] Deterministic templates for rewrite/cover.
  - [ ] When each fallback triggers.
- **7.3.2.3** Cross-link each agent to its implementation file.
  - [ ] Link to `client/templates/` (or `client/agents/`) files so the doc stays truthful to the code.
  - [ ] End file with a `## References` section.

#### 7.3.3 (`docs/usage.md`)

- **7.3.3.1** **Quickstart.**
  - [ ] Document prereqs (`ollama pull`, `uv sync`).
  - [ ] Document the command to run `uv run python test_pipeline.py`/`pipeline.py`.
  - [ ] Document expected outputs (files + console summary).
- **7.3.3.2** **Model configuration.**
  - [ ] Document env-var overrides (`MODEL_PROVIDER`, `MODEL_NAME`, per-agent `{AGENT}_MODEL`/`{AGENT}_PROVIDER`).
  - [ ] Explain how `config/agents.py` picks them.
- **7.3.3.3** **Adding a custom agent.**
  - [ ] Document the steps.
  - [ ] Document the `DEFAULT_AGENT_CLASSES` / registry harness a new class must satisfy.
  - [ ] End file with a `## References` section.

#### 7.3.4 (`docs/api.md`)

- **7.3.4.1** Document the **`ModelClient`** ABC.
  - [ ] `chat()`, `response_format`, optional `json_schema`.
  - [ ] `OllamaClient`/`OpenAIClient` implementations.
- **7.3.4.2** Document **`Agent`**/`PipelineAgent`/`AgentRunner`.
  - [ ] Constructor signatures.
  - [ ] `run()`/`__call__`.
  - [ ] The `purpose`/`inputs`/`output`/`rules` contract.
- **7.3.4.3** Document **`ResumeRenderer`** public API + `formatter` helpers.
  - [ ] `render_plaintext`, `render_markdown`, `render_cover_letter_*`, `render_docx`, `render_pdf`, `render_all`, `build_output_path`.
  - [ ] The `formatter` helpers.
  - [ ] End file with a `## References` section.

**Files changed:** new files `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`

---

## File Structure (Target — items still to create)

```plaintext
tests/
  test_agents.py                  # NEW (Phase 7.2)
  test_pipeline.py                # NEW (Phase 7.2)
docs/
  architecture.md                 # NEW (Phase 7.3)
  agents.md                       # NEW (Phase 7.3)
  usage.md                        # NEW (Phase 7.3)
  api.md                          # NEW (Phase 7.3)
test_real_files.py                # NEW (Phase 7.1)
```

All other files referenced across Phases 1–9 (agents, clients, templates, formatter, renderer, skill normalizer, agents/skills packages, `tests/`) exist — see `resume-done.md`.

---

## Remaining Execution Order

| Step | Phase | Status | Depends On | Estimated Files Changed |
| ------ | ------- | -------- | ------------ | ------------------------ |
| 1 | 7.1: `test_real_files.py` integration test | ❌ TODO | all phases done | 1 |
| 2 | 7.2.1: agent tests (`tests/test_agent_*.py` or `test_agents.py`) | ❌ TODO | all phases done | 7 to 8 |
| 3 | 7.2.2: pipeline tests (`tests/test_pipeline.py`) | ❌ TODO | Step 2 | 1 |
| 4 | 7.3.1: `docs/architecture.md` | ❌ TODO | all | 1 |
| 5 | 7.3.2: `docs/agents.md` | ❌ TODO | Step 4 | 1 |
| 6 | 7.3.3: `docs/usage.md` | ❌ TODO | all | 1 |
| 7 | 7.3.4: `docs/api.md` | ❌ TODO | Step 4 | 1 |