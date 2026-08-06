# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), Phase 4.3 (post-validation for rewrite/cover letter, fallback templates, logging, prompt strengthening, `company_name` — see `resume-done.md`), Phase 5.2 (pipeline wiring — all 7 dedicated classes wired), Phase 6.A (output formatting helpers), Phase 6.B (template renderer: `render_plaintext`/`render_markdown` + cover letter rendering + `build_output_path()` + DOCX + PDF generation + `render_all()` + pipeline wiring + unit tests), Phase 8-contact info (contact extraction + cover letter integration — see `resume-done.md`), and 322 unit tests. The items below are what remains.

---

> Phase 4.3 (Fix LLM Fallback Falsehoods — validation, fallback templates, logging, prompt strengthening, `company_name`) is **complete** — archived in `resume-done.md` §4.3.
>
> Phase 5.2 (wire up the 7-agent pipeline) is **complete** — archived in `resume-done.md` §5.2.
>
> Phase 6.A (output formatting helpers — `client/formatter.py` + `tests/test_formatter.py`) is **complete** — archived in `resume-done.md` §6.2.
>
> Phase 6.B (template renderer — `render_plaintext`/`render_markdown` + cover letter rendering + `build_output_path()` + DOCX + PDF + `render_all()` + pipeline wiring + `tests/test_renderer.py`) is **complete** — archived in `resume-done.md` §6.3.
>
> Phase 8 contact info (8.1 contact fields in `ResumeParsingOutput`, 8.2 cover letter templates with contact line, 8.3 contact info threaded through the Cover Letter agent) is **complete** — archived in `resume-done.md` §8 (Contact Info).

---

## Phase 8: Contact Information Extraction & Cover Letter Integration

**✅ COMPLETE** — archived in `resume-done.md` §8 (Contact Info). Contact fields (`phone`, `email`, `linkedin`, `github`) were added to `ResumeParsingOutput`, extracted by `FormatDetector` and `_regex_fallback`, wired into the cover letter templates as a contact header line, and post-processed into the Cover Letter agent output (`_apply_contact_info`) and fallback signature via `_contact_from_resume`.

---

## Phase 8.5: Skill Normalization & Canonical Taxonomy

Add a centralized skill normalization layer with a canonical skill taxonomy to map synonyms, abbreviations, and variations to standard skill names. This enables accurate JD↔resume skill matching, gap analysis, and keyword optimization across all agents.

### 8.5.1 Create skill normalization module

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.1.1** Create `client/skills/` directory with `normalizer.py`, `taxonomy.json`, and `__init__.py`.
- **8.5.1.2** Define a **canonical skill taxonomy** in `taxonomy.json` — a mapping of **canonical skill names** to their variants/synonyms/abbreviations (e.g., `"javascript": ["js", "javascript", "ecmascript", "es6", "es2015"]`, `"react": ["react.js", "reactjs", "react.js"]`, `"aws": ["amazon web services", "aws", "amazon cloud"]`).
- **8.5.1.3** Implement `SkillNormalizer` class in `normalizer.py` with methods:
  - `normalize(skill: str) -> str` — maps a skill to its **canonical form** using the taxonomy (returns canonical name if match found, otherwise returns normalized lowercase tokenized form)
  - `canonicalize(skill: str) -> str` — alias for `normalize()`, explicit canonicalization
  - `normalize_list(skills: list[str]) -> list[str]` — normalizes, **canonicalizes**, and deduplicates a skill list
  - `get_variants(canonical: str) -> list[str]` — returns all known variants for a canonical skill
  - `match_skills(jd_skills: list[str], resume_skills: list[str]) -> dict` — returns matched, missing, extra skills using canonical forms
- **8.5.1.4** Include skill categories (programming_languages, frameworks, databases, cloud, tools, soft_skills) in taxonomy for future categorization features.
- **8.5.1.5** Add unit tests in `tests/test_skill_normalizer.py` — normalization, canonicalization, deduplication, matching, variant lookup.

**Files changed:** new `client/skills/normalizer.py`, `client/skills/taxonomy.json`, `client/skills/__init__.py`, `tests/test_skill_normalizer.py`

---

### 8.5.2 Integrate skill normalization into JD Parsing Agent

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.2.1** In `jd_parsing.py` `_regex_fallback()`, apply `SkillNormalizer.normalize_list()` to `parsed.requirements` and `parsed.nice_to_have` before assigning to `required_skills`/`preferred_skills`.
- **8.5.2.2** In `_try_llm()` system prompt, add rule: "Normalize all skills to their canonical form (e.g., 'JS' → 'JavaScript', 'React.js' → 'React', 'AWS' → 'Amazon Web Services')."
- **8.5.2.3** Post-process LLM output: apply `SkillNormalizer.normalize_list()` to `required_skills` and `preferred_skills` after Pydantic validation.

**Files changed:** `client/agents/jd_parsing.py`

---

### 8.5.3 Integrate skill normalization into Resume Parsing Agent

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.3.1** In `resume_parsing.py` `_regex_fallback()`, apply `SkillNormalizer.normalize_list()` to `parsed.skills` before assigning.
- **8.5.3.2** In `_try_llm()` system prompt, add same normalization rule as JD parsing.
- **8.5.3.3** Post-process LLM output: apply `SkillNormalizer.normalize_list()` to `skills` after Pydantic validation.

**Files changed:** `client/agents/resume_parsing.py`

---

### 8.5.4 Integrate skill normalization into Gap Analysis Agent

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.4.1** In `gap_analysis.py` `_try_llm()`, pass canonical skill lists (normalized JD required/preferred skills and resume skills) to the LLM prompt.
- **8.5.4.2** Post-process LLM output: apply `SkillNormalizer.normalize_list()` to `missing_skills`, `weak_skills`, `strong_matches`, and `keyword_strategy` fields.
- **8.5.4.3** Use `SkillNormalizer.match_skills()` as a deterministic cross-check alongside LLM analysis; log discrepancies.

**Files changed:** `client/agents/gap_analysis.py`

---

### 8.5.5 Integrate skill normalization into Resume Rewrite Agent

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.5.1** Replace local `_normalize_skill`/`_skill_matches` in `resume_rewrite.py` with `SkillNormalizer` from the shared module.
- **8.5.5.2** In `_sanitize_skills()`, use `SkillNormalizer.normalize()` and `match_skills()` for more accurate filtering.
- **8.5.5.3** In keyword injection logic, use canonical forms to avoid duplicates.

**Files changed:** `client/agents/resume_rewrite.py`

---

### 8.5.6 Integrate skill normalization into Cover Letter Agent

**Status:** ❌ NOT DONE

**Sub-tasks:**

- **8.5.6.1** Replace local `_normalize_skill` in `cover_letter.py` with shared `SkillNormalizer`.
- **8.5.6.2** Use normalized skills when selecting keywords to highlight in the cover letter.

**Files changed:** `client/agents/cover_letter.py`

---

## Phase 9: Cover Letter Creation Fixes (a/b/c)

Fixes for three defects in cover letter creation that surface on live runs: experience entries coming back out of chronological order, the company name being taken from the candidate's resume (or left as `[Company Name]`), and the candidate name left as `[Your Name]`. All three are handled with **pure Python post-processing — no additional LLM calls**.

### 9.1 Chronological ordering of experience (in `resume_rewrite.py`)

**Status:** ✅ DONE

Currently `client/agents/resume_rewrite.py` `_try_llm()` calls `_validate_chronological(result)` and **rejects** the whole rewrite when the experiences are out of order, which drops the entire LLM result and falls back to `_parsed_to_rewrite()`. Now it **intercepts and sorts** the experience section so the rest of the LLM's work is preserved.

**Sub-tasks:**

- **9.1.1** Replace the reject path in `_try_llm()` with a call to `_ensure_chronological(result)`.
  - [x] Read `_try_llm()` in `client/agents/resume_rewrite.py` and locate the current reject block.
  - [x] Confirm the exact current line range in the file (line numbers may have shifted).
  - [x] Replace the reject branch with `result = _ensure_chronological(result)`.
  - [x] Replace the `logger.warning("... -- rejecting")` message with an ordering-fix log ("Output experiences out of chronological order -- sorting").
  - [x] Ensure the branch no longer `return None` (fallback `_parsed_to_rewrite()` is NOT invoked for ordering).
  - [x] Keep the rest of the LLM output preserved end-to-end.
- **9.1.2** Add `_ensure_chronological(result: RewriteOutput) -> RewriteOutput`.
  - [x] Define the helper in `client/agents/resume_rewrite.py` (no LLM call — pure Python).
  - [x] Sort `result.experience` by `_extract_start_year(entry.dates)` descending (most-recent-first).
  - [x] Treat entries whose start year is `None` (unparseable dates) as preserved at the end in their original relative order.
  - [x] Use `sorted()` with a key that falls back to the entry's original index so the sort is stable and lossless.
  - [x] Never drop entries — input list length == output list length.
  - [x] Return the sorted `RewriteOutput`.
- **9.1.3** Keep `_validate_chronological` only as an early signal/log.
  - [x] Downgrade `_validate_chronological` to an optional `DEBUG`-level signal only (early log).
  - [x] Make `_ensure_chronological` the source of truth (post-processor wins).
  - [x] Guard: if a start year is missing for **all** entries, return the list unchanged (nothing to sort).
- **9.1.4** Sort the **input** `parsed_resume` experience (idempotency).
  - [x] In `ResumeParsingAgent._regex_fallback()`, sort `parsed_resume.experience` most-recent-first once.
  - [x] Consider sorting after the LLM parse path as well (idempotent).
  - [x] Verify downstream agents receive most-recent-first data.
  - [x] Confirm the rewrite sort becomes a cheap no-op in the common case.
- **9.1.5** Add/update tests in `tests/test_resume_rewrite_validation.py`.
  - [x] Test: entries sorted correctly, including a None-year entry preserved at the tail.
  - [x] Test: fully-unsortable list (all None-year) left unchanged.
  - [x] Update existing out-of-order tests that previously asserted `None` (rejection) to assert a **sorted** result is returned instead.
  - [x] Run `uv run pytest tests/test_resume_rewrite_validation.py`.

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/resume_parsing.py`, `tests/test_resume_rewrite_validation.py`

---

### 9.2 Company Name must come from the JD, not the candidate's resume

**Status:** ✅ DONE

The cover letter previously could use a **company name pulled from the candidate's resume** (a past employer), or the literal placeholder `[Company Name]`. The source of truth is `JDParsingOutput.company_name` (Phase 4.3.F — employer name exactly as written in the JD), surfaced through the shared `_company_from()` helper. Both failure modes are now fixed with deterministic post-processing (no additional LLM calls).

**Sub-tasks:**

- **9.2.1 Strengthen the prompt so the LLM never picks / restates a wrong name.**
  - [x] Located `_try_llm()` normal-rules in `client/agents/cover_letter.py`.
  - [x] Added `_company_directive()` which injects the exact target company name into the prompt context.
  - [x] Added a rule explicitly forbidding the use of a company from the candidate's resume (e.g. a past employer) as the target.
  - [x] Added a post-fix path (`_apply_company_name`) for when the emitted letter's name is missing / wrong.
- **9.2.2 Add a deterministic company-name normalizer** `_apply_company_name(result: CoverLetterOutput, jd_json: str, resume_json: str = "") -> CoverLetterOutput`.
  - [x] Resolves target via `_company_from(jd_data)` (top-level `company_name`, else `company_signals["company_name"]`).
  - [x] `_check_company` (already present) only `logger.warning` when mismatched (does not reject).
  - [x] Returns normalized `CoverLetterOutput` deterministically (no LLM call).
- **9.2.3** Replace literal placeholder tokens.
  - [x] Match tokens: `[Company Name]`, `[Company]`, `<Company Name>`, `[Employer Name]` (via `_PLACEHOLDER_TOKENS`).
  - [x] Replace matched token with the resolved JD company name via `str.replace`.
  - [x] Tokens matched as ASCII literal strings.
- **9.2.4** Substitute wrong resume-company present in the letter.
  - [x] Detect: target JD company NOT present AND a company from `parsed_resume.experience[*].company` IS present (`_resume_company_in_letter`).
  - [x] Replace the **first** occurrence of the resume-company token with the JD company name (`_replace_first_casefold`).
  - [x] Guard: only apply when the substitution target differs from the JD name (ignores a resume company that matches the target).
  - [x] Log the substitution at `INFO`.
  - [x] No second LLM call.
- **9.2.5** `_build_fallback_cover_letter()`.
  - [x] Confirmed it uses `_company_from` (via `_company_from(jd_data)`).
  - [x] Verified it never emits `[Company Name]` (company omitted when absent, never placeholder text).
- **9.2.6** Add tests in `tests/test_cover_letter_validation.py` (new `TestApplyCompanyName` class).
  - [x] Test: `[Company Name]` placeholder replaced with the JD company.
  - [x] Test: letter naming a resume-company substituted with the JD company.
  - [x] Test: letter already correct left unchanged.
  - [x] Run `uv run pytest tests/test_cover_letter_validation.py` (102 passed).

**Files changed:** `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

---

### 9.3 Candidate Name must come from the candidate's resume

**Context:** The cover letter's signature / opening sometimes contains `[Your Name]`. The candidate name is not currently carried through the pipeline — `ResumeParsingOutput` (in `client/models.py`) has **no `name` field**, even though `FormatDetector` already extracts `ParsedResume.name`. So the cover letter agent cannot know the candidate's real name. The fallback `_build_fallback_cover_letter()` already does `_read_str(resume_data, "name").strip() or "Candidate"`, which returns `"Candidate"` today because the field is absent.

**Sub-tasks:**

- **9.3.1** Add `name: str = ""` to `ResumeParsingOutput` and thread it through.
  - [ ] Add `name: str = ""` field to `ResumeParsingOutput` in `client/models.py`.
  - [ ] In `ResumeParsingAgent._regex_fallback()`, set `name=parsed.name` from the `FormatDetector` result (already extracted).
  - [ ] For the LLM path (`_try_llm`), add `name` to `_SYSTEM_PROMPT` field list.
  - [ ] Add prompt rule: "Extract the candidate's full name exactly as it appears at the top of the resume; empty string if absent."
  - [ ] Ensure no duplicate — add `name` to the schema's field list; confirm the `str` validator handles it.
- **9.3.2** `_apply_candidate_name(result, resume_json)` in `cover_letter.py` `_try_llm()`.
  - [ ] Read the candidate name from `resume_json` (NOT a placeholder).
  - [ ] Add `_apply_candidate_name(result: CoverLetterOutput, resume_json) -> CoverLetterOutput`.
  - [ ] Replace `[Your Name]` / residue with the resolved resume name.
  - [ ] If the name resolves empty, leave the letter untouched.
  - [ ] No LLM call.
- **9.3.3** `_build_fallback_cover_letter()`.
  - [ ] Verify the existing `_read_str(resume_data, "name").strip() or "Candidate"` resolves to the real name once 9.3.1 lands.
- **9.3.4** Add tests.
  - [ ] Test: `name` flows regex → `ResumeParsingOutput.name`.
  - [ ] Test: placeholder `[Your Name]` replaced.
  - [ ] Test: empty name leaves the letter unchanged (or emits "Candidate"/nothing).
  - [ ] Run `uv run pytest tests/test_cover_letter_validation.py` (name-replacement).

**Files changed:** `client/models.py`, `client/agents/resume_parsing.py`, `client/agents/cover_letter.py`, `tests/test_resume_rewrite_validation.py` (no), `tests/test_cover_letter_validation.py` (name-replacement)

---

### 9.4 Cross-cutting notes

- `_try_llm()` must stay pure (serialize/validate only, no side effects) per the AGENTS.md convention.
  - [ ] Confirm all string replacement/sorting runs on the validated `CoverLetterOutput`/`RewriteOutput` inside `_try_llm` **after** Pydantic validation.
  - [ ] Mirror how `_coerce_*` validators and `_sanitize_skills` already work.
- The ASCII-only convention applies to any new placeholder/token matching the LLM output.
  - [ ] Use straight tokens like `[Company Name]` / `[Your Name]`.
- Final verification for 9.1–9.3.
  - [ ] `uv run pytest`
  - [ ] `uv run ruff check .`
  - [ ] `uv run pyright .`
  - [ ] Manual `uv run python wip_testing/test_cover_letter.py`
  - [ ] Manual `uv run python wip_testing/test_resume_rewrite.py`

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

**What exists now:** 322 tests across 8 files:

- `tests/test_format_detector.py` — 46 tests covering all `FormatDetector` static extraction methods + regex-only parse flows
- `tests/test_jd_parsing.py` — 19 tests (`_extract_company_name` + `_sync_company_name`)
- `tests/test_resume_rewrite_validation.py` — 56 tests (§4.3.A checks + §C skill tailoring + §D fallback logging)
- `tests/test_cover_letter_validation.py` — 91 tests (§4.3.B checks + §C fallback builder + §D fallback logging + Phase 8 contact-info post-processing)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 15 tests (shared parser + JSON Schema helpers)
- `tests/test_formatter.py` — 41 tests (Phase 6.A formatting helpers)
- `tests/test_renderer.py` — 43 tests (Phase 6.B renderer + Phase 8 contact-line rendering — archived in `resume-done.md` §6.3 and §8)

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

**What it covers:** `AgentRunner` and `run_resume_pipeline()` orchestration (not the real LLM). Because the real agents are instantiated by the runner via `DEFAULT_AGENT_CLASSES`, the cleanest seam is to either (a) patch/`@mock.patch` the agent classes in the module, or (b) swap `DEFAULT_AGENT_CLASSES` with a list of minimal fakes. This validates ordering, input/output threading, and the `output_files` dict without touching Ollama.

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

**Files changed:** new files `tests/test_agents.py` (+7 split files per layout), `tests/test_pipeline.py` (or the 7.1 `test_pipeline.py` reused), plus `tests/conftest.py` if no `FakeClient` fixture exists yet.

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
| 1 | 8.5.1: skill normalizer module + taxonomy | ❌ TODO | 6.B.1 | 4 |
| 2 | 8.5.2: integrate into JD Parsing | ❌ TODO | 8.5.1 | 1 |
| 3 | 8.5.3: integrate into Resume Parsing | ❌ TODO | 8.5.1 | 1 |
| 4 | 8.5.4: integrate into Gap Analysis | ❌ TODO | 8.5.1 | 1 |
| 5 | 8.5.5: integrate into Resume Rewrite | ❌ TODO | 8.5.1 | 1 |
| 6 | 8.5.6: integrate into Cover Letter | ❌ TODO | 8.5.1 | 1 |
| 7 | 9.1: chronological ordering (sort, don't reject) | ✅ DONE | 6.B.1 | 2 |
| 8 | 9.2: company name from JD + placeholder fix | ✅ DONE | 9.1 | 1 |
| 9 | 9.3: candidate name via `ResumeParsingOutput.name` | ❌ TODO | 9.2 | 3 |
| 10 | 9.4: tests + lint + typecheck for 9.1–9.3 | ❌ TODO | Steps 7–9 | 2 |
| 11 | 7.1: `test_real_files.py` integration test | ❌ TODO | Steps 1–10 (all features) | 1 |
| 12 | 7.2.1: agent unit tests (`tests/test_agent_*.py` or `test_agents.py`) | ❌ TODO | Steps 1–10 | 7 to 8 |
| 13 | 7.2.2: pipeline tests (`tests/test_pipeline.py`) | ❌ TODO | Step 12 | 1 |
| 14 | 7.3.1: `docs/architecture.md` | ❌ TODO | All | 1 |
| 15 | 7.3.2: `docs/agents.md` | ❌ TODO | 7.3.1 | 1 |
| 16 | 7.3.3: `docs/usage.md` | ❌ TODO | All | 1 |
| 17 | 7.3.4: `docs/api.md` | ❌ TODO | 7.3.1 | 1 |
