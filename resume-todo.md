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
| 19 | 7.2.1: agent unit tests (`tests/test_agent_*.py` or `test_agents.py`) | ❌ TODO | Step 16 | 7 to 8 |
| 20 | 7.2.2: pipeline tests (`tests/test_pipeline.py`) | ❌ TODO | Step 19, 16 | 1 |
| 21 | 7.3.1: `docs/architecture.md` | ❌ TODO | All | 1 |
| 22 | 7.3.2: `docs/agents.md` | ❌ TODO | 7.3.1 | 1 |
| 23 | 7.3.3: `docs/usage.md` | ❌ TODO | All | 1 |
| 24 | 7.3.4: `docs/api.md` | ❌ TODO | 7.3.1 | 1 |
