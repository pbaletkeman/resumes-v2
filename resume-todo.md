# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), Phase 4.3 (post-validation for rewrite/cover letter, fallback templates, logging, prompt strengthening, `company_name` — see `resume-done.md`), Phase 5.2 (pipeline wiring — all 7 dedicated classes wired), and 227 unit tests. The items below are what remains.

---

> Phase 4.3 (Fix LLM Fallback Falsehoods — validation, fallback templates, logging, prompt strengthening, `company_name`) is **complete** — archived in `resume-done.md` §4.3.

## Phase 5: Agent Orchestration

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
| 1 | Phase 6.2: Output formatter (`client/formatter.py`) | ❌ TODO | None | 1 |
| 2 | Phase 6.3: Template renderer (`client/templates/renderer.py`) | ❌ TODO | Step 1 | 2 |
| 3 | Phase 7.1: `test_real_files.py` integration test | ❌ TODO | Steps 1, 2 | 1 |
| 4 | Phase 7.2 (remaining): Unit tests for agents + pipeline | ❌ TODO | Steps 1, 2 | 2 |
| 5 | Phase 7.3: Documentation (`docs/architecture.md`, `agents.md`, `usage.md`, `api.md`) | ❌ TODO | All | 4 |
