# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), Phase 4.3 (post-validation for rewrite/cover letter, fallback templates, logging, prompt strengthening, `company_name` — see `resume-done.md`), Phase 5.2 (pipeline wiring — all 7 dedicated classes wired), Phase 6.A (output formatting helpers), Phase 6.B (template renderer: `render_plaintext`/`render_markdown` + cover letter rendering + `build_output_path()` + DOCX + PDF generation + `render_all()` + pipeline wiring + unit tests), and 306 unit tests. The items below are what remains.

---

> Phase 4.3 (Fix LLM Fallback Falsehoods — validation, fallback templates, logging, prompt strengthening, `company_name`) is **complete** — archived in `resume-done.md` §4.3.
>
> Phase 5.2 (wire up the 7-agent pipeline) is **complete** — archived in `resume-done.md` §5.2.
>
> Phase 6.A (output formatting helpers — `client/formatter.py` + `tests/test_formatter.py`) is **complete** — archived in `resume-done.md` §6.2.
>
> Phase 6.B (template renderer — `render_plaintext`/`render_markdown` + cover letter rendering + `build_output_path()` + DOCX + PDF + `render_all()` + pipeline wiring + `tests/test_renderer.py`) is **complete** — archived in `resume-done.md` §6.3.

---

## Phase 9: Cover Letter Creation Fixes (a/b/c)

Fixes for three defects in cover letter creation that surface on live runs: experience entries coming back out of chronological order, the company name being taken from the candidate's resume (or left as `[Company Name]`), and the candidate name left as `[Your Name]`. All three are handled with **pure Python post-processing — no additional LLM calls**.

### 9.1 Chronological ordering of experience (in `resume_rewrite.py`)

**Status:** ❌ NOT DONE

Currently `client/agents/resume_rewrite.py` `_try_llm()` calls `_validate_chronological(result)` and **rejects** the whole rewrite when the experiences are out of order, which drops the entire LLM result and falls back to `_parsed_to_rewrite()`. Instead of rejecting, we should **intercept and sort** the experience section so the rest of the LLM's work is preserved.

**Sub-tasks:**

- **9.1.1** Replace the reject path in `_try_llm()` (currently lines 228–230: `if not _validate_chronological(result): logger.warning("Output experiences not in chronological order -- rejecting"); return None`) with a call to a new `_ensure_chronological(result)` post-processor. Log the ordering message, but reorder the entries in place instead of returning `None`.
- **9.1.2** Add `_ensure_chronological(result: RewriteOutput) -> RewriteOutput` — sorts `result.experience` by `_extract_start_year(entry.dates)` descending (most-recent-first). Entries whose start year is `None` (unparseable dates) are treated as preserved at the end in their original relative order — do **not** drop entries. Use `sorted()` with a key that falls back to the entry's original index so the sort is stable and lossless. No LLM call.
- **9.1.3** Keep `_validate_chronological` only as an early signal/log (optional `DEBUG`); the post-processor is the source of truth. If a start year is missing for **all** entries, leave the list unchanged (nothing to sort).
- **9.1.4** Consider sorting the **input** `parsed_resume` experience once in `ResumeParsingAgent._regex_fallback()` (and/or after LLM parse) so downstream agents always receive most-recent-first data, making the rewrite sort a cheap idempotent no-op in the common case.
- **9.1.5** Add tests in `tests/test_resume_rewrite_validation.py` — entries sorted correctly including a None-year entry preserved at the tail; a fully-unsortable list left unchanged; the existing out-of-order tests that previously asserted `None` (rejection) are updated to assert a sorted result is returned instead.

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/resume_parsing.py`, `tests/test_resume_rewrite_validation.py`

---

### 9.2 Company Name must come from the JD, not the candidate's resume

**Context:** The cover letter occasionally uses a **company name pulled from the candidate's resume** (a past employer), or the literal placeholder `[Company Name]`. The source of truth is `JDParsingOutput.company_name` (Phase 4.3.F — employer name exactly as written in the JD), already surfaced through the shared `_company_from()` helper in `cover_letter.py`. Two failure modes to fix:

1. **Wrong company from the resume:** The `_try_llm()` prompt feeds the JD, and the LLM segfaults into using a resume company or a generic phrase instead of the target employer.
2. **Literal `[Company Name] placeholder** emitted by the letter (or its name).**

**Sub-tasks:**

- **9.2.2 Strengthen the prompt so the LLM never picks / restates a wrong name:** Rename prompt-driven refs. In `cover_letter.py` `_try_llm()` (normal rules), after validating, add the company name. When the emitted letter's name is missing / wrong, post-fix it.
- **9.2.2 Add a deterministic company-name normalizer** `_apply_company_name(result: CoverLetterOutput, jd_json: str) -> CoverLetterOutput` that:
  - Resolves the target via `_company_from(jd_data)` (top-level `company_name`, else `company_signals["company_name"]`).
  - Accepts a check first via `_check_company`;/ only warn when mismatched.
- **9.2.3** If the letter still reads `[Company Name]` (or `[Company]`, `<Company Name>`, `[Employer Name]`), replace that token with the resolved JD company name via `str.replace`.
- **9.2.4** When the target company is **not present** in the letter and the letter instead names a **candidate-resume company** (i.e., a company from `parsed_resume.experience[*].company` appears but the JD company does not), substitute the first occurrence of the resume-company token with the JD company name. Only apply this when the substitution target differs from the JD name, and log the substitution at `INFO`. Do not run a second LLM call.
- **9.2.5** In `_build_fallback_cover_letter()`, confirm the fallback already uses `_company_from` (it does) and never emits `[Company Name]` (verify/reassert).
- **9.2.6** Add tests in `tests/test_cover_letter_validation.py` — `[Company Name]` placeholder replaced; letter naming a resume-company substituted with the JD company; letter already correct left unchanged.

**Files changed:** `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

---

### 9.3 Candidate Name must come from the candidate's resume

**Context:** The cover letter's signature / opening sometimes contains `[Your Name]`. The candidate name is not currently carried through the pipeline — `ResumeParsingOutput` (in `client/models.py`) has **no `name` field**, even though `FormatDetector` already extracts `ParsedResume.name`. So the cover letter agent cannot know the candidate's real name. The fallback `_build_fallback_cover_letter()` already does `_read_str(resume_data, "name").strip() or "Candidate"`, which returns `"Candidate"` today because the field is absent.

**Sub-tasks:**

- **9.3.1** Add `name: str = ""` to `ResumeParsingOutput` in `client/models.py` and thread it through:
  - In `ResumeParsingAgent._regex_fallback()`, set `name=parsed.name` from the `FormatDetector` result (already extracted).
  - For the LLM path (`_try_llm`), add `name` to `_SYSTEM_PROMPT` field list + a rule "Extract the candidate's full name exactly as it appears at the top of the resume; empty string if absent."
  - Ensure no duplicate: `ResumeParsingOutput` already validates a `str` field via its own validator; add `name` to the schema's field list in the prompt.
- **9.3.2** In `cover_letter.py` `_try_llm()`, when `_apply`-ing the candidate name post-output `result`, read the candidate name from `resume_json` (not a placeholder). Add `_apply_candidate_name(result, resume_json) -> CoverLetterOutput` that replaces `[Your Name]` / `[Your Name]`→ resolved name residue with the resolved resume name. If the name resolves empty, leave untouched.
- **9.3.3** In `_build_fallback_cover_letter()` the existing `_read_str(resume_data, "name").strip() or "Candidate"` now resolves to the real name once 9.3.1 lands.
- **9.3.4** Add tests — `name` flows LLM-regex → `ResumeParsingOutput.name`; placeholder `[Your Name]` replaced; empty name leaves the letter unchanged (or emits "Candidate"/nothing).

**Files changed:** `client/models.py`, `client/agents/resume_parsing.py`, `client/agents/cover_letter.py`, `tests/test_resume_rewrite_validation.py` (no), `tests/test_cover_letter_validation.py` (name-replacement)

---

### 9.4 Cross-cutting notes

- `_try_llm()` must stay pure (serialize/validate only, no side effects) per the AGENTS.md convention; all string replacement/sorting runs on the validated `CoverLetterOutput`/`RewriteOutput` inside `_try_llm` **after** Pydantic validation, mirroring how `_coerce_*` validators and `_sanitize_skills` already work.
- The ASCII-only convention applies to any new placeholder/token matching the LLM output. Use straight tokens like `[Company Name]` / `[Your Name]`.
- Verify with `uv run pytest`, `uv run ruff check .`, `uv run pyright .`, and a manual `uv run python wip_testing/test_cover_letter.py` / `test_resume_rewrite.py` run.

---

## Phase 6: Output & Validation

**✅ COMPLETE** — Phase 6.A (output formatting helpers) and Phase 6.B (template-based multi-format renderer) are done. See `resume-done.md` §6.2 (6.A) and §6.3 (6.B.1–6.B.9 renderer, DOCX/PDF, `render_all()`, pipeline wiring, `tests/test_renderer.py`, dependency notes).

---

(Phase 6.B.3–6.B.9 detailed notes and the 6.10 dependency cautions are archived in `resume-done.md` §6.3.)

## Phase 7: Testing & Docs

### 7.1 Create `test_real_files.py`

**Status:** ❌ NOT done

A single end-to-end integration test that runs the full 7-agent pipeline against the real sample files. It is deliberately **not** in `tests/` (which runs under pyright's excluded directory and the deterministic suite) — it depends on a live Ollama, so it is run manually via `uv run python test_real_files.py` (or `uv run pytest test_real_files.py`) and exercises the true agent chain rather than mocks. If Ollama is down, the test should raise a clear `LLMConnectionError`-driven skip/failure message rather than silently pass.

**Depends on:** 6.B.8 (`pipeline.py` wired with `candidate_name`/`company_name` + `render_all()`), 7.2 `test_pipeline.py` for the mocked-agent coverage already in place.

**Sub-tasks:**

- **7.1.1** Create `test_real_files.py` at repo root with a `main()`-style entry (`if __name__ == "__main__":`) so it doubles as a runnable script and a pytest module. Include `configure_logging()` at import/module scope.
- **7.1.2** Add a **file-loading helper** (`_load_job()`/`_load_resume()`, or inline `Path(...).read_text(...)`) that reads `sample/jobs/3Pillar.txt` and `sample/resume/Peter-Letkeman-Resume.txt`, asserting both files exist first with a clear `FileNotFoundError` message.
- **7.1.3** Call `run_resume_pipeline(job_description, resume_text)` with both texts. Capture the returned result dict.
- **7.1.4** **Structure-existence assertions** — assert all 7 agent output keys are present in the result dict: `parsed_job_description`, `parsed_resume`, `tailoring_strategy`, `rewritten_resume`, `ats_compliance`, `polished_resume`, `cover_letter`.
- **7.1.5** **JD parsing assertions** — assert `result["parsed_job_description"]["role_title"]` is non-empty and `result["parsed_job_description"]["required_skills"]` is a non-empty list.
- **7.1.6** **Resume parsing assertions** — assert `result["parsed_resume"]["experience"]` is a list (and non-empty), and that the parsed name matches/corresponds to the input file.
- **7.1.7** **Gap analysis assertions** — assert `result["tailoring_strategy"]["missing_skills"]` exists (list, at least one entry on a normal 3Pillar run).
- **7.1.8** **Rewrite/ATS/polish assertions** — assert `ats_optimized_resume` and `polished_resume` are truthy non-empty (accept a dict, NOT a string), per the final output models.
- **7.1.9** **Cover letter word-count assertion** — assert the `cover_letter` output is 450–600 words. Compute word count on the text content (strip Markdown) and log the computed count.
- **7.1.10** **Chronological ordering assertion** — assert `parsed_resume.experience` is ordered most-recent-first by comparing parsed date ranges; log the ordering it found.
- **7.1.11** **No-added-experience assertion** — compare the set of company/role titles in the input resume vs. the rewritten/polished output; assert nothing new was introduced (no fabricated experience).
- **7.1.12** **Certification-preservation assertion** — assert every certification present in the input resume text still appears in the output (compare normalized lowercase names).
- **7.1.13** **Output-file assertions** — a second call (or reuse) with `candidate_name="..."` and `company_name="..."` so `render_all()` writes files; assert the returned `output_files` dict has the 6 expected keys and that each written `Path` exists and is non-empty.
- **7.1.14** **Naming-pattern assertion** — assert each output filename matches `{YYYYMMDD_HHMM}_{slug(candidate)}_{slug(company)}_{doc_type}.{ext}` (e.g. regex `^\d{8}_\d{4}_.+$`), i.e. exercises the `build_output_path()` format for real files.
- **7.1.15** **Summary print** — at the end, `print()` a compact summary table (per-agent non-empty ✓/✗, cover letter word count, output file list, total elapsed time) so a human can eyeball it at a glance.
- **7.1.16** **Deterministic guard** — add an env-var/module flag (e.g. `RUN_LIVE_PIPELINE`) so the test is skipped (not failed) under the deterministic `pytest` run when live Ollama is unavailable, guarding against the suite being broken on stripped/offline machines.

**Files changed:** new file `test_real_files.py`

---

### 7.2 Add unit tests (`tests/`) — remaining

**Status:** ⚠️ PARTIAL — existing deterministic tests are done; agent + pipeline tests remain

**What exists now:** 306 tests across 8 files:

- `tests/test_format_detector.py` — 46 tests covering all `FormatDetector` static extraction methods + regex-only parse flows
- `tests/test_jd_parsing.py` — 19 tests (`_extract_company_name` + `_sync_company_name`)
- `tests/test_resume_rewrite_validation.py` — 56 tests (§4.3.A checks + §C skill tailoring + §D fallback logging)
- `tests/test_cover_letter_validation.py` — 80 tests (§4.3.B checks + §C fallback builder + §D fallback logging)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 15 tests (shared parser + JSON Schema helpers)
- `tests/test_formatter.py` — 41 tests (Phase 6.A formatting helpers)
- `tests/test_renderer.py` — 38 tests (Phase 6.B renderer — archived in `resume-done.md` §6.3)

**Still needed:**

- `tests/test_agents.py` — mock `ModelClient`, verify prompts and JSON validation
- `tests/test_pipeline.py` — end-to-end with mocked agents

#### 7.2.1 Agent unit tests — per-agent behaviour with a mocked `ModelClient`

**Status:** ❌ NOT done

Verify each dedicated agent runs its `run()` → `_try_llm()` → `_parse_json()` → validation → fallback contract against a fake client that injects canned responses, with **no real LLM**. Because the built-in structured outputs enforce provider JSON, some of these are the only place the parse/validation layer is exercised off-network.

**Pre-requisites.** Define a `FakeClient` (or reuse a `StubModel` from `tests/conftest.py`) whose `chat()` returns a fixed payload from a fixture map keyed by `purpose`, and record the call args so each test can assert the `json_schema`/`response_format`/`purpose`/`output` was passed as specified in AGENTS.md.

- **7.2.1.1** Create `tests/test_agent_jd_parsing.py` — JD Parsing: valid JSON → `JDParsingOutput`; malformed JSON → fallback; `LLMConnectionError` → fallback; `strict=True` retry round on second exception.
- **7.2.1.2** Create `tests/test_agent_resume_parsing.py` — Resume Parsing: valid parse, malformed JSON fallback, missing `experience` key fallback, dict-where-list coercion via `_coerce_str_list`.
- **7.2.1.3** Create `tests/test_agent_gap_analysis.py` — Gap Analysis: LLM happy path, LLM returning `None` → deterministic missing-skills fallback, prompt receives `missing_skills`.
- **7.2.1.4** Create `tests/test_agent_resume_rewrite.py` — Resume Rewrite: post-validation path (§4.3.A) applies, strict-mode retry toggles, invalid-date/empty-tone coercion.
- **7.2.1.5** Create `tests/test_agent_ats_compliance.py` — ATS: compliance checks run on a non-compliant payload and return fix suggestions; fallback when the frame is absent.
- **7.2.1.6** Create `tests/test_agent_tone_polishing.py` — Tone: `tone_guidance` dict→string coercion (`_coerce_tone_guidance`), fallback when LLM fails.
- **7.2.1.7** Create `tests/test_agent_cover_letter.py` — Cover Letter: uses `_sync_company_name`-style verification, word-count/fallback-builder, `CoverLetterOutput` fill.

**(Alternate, factored layout)** — If preferred, one slim `tests/test_agents.py` module with parametrized fixtures that cover items 7.2.1.1–7.2.1.7 above, rather than 7 separate files; the AGENTS.md convention favors function-specific modules, so pick the one that matches `tests/test_jd_parsing.py`/`tests/test_formatter.py` style.

#### 7.2.2 `tests/test_pipeline.py` — pipeline wiring with mocked agents

**Status:** ⚠️ NOT done

**What it covers:** `AgentRunner` and `run_resume_pipeline()` orchestration (not the real LLM). Because the real agents are instantiated by the runner via `DEFAULT_AGENT_CLASSES`, the cleanest seam is to either (a) patch/`@mock.patch` the agent classes in the module, or (b) swap `DEFAULT_AGENT_CLASSES` with a list of minimal fakes. This validates ordering, input/output threading, and the `output_files` dict without touching Ollama.

- **7.2.2.1 — async end-to-end** — `async` test that runs `run_resume_pipeline(jd, resume, candidate_name=..., company_name=...)` with stub agents that return fixed `ParsedJDOutput`/`ParsedResumeOutput`/etc.; assert the 7 keys + `output_files` (6 keys) are present.
- **7.2.2.2 — dependency threading** — test that each agent in the chain receives the preceding agent's output (assert via stub `run()` that records its `inputs` argument).
- **7.2.2.3 — error propagation** — stub an agent that raises `LLMConnectionError`; assert `run_resume_pipeline()` surfaces/logs the failure and does not hallucinate a missing output key.
- **7.2.2.4 — `company`/`candidate` passthrough** — verify the `name`/`company` args reach the renderer call and `render_all()` and that an empty `candidate_name` skips rendering (no `output_files`).
- **7.2.2.5 — `AgentRunner` unit** — `AgentRunner.run(..)` calls the right agent, carries `purpose`/`inputs`/`output`/`response_format`/`json_schema`, and maps LLM failures to the documented error-type handling.

**Files changed:** new files `tests/test_agents.py` (+7 split files per layout), `tests/test_pipeline.py` (or the 7.1 `test_pipeline.py` reused), plus `tests/conftest.py` if no `FakeClient` fixture exists yet.

---

### 7.3 Populate `docs/`

**Status:** ❌ NOT done

`docs/` directory has 3 existing files: `TESTING.md`, `models.md`, `logging-info.md`. Add four new guides. Each docs file should end with a `## References` section pointing at the relevant `client/*.py` and `resume-*.md` files it documents.

#### 7.3.1 (`docs/architecture.md`)

- **7.3.1.1** Write a **system overview** — the 7-agent chain (JD→Resume Parsing→Gap Analysis→Resume Rewrite→ATS→Tone→Cover), the two provider backends, and the renderer/formatter layers.
- **7.3.1.2** Add a **data-flow diagram** (ASCII or Mermaid) showing the input files, agent order, intermediate Pydantic models, and output artifacts (`output_files`).
- **7.3.1.3** Describe the **agent chain** and each transition's input/output contract (mirror the pipeline-flow block in `AGENTS.md`), plus where `ResumeRenderer` hooks in.

#### 7.3.2 (`docs/agents.md`)

- **7.3.2.1** For each of the 7 agents add: **purpose**, the **prompt** it sends, and its **input/output schema** (referencing `client/models.py` model names, e.g. `JDParsingOutput`, `RewriteOutput`).
- **7.3.2.2** Note the **fallback path** per agent (regex for parsing agents, deterministic templates for rewrite/cover) and when it triggers.
- **7.3.2.3** Cross-link each to its implementation file under `client/templates/` (or `client/agents/`) so the doc stays truthful to the code.

#### 7.3.3 (`docs/usage.md`)

- **7.3.3.1** **Quickstart** — prereqs (`ollama pull`, `uv sync`), the command to run `uv run python test_pipeline.py`/`pipeline.py`, expected outputs (files + console summary).
- **7.3.3.2** **Model configuration** — env-var overrides (`MODEL_PROVIDER`, `MODEL_NAME`, and per-agent `{AGENT}_MODEL`/`{AGENT}_PROVIDER`), how `config/agents.py` picks them.
- **7.3.3.3** **Adding a custom agent** — steps and the `DEFAULT_AGENT_CLASSES` / registry harness a new class must satisfy.

#### 7.3.4 (`docs/api.md`)

- **7.3.4.1** Document the **`ModelClient`** ABC (`chat()`, `response_format`, optional `json_schema`) and the `OllamaClient`/`OpenAIClient` implementations.
- **7.3.4.2** Document **`Agent`**/`PipelineAgent`/`AgentRunner` — constructor signatures, `run()`/`__call__`, the `purpose`/`inputs`/`output`/`rules` contract.
- **7.3.4.3** Document **`ResumeRenderer`** public API (`render_plaintext`, `render_markdown`, `render_cover_letter_*`, `render_docx`, `render_pdf`, `render_all`, `build_output_path`) and the `formatter` helpers.

**Files changed:** new files `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`

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

Already created (see `resume-done.md`): `client/formatter.py`, `client/templates/renderer.py`, `tests/test_formatter.py`, `tests/test_renderer.py`.

---

## Remaining Execution Order

| Step | Phase | Status | Depends On | Estimated Files Changed |
| ------ | ------- | -------- | ------------ | ------------------------ |
| 1 | 7.1: `test_real_files.py` integration test | ❌ TODO | Step 1 (6.B.8 wiring) | 1 |
| 2 | 7.2.1: agent unit tests (`tests/test_agent_*.py` or `test_agents.py`) | ❌ TODO | 6.B.8 wiring | 7 to 8 |
| 3 | 7.2.2: pipeline tests (`tests/test_pipeline.py`) | ❌ TODO | Step 2 | 1 |
| 4 | 7.3.1: `docs/architecture.md` | ❌ TODO | All | 1 |
| 5 | 7.3.2: `docs/agents.md` | ❌ TODO | 7.3.1 | 1 |
| 6 | 7.3.3: `docs/usage.md` | ❌ TODO | All | 1 |
| 7 | 7.3.4: `docs/api.md` | ❌ TODO | 7.3.1 | 1 |
| 8 | 9.1: chronological ordering (sort, don't reject) | ❌ TODO | 6.B.1 | 2 |
| 9 | 9.2: company name from JD + placeholder fix | ❌ TODO | 9.1 | 1 |
| 10 | 9.3: candidate name via `ResumeParsingOutput.name` | ❌ TODO | 9.2 | 3 |
| 11 | 9.4: tests + lint + typecheck for 9.1–9.3 | ❌ TODO | Steps 8–10 | 2 |

---
Normalization of skills


Here is the exact instruction you should include in your JD–Resume matching prompt:

“Normalize all skills by mapping synonyms, variations, and related phrases to a single canonical skill. Treat any phrasing differences as equivalent if they refer to the same underlying capability.
Example: ‘REST API’, ‘RESTFul API’, ‘REST API Development’, and ‘REST API Endpoint Development’ must all be treated as the same skill: REST API.”

Then add the general rule:

“Apply this normalization rule to all skills, technologies, tools, and methodologies found in the job description and resume. If two phrases refer to the same capability, treat them as equivalent even if wording differs.”

🛠️ A more complete version (recommended for production)
You can embed this block into your JD–Resume matching pipeline:

Skill Normalization Rule:

Map all skill synonyms, abbreviations, plurals, and variations to a single canonical skill name.

Treat different phrasings as equivalent if they refer to the same underlying capability.

Examples:

REST API = RESTFul API = REST API Development = REST API Endpoint Development

CI/CD = Continuous Integration and Continuous Deployment

Microservices = Microservice Architecture

Node.js = Node = NodeJS

Apply this rule consistently across both the job description and the resume.

This tells the LLM to generalize beyond REST API.

🔍 Why this works
LLMs are excellent at semantic grouping when explicitly instructed.
Without instructions, they treat phrases literally.
With instructions, they cluster them conceptually.

🧪 Optional: Add a canonicalization step
If you want the model to output a clean list of normalized skills:

“After extracting skills, convert all skills to their canonical form using the normalization rules.”

This ensures:

JD skills → canonical

Resume skills → canonical

Gap analysis → canonical

Matching → canonical

Everything aligns.
