# Resume Pipeline Implementation Plan

## Overview

Implement the full 7-agent resume optimization pipeline as described in `bots.md`. Each agent receives structured input, runs an LLM prompt, and returns validated JSON output. The pipeline chains agents sequentially: parsed data flows from one agent to the next.

---

## Current Architecture

The pipeline uses `PipelineAgent` (generic LLM wrappers with fixed system prompts) orchestrated by `AgentRunner`. Per-agent model assignment is handled by `ModelClientRegistry` + `config/agents.py`. The 7 agents are wired in `pipeline.py` via `run_resume_pipeline()`.

### What exists now:

- `client/model_client.py` — Proper ABC for LLM clients
- `client/ollama_client.py` — Ollama client with error handling
- `client/open_ai_client.py` — OpenAI client with error handling
- `client/errors.py` — Custom LLM exceptions
- `client/format_detector.py` — Regex-based document parser with LLM fallback (connected), plain text support, projects, metrics, keywords extraction
- `client/models.py` — `ParsedResume` (with projects, keywords), `ParsedJobDescription`, and `JDParsingOutput` Pydantic models
- `client/model_registry.py` — Per-agent model assignment registry
- `client/templates/` — Jinja2 resume/cover letter templates (no renderer class)
- `client/agents/jd_parsing.py` — JD Parsing Agent (Agent 1) with LLM + regex fallback
- `config/agents.py` — Environment-based agent-to-model configuration
- `pipeline.py` — `AgentRunner`, `PipelineAgent`, and `run_resume_pipeline()`
- `basic.py` — Single-agent demo
- `tests/test_format_detector.py` — 46 tests for FormatDetector regex parsing
- `tests/conftest.py` — Shared test fixtures
- `pyproject.toml` — Project config (ruff, pyright, pytest)
- `AGENTS.md` — Agent instruction file
- `TESTING.md` — Testing guide
- `sample/` — Sample JDs and resume for testing

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
- `_extract_keywords()` — frequency-based keyword extraction with stopword filtering (top 20)
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

**No further work needed** for this phase. The 7 agents will be implemented as `PipelineAgent` instances with specific system prompts, rather than individual agent classes.

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
- `pipeline.py` — `sample_run()` uses `JDParsingAgent`; `run_resume_pipeline()` handles both model and dict results

**Files changed:** `client/agents/jd_parsing.py` (new), `client/agents/__init__.py` (new), `client/models.py`, `pipeline.py`

**Test:** `uv run python wip_testing/debug_jd.py`

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
2. Call `self._chat(prompt, output=["json"], rules=["Output only valid JSON", "Do not add information not present in the JD"], inputs=[inputs["job_description"]])`
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

1. Pre-process with `FormatDetector.parse_resume()` to get a rough structure
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

**Status:** ❌ NOT DONE

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
5. Validate experiences are in chronological order (most recent first)
6. Validate no new experiences were added (compare with input resume experience count)
7. Validate all certifications from input resume are present in output
8. On failure: retry with explicit instruction "Output a JSON object matching this exact schema: ..."
9. On second failure: return the parsed resume unchanged with a warning logged

**Files changed:** new file `client/agents/resume_rewrite.py`

---

### 3.3 Create ATS Compliance Agent (`client/agents/ats_compliance.py`)

**Status:** ❌ NOT DONE

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
4. Validate `ats_score` is between 0 and 100
5. Validate all certifications from input resume are present in the final resume
6. Validate experiences are in chronological order (most recent first)
7. On failure: retry; on second failure, return a default low-score result with the resume unchanged

**Files changed:** new file `client/agents/ats_compliance.py`

---

## Phase 4: Polish & Cover Letter (Agents 6-7)

### 4.1 Create Tone Polishing Agent (`client/agents/tone_polishing.py`)

**Status:** ❌ NOT DONE

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

**Note:** This agent works on raw text, not structured JSON. The prompt should instruct the LLM to return JSON with a single `polished_resume` field containing the full resume.

**Files changed:** new file `client/agents/tone_polishing.py`

---

### 4.2 Create Cover Letter Agent (`client/agents/cover_letter.py`)

**Status:** ❌ NOT DONE

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
    cover_letter: str  # 250-350 word cover letter
```

**Implementation:**

1. Serialize all three inputs to JSON strings
2. Build prompt combining them
3. Call LLM
4. Parse and validate JSON
5. Validate word count is between 250-350
6. On failure: retry; on second failure, return a minimal generic cover letter

**Files changed:** new file `client/agents/cover_letter.py`

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

**Status:** ✅ DONE

`run_resume_pipeline()` chains all 7 agents sequentially:

1. JD Parsing → `parsed_job_description`
2. Resume Parsing → `parsed_resume`
3. Gap Analysis → `tailoring_strategy`
4. Resume Rewrite → `rewritten_resume`
5. ATS Compliance → `ats_optimized_resume`
6. Tone Polishing → `polished_resume`
7. Cover Letter → `cover_letter`

The pipeline currently uses generic `PipelineAgent` instances. Once individual agent classes are created (Phases 2.3-4.2), they can be swapped in.

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

5. **Add to `requirements.txt`:**

   ```plaintext
   python-docx>=1.0.0
   weasyprint>=60.0
   markdown>=3.5
   ```

7. **Wire into pipeline:**

   - `run_resume_pipeline` gains two new parameters: `candidate_name: str` and `company_name: str`
   - These are passed through to `ResumeRenderer.render_all()` for file naming
   - After tone polishing and cover letter agents complete, call `ResumeRenderer.render_all()`
   - Store output paths in the pipeline result dict

**Files changed:** new file `client/templates/renderer.py`, `requirements.txt`, `pipeline.py`

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
9. Assert `cover_letter` is 250-350 words
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

`docs/` directory exists but is empty. Create:

1. **`docs/architecture.md`:** System overview, data flow diagram, agent chain
2. **`docs/agents.md`:** Each agent's purpose, prompt, input/output schema
3. **`docs/usage.md`:** How to run the pipeline, configure models, add custom agents
4. **`docs/api.md`:** `ModelClient`, `PipelineAgent`, `AgentRunner` interfaces

**Files changed:** new files `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`

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
  models.py                        # EXISTS ✅ (ParsedResume, ParsedJobDescription, JDParsingOutput)
  templates/                       # EXISTS ⚠️ needs renderer.py
    __init__.py                    # EXISTS
    modern.py                      # EXISTS
    classic.py                     # EXISTS
    minimal.py                     # EXISTS
    cover_letter.py                # EXISTS
    renderer.py                    # NEW - multi-format resume output
  agents/                          # EXISTS ✅ (partial — Agent 1 done)
    __init__.py                    # EXISTS ✅
    jd_parsing.py                  # EXISTS ✅ - Agent 1
    resume_parsing.py              # NEW - Agent 2
    gap_analysis.py                # NEW - Agent 3
    resume_rewrite.py              # NEW - Agent 4
    ats_compliance.py              # NEW - Agent 5
    tone_polishing.py              # NEW - Agent 6
    cover_letter.py                # NEW - Agent 7
  formatter.py                     # NEW - output formatting
config/
  __init__.py                      # EXISTS (empty)
  agents.py                        # EXISTS ✅
tests/
  __init__.py                      # EXISTS ✅
  conftest.py                      # EXISTS ✅ (shared fixtures)
  test_format_detector.py          # EXISTS ✅ (46 tests)
  test_agents.py                   # NEW
  test_pipeline.py                 # NEW
docs/
  architecture.md                  # NEW
  agents.md                        # NEW
  usage.md                         # NEW
  api.md                           # NEW
pipeline.py                        # EXISTS ✅
basic.py                           # EXISTS ✅
test_real_files.py                 # NEW
pyproject.toml                     # EXISTS ✅ (ruff, pyright, pytest config)
AGENTS.md                          # EXISTS ✅
resume-todo.md                     # THIS FILE
bots.md                            # UNCHANGED (reference)
requirements.txt                   # EXISTS ✅
sample/                            # EXISTS ✅
  jobs/                            # 2 sample JDs
  resume/                          # 1 sample resume
TESTING.md                         # EXISTS ✅
wip_testing/
  parsing.py                       # EXISTS ✅ (regex + LLM parsing demo)
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
| 9 | Phase 3.1: Gap Analysis Agent | ✅ DONE | Steps 6, 7, 8 | 1 |
| 10 | Phase 3.2: Resume Rewrite Agent | ❌ TODO | Steps 6, 8, 9 | 1 |
| 11 | Phase 3.3: ATS Compliance Agent | ❌ TODO | Steps 6, 10 | 1 |
| 12 | Phase 4.1: Tone Polishing Agent | ❌ TODO | Steps 6, 11 | 1 |
| 13 | Phase 4.2: Cover Letter Agent | ❌ TODO | Steps 6, 7, 8, 9 | 1 |
| 14 | Phase 5.2: Wire agents into pipeline | ❌ TODO | Steps 7-13 | 1 |
| 15 | Phase 6.2: Output formatter | ❌ TODO | Step 6 | 1 |
| 16 | Phase 6.3: Template renderer | ❌ TODO | Steps 6, 15 | 2 |
| 17 | Phase 7.1: test_real_files.py | ❌ TODO | Steps 14, 16 | 1 |
| 18 | Phase 7.2: Unit tests (agents, pipeline) | ❌ TODO | Steps 6, 15, 16 | 2 |
| 19 | Phase 7.3: Documentation | ❌ TODO | All | 4 |
