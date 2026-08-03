# Resume Pipeline Implementation Plan

## Overview

Implement the full 7-agent resume optimization pipeline as described in `bots.md`. Each agent receives structured input, runs an LLM prompt, and returns validated JSON output. The pipeline chains agents sequentially: parsed data flows from one agent to the next.

---

## Current Architecture

The pipeline uses `PipelineAgent` (generic LLM wrappers with fixed system prompts) orchestrated by `AgentRunner`. Per-agent model assignment is handled by `ModelClientRegistry` + `config/agents.py`. The 7 agents are wired in `pipeline.py` via `run_resume_pipeline()`.

### What exists now

- `client/model_client.py` — Proper ABC for LLM clients
- `client/ollama_client.py` — Ollama client with error handling
- `client/open_ai_client.py` — OpenAI client with error handling
- `client/errors.py` — Custom LLM exceptions
- `client/format_detector.py` — Regex-based document parser with LLM fallback (connected), plain text support, projects, metrics, keywords extraction
- `client/models.py` — All Pydantic models: `ParsedResume`, `ParsedJobDescription`, `JDParsingOutput`, `ExperienceEntry`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`
- `client/model_registry.py` — Per-agent model assignment registry
- `logging_config.py` — Centralized logging (dictConfig, LOG_LEVEL env var)
- `client/templates/` — Jinja2 resume/cover letter templates (no renderer class)
- `client/agents/` — All 7 dedicated agent classes (JDParsingAgent, ResumeParsingAgent, GapAnalysisAgent, ResumeRewriteAgent, ATSComplianceAgent, TonePolishingAgent, CoverLetterAgent)
- `config/agents.py` — Environment-based agent-to-model configuration
- `pipeline.py` — `AgentRunner`, `PipelineAgent`, and `run_resume_pipeline()`
- `basic.py` — Single-agent demo
- `tests/test_format_detector.py` — 46 tests for FormatDetector regex parsing
- `tests/conftest.py` — Shared test fixtures
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

**No further work needed** for this phase. Agents 1-7 were implemented as dedicated classes (e.g., `JDParsingAgent`, `ResumeRewriteAgent`) rather than `PipelineAgent` instances, with per-agent LLM + validation + fallback logic.

---

### 2.3 JD Parsing Agent

**Status:** ✅ DONE

**Implemented:**

- `client/agents/jd_parsing.py` — dedicated `JDParsingAgent` class
- Uses system prompt from `bots.md`
- Parses LLM response as JSON, validates against `JDParsingOutput` Pydantic model
- Retries once with stricter rules on validation failure
- Falls back to `FormatDetector.parse_job_description()` on second failure
- `client/models.py` — added `JDParsingOutput` model with `@field_validator` for `company_signals` (accepts list or dict)
- `pipeline.py` — `sample_run()` uses `JDParsingAgent`; `run_resume_pipeline()` branches on model vs dict for the JD result only (agents 3-7 assume dict-style access — see §5.2)

**Files changed:** `client/agents/jd_parsing.py` (new), `client/agents/__init__.py` (new), `client/models.py`, `pipeline.py`

**Test:** `uv run python wip_testing/test_job_description.py`

**System prompt (from `bots.md`):**

```plaintext
You are the Job Description Parsing Agent. Your task is to extract structured, machine-readable information from a job description.
Produce a JSON object with the following fields:
- role_title
- seniority_level
- required_skills (hard skills only)
- preferred_skills
- responsibilities
- keywords (ATS-relevant terms)
- industry_terms
- company_signals (culture, values, mission)

Follow these rules:
- Do not add information not present in the job description.
- Normalize skills (e.g., "communication skills" → "communication").
- Extract all relevant keywords.
- Output only valid JSON.
```

**Input schema:**

```python
inputs = {"job_description": str}
```

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
    company_signals: dict[
        str, str
    ]  # {"culture": "...", "values": "...", "mission": "..."}
```

**Implementation:**

1. Build user prompt: `f"Extract structured data from this job description:\n\n{inputs['job_description']}"`
2. Call `self.client.chat(purpose=_SYSTEM_PROMPT, prompt=prompt, output=["json"], rules=rules, inputs=[jd_text])` inside `_try_llm()` (there is no `_chat` method; `rules` defaults to `["Output only valid JSON", "Do not add information not present in the JD"]` and is swapped for `_STRICT_RULES` on the retry)
3. Parse LLM response as JSON
4. Validate against `JDParsingOutput` Pydantic model
5. On validation failure: retry once with a stricter prompt ("You must output valid JSON only. No markdown, no explanation.")
6. On second failure: fall back to `FormatDetector.parse_job_description()` and wrap result in the expected schema

**Files changed:** new file `client/agents/jd_parsing.py`

---

### 2.4 Resume Parsing Agent

**Status:** ✅ DONE

**What to do:**

1. Create `client/agents/resume_parsing.py` with a dedicated agent that:
   - Uses the system prompt from `bots.md`
   - Parses LLM response as JSON
   - Validates against a `ResumeParsingOutput` Pydantic model
   - Falls back to `FormatDetector.parse_resume()` on failure

**System prompt (from `bots.md`):**

```plaintext
You are the Resume Parsing Agent. Your job is to convert a resume into structured JSON.
Extract the following fields:
- summary
- skills (normalize terms)
- experience (list of roles with: title, company, dates, responsibilities, achievements, metrics)
- projects
- certifications
- education

Rules:
- Preserve all quantifiable metrics.
- Convert bullet points into structured lists.
- Do not infer missing information.
- Output only valid JSON.
```

**Input schema:**

```python
inputs = {"resume": str}
```

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

1. Send the full resume text to the LLM first — `FormatDetector.parse_resume()` is NOT a pre-processor; it is used only as the fallback in `_regex_fallback` after both LLM attempts fail
2. Build user prompt with the full resume text
3. Call LLM with the system prompt
4. Parse JSON response
5. Validate against `ResumeParsingOutput`
6. On failure: retry with stricter prompt
7. On second failure: wrap `FormatDetector` output in the expected schema (converting flat bullet lists to `ExperienceEntry` objects where possible)

**Files changed:** new file `client/agents/resume_parsing.py`

---

## Phase 3: Analysis & Rewriting (Agents 3-5)

### 3.1 Create Gap Analysis Agent (`client/agents/gap_analysis.py`)

**Status:** ✅ DONE

**Purpose:** Compare parsed JD vs parsed resume, produce a tailoring strategy.

**System prompt (from `bots.md`):**

```plaintext
You are the Gap Analysis Agent.
Using the parsed job description and parsed resume, produce a Tailoring Strategy with:
- missing_skills
- weak_skills
- strong_matches
- recommended_emphasis
- keyword_strategy
- bullet_point_improvement_plan
- tone_guidance (technical, managerial, creative)

Rules:
- Base all analysis strictly on provided data.
- Identify the most impactful resume improvements.
- Output a structured JSON object.
```

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

**System prompt (from `bots.md`):**

```plaintext
You are the Resume Rewrite Agent.
Rewrite the resume using the Tailoring Strategy.
Output a full resume with:
- Updated summary
- Updated skills section
- Rewritten bullet points
- Quantified achievements
- ATS-aligned keywords
- Strong action verbs
- Clear, concise phrasing

Rules:
- Maintain factual accuracy.
- Do not invent employment history.
- You may add reasonable metrics only if implied (e.g., "managed a team" → "managed a team of 5").
- Produce clean, professional formatting.
- All experiences MUST be listed in proper chronological order (most recent first).
- No new experiences can be added - use the input resume as the reference for all experience entries.
- All certifications from the input resume MUST be included - use the input resume as the reference for certifications.
- Do not use the extended character set:
  - " instead of " or "
  - → becomes ->
  - etc
```

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
5. ~~Validate experiences are in chronological order (most recent first)~~ NOT IMPLEMENTED — prompt rule only (resume_rewrite.py:37); no post-validation. See §4.3.A.4
6. Validate no new experiences were added (compare with input resume experience count) — implemented as `_validate_experience_count` (resume_rewrite.py:204)
7. Validate all certifications from input resume are present in output — implemented as `_validate_certifications` (resume_rewrite.py:208)
8. On failure: retry with explicit instruction "Output a JSON object matching this exact schema: ..."
9. On second failure: return the parsed resume unchanged with a warning logged
10. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/resume_rewrite.py`
- new file `wip_testing/test_resume_rewrite.py`

---

### 3.3 Create ATS Compliance Agent (`client/agents/ats_compliance.py`)

**Status:** ✅ DONE

**Purpose:** Evaluate the rewritten resume for ATS compatibility and fix issues.

**System prompt (from `bots.md`):**

```plaintext
You are the ATS Compliance Agent.
Evaluate the rewritten resume for ATS compatibility.
Output a JSON object with:
- ats_score (0-100)
- missing_keywords
- formatting_issues
- clarity_issues
- recommended_fixes
- auto_fixes_applied
- final_resume

Rules:
- Ensure keyword coverage.
- Remove ATS-unfriendly elements (tables, images, symbols).
- Improve clarity and consistency.
- Verify all certifications from the input resume are present in the output.
- Verify experiences are in chronological order (most recent first).
- Do not add any new experiences - use the input resume as the reference.
```

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
4. Validate `ats_score` is between 0 and 100 — implemented as a clamp (ats_compliance.py:186-188), not a reject; the Pydantic model also enforces `ge=0, le=100`
5. ~~Validate all certifications from input resume are present in the final resume~~ NOT IMPLEMENTED — no cert check in ats_compliance.py
6. ~~Validate experiences are in chronological order (most recent first)~~ NOT IMPLEMENTED — no order check in ats_compliance.py
7. On failure: retry; on second failure, return a default low-score result with the resume unchanged (`_default_result`, ats_compliance.py:268-279)
8. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/ats_compliance.py`
- new file `wip_testing/test_ats_compliance.py`

---

## Phase 4: Polish & Cover Letter (Agents 6-7)

### 4.1 Create Tone Polishing Agent (`client/agents/tone_polishing.py`)

**Status:** ✅ DONE

**Purpose:** Improve tone and professionalism without changing facts.

**System prompt (from `bots.md`):**

```plaintext
You are the Tone Polishing Agent.
Improve the tone of the resume while preserving meaning.
Apply:
- Professional tone
- Confident phrasing
- Clear narrative flow
- Role-appropriate voice (technical, managerial, creative)
- Output the polished resume.

Rules:
- Do not change factual content.
- Do not add new achievements.
- Improve readability and cohesion.
```

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

**Note:** This agent works on raw text, not structured JSON. The prompt should instruct the LLM to return JSON with a single `polished_resume` field containing the full resume.

**Files changed:**

- new file `client/agents/tone_polishing.py`
- new file `wip_testing/test_tone_polishing.py`

---

### 4.2 Create Cover Letter Agent (`client/agents/cover_letter.py`)

**Status:** ✅ DONE

**Purpose:** Generate a tailored cover letter.

**System prompt (from `bots.md`):**

```plaintext
You are the Cover Letter Tailoring Agent.
Using the job description, parsed resume, and tailoring strategy, write a compelling, personalized cover letter.
Include:
- Strong opening paragraph
- Clear alignment with job requirements
- 2-3 achievement highlights
- Narrative showing impact
- ATS-friendly keywords woven naturally
- Confident closing paragraph

Rules:
- Maintain professional tone.
- Do not fabricate achievements.
- Keep length between 450-600 words.
```

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
5. ~~Validate word count is between 450-600~~ NOT IMPLEMENTED — current code only warns at < 250 / > 700 and always accepts (cover_letter.py:260-269). See §4.3.B.4
6. On failure: retry; on second failure, return a minimal generic cover letter
7. Create a standalone test script that can be used to test this functionality

**Files changed:**

- new file `client/agents/cover_letter.py`
- new file `wip_testing/test_cover_letter.py`

---

### 4.3 Fix LLM Fallback Falsehoods

**Status:** ⚠️ PARTIAL — §F (company_name), §A (resume rewrite validation), and §B (cover letter validation) are DONE; §C–§E remain

**Problem:**
Two distinct failure modes produce bad output:

1. **LLM succeeds but fabricates** — The LLM returns valid JSON, but it adds skills not in the original resume, invents achievements, or writes generic text unrelated to the target company.
2. **LLM fails, fallback is useless** — Agents fall back to defaults that are either unoptimized (resume rewrite returns unchanged data) or contain placeholder text (cover letter returns `_MINIMAL_COVER_LETTER` with `[Your Name]`).

**Root Cause:**

- No post-validation to catch falsehoods before returning LLM results
- Fallback templates are too generic and don't use actual input data
- Existing validation is incomplete

**What already exists:**

- `resume_rewrite.py:204-210` — validates experience count (`_validate_experience_count`) and certifications (`_validate_certifications`) ✅
- `cover_letter.py:255-269` — validates word count (warns but accepts) and empty-content fallback ⚠️

**Key data facts that constrain the design:**

- `JDParsingOutput` now has a **`company_name` field** (see §F, ✅ DONE) — `company_signals` also carries it under the `"company_name"` key. The cover letter company check (B.2) and fallback letter (C.2) can rely on this structured source of truth.
- `Role title` **is** structured (`JDParsingOutput.role_title`) — a reliable check target for the cover letter.
- Company names **are** structured in the resume (`ExperienceEntry.company`) — a reliable check target for resume rewrite.
- The word-count spec is **450-600** (per `bots.md` and `cover_letter.py` prompts). The todo's old "250-350 words" references in §4.2 and §7.1 were **wrong** and have already been corrected.

**Approach: F first (adds `company_name`, unblocking B.2/C.2), then A + B + C in that priority order. D last.**

**Scope note:** This section targets `resume_rewrite.py` and `cover_letter.py` — the two agents with template/placeholder fallbacks. Other agents' fallbacks are less harmful but worth flagging:

- **GapAnalysisAgent** returns an empty `GapAnalysisOutput()` on failure (lines 73, 91) — cascades an empty strategy to downstream agents. Acceptable (no safe deterministic alternative), but must be logged so failures are visible.
- **ATSComplianceAgent** returns `_default_result()` with a hardcoded `ats_score=30` and `"Unable to evaluate -- LLM unavailable"` (lines 268-279). A fixed score is itself a falsehood; consider `ats_score=0` plus an explicit "not evaluated" marker instead.
- **TonePolishingAgent** passes the input through unchanged — safe by design.

---

#### A. Improve Post-Validation for Resume Rewrite (HIGH priority)

**Status:** ✅ DONE

Checks added in `resume_rewrite.py` `_try_llm()`, after the existing experience-count and certification checks (previously at lines 204-210).

1. **Skill check — sanitize, don't reject** (`_sanitize_skills`). Filters output skills to those present in input resume skills. Matching is case-insensitive with a fuzzy match (`_normalize_skill` + `_skill_matches`: exact, substring ≥3 chars, shared-token) to tolerate LLM renaming (e.g., `SQL` vs `PostgreSQL`). Fabricated skills are dropped with a warning, and the rest of the LLM's work is kept. If **>50%** of output skills are dropped, the result is rejected (returns `None`) and falls through to `_parsed_to_rewrite()`.
2. **Company check — reject on fabrication** (`_validate_companies`). Each output `experience.company` must match an input `ExperienceEntry.company` (case-insensitive substring, `_company_matches`). The LLM may reorder entries, so output companies are matched **by name against the set of input companies** rather than by position; empty output companies are skipped. An output company matching none is a fabricated employer — the result is rejected. Counts are already covered by the existing `_validate_experience_count`.
3. **Date check — skipped.** Prompt already prohibits fabricated dates; regex date matching is fragile and low-value.
4. **Chronological order check — add** (`_validate_chronological`). Verifies experience entries are most-recent-first by comparing start years (`_extract_start_year` — first 4-digit year in each `dates` string). Entries without a parseable year are skipped; results with <2 parseable years pass (cannot be validated). Out-of-order results are rejected.

**On rejection:** `_try_llm()` returns `None` so `run()` falls back to `_parsed_to_rewrite()`.

**Data-access gap (still open, relevant to §C.1/C.2):** `_parsed_to_rewrite()` only receives the resume — the JD is **not** an input to `ResumeRewriteAgent.run()`. Options C.1 (reorder by JD `required_skills`) and C.2 (prepend JD `keywords`) therefore cannot run today without either (a) threading the JD through `run()` inputs, or (b) relying on `tailoring_strategy` fields (`keyword_strategy`, `strong_matches`) that are already available. Recommend (b) to avoid an input-schema change, or add JD to `inputs` if the tailoring strategy proves too sparse.

---

#### B. Improve Post-Validation for Cover Letter (HIGH priority)

**Status:** ✅ DONE

Checks added in `cover_letter.py` `_try_llm()`, after the empty-content fallback (which now returns early).

1. **Role check — reject only when role_title is meaningful** (`_validate_role`). The JD's `role_title` must appear in the cover letter. Matching is case-insensitive: the full title is tried first, then the non-filler tokens (seniority words like "senior"/"junior" and function words are stripped) must each appear as whole words — so "Senior Data Scientist" still passes a letter that only says "Data Scientist". `role_title` defaults to `""`, in which case the check passes. A meaningful title absent from the letter is rejected (returns `None` → fallback).
2. **Company check — best-effort warning, never reject** (`_check_company`). Compares `JDParsingOutput.company_name` (see §F, source of truth) against the letter, falling back to `company_signals["company_name"]` via `_get_company_name`. A letter that omits the name logs a warning but is accepted. Partial mention passes if **any** significant token appears as a whole word (e.g. "Acme Corporation" vs a letter that only says "Acme"). No proper-noun heuristic on raw JD text — the structured field covers the realistic cases.
3. **Skill check — warn only** (`_check_skills`). Candidate skill nouns come from the JD's `required_skills`/`preferred_skills` plus the resume's skill list. A skill mentioned in the letter but absent from the resume is flagged with a warning; nothing is rejected. Matching uses whole-word boundaries so short tokens like "ai" do not match inside "aimed", and fuzzy matching (`_skill_in_list`: exact / substring / shared-token) suppresses false warnings for e.g. "SQL" vs resume "PostgreSQL".
4. **Length check — reject only on extreme outliers** (`_validate_length`). Spec is **450-600**. Rejects (returns `None` → fallback) only if < 200 or > 800; accepts with a warning between 200-450 and 600-800. Replaces the old `<250`/`>700` warn-only check.
5. **Date check — skipped.** Prompt already prohibits "current"/"now"/"presently"; post-validation on natural language is fragile and low-value.

**Note:** the plain-text fallback in `_parse_json` treats any >50-char non-JSON response as the letter. All of the above checks still run on that path — they flow through `_try_llm` unchanged.

---

#### C. Improve Fallback Templates (MEDIUM priority)

**Resume Rewrite fallback** (`_parsed_to_rewrite`): Add lightweight deterministic tailoring without an LLM:

1. Reorder skills so skills matching JD `required_skills` (or `tailoring_strategy.keyword_strategy` — see the data-access gap in §A) appear first.
2. Prepend JD `keywords` (or strategy keywords) not already present in the resume skills (up to 5).
3. Leave experience, projects, certifications, education unchanged.

**Cover Letter fallback** (`_MINIMAL_COVER_LETTER`): Replace the placeholder with a data-driven `_build_fallback_cover_letter(jd, resume, strategy)` helper:

1. Use the real `role_title` from the JD.
2. Use the real company name from `JDParsingOutput.company_name` (see §F); fall back to `company_signals` / raw JD, otherwise omit rather than use "your company".
3. Pick 2-3 skills from the resume overlapping JD `required_skills`.
4. Reference 1 achievement from the most recent experience entry.
5. Use the candidate's name from the resume's name field (or "Candidate" if missing).
6. Keep the three-paragraph structure (opening, middle, closing).

**Apply the same fallback at all three call sites:** empty input (`cover_letter.py:121`), double LLM failure (`:147`), and empty content (`:258`).

**Note:** the empty-content call site (line 258) lives inside `_try_llm`, which only has the serialized JSON strings — not the raw `jd`/`resume`/`strategy` objects. To build a data-driven letter there, either pass the structured objects into `_try_llm`, or move the empty-content handling up to `run()` (recommended — keeps `_try_llm` pure).

---

#### D. Add Fallback Detection Logging (LOW priority)

Add `logger.info()` calls in both agents:

- Resume rewrite: `"LLM rewrite succeeded"` vs `"Fallback: parsed resume used (reason: %s)"`
- Cover letter: `"LLM cover letter succeeded"` vs `"Fallback: template cover letter used (reason: %s)"`
- Include skill count and word count metrics in the success path.

---

#### E. Strengthen Prompts (root-cause mitigation, pairs with A/B)

Post-validation catches falsehoods after the fact but wastes a retry when the LLM consistently ignores constraints. Tighten the prompts that already exist:

- **Resume rewrite** (`_SYSTEM_PROMPT`, line 34): the rule *"You may add reasonable metrics only if implied (e.g., 'managed a team' → 'managed a team of 5')"* actively invites fabrication. Remove it or replace with *"Never add metrics that are not explicitly in the resume. If a metric is missing, rephrase without inventing a number."* This is the single highest-leverage fix for fabricated metrics.
- **Resume rewrite** (`_SYSTEM_PROMPT`, line 41): strengthen *"All certifications ... MUST be included"* — already enforced by `_validate_certifications`, so keep both.
- **Cover letter** (`_SYSTEM_PROMPT`, line 36): the unicode char `吸引` is a stray non-ASCII artifact in an otherwise English prompt — replace with "attracts". It may confuse models and contradicts the "ASCII only" rule on line 56.

---

#### F. Add `company_name` to `JDParsingOutput` and `company_signals` (HIGH priority, prerequisite for B.2/C.2)

**Status:** ✅ DONE

`JDParsingOutput` previously had **no `company_name` field** — `company_signals` held only `{culture, values, mission}`. Without a structured company name, the cover letter company check (B.2) and the data-driven fallback letter (C.2) must rely on fragile heuristics. A first-class `company_name` field now exists and is surfaced through `company_signals`:

1. **Field added** to `JDParsingOutput` in `client/models.py`:

   ```python
   company_name: str = ""  # employer name exactly as written in the JD
   ```

2. **Extracted in the JD Parsing Agent** (`client/agents/jd_parsing.py`):
   - `company_name` added to the LLM prompt's JSON field list (`_SYSTEM_PROMPT`).
   - Rule added: *"Extract the company name exactly as it appears in the job description; output empty string if not present."*
   - `_sync_company_name()` keeps the field and `company_signals["company_name"]` in agreement after every successful LLM parse — prefers the top-level field, falls back to the value embedded in `company_signals`, and injects the name under the `"company_name"` key.
3. **Regex fallback** (`_regex_fallback`): `_extract_company_name()` is a best-effort deterministic extractor — tries explicit labels (`Company:` / `Employer:` / `Organization:` / `Hiring Company:`), then the common JD opening pattern `<Name> is/are ...`, then `at/for/with <Name>` references. Filters out pure-number tokens, pronoun openers (`We`/`Our`/etc.), and returns empty string when nothing confident is derivable. The result populates both `company_name` and `company_signals["company_name"]`.
4. **Consumers** (still pending — part of B.2 / C.2): once B.2 / C.2 are implemented, use `JDParsingOutput.company_name` as the source of truth in:
   - Cover letter company check (B.2) — upgrade from "derive via heuristic" to "compare against structured field".
   - Cover letter fallback template (C.2) — use the real company name instead of omitting it.

**Files changed:** `client/models.py`, `client/agents/jd_parsing.py`, `wip_testing/test_job_description.py`, `tests/test_jd_parsing.py`

---

**Files to modify:**

- `client/models.py` — ✅ Add `company_name: str = ""` to `JDParsingOutput` (see §F)
- `client/agents/jd_parsing.py` — ✅ Extract `company_name` in the LLM prompt and regex fallback; include it in `company_signals` (see §F)
- `client/agents/resume_rewrite.py` — ✅ skill sanitize + company + chronological checks added to `_try_llm()` (see §A); still open: improve `_parsed_to_rewrite()` with skill reordering (from strategy keywords) and tighten the "add reasonable metrics" prompt rule
- `client/agents/cover_letter.py` — ✅ role + company + length checks added to `_try_llm()` (see §B); still open: replace `_MINIMAL_COVER_LETTER` with `_build_fallback_cover_letter()` at all 3 call sites and fix the stray non-ASCII char in the system prompt (see §C/E)
- `tests/` — ✅ `tests/test_jd_parsing.py` covers `_extract_company_name` + `_sync_company_name`; ✅ `tests/test_resume_rewrite_validation.py` covers the A checks; ✅ `tests/test_cover_letter_validation.py` covers the B checks (role/company/skill/length — deterministic, no LLM)

**Testing:**

- Run `uv run python wip_testing/test_resume_rewrite.py` with `LOG_LEVEL=DEBUG`
- Run `uv run python wip_testing/test_cover_letter.py` with `LOG_LEVEL=DEBUG`
- Run `uv run python wip_testing/test_job_description.py` with `LOG_LEVEL=DEBUG` — verify `company_name` is populated in both LLM and regex-fallback paths ✅ (script now prints `company_name`; regex path verified against `sample/jobs/3Pillar.txt` → `3Pillar`, `Zafin.txt` → `Zafin`)
- Run `uv run pytest` for the new deterministic validation unit tests ✅ (`tests/test_jd_parsing.py` — 19 tests; `tests/test_resume_rewrite_validation.py` — 25 tests; `tests/test_cover_letter_validation.py` — 48 tests)
- Verify no skills appear in output that aren't in input resume (dropped with a warning, not silently kept) ✅ (see §A `_sanitize_skills`)
- Verify cover letter contains the JD role title ✅ (see §B `_validate_role`; rejected when absent and role_title meaningful)
- Verify fallback cover letter uses real JD/resume data, not placeholders
- Verify rewritten metrics never exceed what the input resume states

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

---

### 5.2 Wire up the 7-agent pipeline

**Status:** ⚠️ PARTIAL

`run_resume_pipeline()` chains all 7 agents sequentially:

1. JD Parsing → `parsed_job_description`
2. Resume Parsing → `parsed_resume`
3. Gap Analysis → `tailoring_strategy`
4. Resume Rewrite → `rewritten_resume`
5. ATS Compliance → `ats_optimized_resume`
6. Tone Polishing → `polished_resume`
7. Cover Letter → `cover_letter`

**What works:** The pipeline runs end-to-end. `sample_run()` uses dedicated `JDParsingAgent` and `ResumeParsingAgent` for agents 1-2, and generic `PipelineAgent` wrappers for agents 3-7. `create_runner_from_config()` accepts a dict of dedicated agent classes but requires the caller to pass them.

**What's incomplete:** Agents 3-7 are not wired as dedicated classes in `sample_run()`. The pipeline code at lines like `tailoring_strategy = gap_result["tailoring_strategy"]` assumes dict-style access, which works with `PipelineAgent` (returns raw LLM text) but will break with dedicated agents that return Pydantic model objects. Wiring agents 3-7 requires updating `run_resume_pipeline()` to handle both dict and Pydantic model returns.

**Optional improvement:** Add `candidate_name` and `company_name` parameters to `run_resume_pipeline()` for output file naming (see Phase 6.3).

---

## Phase 6: Output & Validation

### 6.1 Add Pydantic models (`client/models.py`)

**Status:** ✅ DONE

**What exists now:** `ParsedResume` (with `projects`, `keywords` fields) and `ParsedJobDescription` models.

**What's missing:** All 7 agent output schemas. Add these to `client/models.py`:

```python
from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    responsibilities: list[str]
    achievements: list[str]
    metrics: list[str]


class JDParsingOutput(BaseModel):
    role_title: str
    seniority_level: str
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    keywords: list[str]
    industry_terms: list[str]
    company_signals: dict[str, str]


class ResumeParsingOutput(BaseModel):
    summary: str
    skills: list[str]
    experience: list[ExperienceEntry]
    projects: list[str]
    certifications: list[str]
    education: list[str]


class GapAnalysisOutput(BaseModel):
    missing_skills: list[str]
    weak_skills: list[str]
    strong_matches: list[str]
    recommended_emphasis: list[str]
    keyword_strategy: list[str]
    bullet_point_improvement_plan: list[str]
    tone_guidance: str


class RewriteOutput(BaseModel):
    summary: str
    skills: list[str]
    experience: list[ExperienceEntry]
    projects: list[str]
    certifications: list[str]
    education: list[str]


class ATSComplianceOutput(BaseModel):
    ats_score: int = Field(ge=0, le=100)
    missing_keywords: list[str]
    formatting_issues: list[str]
    clarity_issues: list[str]
    recommended_fixes: list[str]
    auto_fixes_applied: list[str]
    final_resume: str


class TonePolishingOutput(BaseModel):
    polished_resume: str


class CoverLetterOutput(BaseModel):
    cover_letter: str
```

**Files changed:** `client/models.py`

---

### 6.2 Add output formatting utilities (`client/formatter.py`)

**Status:** ❌ NOT DONE

Create a formatter that converts structured output to clean documents:

```python
def format_resume_markdown(rewrite: RewriteOutput) -> str:
    """Convert structured resume to clean Markdown."""


def format_resume_plain(ats: ATSComplianceOutput) -> str:
    """Convert to plain-text ATS-friendly format (no Markdown)."""


def format_cover_letter(text: str) -> str:
    """Clean up cover letter text (normalize whitespace, fix encoding)."""
```

**Files changed:** new file `client/formatter.py`

---

### 6.3 Add template-based resume output (`client/templates/`)

**Status:** ⚠️ PARTIAL

**What exists now:** `client/templates/` has 4 Jinja2 template files:

- `modern.py` — clean lines, bold section headers
- `classic.py` — traditional format with underlined headers
- `minimal.py` — whitespace-focused, no decorative elements
- `cover_letter.py` — professional cover letter format

**What's missing:** A `ResumeRenderer` class to render templates with data.

**What to do:**

1. Create `client/templates/renderer.py` with:

   ```python
   from pathlib import Path
   from client.models import RewriteOutput, CoverLetterOutput


   class ResumeRenderer:
       def __init__(self, template_dir: Path | None = None) -> None: ...

       def render_plaintext(
           self, resume: RewriteOutput, template: str = "modern"
       ) -> str: ...
       def render_markdown(
           self, resume: RewriteOutput, template: str = "modern"
       ) -> str: ...
       def render_docx(self, resume: RewriteOutput, output_path: Path) -> Path: ...
       def render_pdf(self, resume: RewriteOutput, output_path: Path) -> Path: ...
       def render_cover_letter_plaintext(self, letter: CoverLetterOutput) -> str: ...
       def render_cover_letter_markdown(self, letter: CoverLetterOutput) -> str: ...

       @staticmethod
       def build_output_path(
           output_dir: Path,
           candidate_name: str,
           company_name: str,
           doc_type: str,
           ext: str,
       ) -> Path:
           """Build a file path like: 20260727_1430_JohnSmith_AcmeCorp_Resume.pdf"""
           ...

       def render_all(
           self,
           resume: RewriteOutput,
           letter: CoverLetterOutput,
           candidate_name: str,
           company_name: str,
           output_dir: Path,
       ) -> dict[str, Path]: ...
   ```

2. **DOCX generation:**
   - Use `python-docx` library
   - Professional font (Calibri or Arial), 10-11pt body, 14pt name
   - Section headers in bold, slightly larger
   - 1-inch margins, single spacing
   - Save to `.docx` file

3. **PDF generation:**
   - Use `weasyprint` or `pdfkit` (HTML → PDF pipeline)
   - Render Markdown to HTML first, then convert to PDF
   - Same professional styling as DOCX
   - Save to `.pdf` file

4. **`render_all` convenience method:**
   - Takes a `RewriteOutput`, `CoverLetterOutput`, candidate name, company name, and output directory
   - Generates all 4 formats for resume + cover letter
   - File names follow the pattern: `{date}_{candidate_name}_{company_name}_{document_type}.{ext}`
   - Date format: `YYYYMMDD_HHMM`
   - Example: `20260727_1430_JohnSmith_AcmeCorp_Resume.pdf`
   - Returns a dict mapping format name to file path:

      ```python
      {
          "plaintext": output_dir / "20260727_1430_JohnSmith_AcmeCorp_Resume.txt",
          "markdown": output_dir / "20260727_1430_JohnSmith_AcmeCorp_Resume.md",
          "docx": output_dir / "20260727_1430_JohnSmith_AcmeCorp_Resume.docx",
          "pdf": output_dir / "20260727_1430_JohnSmith_AcmeCorp_Resume.pdf",
          "cover_letter_plaintext": output_dir
          / "20260727_1430_JohnSmith_AcmeCorp_CoverLetter.txt",
          "cover_letter_markdown": output_dir
          / "20260727_1430_JohnSmith_AcmeCorp_CoverLetter.md",
          "cover_letter_docx": output_dir
          / "20260727_1430_JohnSmith_AcmeCorp_CoverLetter.docx",
          "cover_letter_pdf": output_dir / "20260727_1430_JohnSmith_AcmeCorp_CoverLetter.pdf",
      }
      ```

5. **Add to `pyproject.toml` dependencies:****

   ```plaintext
   python-docx>=1.0.0
   weasyprint>=60.0
   markdown>=3.5
   ```

6. **Wire into pipeline:**

   - `run_resume_pipeline` gains two new parameters: `candidate_name: str` and `company_name: str`
   - These are passed through to `ResumeRenderer.render_all()` for file naming
   - After tone polishing and cover letter agents complete, call `ResumeRenderer.render_all()`
   - Store output paths in the pipeline result dict

**Files changed:** new file `client/templates/renderer.py`, `pyproject.toml`, `pipeline.py`

---

## Phase 7: Testing & Docs

### 7.1 Create `test_real_files.py`

**Status:** ❌ NOT DONE

Create an integration test that runs the full pipeline against real files:

1. Read `sample/jobs/3Pillar.txt` and `sample/resume/Peter-Letkeman-Resume.txt`
2. Run `run_resume_pipeline()` with both files
3. Assert all 7 output keys are present
4. Assert `parsed_job_description` has `role_title` and `required_skills`
5. Assert `parsed_resume` has `experience` as a list
6. Assert `tailoring_strategy` has `missing_skills`
7. Assert `ats_optimized_resume` is not empty
8. Assert `polished_resume` is not empty
9. Assert `cover_letter` is 450-600 words
10. Assert experiences are in chronological order (most recent first)
11. Assert no new experiences were added (compare with input resume)
12. Assert all certifications from input resume are present in output
13. Call pipeline with candidate name and company name
14. Assert output files are created with correct naming pattern
15. Print summary of results

**Files changed:** new file `test_real_files.py`

---

### 7.2 Add unit tests (`tests/`)

**Status:** ⚠️ PARTIAL

**What exists now:** `tests/test_format_detector.py` with 46 tests covering:

- All `FormatDetector` static extraction methods (name, title, section, list, bullet points)
- New Phase 2.1 methods (projects, metrics, keywords, format detection)
- `_safe_json` and insufficiency checks
- `parse_resume()` and `parse_job_description()` async flows (regex-only mode)

**Still needed:**

- `tests/test_agents.py` — mock `ModelClient`, verify prompts and JSON validation
- `tests/test_pipeline.py` — end-to-end with mocked agents

**Files changed:** new directory `tests/`, new files `tests/__init__.py`, `tests/test_format_detector.py`, `tests/test_agents.py`, `tests/test_pipeline.py`

---

### 7.3 Populate `docs/`

**Status:** ❌ NOT DONE

`docs/` directory has 3 existing files: `TESTING.md`, `models.md`, `logging-info.md`. Add:

1. **`docs/architecture.md`:** System overview, data flow diagram, agent chain
2. **`docs/agents.md`:** Each agent's purpose, prompt, input/output schema
3. **`docs/usage.md`:** How to run the pipeline, configure models, add custom agents
4. **`docs/api.md`:** `ModelClient`, `PipelineAgent`, `AgentRunner` interfaces

**Files changed:** new files `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`

---

## Phase 8: Enforce Structured JSON Output via `response_format`

**Status:** ❌ TODO

**Goal:** Make every JSON-returning LLM call request structured JSON through the provider's native mechanism (`response_format`) instead of relying on prompt instructions alone. The agent-side `_parse_json` helpers stay as a safety net.

### Why

Every agent prompt ends with "Output only valid JSON", and each agent re-implements a `_parse_json` helper that strips markdown fences and calls `json.loads`. This works but wastes a retry (or the regex fallback) whenever the model:

- wraps the JSON in ```json fences
- prepends explanatory prose
- returns malformed/truncated JSON

Both providers support a native JSON mode that strongly constrains the response:

- **OpenAI** (`OpenAIClient`): pass `response_format={"type": "json_object"}` to `chat.completions.create()`.
- **Ollama** (`OllamaClient`): pass `format="json"` to the ollama `chat()` call.

The pinned SDK versions already support these parameters (`openai>=1.0.0`, `ollama>=0.4.0` per `pyproject.toml`).

### 8.1 Extend the `ModelClient` interface

**File:** `client/model_client.py`

Add a required `response_format` parameter to the abstract `chat()` signature:

```python
async def chat(
    self,
    purpose: str,
    prompt: str,
    output: list[str],
    rules: list[str],
    inputs: list[str],
    response_format: str,
) -> str:
    ...
```

- `response_format="json"` — the only supported value. Every LLM call in the pipeline must request JSON through the provider's native mechanism.
- No default and no `None` passthrough: free-text responses are no longer part of the contract. The signature is free to change; all callers are updated in §8.4.

### 8.2 OllamaClient — pass `format="json"`

**File:** `client/ollama_client.py`

Ollama's native JSON mode is always on (`format="json"`); there is no free-text branch.

```python
response = await asyncio.wait_for(
    self.client.chat(
        model=self.model,
        messages=[
            {"role": "system", "content": purpose},
            {"role": "user", "content": task},
        ],
        stream=False,
        format="json",  # response_format="json" is the only supported mode
    ),
    timeout=self.timeout,
)
```

Notes:

- Ollama's JSON mode guarantees a **valid JSON object** but not the schema — Pydantic validation in the agents still enforces the schema.
- Update the debug log line to record the mode: `model=%s format=%s prompt_len=%d`.

### 8.3 OpenAIClient — pass `response_format={"type": "json_object"}`

**File:** `client/open_ai_client.py`

OpenAI's native JSON mode is always on; there is no free-text branch.

```python
response: ChatCompletion = await asyncio.wait_for(
    self.client.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": purpose},
            {"role": "user", "content": task},
        ],
        response_format={"type": "json_object"},
    ),
    timeout=90,
)
```

Notes:

- OpenAI's `json_object` mode requires the word "json" to appear somewhere in the messages. All agent prompts already satisfy this ("Output only valid JSON") — **do not remove the rule string**.
- Optional future upgrade: Structured Outputs (`response_format={"type": "json_schema", "json_schema": {...}}`) using `model_json_schema()` from `client/models.py`. Blocked on model versions (`gpt-4o-mini-2024-07-18`+ / `gpt-4o-2024-08-06`+) — see §8.7.

### 8.4 Update every call site

Since the interface change is not gated on backward compatibility, update **all** `client.chat(...)` callers to pass `response_format="json"`:

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

Each becomes:

```python
raw = await self.client.chat(
    purpose=_SYSTEM_PROMPT,
    prompt=prompt,
    output=["json"],
    rules=rules,
    inputs=[...],
    response_format="json",
)
```

- `PipelineAgent.run` forwards the parameter straight through (add `response_format="json"` to the forwarded call).
- `basic.py` is no longer a free-text demo: pass `response_format="json"` and parse/print the returned JSON object.
- The regex-only paths in `client/format_detector.py` are unaffected (they never call `chat`).

### 8.5 Keep the `_parse_json` safety net

The per-agent `_parse_json` / `FormatDetector._safe_json` helpers (strip fences → `json.loads`) must stay. `response_format` is a strong hint, not a guarantee — a local Ollama model can still emit fence-wrapped or truncated JSON. With JSON mode active:

- Fence stripping becomes effectively a no-op for well-behaved providers (good).
- The helper still guards residual failure modes before the retry/fallback path (good).

### 8.6 Tests

**Files:** `tests/test_model_clients.py` (new)

- Unit test `OllamaClient` always passes `format="json"` to the underlying `ollama.AsyncClient.chat`. Use a stubbed `AsyncClient` (no real Ollama server).
- Unit test `OpenAIClient` always passes `response_format={"type": "json_object"}`. Use a stubbed `AsyncOpenAI`.
- Add an assertion/grep-style test that every `client.chat(...)` call site — all 7 agents, both `FormatDetector` fallbacks, `PipelineAgent`, and `SimpleAgent` — passes `response_format="json"` (so a future call can't silently regress to prompt-only JSON).
- Existing deterministic tests (`test_format_detector.py`, `test_jd_parsing.py`, `test_resume_rewrite_validation.py`, `test_cover_letter_validation.py`) must stay green — they never hit a live client.
- Manual: `uv run python wip_testing/test_<agent>.py` with `LOG_LEVEL=DEBUG` — confirm the debug log shows the JSON mode and the first LLM attempt succeeds (no retry).

### 8.7 Optional future: provider-native JSON Schema (Structured Outputs)

Instead of `{"type": "json_object"}`, OpenAI Structured Outputs allows passing the actual JSON Schema for ~100% schema conformance, eliminating most `_parse_json` / fallback code. Generate the schema from the Pydantic models via `model_json_schema()`.

Blocked on:

- OpenAI model versions: `gpt-4o-mini-2024-07-18`+, `gpt-4o-2024-08-06`+.
- Ollama equivalent: pass the JSON Schema dict as `format=<schema>` (supported by newer Ollama releases). Requires per-model verification.
- The cover letter and tone agents emit free text inside a single field — still expressible as `{"cover_letter": str}` / `{"polished_resume": str}` schemas.

### 8.8 Optional cleanup: shared JSON parser

All 7 agents + `FormatDetector` define the same `_parse_json`/`_safe_json` (strip fences, `json.loads`, log failure). Extract one shared helper (e.g. `client/json_utils.py: parse_json_response(raw) -> dict[str, Any] | None`) and delete the per-file copies. Reduces the surface that `response_format` work needs to touch and removes ~80 duplicated lines.

---

**Files to modify:**

- `client/model_client.py` — add required `response_format: str` param to the ABC (`"json"` is the only supported value)
- `client/ollama_client.py` — always pass `format="json"`
- `client/open_ai_client.py` — always pass `response_format={"type": "json_object"}`
- `client/agents/jd_parsing.py` — pass `response_format="json"`
- `client/agents/resume_parsing.py` — pass `response_format="json"`
- `client/agents/gap_analysis.py` — pass `response_format="json"`
- `client/agents/resume_rewrite.py` — pass `response_format="json"`
- `client/agents/ats_compliance.py` — pass `response_format="json"`
- `client/agents/tone_polishing.py` — pass `response_format="json"`
- `client/agents/cover_letter.py` — pass `response_format="json"`
- `client/format_detector.py` — pass `response_format="json"` in both LLM fallbacks
- `pipeline.py` — `PipelineAgent.run` forwards `response_format="json"`
- `basic.py` — `SimpleAgent.run` passes `response_format="json"` (demo now returns JSON)
- `tests/test_model_clients.py` — new (response_format plumbing tests)
- `resume-todo.md` — this section

**Testing:**

- `uv run pytest`
- `uv run ruff check .` / `uv run ruff format .`
- `uv run pyright .`
- `uv run python wip_testing/test_parsing.py` (LLM mode) with `LOG_LEVEL=DEBUG` — confirm the response parses on the first attempt (no retry) with JSON mode active

---

## File Structure (Current → Target)

```plaintext
client/
  __init__.py                      # EXISTS (empty)
  errors.py                        # EXISTS ✅
  model_client.py                  # EXISTS ✅
  model_registry.py                # EXISTS ✅
  ollama_client.py                 # EXISTS ✅ (configurable timeout, default 300s)
  open_ai_client.py                # EXISTS ✅
  format_detector.py               # EXISTS ✅ (expanded with projects, metrics, keywords)
  models.py                        # EXISTS ✅ (ParsedResume, ParsedJobDescription, JDParsingOutput, + all agent output models)
  templates/                       # EXISTS ⚠️ needs renderer.py
    __init__.py                    # EXISTS
    modern.py                      # EXISTS
    classic.py                     # EXISTS
    minimal.py                     # EXISTS
    cover_letter.py                # EXISTS
    renderer.py                    # NEW - multi-format resume output
  agents/                          # EXISTS ✅ (all 7 agents done)
    __init__.py                    # EXISTS (docstring only, no exports)
    jd_parsing.py                  # EXISTS ✅ - Agent 1 (JDParsingAgent)
    resume_parsing.py              # EXISTS ✅ - Agent 2 (ResumeParsingAgent)
    gap_analysis.py                # EXISTS ✅ - Agent 3 (GapAnalysisAgent)
    resume_rewrite.py              # EXISTS ✅ - Agent 4 (ResumeRewriteAgent)
    ats_compliance.py              # EXISTS ✅ - Agent 5 (ATSComplianceAgent)
    tone_polishing.py              # EXISTS ✅ - Agent 6 (TonePolishingAgent)
    cover_letter.py                # EXISTS ✅ - Agent 7 (CoverLetterAgent)
  formatter.py                     # NEW - output formatting
config/
  __init__.py                      # EXISTS (empty)
  agents.py                        # EXISTS ✅
tests/
  __init__.py                      # EXISTS ✅
  conftest.py                      # EXISTS ✅ (shared fixtures)
  test_format_detector.py          # EXISTS ✅ (46 tests)
  test_jd_parsing.py               # EXISTS ✅ (19 tests)
  test_resume_rewrite_validation.py # EXISTS ✅ (25 tests)
  test_cover_letter_validation.py  # EXISTS ✅ (48 tests)
  test_model_clients.py            # NEW (response_format plumbing tests)
  test_agents.py                   # NEW
  test_pipeline.py                 # NEW
docs/
  TESTING.md                       # EXISTS ✅ (moved from root)
  models.md                        # EXISTS ✅
  logging-info.md                  # EXISTS ✅
  architecture.md                  # NEW
  agents.md                        # NEW
  usage.md                         # NEW
  api.md                           # NEW
pipeline.py                        # EXISTS ✅
basic.py                           # EXISTS ✅
logging_config.py                  # EXISTS ✅ (centralized logging, LOG_LEVEL env var)
test_real_files.py                 # NEW
pyproject.toml                     # EXISTS ✅ (ruff, pyright, pytest config)
AGENTS.md                          # EXISTS ✅
resume-todo.md                     # THIS FILE
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

## Tooling

- **Lint/Format:** ruff (`ruff check .`, `ruff format .`) — rules: E, F, I, UP, B, SIM
- **Typecheck:** pyright (strict mode, Python 3.14)
- **Test:** pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- **Config:** all in `pyproject.toml`

---

## Execution Order

| Step | Phase | Status | Depends On | Estimated Files Changed |
| ------ | ------- | -------- | ------------ | ------------------------ |
| 1 | Phase 1.2: OpenAI error handling | ✅ DONE | None | 1 |
| 2 | Phase 1.3: Clean requirements.txt | ✅ DONE | None | 1 |
| 3 | Phase 2.1: Expand FormatDetector | ✅ DONE | None | 2 |
| 4 | Phase 7.2: Unit tests (format_detector) | ✅ DONE | Step 3 | 1 |
| 5 | Tooling: ruff, pyright, pytest | ✅ DONE | None | 3 |
| 6 | Phase 6.1: Agent output models | ✅ DONE | None | 1 |
| 7 | Phase 2.3: JD Parsing Agent | ✅ DONE | Steps 3, 6 | 3 |
| 8 | Phase 2.4: Resume Parsing Agent | ✅ DONE | Steps 3, 6 | 2 |
| 9 | Phase 3.1: Gap Analysis Agent | ✅ DONE | Steps 6, 7, 8 | 2 |
| 10 | Phase 3.2: Resume Rewrite Agent | ✅ DONE | Steps 6, 8, 9 | 2 |
| 11 | Phase 3.3: ATS Compliance Agent | ✅ DONE | Steps 6, 10 | 2 |
| 12 | Phase 4.1: Tone Polishing Agent | ✅ DONE | Steps 6, 11 | 2 |
| 13 | Phase 4.2: Cover Letter Agent | ✅ DONE | Steps 6, 7, 8, 9 | 2 |
| 14 | Phase 4.3: Fix LLM Fallback Falsehoods | ❌ TODO | Steps 10, 13 | 2 |
| 15 | Phase 5.2: Wire agents into pipeline | ⚠️ PARTIAL (runs end-to-end; agents 3-7 still use generic `PipelineAgent` — see §5.2) | Steps 7-14 | 1 |
| 16 | Phase 6.2: Output formatter | ❌ TODO | Step 6 | 1 |
| 17 | Phase 6.3: Template renderer | ❌ TODO | Steps 6, 16 | 2 |
| 18 | Phase 7.1: test_real_files.py | ❌ TODO | Steps 15, 17 | 1 |
| 19 | Phase 7.2: Unit tests (agents, pipeline) | ❌ TODO | Steps 6, 16, 17 | 2 |
| 20 | Phase 7.3: Documentation | ❌ TODO | All | 4 |
| 21 | Phase 8.1: `response_format` required on `ModelClient` ABC | ❌ TODO | None | 1 |
| 22 | Phase 8.2-8.3: Ollama `format="json"` + OpenAI `json_object` | ❌ TODO | Step 21 | 2 |
| 23 | Phase 8.4: Pass `response_format="json"` in all 7 agents + FormatDetector + PipelineAgent + basic.py | ❌ TODO | Step 22 | 11 |
| 24 | Phase 8.6: `tests/test_model_clients.py` plumbing tests | ❌ TODO | Step 23 | 1 |
