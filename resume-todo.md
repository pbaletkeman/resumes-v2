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

Phase 6 produces clean, formatted output from the pipeline. It breaks into two workstreams: **6.A** (simple formatting helpers) and **6.B** (template-based multi-format renderer). 6.A is independent; 6.B depends on 6.A for the `RewriteOutput` → text conversion that feeds DOCX/PDF generation.

### 6.A — Output Formatting Helpers

#### 6.A.1 Create `client/formatter.py` with `format_resume_markdown()`

**Status:** ✅ DONE

Convert a `RewriteOutput` to clean Markdown. Handles: name/title header, summary, skills as bullet list, experience blocks (title, company, dates, responsibilities, achievements, metrics), certifications, projects, education. No external dependencies.

**Files changed:** new file `client/formatter.py`

---

#### 6.A.2 Add `format_resume_plain()` to `client/formatter.py`

**Status:** ✅ DONE

Convert a `RewriteOutput` (or `ATSComplianceOutput`'s `final_resume`) to plain-text ATS-friendly format. No Markdown syntax, no special characters. Suitable for ATS upload and as input to DOCX/PDF rendering.

**Depends on:** 6.A.1 (same file)

**Files changed:** `client/formatter.py`

---

#### 6.A.3 Add `format_cover_letter()` to `client/formatter.py`

**Status:** ❌ NOT DONE

Clean up cover letter text: normalize whitespace, fix encoding artifacts, ensure consistent paragraph spacing. Takes a `CoverLetterOutput` or raw string, returns clean string.

**Depends on:** 6.A.1 (same file)

**Files changed:** `client/formatter.py`

---

#### 6.A.4 Add unit tests for formatting helpers

**Status:** ❌ NOT DONE

Test all three functions with sample `RewriteOutput` and `CoverLetterOutput` fixtures. Verify: Markdown output has correct headers/bullets, plain output has no Markdown syntax, cover letter whitespace is normalized.

**Depends on:** 6.A.1–6.A.3

**Files changed:** new file `tests/test_formatter.py`

---

### 6.B — Template-Based Multi-Format Renderer

#### 6.B.1 Create `client/templates/renderer.py` with `ResumeRenderer` class skeleton

**Status:** ❌ NOT DONE

Create the `ResumeRenderer` class with `__init__`, template loading from `client/templates/`, and the `render_plaintext()` method (Jinja2 rendering of `RewriteOutput` against template dict). No DOCX/PDF yet — just Jinja2 text output.

```python
class ResumeRenderer:
    def __init__(self, template_dir: Path | None = None) -> None: ...
    def render_plaintext(self, resume: RewriteOutput, template: str = "modern") -> str: ...
```

**Depends on:** None (independent of 6.A)

**Files changed:** new file `client/templates/renderer.py`

---

#### 6.B.2 Add `render_markdown()` to `ResumeRenderer`

**Status:** ❌ NOT DONE

Render `RewriteOutput` using the template's `"markdown"` key. Same Jinja2 approach as `render_plaintext()`.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.3 Add `render_cover_letter_plaintext()` and `render_cover_letter_markdown()`

**Status:** ❌ NOT DONE

Render `CoverLetterOutput` using `COVER_LETTER` template. Two methods for plaintext and markdown variants.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.4 Add `build_output_path()` static method

**Status:** ❌ NOT DONE

Static utility to build timestamped file paths: `{date}_{candidate_name}_{company_name}_{document_type}.{ext}`. Date format `YYYYMMDD_HHMM`. Pure path logic, no I/O.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.5 Add DOCX generation (`render_docx()`)

**Status:** ❌ NOT DONE

Use `python-docx` to render `RewriteOutput` as a `.docx` file. Professional font (Calibri/Arial), 10–11pt body, 14pt name, bold section headers, 1-inch margins, single spacing.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `python-docx>=1.0.0`)

---

#### 6.B.6 Add PDF generation (`render_pdf()`)

**Status:** ❌ NOT DONE

Use `weasyprint` (or `pdfkit`) to render `RewriteOutput` as a `.pdf` file. Markdown → HTML → PDF pipeline. Same professional styling as DOCX.

**Depends on:** 6.B.1 (same class)

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `weasyprint>=60.0`, `markdown>=3.5`)

---

#### 6.B.7 Add `render_all()` convenience method

**Status:** ❌ NOT DONE

Takes `RewriteOutput`, `CoverLetterOutput`, candidate name, company name, and output directory. Generates all 4 resume formats (plaintext, markdown, DOCX, PDF) + 2 cover letter formats (plaintext, markdown). Returns `dict[str, Path]` mapping format name to file path.

**Depends on:** 6.B.2–6.B.6

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.8 Wire renderer into pipeline (`pipeline.py`)

**Status:** ❌ NOT DONE

Add `candidate_name: str` and `company_name: str` parameters to `run_resume_pipeline()`. After tone polishing and cover letter agents complete, call `ResumeRenderer.render_all()` and store output paths in the pipeline result dict.

**Depends on:** 6.B.7

**Files changed:** `pipeline.py`

---

#### 6.B.9 Add unit tests for `ResumeRenderer`

**Status:** ❌ NOT DONE

Test template loading, `render_plaintext()`, `render_markdown()`, cover letter rendering, `build_output_path()`, and `render_all()` with mocked file I/O. Verify DOCX/PDF generation produces non-empty files.

**Depends on:** 6.B.1–6.B.7

**Files changed:** new file `tests/test_renderer.py`

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
  formatter.py                    # NEW - output formatting (Phase 6.A)
  templates/
    renderer.py                   # NEW - multi-format resume output (Phase 6.B)
tests/
  test_formatter.py               # NEW (Phase 6.A.4)
  test_renderer.py                # NEW (Phase 6.B.9)
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
| 1 | 6.A.1: `format_resume_markdown()` | ❌ TODO | None | 1 |
| 2 | 6.A.2: `format_resume_plain()` | ❌ TODO | Step 1 | 1 |
| 3 | 6.A.3: `format_cover_letter()` | ❌ TODO | Step 1 | 1 |
| 4 | 6.A.4: Formatter unit tests | ❌ TODO | Steps 1–3 | 1 |
| 5 | 6.B.1: `ResumeRenderer` skeleton + `render_plaintext()` | ❌ TODO | None | 1 |
| 6 | 6.B.2: `render_markdown()` | ❌ TODO | Step 5 | 1 |
| 7 | 6.B.3: Cover letter rendering | ❌ TODO | Step 5 | 1 |
| 8 | 6.B.4: `build_output_path()` | ❌ TODO | Step 5 | 1 |
| 9 | 6.B.5: DOCX generation | ❌ TODO | Step 5 | 2 |
| 10 | 6.B.6: PDF generation | ❌ TODO | Step 5 | 2 |
| 11 | 6.B.7: `render_all()` | ❌ TODO | Steps 6–10 | 1 |
| 12 | 6.B.8: Wire renderer into pipeline | ❌ TODO | Step 11 | 1 |
| 13 | 6.B.9: Renderer unit tests | ❌ TODO | Steps 5–11 | 1 |
| 14 | 7.1: `test_real_files.py` integration test | ❌ TODO | Steps 4, 12 | 1 |
| 15 | 7.2 (remaining): Unit tests for agents + pipeline | ❌ TODO | Steps 4, 12 | 2 |
| 16 | 7.3: Documentation (`docs/`) | ❌ TODO | All | 4 |
