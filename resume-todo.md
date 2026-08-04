# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), the Phase 4.3 post-validation work (§A/§B/§C/§D/§F), and 227 unit tests. The items below are what remains.

---

## Phase 4.3 (remaining): Fix LLM Fallback Falsehoods — §E

**Status:** §A (resume rewrite validation), §B (cover letter validation), §C (fallback templates), §D (fallback detection logging), and §F (`company_name`) are ✅ DONE — see `resume-done.md`. §E remains.

**Problem (context):** Two distinct failure modes produce bad output:

1. **LLM succeeds but fabricates** — The LLM returns valid JSON, but it adds skills not in the original resume, invents achievements, or writes generic text unrelated to the target company.
2. **LLM fails, fallback is useless** — Agents fall back to defaults that are either unoptimized (resume rewrite returns unchanged data) or contain placeholder text (cover letter returns `_MINIMAL_COVER_LETTER` with `[Your Name]`).

**Key data facts that constrain the design:**

- `JDParsingOutput` now has a **`company_name` field** (✅ DONE) — `company_signals` also carries it under the `"company_name"` key. The fallback letter (C.2) can rely on this structured source of truth.
- `Role title` **is** structured (`JDParsingOutput.role_title`) — a reliable check target for the cover letter.
- Company names **are** structured in the resume (`ExperienceEntry.company`) — a reliable check target for resume rewrite.
- The word-count spec is **450-600** (per `bots.md` and `cover_letter.py` prompts).

---

#### C. Improve Fallback Templates (MEDIUM priority) — ✅ DONE

**Done — see `resume-done.md` §4.3.C.** Resume Rewrite now reorders/prepends skills deterministically (`_tailor_skills` in `_parsed_to_rewrite`), and the Cover Letter agent builds a data-driven `_build_fallback_cover_letter(jd, resume, strategy)` at all 3 call sites (empty input, double LLM failure, empty content — the last now rejects in `_try_llm` and falls back through `run()`, keeping `_try_llm` pure).

---

#### D. Add Fallback Detection Logging (LOW priority) — ✅ DONE

**Done.** Both agents now `logger.info()` the outcome so LLM success vs deterministic fallback is visible at a glance:

- Resume rewrite: `"LLM rewrite succeeded (skills=%d, words=%d)"` vs `"Fallback: parsed resume used (reason: %s)"` — skill count and word count via `_count_words`.
- Cover letter: `"LLM cover letter succeeded (words=%d)"` vs `"Fallback: template cover letter used (reason: %s)"` — reason covers `"empty input"` and `"LLM failed on both attempts"`.
- `wip_testing/test_resume_rewrite.py` and `test_cover_letter.py` now call `configure_logging()` so `LOG_LEVEL=DEBUG` surfaces the INFO lines.
- Tests: `TestCountWords` + `TestFallbackLogging` in both validation test files (227 total). See `resume-done.md` §4.3.D.

---

#### E. Strengthen Prompts (root-cause mitigation, pairs with A/B)

Post-validation catches falsehoods after the fact but wastes a retry when the LLM consistently ignores constraints. Tighten the prompts that already exist:

- **Resume rewrite** (`_SYSTEM_PROMPT`, line 34): the rule *"You may add reasonable metrics only if implied (e.g., 'managed a team' → 'managed a team of 5')"* actively invites fabrication. Remove it or replace with *"Never add metrics that are not explicitly in the resume. If a metric is missing, rephrase without inventing a number."* This is the single highest-leverage fix for fabricated metrics.
- **Resume rewrite** (`_SYSTEM_PROMPT`, line 41): strengthen *"All certifications ... MUST be included"* — already enforced by `_validate_certifications`, so keep both.
- **Cover letter** (`_SYSTEM_PROMPT`, line 36): the unicode char `吸引` is a stray non-ASCII artifact in an otherwise English prompt — replace with "attracts". It may confuse models and contradicts the "ASCII only" rule on line 56.

---

**Files to modify (remaining):**

- `client/agents/resume_rewrite.py` — tighten the "add reasonable metrics" prompt rule (§E)
- `client/agents/cover_letter.py` — fix the stray non-ASCII char in the system prompt (§E)

**Testing:**

- Run `uv run python wip_testing/test_resume_rewrite.py` with `LOG_LEVEL=DEBUG`
- Run `uv run python wip_testing/test_cover_letter.py` with `LOG_LEVEL=DEBUG`
- Verify rewritten metrics never exceed what the input resume states

---

## Phase 5: Agent Orchestration

### 5.2 Wire up the 7-agent pipeline

**Status:** ⚠️ PARTIAL — runs end-to-end; agents 3-7 still use generic `PipelineAgent` wrappers in `sample_run()`

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

**Status:** ⚠️ PARTIAL — template files exist, renderer is missing

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
   - Returns a dict mapping format name to file path

5. **Add to `pyproject.toml` dependencies:**

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

### 7.2 Add unit tests (`tests/`) — remaining

**Status:** ⚠️ PARTIAL — existing deterministic tests are done; agent + pipeline tests remain

**What exists now:** 227 tests across 6 files:

- `tests/test_format_detector.py` — 46 tests covering all `FormatDetector` static extraction methods + regex-only parse flows
- `tests/test_jd_parsing.py` — 19 tests (`_extract_company_name` + `_sync_company_name`)
- `tests/test_resume_rewrite_validation.py` — 56 tests (§4.3.A checks + §C skill tailoring + §D fallback logging)
- `tests/test_cover_letter_validation.py` — 80 tests (§4.3.B checks + §C fallback builder + §D fallback logging)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 15 tests (shared parser + JSON Schema helpers)

**Still needed:**

- `tests/test_agents.py` — mock `ModelClient`, verify prompts and JSON validation
- `tests/test_pipeline.py` — end-to-end with mocked agents

**Files changed:** new files `tests/test_agents.py`, `tests/test_pipeline.py`

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

## File Structure (Target — items still to create)

```plaintext
client/
  formatter.py                    # NEW - output formatting (Phase 6.2)
  templates/
    renderer.py                   # NEW - multi-format resume output (Phase 6.3)
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

---

## Remaining Execution Order

| Step | Phase | Status | Depends On | Estimated Files Changed |
| ------ | ------- | -------- | ------------ | ------------------------ |
| 1 | Phase 4.3 §C: Improve fallback templates (skill reorder + data-driven cover letter) | ✅ DONE | Done work | 2 |
| 2 | Phase 4.3 §D: Fallback detection logging | ✅ DONE | Step 1 | 2 |
| 3 | Phase 4.3 §E: Strengthen prompts (remove "reasonable metrics" rule; fix `吸引` → "attracts") | ❌ TODO | None | 2 |
| 4 | Phase 5.2: Wire agents 3-7 into pipeline as dedicated classes | ⚠️ PARTIAL (runs end-to-end; agents 3-7 still use generic `PipelineAgent` — see §5.2) | Done work | 1 |
| 5 | Phase 6.2: Output formatter (`client/formatter.py`) | ❌ TODO | None | 1 |
| 6 | Phase 6.3: Template renderer (`client/templates/renderer.py`) | ❌ TODO | Step 5 | 2 |
| 7 | Phase 7.1: `test_real_files.py` integration test | ❌ TODO | Steps 4, 6 | 1 |
| 8 | Phase 7.2 (remaining): Unit tests for agents + pipeline | ❌ TODO | Steps 4, 5, 6 | 2 |
| 9 | Phase 7.3: Documentation (`docs/architecture.md`, `agents.md`, `usage.md`, `api.md`) | ❌ TODO | All | 4 |
