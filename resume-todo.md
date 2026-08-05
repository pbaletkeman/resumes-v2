# Resume Pipeline — Remaining Work

Everything still left to implement. For the archive of what is complete, see [resume-done.md](resume-done.md).

## Overview

The 7-agent resume optimization pipeline (see `bots.md`) is largely implemented. The dedicated agent classes for all 7 agents are done, as are Phase 8 (structured JSON output), Phase 4.3 (post-validation for rewrite/cover letter, fallback templates, logging, prompt strengthening, `company_name` — see `resume-done.md`), Phase 5.2 (pipeline wiring — all 7 dedicated classes wired), Phase 6.A (output formatting helpers), Phase 6.B.1–6.B.2 (renderer skeleton + `render_plaintext`/`render_markdown`), and 268 unit tests. The items below are what remains.

---

> Phase 4.3 (Fix LLM Fallback Falsehoods — validation, fallback templates, logging, prompt strengthening, `company_name`) is **complete** — archived in `resume-done.md` §4.3.
>
> Phase 5.2 (wire up the 7-agent pipeline) is **complete** — archived in `resume-done.md` §5.2.
>
> Phase 6.A (output formatting helpers — `client/formatter.py` + `tests/test_formatter.py`) is **complete** — archived in `resume-done.md` §6.2.
>
> Phase 6.B.1 (renderer skeleton + `render_plaintext()`) and 6.B.2 (`render_markdown()`) are **complete** — archived in `resume-done.md` §6.3.

## Phase 6: Output & Validation

Phase 6 produces clean, formatted output from the pipeline. It breaks into two workstreams: **6.A** (simple formatting helpers) and **6.B** (template-based multi-format renderer). 6.A is complete (see `resume-done.md` §6.2). The remaining work is 6.B.3–6.B.9 below. 6.B.3–6.B.6 are independent of each other; 6.B.7 depends on 6.B.2–6.B.6; 6.B.8 depends on 6.B.7; 6.B.9 depends on 6.B.1–6.B.7.

### 6.B — Template-Based Multi-Format Renderer (remaining work)

Current state of `client/templates/renderer.py`: `ResumeRenderer` with `__init__`, template loading from `client.templates.TEMPLATES`, `render_plaintext()`, `render_markdown()` (Jinja2 against template dicts), `_build_context()` (Pydantic → dict), and `_clean_output()`. No cover letter rendering, DOCX/PDF, or output paths yet.

---

#### 6.B.3 Add `render_cover_letter_plaintext()` and `render_cover_letter_markdown()`

**Status:** ❌ NOT DONE

Render `CoverLetterOutput` using the `COVER_LETTER` template. Two methods for plaintext and markdown variants. Follow the existing `render_plaintext()`/`render_markdown()` pattern (lookup template dict key, `_env.from_string(...).render(**context)`, `_clean_output`).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.3.1** Add `_build_cover_letter_context()` helper to `ResumeRenderer` — converts a `CoverLetterOutput` (plus candidate name / company name) into the context dict expected by the `COVER_LETTER` template. Inspect `client/templates/cover_letter.py` first to match its template variables exactly.
- **6.B.3.2** Add `render_cover_letter_plaintext(cover_letter, *, name="", company="")` — render against the `COVER_LETTER` template's `"plaintext"` key, run through `_clean_output()`. Follow the exact signature/style of `render_plaintext()`.
- **6.B.3.3** Add `render_cover_letter_markdown(cover_letter, *, name="", company="")` — same as 6.B.3.2 against the `"markdown"` key.

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.4 Add `build_output_path()` static method

**Status:** ❌ NOT DONE

Static utility to build timestamped file paths: `{date}_{candidate_name}_{company_name}_{document_type}.{ext}`. Date format `YYYYMMDD_HHMM`. Pure path logic, no I/O. Must be filename-safe (sanitize spaces, invalid chars, empty segments).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.4.1** Add a `_slugify()` static helper — normalize a name/company string to a filename-safe ASCII token (lowercase, non-alphanumerics → `-`, collapse repeats, strip leading/trailing hyphens, empty → `""`).
- **6.B.4.2** Implement `build_output_path(document_type, *, candidate_name, company_name, output_dir, ext=None)` — build `{output_dir}/{YYYYMMDD_HHMM}_{slug(candidate)}_{slug(company)}_{document_type}.{ext}`, defaulting `ext` per document type (e.g., `.txt`, `.md`, `.docx`, `.pdf`). Return `Path`. No file I/O.

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.5 Add DOCX generation (`render_docx()`)

**Status:** ❌ NOT DONE

Use `python-docx` to render `RewriteOutput` as a `.docx` file. Professional font (Calibri/Arial), 10–11pt body, 14pt name, bold section headers, 1-inch margins, single spacing.

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.5.1** Add `python-docx>=1.0.0` to `pyproject.toml` (under the existing dependencies) and run `uv sync`.
- **6.B.5.2** Add `render_docx(resume, *, name="", title="", template="modern", output_path=None) -> Path` — create the `Document`, apply page setup (1-inch margins, letter size), set default font (Calibri 11pt), and write to `output_path` (or a temp path when `None`). Return the written `Path`.
- **6.B.5.3** Add `_populate_docx_paragraphs(doc, context)` helper — walk the `_build_context()` dict and add body content: summary paragraph, skills line/bullets, per-experience blocks (title bold, company + dates, responsibilities/achievements/metrics bullets), projects, certifications, education. Name rendered at 14pt bold.
- **6.B.5.4** Add `_docx_heading(doc, text)` + `_docx_bullet(doc, text)` helpers — encapsulate the run-level font/bold/spacing styling so the styling rules live in one place.

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `python-docx>=1.0.0`)

---

#### 6.B.6 Add PDF generation (`render_pdf()`)

**Status:** ❌ NOT DONE

Use `reportlab` to render `RewriteOutput` as a `.pdf` file. ReportLab builds the PDF **directly** with the Platypus framework (`SimpleDocTemplate`, `Paragraph`, `Spacer`, `ListFlowable`) — no HTML/Markdown intermediate, so the `markdown` package is **not** needed. Same professional styling as DOCX (Calibri/Arial-equivalent Helvetica, 10–11pt body, 14pt name, bold section headers, 1-inch margins, single spacing).

**Depends on:** 6.B.1 (same class)

**Sub-tasks:**

- **6.B.6.1** Add `reportlab>=4.0` to `pyproject.toml` and run `uv sync`. If you plan to add a **profile photo, icons, or complex graphical decorations** to the resume, also install `pillow` alongside ReportLab (Platypus uses PIL to draw and size embedded images) — add `pillow>=10.0` to `pyproject.toml` and `uv sync`. Do **not** add `markdown>=3.5` — ReportLab does not use an HTML pipeline.
- **6.B.6.2** Add PDF styling helpers — a `_pdf_styles()` static helper that returns a dict of `ParagraphStyle` objects (name at 14pt bold, section headers bold, body at 10–11pt, Helvetica family, single leading) so the styling lives in one place. Note ReportLab's built-in Helvetica/Helvetica-Bold is a Type-1 base-14 font (fine for the project's ASCII-only convention) — switch to an embedded TTF font only if non-Latin text is ever required.
- **6.B.6.3** Add `render_pdf(resume, *, name="", title="", template="modern", output_path=None) -> Path` — create a `SimpleDocTemplate` (letter size, 1-inch margins), build a list of Platypus flowables from `_build_context()` (header paragraph, summary, skills, per-experience blocks, projects, certifications, education), call `doc.build(flowables)`, and return the written `Path`.
- **6.B.6.4** Add a `_populate_pdf_flowables(context, styles)` helper — returns the `list[Flowable]` (paragraphs, spacers, bullet `ListFlowable`) for the resume body, mirroring the DOCX `_populate_docx_paragraphs` structure.
- **6.B.6.5** Add a graceful import guard — `reportlab` and `pillow` install cleanly cross-platform (no system deps like WeasyPrint's `pango`), but still wrap imports so a missing package raises a clear `ImportError`/log message naming the missing library rather than failing deep in the pipeline. Confirm `from reportlab.platypus import SimpleDocTemplate` imports under `uv run` on this machine before marking done.

**Files changed:** `client/templates/renderer.py`, `pyproject.toml` (add `reportlab>=4.0`; add `pillow>=10.0` only if graphics are added)

---

#### 6.B.7 Add `render_all()` convenience method

**Status:** ❌ NOT DONE

Takes `RewriteOutput`, `CoverLetterOutput`, candidate name, company name, and output directory. Generates all 4 resume formats (plaintext, markdown, DOCX, PDF) + 2 cover letter formats (plaintext, markdown). Returns `dict[str, Path]` mapping format name to file path.

**Depends on:** 6.B.2–6.B.6

**Sub-tasks:**

- **6.B.7.1** Add `render_all(resume, cover_letter, *, candidate_name, company_name, output_dir, resume_template="modern") -> dict[str, Path]` — wire together `render_plaintext`, `render_markdown`, `render_docx`, `render_pdf`, `render_cover_letter_plaintext`, `render_cover_letter_markdown`, each writing to `build_output_path(...)`.
- **6.B.7.2** Ensure `output_dir` exists (`Path.mkdir(parents=True, exist_ok=True)`) before writing; handle a missing/empty `cover_letter` gracefully (skip the two letter formats rather than error).
- **6.B.7.3** Return the `dict[str, Path]` keyed by format name (`"resume_plaintext"`, `"resume_markdown"`, `"resume_docx"`, `"resume_pdf"`, `"cover_letter_plaintext"`, `"cover_letter_markdown"`). Verify all 6 keys present and files non-empty via a quick manual run.

**Files changed:** `client/templates/renderer.py`

---

#### 6.B.8 Wire renderer into pipeline (`pipeline.py`)

**Status:** ❌ NOT DONE

Add `candidate_name: str` and `company_name: str` parameters to `run_resume_pipeline()`. After tone polishing and cover letter agents complete, call `ResumeRenderer.render_all()` and store output paths in the pipeline result dict.

**Depends on:** 6.B.7

**Sub-tasks:**

- **6.B.8.1** Add `candidate_name: str = ""` and `company_name: str = ""` parameters to `run_resume_pipeline()` (and thread through any caller, e.g., `sample_run()` / `wip_testing/test_cover_letter.py`).
- **6.B.8.2** After the tone polishing and cover letter agents complete, instantiate `ResumeRenderer()` and call `render_all(...)` with the collected `polished_resume`/`cover_letter` outputs. Skip rendering when `candidate_name` is empty (log at INFO).
- **6.B.8.3** Store the returned `dict[str, Path]` in the pipeline result dict under an `"output_files"` key (alongside the existing agent output keys).

**Files changed:** `pipeline.py`

---

#### 6.B.9 Add unit tests for `ResumeRenderer`

**Status:** ❌ NOT DONE

Test template loading, `render_plaintext()`, `render_markdown()`, cover letter rendering, `build_output_path()`, and `render_all()` with mocked file I/O. Verify DOCX/PDF generation produces non-empty files.

**Depends on:** 6.B.1–6.B.7

**Sub-tasks:**

- **6.B.9.1** Create `tests/test_renderer.py` with a sample `RewriteOutput` fixture (reuse the patterns in `tests/test_formatter.py` / `tests/conftest.py`).
- **6.B.9.2** Tests for template loading, `render_plaintext()`, and `render_markdown()` — sections present, ordering, `_clean_output()` behavior, unknown-template `KeyError`.
- **6.B.9.3** Tests for `render_cover_letter_plaintext()` / `render_cover_letter_markdown()` — output contains the letter body, salutation, and signature.
- **6.B.9.4** Tests for `build_output_path()` — naming pattern, `YYYYMMDD_HHMM` date format, slugification (spaces, punctuation, empty candidate/company), extension defaults, output dir joining.
- **6.B.9.5** Tests for `render_all()` with `tmp_path` + mocked individual renderer methods (verify it writes 6 files with the expected naming pattern and returns all 6 keys).
- **6.B.9.6** DOCX/PDF smoke tests — render to a real `tmp_path` file and assert a non-empty file is produced (skip if optional dependencies unavailable; use `pytest.importorskip`).

**Files changed:** new file `tests/test_renderer.py`

---

### 6.10 Dependency Library Notes & Cautions

Caveats worth keeping in mind when adding the 6.B dependencies:

- **`reportlab` + `pillow`:** Both are pure wheels, install cleanly cross-platform, and carry **no system-level deps** (unlike WeasyPrint, which needs `pango`/`cairo`). If you eventually add a profile photo, icons, or complex graphical decorations, **`pillow` must be installed alongside `reportlab`** — Platypus embeds and sizes images through PIL (`_img_utils`, `Image` flowable) and raises an error if PIL is missing. (Once Pillow 10+ is installed, ReportLab 4.x resolves a known wheel/pillow naming collision automatically.)
- **ReportLab built-in fonts (base-14):** Helvetica/Helvetica-Bold/Times are Type-1 fonts that **cannot render Unicode/emoji** (the ASCII-only convention in this repo sidesteps this). If non-Latin text is ever needed, you must register a TTF font via `pdfmetrics.registerFont(TTFont(...))`; otherwise ReportLab just renders a thin bar / drops the glyph.
- **`markdown` package is no longer needed** — ReportLab replaces the old HTML→PDF pipeline, so do **not** add `markdown>=3.5` (dropped from 6.B.6.1).
- **`python-docx`:** Pure Python, no system deps or font-caching — the lowest-risk dependency in 6.B. It shells out to nothing and only writes OOXML.
- **`jinja2` (already added):** No system issues; validate templates once per render with a single `Environment` (already cached in `ResumeRenderer.__init__`). `StrictUndefined` is correct to surface template bugs.
- **`pytest.importorskip` for 6.B.9.6:** DOCX/PDF smoke tests should skip (not fail) when `python-docx`/`reportlab` are unavailable, so the tests don't break the deterministic suites on stripped installs.

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

**What exists now:** 268 tests across 7 files:

- `tests/test_format_detector.py` — 46 tests covering all `FormatDetector` static extraction methods + regex-only parse flows
- `tests/test_jd_parsing.py` — 19 tests (`_extract_company_name` + `_sync_company_name`)
- `tests/test_resume_rewrite_validation.py` — 56 tests (§4.3.A checks + §C skill tailoring + §D fallback logging)
- `tests/test_cover_letter_validation.py` — 80 tests (§4.3.B checks + §C fallback builder + §D fallback logging)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 15 tests (shared parser + JSON Schema helpers)
- `tests/test_formatter.py` — 41 tests (Phase 6.A formatting helpers)

**Still needed:**

- `tests/test_renderer.py` — see 6.B.9
- `tests/test_agents.py` — mock `ModelClient`, verify prompts and JSON validation
- `tests/test_pipeline.py` — end-to-end with mocked agents

**Files changed:** new files `tests/test_agents.py`, `tests/test_pipeline.py` (plus `tests/test_renderer.py` from 6.B.9)

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
tests/
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

Already created (see `resume-done.md`): `client/formatter.py`, `client/templates/renderer.py`, `tests/test_formatter.py`.

---

## Remaining Execution Order

| Step | Phase | Status | Depends On | Estimated Files Changed |
| ------ | ------- | -------- | ------------ | ------------------------ |
| 1 | 6.B.3.1: `_build_cover_letter_context()` | ❌ TODO | 6.B.1 | 1 |
| 2 | 6.B.3.2: `render_cover_letter_plaintext()` | ❌ TODO | Step 1 | 1 |
| 3 | 6.B.3.3: `render_cover_letter_markdown()` | ❌ TODO | Step 2 | 1 |
| 4 | 6.B.4.1: `_slugify()` helper | ❌ TODO | 6.B.1 | 1 |
| 5 | 6.B.4.2: `build_output_path()` | ❌ TODO | Step 4 | 1 |
| 6 | 6.B.5.1: add `python-docx` dep | ❌ TODO | 6.B.1 | 1 |
| 7 | 6.B.5.2: `render_docx()` + page setup | ❌ TODO | Step 6 | 1 |
| 8 | 6.B.5.3: `_populate_docx_paragraphs()` | ❌ TODO | Step 7 | 1 |
| 9 | 6.B.5.4: `_docx_heading()`/`_docx_bullet()` | ❌ TODO | Step 7 | 1 |
| 10 | 6.B.6.1: add `reportlab` dep (+`pillow` if graphics) | ❌ TODO | 6.B.1 | 1 |
| 11 | 6.B.6.2: `_pdf_styles()` | ❌ TODO | 6.B.2 | 1 |
| 12 | 6.B.6.3: `render_pdf()` | ❌ TODO | Steps 10-11 | 1 |
| 13 | 6.B.6.4: `_populate_pdf_flowables()` | ❌ TODO | Step 12 | 1 |
| 14 | 6.B.6.5: import guard + verify on Windows | ❌ TODO | Step 12 | 1 |
| 15 | 6.B.7.1-6.B.7.3: `render_all()` | ❌ TODO | Steps 2-14 | 1 |
| 16 | 6.B.8.1-6.B.8.3: wire renderer into pipeline | ❌ TODO | Step 15 | 1 |
| 17 | 6.B.9.1-6.B.9.6: renderer unit tests | ❌ TODO | Steps 1-16 | 1 |
| 18 | 7.1: `test_real_files.py` integration test | ❌ TODO | Step 16 | 1 |
| 19 | 7.2 (remaining): Unit tests for agents + pipeline | ❌ TODO | Step 16 | 2 |
| 20 | 7.3: Documentation (`docs/`) | ❌ TODO | All | 4 |
