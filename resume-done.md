# Resume Pipeline — Completed Work

Archive of everything implemented in the resume optimization pipeline.
For what is still left to do, see [resume-todo.md](resume-todo.md).

## Overview

The full 7-agent resume optimization pipeline described in `bots.md`. Each agent receives structured input, runs an LLM prompt, and returns validated JSON output. The pipeline chains agents sequentially: parsed data flows from one agent to the next.

## Current Architecture

The pipeline uses dedicated agent classes orchestrated by `AgentRunner`. Per-agent model assignment is handled by `ModelClientRegistry` + `config/agents.py`. The 7 agents are wired in `pipeline.py` via `run_resume_pipeline()`.

### What exists now

- `client/model_client.py` — Proper ABC for LLM clients (`chat()` requires `response_format`; optional `json_schema`)
- `client/ollama_client.py` — Ollama client with error handling (configurable timeout, default 300s; `format="json"` always)
- `client/open_ai_client.py` — OpenAI client with error handling (`response_format` json_object / json_schema envelope)
- `client/errors.py` — Custom LLM exceptions (`LLMError`, `LLMConnectionError`, `LLMResponseError`, `LLMTimeoutError`)
- `client/json_utils.py` — Shared `parse_json_response` + `model_to_json_schema` helpers
- `client/format_detector.py` — Regex-based document parser with LLM fallback (connected), plain text support, projects, metrics, keywords extraction
- `client/models.py` — All Pydantic models: `ParsedResume`, `ParsedJobDescription`, `JDParsingOutput` (with `company_name`), `ExperienceEntry`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`
- `client/model_registry.py` — Per-agent model assignment registry
- `logging_config.py` — Centralized logging (dictConfig, LOG_LEVEL env var)
- `client/templates/` — Jinja2 resume/cover letter templates + `ResumeRenderer` (renderer.py, Phase 6.3)
- `client/agents/` — All 7 dedicated agent classes (JDParsingAgent, ResumeParsingAgent, GapAnalysisAgent, ResumeRewriteAgent, ATSComplianceAgent, TonePolishingAgent, CoverLetterAgent)
- `config/agents.py` — Environment-based agent-to-model configuration
- `pipeline.py` — `AgentRunner`, `PipelineAgent`, and `run_resume_pipeline()`
- `basic.py` — Single-agent demo (JSON mode)
- `tests/` — 362 tests across 9 files (FormatDetector regex, JD parsing, resume rewrite validation, cover letter validation, model clients, JSON utils, formatter, renderer, skill normalizer)
- `pyproject.toml` — Project config (ruff, pyright, pytest)
- `AGENTS.md` — Agent instruction file
- `docs/TESTING.md` — Testing guide
- `docs/models.md`, `docs/logging-info.md` — Additional docs
- `sample/` — Sample JDs and resume for testing
- `wip_testing/` — Manual agent test scripts (8 files, one per agent chain)

---

## Phase 1: Core Infrastructure

### 1.1 Refactor `client/model_client.py`

**Status:** ✅ DONE

The file is already a clean ABC with `@abstractmethod async def chat(...)`. No orphaned fields or dead code.

---

### 1.2 Add error handling to LLM clients

**Status:** ✅ DONE

**`client/errors.py`:** ✅ Done — defines `LLMError`, `LLMConnectionError`, `LLMResponseError`, `LLMTimeoutError`

**`client/ollama_client.py`:** ✅ Done — wraps `ollama.RequestError`, `ollama.ResponseError`, `asyncio.TimeoutError`

**`client/open_ai_client.py`:** ✅ Done — wraps `openai.AuthenticationError`, `openai.RateLimitError`, `openai.APIConnectionError`, `openai.APIError`, `asyncio.TimeoutError`

---

### 1.3 Clean up `requirements.txt`

**Status:** ✅ DONE

Replaced 128-line pip freeze dump with 3 direct dependencies: `ollama`, `openai`, `pydantic`.

---

## Phase 2: Document Parsing (Agents 1 & 2)

### 2.1 Expand `client/format_detector.py`

**Status:** ✅ DONE

**Implemented:**

- `_extract_projects()` — extracts bullet points from `## Projects` section
- `_extract_metrics()` — regex for percentages, dollar amounts, team sizes, timeframes
- `extract_keywords()` — frequency-based keyword extraction with stopword filtering (top 20)
- `_detect_format()` — returns `"markdown"` or `"plain"` based on `##` heading presence
- `_section_pattern()` — builds regex matching both Markdown (`## Name`) and plain text (`Name:`) headings
- `_extract_bullet_points()` — rewritten to handle plain text lines (not just `*`/`-` bullets), with heading-anchored keyword matching
- `_extract_name()` / `_extract_title()` — fall back to first/second non-empty line for plain-text resumes; strip BOM characters
- `_extract_section()` — detects plain text headings as section boundaries (not just `##`)
- `_normalize_list_fields()` — flattens LLM dict responses into `list[str]` for Pydantic compatibility
- `parse_job_description()` — expanded keyword lists: `must have`, `minimum qualifications`, `additional experience desired`, `preferred qualifications`, etc.
- LLM fallback connected: `FormatDetector(client=OllamaClient("qwen2.5:7b-instruct"))` works end-to-end
- `ParsedResume` updated with `projects` and `keywords` fields
- `parse_resume()` wired to call all new methods

**Files changed:** `client/format_detector.py`, `client/models.py`, `tests/test_format_detector.py`, `client/ollama_client.py`

---

### 2.2 Agent Infrastructure

**Status:** ✅ DONE (different approach than originally planned)

The original plan called for `client/agents/base.py` with a `BaseAgent` ABC. Instead, the codebase uses:

- `PipelineAgent` in `pipeline.py` — generic LLM wrapper with a fixed `purpose` (system prompt)
- `Agent` Protocol in `pipeline.py` — structural type for any agent with `async run(inputs)`
- `AgentRunner` in `pipeline.py` — orchestrates named agents with timing/logging
- `ModelClientRegistry` in `client/model_registry.py` — per-agent model assignment
- `config/agents.py` — environment-based configuration

Agents 1-7 were implemented as dedicated classes (e.g., `JDParsingAgent`, `ResumeRewriteAgent`) rather than `PipelineAgent` instances, with per-agent LLM + validation + fallback logic.

---

### 2.3 JD Parsing Agent

**Status:** ✅ DONE

**Implemented:**

- `client/agents/jd_parsing.py` — dedicated `JDParsingAgent` class
- Uses system prompt from `bots.md`
- Parses LLM response as JSON, validates against `JDParsingOutput` Pydantic model
- Retries once with stricter rules on validation failure
- Falls back to `FormatDetector.parse_job_description()` on second failure
- `client/models.py` — `JDParsingOutput` model with `@field_validator` for `company_signals` (accepts list or dict) and a `company_name` field (Phase 4.3.F)
- `pipeline.py` — `sample_run()` uses `JDParsingAgent`; `run_resume_pipeline()` branches on model vs dict for the JD result only

**Files changed:** `client/agents/jd_parsing.py` (new), `client/agents/__init__.py` (new), `client/models.py`, `pipeline.py`

**Test:** `uv run python wip_testing/test_job_description.py`

**Output schema (Pydantic model):**

```python
class JDParsingOutput(BaseModel):
    role_title: str
    seniority_level: str  # "junior", "mid", "senior", "lead", "executive"
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    keywords: list[str]
    industry_terms: list[str]
    company_signals: dict[str, str]  # {"culture": ..., "values": ..., "mission": ...}
    company_name: str = ""  # employer name exactly as written in the JD
```

**Implementation:**

1. Build user prompt: `f"Extract structured data from this job description:\n\n{inputs['job_description']}"`
2. Call `self.client.chat(purpose=_SYSTEM_PROMPT, prompt=prompt, output=["json"], rules=rules, inputs=[jd_text])` inside `_try_llm()`
3. Parse LLM response as JSON
4. Validate against `JDParsingOutput` Pydantic model
5. On validation failure: retry once with a stricter prompt ("You must output valid JSON only. No markdown, no explanation.")
6. On second failure: fall back to `FormatDetector.parse_job_description()` and wrap result in the expected schema

---

### 2.4 Resume Parsing Agent

**Status:** ✅ DONE

**Implemented:**

- `client/agents/resume_parsing.py` — dedicated agent
- Uses the system prompt from `bots.md`
- Parses LLM response as JSON
- Validates against a `ResumeParsingOutput` Pydantic model
- Falls back to `FormatDetector.parse_resume()` on failure
- `FormatDetector.parse_resume()` is NOT a pre-processor; it is used only as the fallback after both LLM attempts fail

**Output schema (Pydantic model):**

```python
class ExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    responsibilities: list[str]
    achievements: list[str]
    metrics: list[str]


class ResumeParsingOutput(BaseModel):
    summary: str
    skills: list[str]
    experience: list[ExperienceEntry]
    projects: list[str]
    certifications: list[str]
    education: list[str]
```

**Implementation:**

1. Send the full resume text to the LLM first
2. Build user prompt with the full resume text
3. Call LLM with the system prompt
4. Parse JSON response
5. Validate against `ResumeParsingOutput`
6. On failure: retry with stricter prompt
7. On second failure: wrap `FormatDetector` output in the expected schema

**Files changed:** new file `client/agents/resume_parsing.py`

---

## Phase 3: Analysis & Rewriting (Agents 3-5)

### 3.1 Create Gap Analysis Agent (`client/agents/gap_analysis.py`)

**Status:** ✅ DONE

**Purpose:** Compare parsed JD vs parsed resume, produce a tailoring strategy.

**Input schema:**

```python
inputs = {
    "parsed_job_description": JDParsingOutput,  # serialized dict
    "parsed_resume": ResumeParsingOutput,  # serialized dict
}
```

**Output schema (Pydantic model):**

```python
class GapAnalysisOutput(BaseModel):
    missing_skills: list[str]
    weak_skills: list[str]
    strong_matches: list[str]
    recommended_emphasis: list[str]
    keyword_strategy: list[str]
    bullet_point_improvement_plan: list[str]
    tone_guidance: str  # "technical", "managerial", or "creative"
```

**Implementation:**

1. Serialize both parsed inputs to JSON strings for the prompt
2. Build prompt: combine system prompt + serialized JD + serialized resume
3. Call LLM
4. Parse and validate JSON response
5. On failure: retry once; no regex fallback (gap analysis requires LLM reasoning)

**Files changed:** new file `client/agents/gap_analysis.py`

---

### 3.2 Create Resume Rewrite Agent (`client/agents/resume_rewrite.py`)

**Status:** ✅ DONE

**Purpose:** Rewrite the resume using the tailoring strategy.

**Input schema:**

```python
inputs = {
    "parsed_resume": ResumeParsingOutput,
    "tailoring_strategy": GapAnalysisOutput,
}
```

**Output schema (Pydantic model):**

```python
class RewriteOutput(BaseModel):
    summary: str
    skills: list[str]
    experience: list[ExperienceEntry]
    projects: list[str]
    certifications: list[str]
    education: list[str]
```

**Implementation:**

1. Serialize parsed resume and tailoring strategy to JSON
2. Build prompt combining both inputs
3. Call LLM
4. Parse and validate JSON
5. Post-validation in `_try_llm()` (Phase 4.3.A): `_validate_experience_count`, `_validate_certifications`, `_validate_companies`, `_validate_chronological`, `_sanitize_skills` — see Phase 4 below
6. On failure: retry with explicit instruction "Output a JSON object matching this exact schema: ..."
7. On second failure: return the parsed resume unchanged with a warning logged

**Files changed:**

- new file `client/agents/resume_rewrite.py`
- new file `wip_testing/test_resume_rewrite.py`

---

### 3.3 Create ATS Compliance Agent (`client/agents/ats_compliance.py`)

**Status:** ✅ DONE

**Purpose:** Evaluate the rewritten resume for ATS compatibility and fix issues.

**Input schema:**

```python
inputs = {"rewritten_resume": RewriteOutput}
```

**Output schema (Pydantic model):**

```python
class ATSComplianceOutput(BaseModel):
    ats_score: int  # 0-100
    missing_keywords: list[str]
    formatting_issues: list[str]
    clarity_issues: list[str]
    recommended_fixes: list[str]
    auto_fixes_applied: list[str]
    final_resume: str  # Full resume text after auto-fixes
```

**Implementation:**

1. Serialize the full rewritten resume (not truncated!) to the prompt
2. Call LLM
3. Parse and validate JSON
4. Validate `ats_score` is between 0 and 100 — implemented as a clamp, not a reject; the Pydantic model also enforces `ge=0, le=100`
5. On failure: retry; on second failure, return a default low-score result with the resume unchanged (`_default_result`)
6. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/ats_compliance.py`
- new file `wip_testing/test_ats_compliance.py`

---

## Phase 4: Polish & Cover Letter (Agents 6-7)

> Note: §4.1 and §4.2 (the two agents) are complete. §4.3 is complete for all items §A-§F.

### 4.1 Create Tone Polishing Agent (`client/agents/tone_polishing.py`)

**Status:** ✅ DONE

**Purpose:** Improve tone and professionalism without changing facts.

**Input schema:**

```python
inputs = {"ats_optimized_resume": ATSComplianceOutput.final_resume}
```

**Output schema (Pydantic model):**

```python
class TonePolishingOutput(BaseModel):
    polished_resume: str  # Full polished resume text
```

**Implementation:**

1. Receive the `final_resume` string from ATS compliance output
2. Build prompt with the full resume text
3. Call LLM
4. Parse and validate JSON
5. On failure: retry; on second failure, return the input unchanged
6. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/tone_polishing.py`
- new file `wip_testing/test_tone_polishing.py`

---

### 4.2 Create Cover Letter Agent (`client/agents/cover_letter.py`)

**Status:** ✅ DONE

**Purpose:** Generate a tailored cover letter.

**Input schema:**

```python
inputs = {
    "parsed_job_description": JDParsingOutput,
    "parsed_resume": ResumeParsingOutput,
    "tailoring_strategy": GapAnalysisOutput,
}
```

**Output schema (Pydantic model):**

```python
class CoverLetterOutput(BaseModel):
    cover_letter: str  # 450-600 word cover letter
```

**Implementation:**

1. Serialize all three inputs to JSON strings
2. Build prompt combining them
3. Call LLM
4. Parse and validate JSON
5. Word count validation (450-600 spec) implemented via `_validate_length` (see Phase 4.3.B.4) — rejects only <200/>800, warns on 200-450/600-800
6. On failure: retry; on second failure, return a minimal generic cover letter
7. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/cover_letter.py`
- new file `wip_testing/test_cover_letter.py`

---

### 4.3 Fix LLM Fallback Falsehoods — completed items

**Status:** ✅ COMPLETE — §A-§F are all DONE

#### A. Improve Post-Validation for Resume Rewrite (HIGH priority) — ✅ DONE

Checks added in `resume_rewrite.py` `_try_llm()`, after the existing experience-count and certification checks.

1. **Skill check — sanitize, don't reject** (`_sanitize_skills`). Filters output skills to those present in input resume skills. Matching is case-insensitive with a fuzzy match (`_normalize_skill` + `_skill_matches`: exact, substring ≥3 chars, shared-token) to tolerate LLM renaming (e.g., `SQL` vs `PostgreSQL`). Fabricated skills are dropped with a warning, and the rest of the LLM's work is kept. If **>50%** of output skills are dropped, the result is rejected (returns `None`) and falls through to `_parsed_to_rewrite()`.
2. **Company check — reject on fabrication** (`_validate_companies`). Each output `experience.company` must match an input `ExperienceEntry.company` (case-insensitive substring, `_company_matches`). The LLM may reorder entries, so output companies are matched **by name against the set of input companies** rather than by position; empty output companies are skipped. An output company matching none is a fabricated employer — the result is rejected.
3. **Date check — skipped.** Prompt already prohibits fabricated dates; regex date matching is fragile and low-value.
4. **Chronological order check — add** (`_validate_chronological`). Verifies experience entries are most-recent-first by comparing start years (`_extract_start_year` — first 4-digit year in each `dates` string). Entries without a parseable year are skipped; results with <2 parseable years pass (cannot be validated). Out-of-order results are rejected.

**On rejection:** `_try_llm()` returns `None` so `run()` falls back to `_parsed_to_rewrite()`.

#### B. Improve Post-Validation for Cover Letter (HIGH priority) — ✅ DONE

Checks added in `cover_letter.py` `_try_llm()`, after the empty-content fallback (which returns early).

1. **Role check — reject only when role_title is meaningful** (`_validate_role`). The JD's `role_title` must appear in the cover letter. Matching is case-insensitive: the full title is tried first, then the non-filler tokens (seniority words like "senior"/"junior" and function words are stripped) must each appear as whole words. `role_title` defaults to `""`, in which case the check passes. A meaningful title absent from the letter is rejected (returns `None` → fallback).
2. **Company check — best-effort warning, never reject** (`_check_company`). Compares `JDParsingOutput.company_name` (see §F, source of truth) against the letter, falling back to `company_signals["company_name"]` via `_get_company_name`. A letter that omits the name logs a warning but is accepted. Partial mention passes if **any** significant token appears as a whole word.
3. **Skill check — warn only** (`_check_skills`). Candidate skill nouns come from the JD's `required_skills`/`preferred_skills` plus the resume's skill list. A skill mentioned in the letter but absent from the resume is flagged with a warning; nothing is rejected. Matching uses whole-word boundaries and fuzzy matching (`_skill_in_list`: exact / substring / shared-token).
4. **Length check — reject only on extreme outliers** (`_validate_length`). Spec is **450-600**. Rejects (returns `None` → fallback) only if < 200 or > 800; accepts with a warning between 200-450 and 600-800.
5. **Date check — skipped.** Prompt already prohibits "current"/"now"/"presently"; post-validation on natural language is fragile and low-value.

**Note:** the plain-text fallback in `_parse_json` treats any >50-char non-JSON response as the letter. All of the above checks still run on that path.

#### C. Improve Fallback Templates (MEDIUM priority) — ✅ DONE

Two data-driven, deterministic fallbacks that replace the previous defaults (an untailored parsed resume and a `[Your Name]` placeholder letter).

**Resume Rewrite fallback** (`client/agents/resume_rewrite.py`):

- `_parsed_to_rewrite(parsed, jd=None, strategy=None)` now calls `_tailor_skills()`, which:
  1. **Reorders skills** so those matching the JD `required_skills` (or, when the JD is not passed to the agent, the strategy's `keyword_strategy`) appear first, preserving original relative order.
  2. **Prepends up to 5 JD `keywords`** (or strategy keywords) not already present in the resume skills. Presence is checked with the existing fuzzy `_skill_matches`/`_normalize_skill` logic, so "SQL" vs "PostgreSQL" is handled. Non-ASCII keywords are skipped (project "no extended characters" convention).
  3. Experience, projects, certifications, and education pass through unchanged.
- `run()` reads an optional `parsed_job_description` from inputs (in addition to `parsed_resume`/`tailoring_strategy`) so the fallback has the JD when the caller provides it.

**Cover Letter fallback** (`client/agents/cover_letter.py`):

- `_MINIMAL_COVER_LETTER` removed; replaced by `_build_fallback_cover_letter(jd, resume, strategy)` which:
  1. Uses the real `role_title` from the JD ("the advertised position" when absent).
  2. Uses the real company name via the shared dict helper `_company_from` (top-level `company_name` first, then `company_signals["company_name"]`); omitted entirely rather than "your company" when unavailable.
  3. Picks up to 3 resume skills overlapping JD `required_skills` (fuzzy `_skill_in_list`); falls back to `keyword_strategy` when there is no required-skill overlap.
  4. References one achievement from the most recent experience entry (`_most_recent_achievement`), falling back to a responsibility only when the entry has no achievements.
  5. Uses the candidate name from the resume's `name` field (or "Candidate" when missing).
  6. Keeps the three-paragraph structure (opening / middle / closing) plus salutation and `Sincerely,\n<name>` signature, ASCII-only.
- Applied at **all three call sites**: empty input in `run()`, double LLM failure in `run()`, and empty content in `_try_llm`. The empty-content path now returns `None` (per the todo note) so `run()` falls back — `_try_llm` stays pure (only serialized JSON strings).
- `_get_company_name` was refactored to delegate to the shared `_company_from` (behavior unchanged; existing tests still pass).

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/cover_letter.py`, `wip_testing/test_cover_letter.py` (fallback detection no longer checks for `[Your Name]`; uses word count < 300)

#### D. Add Fallback Detection Logging (LOW priority) — ✅ DONE

Both agents log the outcome at `INFO` so an LLM success vs a deterministic fallback is visible at a glance (`LOG_LEVEL=INFO` or `DEBUG`).

**Resume Rewrite** (`client/agents/resume_rewrite.py`):

- Success: `"LLM rewrite succeeded (skills=%d, words=%d)"` — metrics via the new `_count_words(result)` helper (sums words across summary, skills, experience title/company/dates/responsibilities/achievements/metrics, projects, certifications, education).
- Fallback: `"Fallback: parsed resume used (reason: %s)"` with reason `"LLM failed on both attempts"` (kept alongside the existing `logger.warning`).

**Cover Letter** (`client/agents/cover_letter.py`):

- Success: `"LLM cover letter succeeded (words=%d)"` (the 450-600 word-count spec makes this the natural metric).
- Fallback: `"Fallback: template cover letter used (reason: %s)"` — reason is `"empty input"` at the empty-input call site and `"LLM failed on both attempts"` at the double-failure site.

`wip_testing/test_resume_rewrite.py` and `wip_testing/test_cover_letter.py` now call `configure_logging()` (they previously relied on Python's default WARNING-only config, which silently dropped INFO messages even with `LOG_LEVEL=DEBUG` set).

**Tests added:** `TestCountWords` (2) + `TestFallbackLogging` (2) in `tests/test_resume_rewrite_validation.py`; `TestFallbackLogging` (3) in `tests/test_cover_letter_validation.py` — each drives `run()` through a stub `ModelClient` (`_MockClient`) with `caplog.set_level(logging.INFO)` to assert the exact success/fallback messages. 227 tests total.

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/cover_letter.py`, `wip_testing/test_resume_rewrite.py`, `wip_testing/test_cover_letter.py`

#### E. Strengthen Prompts (root-cause mitigation, pairs with A/B) — ✅ DONE

Root-cause mitigation so the LLM is less likely to fabricate in the first place (post-validation in §A/§B stays as the safety net).

**Resume Rewrite** (`client/agents/resume_rewrite.py`, `_SYSTEM_PROMPT`):

- Removed the fabrication-inviting rule *"You may add reasonable metrics only if implied (e.g., 'managed a team' → 'managed a team of 5')"*.
- Replaced it with *"Never add metrics that are not explicitly in the resume. If a metric is missing, rephrase without inventing a number."* — the single highest-leverage fix for fabricated metrics.
- The certifications rule ("All certifications ... MUST be included") is unchanged — already enforced by `_validate_certifications`.

**Cover Letter** (`client/agents/cover_letter.py`, `_SYSTEM_PROMPT`):

- Replaced the stray non-ASCII `吸引` with "attracts" ("...or what attracts you to them"). It was an artifact in an otherwise English prompt and contradicted the prompt's own ASCII-only rule. Both prompt files are now ASCII-only (verified programmatically).

**Verification:**

- `uv run python wip_testing/test_resume_rewrite.py` with `LOG_LEVEL=DEBUG` → `LLM rewrite succeeded (skills=25, words=438)`.
- `uv run python wip_testing/test_cover_letter.py` with `LOG_LEVEL=DEBUG` → `LLM cover letter succeeded (words=280)`.
- Groundedness cross-check: extracted every number from the input resume text and every number from the rewritten metrics/achievements — **0 ungrounded numbers** (verified on both the LLM-success and deterministic-fallback paths).
- `uv run pytest` → 227 passed; ruff check/format + scoped pyright all clean.

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/cover_letter.py`

#### F. Add `company_name` to `JDParsingOutput` and `company_signals` (HIGH priority, prerequisite for B.2/C.2) — ✅ DONE

1. **Field added** to `JDParsingOutput` in `client/models.py`:

   ```python
   company_name: str = ""  # employer name exactly as written in the JD
   ```

2. **Extracted in the JD Parsing Agent** (`client/agents/jd_parsing.py`):
   - `company_name` added to the LLM prompt's JSON field list (`_SYSTEM_PROMPT`).
   - Rule added: *"Extract the company name exactly as it appears in the job description; output empty string if not present."*
   - `_sync_company_name()` keeps the field and `company_signals["company_name"]` in agreement after every successful LLM parse — prefers the top-level field, falls back to the value embedded in `company_signals`, and injects the name under the `"company_name"` key.
3. **Regex fallback** (`_regex_fallback`): `_extract_company_name()` is a best-effort deterministic extractor — tries explicit labels (`Company:` / `Employer:` / `Organization:` / `Hiring Company:`), then the common JD opening pattern `<Name> is/are ...`, then `at/for/with <Name>` references. Filters out pure-number tokens, pronoun openers (`We`/`Our`/etc.), and returns empty string when nothing confident is derivable. The result populates both `company_name` and `company_signals["company_name"]`.
4. **Consumers:** the cover letter company check (B.2) and the fallback letter (C.2) both use `JDParsingOutput.company_name` as the source of truth via the shared `_company_from` helper.

**Files changed:** `client/models.py`, `client/agents/jd_parsing.py`, `wip_testing/test_job_description.py`, `tests/test_jd_parsing.py`

**Tests added for the completed §4.3 items:**

- `tests/test_jd_parsing.py` — covers `_extract_company_name` + `_sync_company_name` (19 tests)
- `tests/test_resume_rewrite_validation.py` — covers the A checks + §C `_tailor_skills`/`_parsed_to_rewrite` + §D fallback logging (56 tests)
- `tests/test_cover_letter_validation.py` — covers the B checks + §C fallback builder helpers + §D fallback logging + Phase 8 contact-info post-processing (91 tests)

---

## Phase 5: Agent Orchestration

### 5.1 Implement `AgentRunner` in `pipeline.py`

**Status:** ✅ DONE

The `AgentRunner` class is fully implemented with:

- Named agent dispatch with input dictionaries
- Async execution via `asyncio.run()`
- Per-agent timing and logging
- Registry-based agent instantiation
- Error propagation with logging

**No further work needed.**

> Phase 5.2 (wire the 7-agent pipeline with dedicated classes for agents 3-7) is **complete** — all 7 agents are wired as dedicated classes in `sample_run()` and `create_runner_from_config()`. `client/agents/__init__.py` exports all 7 classes. `run_resume_pipeline()` handles both dict and Pydantic model returns via `_extract_field()`.

### 5.2 Wire up the 7-agent pipeline

**Status:** ✅ COMPLETE — all 7 agents wired as dedicated classes; both dict and Pydantic model returns handled

`run_resume_pipeline()` chains all 7 agents sequentially:

1. JD Parsing → `parsed_job_description`
2. Resume Parsing → `parsed_resume`
3. Gap Analysis → `tailoring_strategy`
4. Resume Rewrite → `rewritten_resume`
5. ATS Compliance → `ats_optimized_resume`
6. Tone Polishing → `polished_resume`
7. Cover Letter → `cover_letter`

**What works:** `sample_run()` now wires all 7 dedicated classes via `create_runner_from_config()`, which defaults to `DEFAULT_AGENT_CLASSES` (all 7 dedicated classes) and builds a `ModelClientRegistry` from the environment. The `_extract_field()` helper handles both dict returns (from generic `PipelineAgent`) and Pydantic model returns (from dedicated classes).

**What changed:** `client/agents/__init__.py` now exports all 7 agent classes. `pipeline.py` imports from the package, defines `DEFAULT_AGENT_CLASSES` constant, and `create_runner_from_config()` defaults to the full set when `agent_classes=None`.

---

## Phase 6: Output & Validation

### 6.1 Add Pydantic models (`client/models.py`)

**Status:** ✅ DONE

All 7 agent output schemas plus `ParsedResume` (with `projects`, `keywords` fields) and `ParsedJobDescription` models exist in `client/models.py`. Models: `ExperienceEntry`, `JDParsingOutput`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput` (`ats_score: int = Field(ge=0, le=100)`), `TonePolishingOutput`, `CoverLetterOutput`.

**Files changed:** `client/models.py`

> Phase 6.2 (output formatter) and Phase 6.3 (template renderer) are **complete** — the formatter (§6.A all four items) and the full 6.B renderer (plaintext/Markdown, cover letter rendering, `build_output_path()`, DOCX, PDF, `render_all()`, pipeline wiring, and renderer tests) are done.

### 6.2 Output Formatting Helpers (Phase 6.A)

**Status:** ✅ COMPLETE — 6.A.1–6.A.4 all DONE

#### 6.A.1 `format_resume_markdown()` (`client/formatter.py`)

**Status:** ✅ DONE

Convert a `RewriteOutput` to clean Markdown. Handles: name/title header, summary, skills as bullet list, experience blocks (title, company, dates, responsibilities, achievements, metrics), certifications, projects, education. No external dependencies.

**Files changed:** new file `client/formatter.py`

#### 6.A.2 `format_resume_plain()` (`client/formatter.py`)

**Status:** ✅ DONE

Convert a `RewriteOutput` (or `ATSComplianceOutput`'s `final_resume`) to plain-text ATS-friendly format. No Markdown syntax, no special characters. Suitable for ATS upload and as input to DOCX/PDF rendering.

**Depends on:** 6.A.1 (same file)

**Files changed:** `client/formatter.py`

#### 6.A.3 `format_cover_letter()` (`client/formatter.py`)

**Status:** ✅ DONE

Clean up cover letter text: normalize whitespace, fix encoding artifacts, ensure consistent paragraph spacing. Takes a `CoverLetterOutput` or raw string, returns clean string.

**Depends on:** 6.A.1 (same file)

**Files changed:** `client/formatter.py`

#### 6.A.4 Unit tests for formatting helpers

**Status:** ✅ DONE

41 tests covering `format_resume_markdown()` (empty resume, headers, all sections, ordering, edge cases), `format_resume_plain()` (same coverage), `format_cover_letter()` (model input, raw string, whitespace normalization, encoding artifacts, empty input), and `_fix_encoding()` (all replacements, no-op, empty string).

**Depends on:** 6.A.1–6.A.3

**Files changed:** new file `tests/test_formatter.py`

---

### 6.3 Template-Based Multi-Format Renderer (Phase 6.B)

**Status:** ✅ COMPLETE — 6.B.1–6.B.9 all DONE

#### 6.B.1 `ResumeRenderer` class skeleton (`client/templates/renderer.py`)

**Status:** ✅ DONE

`ResumeRenderer` with `__init__`, template loading from `client.templates.TEMPLATES`, `render_plaintext()` (Jinja2 rendering of `RewriteOutput` against template dicts), `_build_context()` helper to convert Pydantic models to plain dicts, and `_clean_output()` to collapse excess blank lines. No DOCX/PDF yet.

**Depends on:** None (independent of 6.A)

**Files changed:** new file `client/templates/renderer.py`, `pyproject.toml` (added `jinja2>=3.1.0`)

#### 6.B.2 `render_markdown()` on `ResumeRenderer`

**Status:** ✅ DONE

Render `RewriteOutput` using the template's `"markdown"` key. Same Jinja2 approach as `render_plaintext()`. Present in `renderer.py`.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`

#### 6.B.3 Add `render_cover_letter_plaintext()` and `render_cover_letter_markdown()`

Render `CoverLetterOutput` using the `COVER_LETTER` template. Two methods for plaintext and markdown variants, following the `render_plaintext()`/`render_markdown()` pattern (lookup template dict key, `_env.from_string(...).render(**context)`, `_clean_output`).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.3.1** ✅ Add `_build_cover_letter_context()` helper — converts a `CoverLetterOutput` (plus candidate name / company name) into the context dict expected by the `COVER_LETTER` template (supplies `candidate_name`, `company`, `date` via `date.today()`, and `opening_paragraph`/`body_paragraph`/`closing_paragraph` split from the letter body on blank lines).
- **6.B.3.2** ✅ Add `render_cover_letter_plaintext(cover_letter, *, name="", company="")` — render against the `COVER_LETTER` template's `"plaintext"` key, through `_clean_output()`.
- **6.B.3.3** ✅ Add `render_cover_letter_markdown(cover_letter, *, name="", company="")` — same as 6.B.3.2 against the `"markdown"` key.

The letter body is normalized by `_split_paragraphs()` before rendering: the `COVER_LETTER` template renders its own salutation and signature, so a leading `Dear ...` line and a trailing `Sincerely, ...` block embedded in the agent's letter text are stripped to avoid duplication.

**Files changed:** `client/templates/renderer.py`

#### 6.B.4 Add `build_output_path()` static method

Static utility to build timestamped file paths: `{date}_{candidate_name}_{company_name}_{document_type}.{ext}`. Date format `YYYYMMDD_HHMM`. Pure path logic, no I/O; filename-safe (sanitizes spaces, invalid chars, empty segments).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.4.1** ✅ Add a `_slugify()` static helper — normalize a name/company string to a filename-safe ASCII token (lowercase, non-alphanumerics → `-`, collapse repeats, strip leading/trailing hyphens, empty → `""`).
- **6.B.4.2** ✅ Implement `build_output_path(document_type, *, candidate_name, company_name, output_dir, ext=None)` — build `{output_dir}/{YYYYMMDD_HHMM}_{slug(candidate)}_{slug(company)}_{document_type}.{ext}`, defaulting `ext` per document type (`.txt`, `.md`, `.docx`, `.pdf`). Returns `Path`. No file I/O.

**Files changed:** `client/templates/renderer.py`

#### 6.B.5 Add DOCX generation (`render_docx()`)

Use `python-docx` to render `RewriteOutput` as a `.docx` file. Professional font (Calibri/Arial), 10–11pt body, 14pt name, bold section headers, 1-inch margins, single spacing.

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.5.1** ✅ Add `python-docx>=1.0.0` to `pyproject.toml` and run `uv sync`.
- **6.B.5.2** ✅ Add `render_docx(resume, *, name="", title="", template="modern", output_path=None) -> Path` — create the `Document`, apply page setup (1-inch margins, letter size), set default font (Calibri 11pt), write to `output_path` (or a temp path when `None`), return the written `Path`.
- **6.B.5.3** ✅ Add `_populate_docx_paragraphs(doc, context)` helper — walk the `_build_context()` dict and add body content: summary paragraph, skills line/bullets, per-experience blocks (title bold, company + dates, responsibilities/achievements/metrics bullets), projects, certifications, education. Name rendered at 14pt bold.
- **6.B.5.4** ✅ Add `_docx_heading(doc, text)` + `_docx_bullet(doc, text)` helpers — encapsulate the run-level font/bold/spacing styling so the styling rules live in one place.

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `python-docx>=1.0.0`)

#### 6.B.6 Add PDF generation (`render_pdf()`)

Use `reportlab` to render `RewriteOutput` as a `.pdf` file. ReportLab builds the PDF **directly** with the Platypus framework (`SimpleDocTemplate`, `Paragraph`, `Spacer`, `ListFlowable`) — no HTML/Markdown intermediate, so the `markdown` package is **not** needed. Same professional styling as DOCX (Helvetica, 10–11pt body, 14pt name, bold section headers, 1-inch margins, single spacing).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.6.1** ✅ Add `reportlab>=4.0` to `pyproject.toml` and run `uv sync`. (Add `pillow>=10.0` only if a profile photo, icons, or complex graphical decorations are ever added — Platypus uses PIL to draw and size embedded images.) Do **not** add `markdown>=3.5`.
- **6.B.6.2** ✅ Add PDF styling helpers — a `_pdf_styles()` static helper returning a dict of `ParagraphStyle` objects (name at 14pt bold, section headers bold, body at 10–11pt, Helvetica family, single leading). ReportLab's built-in Helvetica/Helvetica-Bold is a Type-1 base-14 font (fine for the project's ASCII-only convention) — switch to an embedded TTF font only if non-Latin text is ever required.
- **6.B.6.3** ✅ Add `render_pdf(resume, *, name="", title="", template="modern", output_path=None) -> Path` — create a `SimpleDocTemplate` (letter size, 1-inch margins), build a list of Platypus flowables from `_build_context()` (header paragraph, summary, skills, per-experience blocks, projects, certifications, education), call `doc.build(flowables)`, return the written `Path`.
- **6.B.6.4** ✅ Add a `_populate_pdf_flowables(context, styles)` helper — returns the `list[Flowable]` (paragraphs, spacers, bullet `ListFlowable`) for the resume body, mirroring `_populate_docx_paragraphs`.
- **6.B.6.5** ✅ Add a graceful import guard — `reportlab` and `pillow` install cleanly cross-platform (no system deps like WeasyPrint's `pango`), but imports are wrapped so a missing package raises a clear `ImportError`/log message naming the missing library. Confirmed `from reportlab.platypus import SimpleDocTemplate` imports under `uv run` on this machine.

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `reportlab>=4.0`; `pillow>=10.0` only if graphics added)

#### 6.B.7 Add `render_all()` convenience method

Takes `RewriteOutput`, `CoverLetterOutput`, candidate name, company name, and output directory. Generates all 4 resume formats (plaintext, markdown, DOCX, PDF) + 2 cover letter formats (plaintext, markdown). Returns `dict[str, Path]` mapping format name to file path.

**Depends on:** 6.B.2–6.B.6

**Sub-tasks:**

- **6.B.7.1** ✅ Add `render_all(resume, cover_letter, *, candidate_name, company_name, output_dir, resume_template="modern") -> dict[str, Path]` — wire `render_plaintext`/`render_markdown`/`render_docx`/`render_pdf`/`render_cover_letter_plaintext`/`render_cover_letter_markdown`, each writing to `build_output_path(...)`; `output_dir` is created eagerly inside `render_all`.
- **6.B.7.2** ✅ Ensure `output_dir` exists (`Path.mkdir(parents=True, exist_ok=True)`) before writing; handle a missing/empty `cover_letter` gracefully (`CoverLetterOutput | None`, letter formats added only when non-`None`/non-empty).
- **6.B.7.3** ✅ Return the `dict[str, Path]` keyed by format name (`"resume_plaintext"`, `"resume_markdown"`, `"resume_docx"`, `"resume_pdf"`, `"cover_letter_plaintext"`, `"cover_letter_markdown"`). Verified all 6 keys present and files non-empty.

**Files changed:** `client/templates/renderer.py`

#### 6.B.8 Wire renderer into pipeline (`pipeline.py`)

Add `candidate_name: str` and `company_name: str` parameters to `run_resume_pipeline()`. After tone polishing and cover letter agents complete, call `ResumeRenderer.render_all()` and store output paths in the pipeline result dict.

**Depends on:** 6.B.7

**Sub-tasks:**

- **6.B.8.1** ✅ Add `candidate_name: str = ""` and `company_name: str = ""` parameters to `run_resume_pipeline()` (threaded through `sample_run()`).
- **6.B.8.2** ✅ After the tone polishing and cover letter agents complete, instantiate `ResumeRenderer()` and call `render_all(...)` with the collected `polished_resume`/`cover_letter` outputs. Skip rendering when `candidate_name` is empty (INFO log). A `_to_rewrite_output()` helper converts the parsed resume into a `RewriteOutput`; `output_dir` is `Path("output")`; paths are captured in a local `output_files` dict.
- **6.B.8.3** ✅ Store the returned `dict[str, Path]` in the pipeline result dict under an `"output_files"` key (alongside the agent output keys).

**Files changed:** `pipeline.py`

#### 6.B.9 Add unit tests for `ResumeRenderer`

**Depends on:** 6.B.1–6.B.7

**Sub-tasks:**

- **6.B.9.1** ✅ Create `tests/test_renderer.py` with a sample `RewriteOutput` fixture (patterns from `tests/test_formatter.py` / `tests/conftest.py`).
- **6.B.9.2** ✅ Template loading, `render_plaintext()`, `render_markdown()` — sections present, ordering, `_clean_output()` behavior, unknown-template `KeyError`. 15 tests.
- **6.B.9.3** ✅ `render_cover_letter_plaintext()` / `render_cover_letter_markdown()` — body text, salutation (`Dear Hiring Manager,`), `Sincerely,` + candidate signature, rendered date. 7 tests.
- **6.B.9.4** ✅ `build_output_path()` — naming pattern, `YYYYMMDD_HHMM` date format, slugification, extension defaults, output dir joining. 8 tests.
- **6.B.9.5** ✅ `render_all()` with `tmp_path` + mocked individual renderer methods — 6 files written with the naming pattern, all 6 keys returned. 5 tests.
- **6.B.9.6** ✅ DOCX/PDF smoke tests — render to a real `tmp_path` file and assert a non-empty file is produced (skip if optional deps unavailable; `pytest.importorskip`). 2 tests: `.docx` produced & non-empty, PDF produced with a `%PDF` magic header.

**Files changed:** new file `tests/test_renderer.py`

### 6.10 Dependency Library Notes & Cautions

Caveats from adding the 6.B dependencies:

- **`reportlab` + `pillow`:** Both are pure wheels, install cleanly cross-platform, with **no system-level deps** (unlike WeasyPrint, which needs `pango`/`cairo`). If a profile photo, icons, or complex graphical decorations are ever added, **`pillow` must be installed alongside `reportlab`** — Platypus embeds and sizes images through PIL (`_img_utils`, `Image` flowable). (Once Pillow 10+ is installed, ReportLab 4.x resolves a known wheel/pillow naming collision automatically.)
- **ReportLab built-in fonts (base-14):** Helvetica/Helvetica-Bold/Times are Type-1 fonts that **cannot render Unicode/emoji** (the ASCII-only convention sidesteps this). If non-Latin text is ever needed, register a TTF via `pdfmetrics.registerFont(TTFont(...))`.
- **`python-docx`:** Pure Python, no system deps or font-caching — the lowest-risk dependency in 6.B. Only writes OOXML.
- **`jinja2`:** No system issues; templates validated once per render with a single cached `Environment` (in `ResumeRenderer.__init__`). `StrictUndefined` surfaces template bugs.
- **`pytest.importorskip` for 6.B.9.6:** DOCX/PDF smoke tests skip (not fail) when `python-docx`/`reportlab` are unavailable (and the `markdown` package is no longer needed — dropped from 6.B.6.1).

---

## Phase 8: Enforce Structured JSON Output via `response_format`

**Status:** ✅ DONE — §8.1–§8.8 complete (incl. both optional follow-ups)

**Goal:** Make every JSON-returning LLM call request structured JSON through the provider's native mechanism (`response_format`) instead of relying on prompt instructions alone. The agent-side `_parse_json` helpers stay as a safety net.

Both providers support a native JSON mode that strongly constrains the response:

- **OpenAI** (`OpenAIClient`): pass `response_format={"type": "json_object"}` to `chat.completions.create()`.
- **Ollama** (`OllamaClient`): pass `format="json"` to the ollama `chat()` call.

### 8.1 Extend the `ModelClient` interface

**File:** `client/model_client.py`

`chat()` has a required `response_format: str` parameter (`"json"` is the only supported value) plus optional `json_schema: dict[str, Any] | None = None`. No default and no `None` passthrough: free-text responses are no longer part of the contract.

### 8.2 OllamaClient — pass `format="json"` / schema

**Status:** ✅ DONE

**File:** `client/ollama_client.py`

- Native JSON mode always on: `format=actual_format` where `actual_format = json_schema if json_schema is not None else "json"`.
- Ollama's JSON mode guarantees a **valid JSON object** but not the schema — Pydantic validation in the agents still enforces the schema.
- Debug log reports the actual format value (schema dict or `"json"`).

### 8.3 OpenAIClient — pass `response_format={"type": "json_object"}` / schema envelope

**Status:** ✅ DONE

**File:** `client/open_ai_client.py`

- Native JSON mode always on: `{"type": "json_object"}` by default, or `{"type": "json_schema", "json_schema": {"name": ..., "schema": ..., "strict": True}}` when `json_schema` is provided.
- Schema name derived from the Pydantic `title` via `_schema_name` (validated against `^[a-zA-Z0-9_-]{1,64}$`).
- OpenAI's `json_object` mode requires the word "json" to appear somewhere in the messages — all agent prompts satisfy this ("Output only valid JSON") — **do not remove the rule string**.

### 8.4 Update every call site

**Status:** ✅ DONE

All `client.chat(...)` callers pass `response_format="json"`:

| Call site | File |
|---|---|
| `PipelineAgent.run` | `pipeline.py` |
| `SimpleAgent.run` | `basic.py` |
| Agent 1 JD Parsing | `client/agents/jd_parsing.py` (`_try_llm`) |
| Agent 2 Resume Parsing | `client/agents/resume_parsing.py` (`_try_llm`) |
| Agent 3 Gap Analysis | `client/agents/gap_analysis.py` (`_try_llm`) |
| Agent 4 Resume Rewrite | `client/agents/resume_rewrite.py` (`_try_llm`) |
| Agent 5 ATS Compliance | `client/agents/ats_compliance.py` (`_try_llm`) |
| Agent 6 Tone Polishing | `client/agents/tone_polishing.py` (`_try_llm`) |
| Agent 7 Cover Letter | `client/agents/cover_letter.py` (`_try_llm`) |
| FormatDetector resume LLM fallback | `client/format_detector.py` (`_llm_parse_resume`) |
| FormatDetector JD LLM fallback | `client/format_detector.py` (`_llm_parse_job_description`) |

### 8.5 Keep the `_parse_json` safety net

**Status:** ✅ DONE

The per-agent `_parse_json` / `FormatDetector._safe_json` helpers (strip fences → `json.loads`) stay. `response_format` is a strong hint, not a guarantee — a local Ollama model can still emit fence-wrapped or truncated JSON.

### 8.6 Tests

**Status:** ✅ DONE

**Files:** `tests/test_model_clients.py` (new)

- Unit test `OllamaClient` always passes `format="json"` to the underlying `ollama.AsyncClient.chat`. ✅
- Unit test `OpenAIClient` always passes `response_format={"type": "json_object"}`. ✅
- An assertion/grep-style test that every `client.chat(...)` call site passes `response_format="json"`. ✅
- Manual: `uv run python wip_testing/test_<agent>.py` with `LOG_LEVEL=DEBUG` — confirm JSON mode and first-attempt success. ✅ Verified 2026-08-03 (Ollama 0.32.5).

### 8.7 ✅ DONE — provider-native JSON Schema (Structured Outputs)

- `client/json_utils.py` — `model_to_json_schema(model: type[BaseModel]) -> dict[str, Any]` builds a strict-mode provider-ready schema from `model.model_json_schema()`: `additionalProperties: false` on every object with an explicit `properties` map and every property moved into `required` (recursively, including nested `$defs`). Free-form dict fields (`dict[str, str]` like `company_signals`) keep their value schema — hardening them with `additionalProperties: false` would force the model to emit an empty object (bug found and fixed during live testing).
- `client/model_client.py` — `chat()` gains optional `json_schema: dict[str, Any] | None = None`.
- `client/ollama_client.py` — when `json_schema` is provided, `format` carries the schema dict; otherwise `format="json"`.
- `client/open_ai_client.py` — when `json_schema` is provided, `response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": ..., "strict": True}}`; otherwise `{"type": "json_object"}`.
- **All 7 agents pass `json_schema=model_to_json_schema(<OutputModel>)`** in `_try_llm`.

Verification — **COMPLETE (Ollama)**, model-version dependent:

- ✅ Ollama `qwen2.5:7b-instruct` on server **0.32.5** (`format=<schema>` supported since 0.5.0): verified end-to-end — full 7-agent chain succeeded with no fallbacks; raw `format=<schema>` API test returned schema-conformant JSON; debug logs show the schema dict in `format=`.
- ⚠️ OpenAI: `gpt-4o-mini-2024-07-18`+, `gpt-4o-2024-08-06`+ required — not verified (no API key). The `json_schema` envelope + `_schema_name` are covered by stub tests.

### 8.8 ✅ DONE — shared JSON parser

- `client/json_utils.py` — `parse_json_response(raw: str, *, plain_text_fallback: str | None = None) -> dict[str, Any] | None` strips markdown fences, calls `json.loads`, logs failure. The optional `plain_text_fallback` preserves the cover letter agent's special case (substantial non-JSON text >50 chars becomes `{"cover_letter": text}`).
- Each agent's `_parse_json` is now a one-line wrapper over the shared helper; `FormatDetector._safe_json` likewise delegates.
- Removed now-unused `import json` / `import re` where the parser was the only user.

---

## Phase 8 (Contact Info): Contact Information Extraction & Cover Letter Integration

**Status:** Complete — archived 2026-08-06 (8.1-8.3 all DONE)

**Goal:** Extract the candidate's phone number, email address, LinkedIn URL, and GitHub URL from the parsed resume and thread them through to cover letter generation. Update the cover letter templates to render these contact details, and post-process LLM output so the contact line always lands in the finished letter. Pure-Python wiring of existing infrastructure — no new LLM calls.

### 8.1 Add contact fields to `ResumeParsingOutput`

**Status:** DONE

- `ResumeParsingOutput` in `client/models.py` gains optional contact fields: `phone: str = ""`, `email: str = ""`, `linkedin: str = ""`, `github: str = ""` (mirrored on `ParsedResume`).
- `FormatDetector` gains `_extract_phone()`, `_extract_email()`, `_extract_linkedin()`, `_extract_github()` (with regex patterns); `parse_resume()` / `_llm_parse_resume()` populate the four fields.
- `ResumeParsingAgent._regex_fallback()` assigns the `FormatDetector` contact values onto `ResumeParsingOutput`.
- LLM path: `_SYSTEM_PROMPT` (`purpose`) lists `phone, email, linkedin, github` with the rule "Extract the candidate's phone number, email address, LinkedIn profile URL, and GitHub profile URL exactly as they appear in the resume; empty string if absent."
- Coercion: new `_coerce_str()` helper in `client/models.py` handles dict→string (and list→string) inputs, applied to the four contact fields via a validator — so an LLM returning a structured contact object still validates.

**Files changed:** `client/models.py`, `client/format_detector.py`, `client/agents/resume_parsing.py`

### 8.2 Update cover letter templates to include contact info

**Status:** DONE

- `client/templates/cover_letter.py`: the shared `COVER_LETTER` template (`plaintext` and `markdown` keys) renders an optional header contact line via `{% if contact_line %}{{ contact_line }}` (the `*...*`-italicized form in markdown). Note: there is no `cover_letter.j2` file and no per-style variants — cover letter styling lives in this one dict; `modern`/`classic`/`minimal` are resume-only templates.
- Renderer thread-through: `client/templates/renderer.py` — `render_cover_letter_plaintext()` / `render_cover_letter_markdown()` / `render_all()` accept optional `phone`/`email`/`linkedin`/`github` kwargs; `_build_cover_letter_context()` joins the non-empty values on ` | ` into `contact_line`. (No `render_cover_letter_docx/pdf` — letters render as plaintext + markdown only.)
- Empty/absent contact fields render neither the line nor a spurious blank line (`test_cover_letter_no_blank_line_between_name_and_date`).
- `test_renderer.py` additions: cover letter plaintext/markdown include contact line; line omitted when empty; `render_all` letter files include contact info.

**Files changed:** `client/templates/cover_letter.py`, `client/templates/renderer.py`, `tests/test_renderer.py`

### 8.3 Pass contact info to the Cover Letter agent and use it in generation

**Status:** DONE

- `client/agents/cover_letter.py`: `_contact_from_resume(resume_json)` builds a `CANDIDATE CONTACT INFORMATION` block; `_try_llm()` passes it into the prompt with the constraint that the listed details are the *only* contact info the model may use (never invent contact details), and may close with a contact line.
- `_apply_contact_info(result, resume_json)` post-processes the validated `CoverLetterOutput` inside `_try_llm` (after Pydantic validation + length check): when at least one contact value exists and none appears in the letter, it appends a ` | `-joined contact line after the signature and logs at INFO. When values are already present or no contact info exists, the letter is returned unchanged.
- Fallback: `_contact_signature_line(resume_data)` joins the resume's contact fields; `_build_fallback_cover_letter()` appends it to the signature (`Sincerely,\n<Name>\n<contact line>`). Missing fields degrade gracefully (no line).
- Tests in `tests/test_cover_letter_validation.py`: `TestApplyContactInfo` (inject-when-absent, leave-unused-when-present, no-contact unchanged, invalid JSON unchanged, missing input breaks nothing), fallback contact-line / signature-line cases, and LLM-success path that injects the contact block.

**Files changed:** `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

**Verification:** `uv run pytest tests/ -q` 322 passed (up from 306; +11 cover letter validation = 91, +5 renderer = 43); `uv run ruff check .` clean; `uv run pyright` (strict) 0 errors. The LSP "private member used outside class" warnings inside tests are pre-existing pyright-strict noise under the `tests/` exclusion (see AGENTS.md Toolchain quirks).

---

## File Structure (Current State)

```plaintext
client/
  __init__.py                      # EXISTS (empty)
  errors.py                        # EXISTS ✅
  model_client.py                  # EXISTS ✅
  model_registry.py                # EXISTS ✅
  json_utils.py                    # EXISTS ✅ (shared parse_json_response + model_to_json_schema)
  ollama_client.py                 # EXISTS ✅ (configurable timeout, default 300s)
  open_ai_client.py                # EXISTS ✅
  format_detector.py               # EXISTS ✅ (expanded with projects, metrics, keywords)
  formatter.py                     # EXISTS ✅ (format_resume_markdown/plain, format_cover_letter — Phase 6.2)
  models.py                        # EXISTS ✅ (ParsedResume, ParsedJobDescription, JDParsingOutput, + all agent output models)
  templates/                       # EXISTS ✅ (renderer.py added — Phase 6.3)
    __init__.py                    # EXISTS
    renderer.py                    # EXISTS ✅ (ResumeRenderer: render_plaintext/markdown, cover letter, DOCX, PDF, render_all — Phase 6.3)
    modern.py                      # EXISTS
    classic.py                     # EXISTS
    minimal.py                     # EXISTS
    cover_letter.py                # EXISTS
  agents/                          # EXISTS ✅ (all 7 agents done)
    __init__.py                    # EXISTS ✅ (exports all 7 agent classes)
    jd_parsing.py                  # EXISTS ✅ - Agent 1 (JDParsingAgent)
    resume_parsing.py              # EXISTS ✅ - Agent 2 (ResumeParsingAgent)
    gap_analysis.py                # EXISTS ✅ - Agent 3 (GapAnalysisAgent)
    resume_rewrite.py              # EXISTS ✅ - Agent 4 (ResumeRewriteAgent)
    ats_compliance.py              # EXISTS ✅ - Agent 5 (ATSComplianceAgent)
    tone_polishing.py              # EXISTS ✅ - Agent 6 (TonePolishingAgent)
    cover_letter.py                # EXISTS ✅ - Agent 7 (CoverLetterAgent)
config/
  __init__.py                      # EXISTS (empty)
  agents.py                        # EXISTS ✅
tests/
  __init__.py                      # EXISTS ✅
  conftest.py                      # EXISTS ✅ (shared fixtures)
  test_format_detector.py          # EXISTS ✅ (46 tests)
  test_jd_parsing.py               # EXISTS ✅ (19 tests)
  test_resume_rewrite_validation.py # EXISTS ✅ (56 tests)
  test_cover_letter_validation.py  # EXISTS ✅ (91 tests)
  test_formatter.py                # EXISTS ✅ (41 tests — Phase 6.2)
  test_renderer.py                 # EXISTS ✅ (43 tests — Phase 6.3)
  test_model_clients.py            # EXISTS ✅ (11 tests — response_format + Structured Outputs plumbing)
  test_json_utils.py               # EXISTS ✅ (15 tests — shared parser + JSON Schema helpers)
docs/
  TESTING.md                       # EXISTS ✅
  models.md                        # EXISTS ✅
  logging-info.md                  # EXISTS ✅
pipeline.py                        # EXISTS ✅
basic.py                           # EXISTS ✅
logging_config.py                  # EXISTS ✅ (centralized logging, LOG_LEVEL env var)
pyproject.toml                     # EXISTS ✅ (ruff, pyright, pytest config)
AGENTS.md                          # EXISTS ✅
resume-done.md                     # THIS FILE
resume-todo.md                     # Remaining work (see link at top)
bots.md                            # UNCHANGED (reference)
README.md                          # EXISTS ✅
opencode.json                      # EXISTS ✅
.gitignore                         # EXISTS ✅
sample/                            # EXISTS ✅
  jobs/                            # 2 sample JDs (3Pillar.txt, Zafin.txt)
  resume/                          # 1 sample resume (Peter-Letkeman-Resume.txt)
wip_testing/
  test_parsing.py                  # EXISTS ✅ (regex + LLM parsing demo)
  test_job_description.py          # EXISTS ✅ (Agent 1 test)
  test_resume_parsing.py           # EXISTS ✅ (Agent 2 test)
  test_gap_analysis.py             # EXISTS ✅ (Agents 1-3 chain test)
  test_resume_rewrite.py           # EXISTS ✅ (Agents 1-4 chain test)
  test_ats_compliance.py           # EXISTS ✅ (Agents 1-5 chain test)
  test_tone_polishing.py           # EXISTS ✅ (Agents 1-6 chain test)
  test_cover_letter.py             # EXISTS ✅ (Agents 1-7 chain test)
```

---

## Phase 8.5: Skill Normalization & Canonical Taxonomy

**Status:** ✅ COMPLETE (8.5.1–8.5.6)

A centralized skill normalization layer with a canonical skill taxonomy maps synonyms, abbreviations, and variations to standard skill names. This enables accurate JD↔resume skill matching, gap analysis, and keyword optimization across all agents.

### 8.5.1 Create skill normalization module

**Status:** ✅ DONE

Created the `client/skills/` package. `SkillNormalizer` (in `normalizer.py`) maps raw skill names to canonical taxonomy names deterministically (no LLM). Taxonomy lives in `taxonomy.json` (`client/skills/taxonomy.json`), loaded via `importlib.resources`.

- Created `client/skills/__init__.py` (exports `SkillNormalizer`), `client/skills/normalizer.py`, `client/skills/taxonomy.json`.
- Taxonomy maps canonical skill names to variants/synonyms/abbreviations (e.g., `"JavaScript": ["js", "javascript", "ecmascript", "es6", "es2015"]`, `"React": ["react.js", "reactjs"]`, `"Amazon Web Services": ["aws", "amazon web services", "amazon cloud"]`).
- `SkillNormalizer` API:
  - `normalize(skill) -> str` — maps to canonical form via lower/squashed/tokenized key matching; returns the canonical name on a hit, else the normalized lowercase tokenized form.
  - `canonicalize(skill) -> str` — alias for `normalize()`.
  - `normalize_list(skills) -> list[str]` — normalizes, canonicalizes, de-duplicates (order-preserving).
  - `get_variants(canonical) -> list[str]` — known variants for a canonical skill (empty when unknown).
  - `match_skills(jd_skills, resume_skills) -> dict` — returns `missing` / `matched` / `extra` using canonical forms.
- Categories `programming_languages`, `frameworks`, `databases`, `cloud`, `tools`, `soft_skills` present in `taxonomy.json`.
- Tests in `tests/test_skill_normalizer.py` (15 tests): normalization, canonicalization, dedup, matching, variant lookup.

**Files changed:** new `client/skills/normalizer.py`, `client/skills/taxonomy.json`, `client/skills/__init__.py`, `tests/test_skill_normalizer.py`

### 8.5.2 Integrate skill normalization into JD Parsing Agent

**Status:** ✅ DONE

`JDParsingAgent` canonicalizes skill lists on both the LLM and regex paths via a shared `_NORMALIZER = SkillNormalizer()` instance.

- `_regex_fallback()`: `required_skills=_NORMALIZER.normalize_list(parsed.requirements)`, `preferred_skills=_NORMALIZER.normalize_list(parsed.nice_to_have)`.
- `_SYSTEM_PROMPT` rule added: "Normalize all skills to their canonical form (e.g., 'JS' → 'JavaScript', 'React.js' → 'React', 'AWS' → 'Amazon Web Services')."
- Post-process LLM output: after `_sync_company_name(result)`, return `result.model_copy(update={"required_skills": ..., "preferred_skills": ...})` with both lists normalized.

**Files changed:** `client/agents/jd_parsing.py`

### 8.5.3 Integrate skill normalization into Resume Parsing Agent

**Status:** ✅ DONE

`ResumeParsingAgent` canonicalizes the resume skills list on both the LLM and regex paths via a shared `_NORMALIZER = SkillNormalizer()` instance.

- `_regex_fallback()`: `skills=_NORMALIZER.normalize_list(parsed.skills)`.
- `_SYSTEM_PROMPT` rule added: same canonical-form rule as JD parsing.
- Post-process LLM output: `parsed.skills = _NORMALIZER.normalize_list(parsed.skills)` after `ResumeParsingOutput(**data)` validation.

**Files changed:** `client/agents/resume_parsing.py`

### 8.5.4 Integrate skill normalization into Gap Analysis Agent

**Status:** ✅ DONE

`GapAnalysisAgent` feeds canonical skill lists to the LLM prompt, canonicalizes the LLM's skill fields, and cross-checks the LLM against deterministic matching.

- `_canonical_skills_context(jd_json, resume_json)` appends a `NORMALIZED SKILLS` block (canonical JD / resume lists + the deterministic cross-check result) to the LLM prompt.
- `_post_process()` returns `result.model_copy(update={...})` with `missing_skills`, `weak_skills`, `strong_matches`, and `keyword_strategy` all normalized.
- `SkillNormalizer.match_skills()` used as a deterministic cross-check; `logger.warning` emitted when the `missing` set differs from the LLM's normalized `missing_skills`.

**Files changed:** `client/agents/gap_analysis.py`

### 8.5.5 Integrate skill normalization into Resume Rewrite Agent

**Status:** ✅ DONE

`ResumeRewriteAgent` uses the shared `SkillNormalizer` for canonical skill matching in tailoring and sanitizing. The tolerant (substring/token) matcher is retained for fuzzy matches but is now canonical-aware.

- `_tailor_skills` priority / "present" lists use `_NORMALIZER.normalize_list`; `_skill_matches` first checks `_NORMALIZER.normalize(skill)` before the fuzzy substring/token path (case-insensitive).
- `_sanitize_skills()` uses `_NORMALIZER.normalize_list(input_skills)` and folds `_NORMALIZER.match_skills(result.skills, input_skills)["matched"]` into the keep/drop decision.
- Keyword dedup in `_tailor_skills` compares `_NORMALIZER.normalize(keyword)` against canonical `present`/`additions_norm` before prepending.

**Files changed:** `client/agents/resume_rewrite.py`

### 8.5.6 Integrate skill normalization into Cover Letter Agent

**Status:** ✅ DONE

`CoverLetterAgent` uses the shared `SkillNormalizer` for skill matching and canonical keyword highlighting in the fallback builder.

- Replaced the local `_normalize_skill` helper; `_skill_in_list` now tries `_NORMALIZER.normalize(skill)` against `_NORMALIZER.normalize_list(skills)` first, then the tolerant tokenized fuzzy matcher.
- `_overlapping_skills()` returns `_NORMALIZER.normalize(skill)` (canonical form) for each overlapping skill, so the fallback letter highlights standard skill names.
- Removed the redundant local `_normalize_skill` test class from `tests/test_cover_letter_validation.py`; coverage moved to `tests/test_skill_normalizer.py`.

**Files changed:** `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

**Verification (Phase 8.5):** `uv run pytest` → **362 passed**; `uv run ruff check .` clean; `uv run pyright` → **0 errors**.

---

## Phase 9: Cover Letter Creation Fixes (a/b/c)

**Status:** ✅ DONE (9.1–9.4)

Fixes for three defects in cover letter creation that surfaced on live runs: experience entries coming back out of chronological order, the company name being taken from the candidate's resume (or left as `[Company Name]`), and the candidate name left as `[Your Name]`. All three are handled with **pure Python post-processing — no additional LLM calls**.

### 9.1 Chronological ordering of experience (in `resume_rewrite.py`)

**Status:** ✅ DONE

`_try_llm()` no longer **rejects** the whole rewrite when experiences are out of order (which dropped the entire LLM result and fell back to `_parsed_to_rewrite()`). It now **intercepts and sorts** the experience section so the rest of the LLM's work is preserved.

- Added `_ensure_chronological(result: RewriteOutput) -> RewriteOutput` — pure Python, no LLM call.
- Sorts `result.experience` by `_extract_start_year(entry.dates)` descending (most-recent-first), with `sorted()` on a stable key that falls back to the original index so the sort is lossless.
- Entries whose start year is `None` (unparseable dates) are preserved at the end in their original relative order; never drops entries (input length == output length).
- A fully-unsortable list (all `None` years) is returned unchanged.
- `_validate_chronological` downgraded to an optional `DEBUG`-level signal only; `_ensure_chronological` is the source of truth.
- Input resume experience is pre-sorted most-recent-first in `ResumeParsingAgent._regex_fallback()` (idempotency; the rewrite sort becomes a cheap no-op in the common case).

**Files changed:** `client/agents/resume_rewrite.py`, `client/agents/resume_parsing.py`, `tests/test_resume_rewrite_validation.py`

### 9.2 Company Name must come from the JD, not the candidate's resume

**Status:** ✅ DONE

The cover letter previously could use a company name pulled from the candidate's resume (a past employer) or the literal placeholder `[Company Name]`. The source of truth is `JDParsingOutput.company_name` (Phase 4.3.F), surfaced through the shared `_company_from()` helper. Both failure modes are fixed deterministically (no additional LLM calls).

- `_company_directive()` in `_try_llm()` injects the exact target company into the prompt; a new rule forbids using a company from the candidate's resume as the target.
- `_apply_company_name(result, jd_json, resume_json="")` resolves the target via `_company_from(jd_data)` (top-level `company_name`, else `company_signals["company_name"]`).
- `_PLACEHOLDER_TOKENS` match ASCII tokens `[Company Name]`, `[Company]`, `<Company Name>`, `[Employer Name]` and replace with the resolved JD company name via `str.replace`.
- `_resume_company_in_letter()` detects a resume-company present but the JD company absent; `_replace_first_casefold()` substitutes the **first** occurrence with the JD name. Guarded so a resume company that matches the target is ignored.
- `_check_company` (already present) now only `logger.warning` on mismatch — it does not reject.
- `_build_fallback_cover_letter()` confirmed to use `_company_from` and never emit `[Company Name]` (company omitted when absent).
- Tests added in new `TestApplyCompanyName` class (`tests/test_cover_letter_validation.py`).

**Files changed:** `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

### 9.3 Candidate Name must come from the candidate's resume

**Status:** ✅ DONE

The cover letter's signature / opening previously contained `[Your Name]`, because `ResumeParsingOutput` had **no `name` field** even though `FormatDetector` already extracts `ParsedResume.name`. `name` now flows through the pipeline and is post-processed into the cover letter.

- Added `name: str = ""` to `ResumeParsingOutput` in `client/models.py`.
- `ResumeParsingAgent._regex_fallback()` sets `name=_normalize_extracted_name(parsed.name)`; the LLM path includes `name` in `_SYSTEM_PROMPT` / field list, with rule "Extract the candidate's full name exactly as it appears at the top of the resume; empty string if absent."
- `_apply_candidate_name(result, resume_json)` reads the name via `_candidate_name_from_resume` and replaces `[Your Name]` / `[Candidate Name]` / `<Your Name>` residue with the resolved resume name (leaves the letter untouched when empty). No LLM call.
- `_build_fallback_cover_letter()` `_read_str(resume_data, "name").strip() or "Candidate"` now resolves to the real name.
- Tests added `TestResumeParsingName` and `TestApplyCandidateName`.

**Files changed:** `client/models.py`, `client/agents/resume_parsing.py`, `client/agents/cover_letter.py`, `tests/test_cover_letter_validation.py`

### 9.4 Cross-cutting notes

**Status:** ✅ DONE

- `_try_llm()` stays pure: all string replacement / sorting (`_ensure_chronological`, `_apply_company_name`, `_apply_candidate_name`) runs on the validated `RewriteOutput`/`CoverLetterOutput` **after** Pydantic validation; data returned via `model_copy` / new output object, never mutated in place.
- ASCII-only convention: tokens used are `[Company Name]`, `[Your Name]`, `[Candidate Name]`, `<Your Name>`, `[Employer Name]` (no extended characters).
- Verification: `uv run pytest` → **350 passed**; `uv run ruff check .` clean; `uv run pyright .` → **0 errors**; manual `wip_testing/test_cover_letter.py` (full 1–7 chain, LLM success, real candidate name `Peter Letkeman` in signature, contact line injected, company honored) and `wip_testing/test_resume_rewrite.py` (full 1–4 chain, chronologically ordered, certifications preserved).

**Files changed:** (verification only — no code changes)

---

## Tooling

- **Lint/Format:** ruff (`ruff check .`, `ruff format .`) — rules: E, F, I, UP, B, SIM
- **Typecheck:** pyright (strict mode, Python 3.14)
- **Test:** pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- **Config:** all in `pyproject.toml`
