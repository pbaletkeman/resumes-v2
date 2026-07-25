# Resume Pipeline Implementation Plan

## Overview

Implement the full 7-agent resume optimization pipeline as described in `bots.md`. Each agent receives structured input, runs an LLM prompt, and returns validated JSON output. The pipeline chains agents sequentially: parsed data flows from one agent to the next.

---

## Phase 1: Core Infrastructure

### 1.1 Refactor `client/model_client.py`

**What exists now:**
- Abstract `chat()` method with manual `raise NotImplementedError`
- 8 orphaned pipeline state fields (`_job_description`, `_resume`, etc.) stored as instance attributes with property getters/setters — none are used anywhere

**What to do:**
1. Remove all 8 pipeline state fields and their properties from `ModelClient`. The `chat()` method takes everything it needs as parameters; these attributes are dead code.
2. Convert to a proper ABC:
   ```python
   from abc import ABC, abstractmethod

   class ModelClient(ABC):
       @abstractmethod
       async def chat(self, purpose: str, prompt: str, output: list[str], rules: list[str], inputs: list[str]) -> str:
           ...
   ```
3. Keep the class docstring explaining the interface contract.
4. Remove the `__init__` entirely — subclasses handle their own initialization.

**Files changed:** `client/model_client.py`

---

### 1.2 Add error handling to LLM clients

**`client/ollama_client.py`:**
1. Import `ollama` exceptions: `ollama.ResponseError`, `ollama.ConnectionError`
2. Wrap the `self.client.chat()` call in try/except:
   - `ollama.ConnectionError` → raise a custom `LLMConnectionError` with a message like "Cannot connect to Ollama. Is the server running?"
   - `ollama.ResponseError` → raise `LLMResponseError` with the model name and error detail
   - `asyncio.TimeoutError` → raise `LLMTimeoutError` with the model name and 90s timeout info
3. Create a `client/errors.py` module defining these custom exceptions:
   ```python
   class LLMError(Exception): ...
   class LLMConnectionError(LLMError): ...
   class LLMResponseError(LLMError): ...
   class LLMTimeoutError(LLMError): ...
   ```

**`client/open_ai_client.py`:**
1. Import `openai` exceptions: `openai.APIError`, `openai.AuthenticationError`, `openai.RateLimitError`, `openai.APIConnectionError`
2. Wrap the `self.client.chat.completions.create()` call:
   - `openai.AuthenticationError` → raise `LLMError("Invalid OpenAI API key")`
   - `openai.RateLimitError` → raise `LLMError("OpenAI rate limit exceeded")`
   - `openai.APIConnectionError` → raise `LLMConnectionError("Cannot connect to OpenAI API")`
   - `openai.APIError` → raise `LLMResponseError` with the error message
   - `asyncio.TimeoutError` → raise `LLMTimeoutError`

**Files changed:** `client/ollama_client.py`, `client/open_ai_client.py`, new file `client/errors.py`

---

### 1.3 Clean up `requirements.txt`

**What exists now:** A `pip freeze` dump of 128 packages, most unused.

**What to do:**
1. Replace with a minimal list of direct dependencies:
   ```
   ollama>=0.4.0
   openai>=1.0.0
   pydantic>=2.0.0
   ```
2. Create a separate `requirements-dev.txt` for dev/test dependencies if needed later.

**Files changed:** `requirements.txt`

---

## Phase 2: Document Parsing (Agents 1 & 2)

### 2.1 Expand `client/format_detector.py`

**What exists now:** Markdown-only regex parser. Extracts: name, title, summary, skills, experience, education from resumes; title, responsibilities, requirements, nice-to-have from JDs.

**What to add:**

1. **Projects section extraction:**
   ```python
   @staticmethod
   def _extract_projects(content: str) -> list[str]:
       # Match "## Projects" heading, extract bullet points
   ```

2. **Certifications section extraction:**
   ```python
   @staticmethod
   def _extract_certifications(content: str) -> list[str]:
       # Match "## Certifications" or "## Certificates" heading
   ```

3. **Metric extraction from experience bullets:**
   ```python
   @staticmethod
   def _extract_metrics(text: str) -> list[str]:
       # Regex patterns for:
       # - Percentages: r"\d+(\.\d+)?%"
       # - Dollar amounts: r"\$[\d,]+([KMB])?"
       # - Team sizes: r"team of \d+"
       # - Timeframes: r"\d+ (months?|years?|weeks?)"
       # Returns list of metric strings found in the text
   ```

4. **Keyword extraction (frequency-based):**
   ```python
   @staticmethod
   def _extract_keywords(content: str, top_n: int = 20) -> list[str]:
       # Split on whitespace/punctuation
       # Filter stopwords (the, a, is, and, etc.)
       # Count frequency, return top N meaningful terms
   ```

5. **Plain-text support:**
   - Detect if content is Markdown (has `## ` patterns) or plain text
   - For plain text: split on blank lines to find sections, look for lines ending with `:` as section headers
   - Add a `_detect_format(content: str) -> str` method returning `"markdown"` or `"plain"`

6. **Update `parse_resume()` return type** to include new fields:
   ```python
   return {
       "name": ...,
       "title": ...,
       "summary": ...,
       "skills": ...,
       "experience": ...,
       "education": ...,
       "projects": FormatDetector._extract_projects(content),  # NEW
       "certifications": FormatDetector._extract_certifications(content),  # NEW
       "keywords": FormatDetector._extract_keywords(content),  # NEW
       "raw": content,
   }
   ```

**Files changed:** `client/format_detector.py`

---

### 2.2 Create Agent Base Class (`client/agents/base.py`)

**What to do:**

1. Create directory `client/agents/` with `__init__.py`

2. Define `BaseAgent` ABC:
   ```python
   from abc import ABC, abstractmethod
   from typing import Any
   from client.model_client import ModelClient

   class BaseAgent(ABC):
       """Base class for all pipeline agents."""

       def __init__(self, client: ModelClient) -> None:
           self.client = client

       @property
       @abstractmethod
       def name(self) -> str:
           """Agent name for logging."""
           ...

       @property
       @abstractmethod
       def system_prompt(self) -> str:
           """System prompt sent as the model's role."""
           ...

       @abstractmethod
       async def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
           """Execute the agent and return structured output."""
           ...

       async def _chat(self, prompt: str, output: list[str], rules: list[str], inputs: list[str]) -> str:
           """Helper to call the LLM with the agent's system prompt."""
           return await self.client.chat(
               purpose=self.system_prompt,
               prompt=prompt,
               output=output,
               rules=rules,
               inputs=inputs,
           )
   ```

**Files changed:** new file `client/agents/base.py`, new file `client/agents/__init__.py`

---

### 2.3 Create JD Parsing Agent (`client/agents/jd_parsing.py`)

**Purpose:** Extract structured data from a job description using LLM.

**System prompt (from `bots.md`):**
```
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
    company_signals: dict[str, str]  # {"culture": "...", "values": "...", "mission": "..."}
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

### 2.4 Create Resume Parsing Agent (`client/agents/resume_parsing.py`)

**Purpose:** Convert a resume into structured JSON.

**System prompt (from `bots.md`):**
```
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

**Purpose:** Compare parsed JD vs parsed resume, produce a tailoring strategy.

**System prompt (from `bots.md`):**
```
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

**Purpose:** Rewrite the resume using the tailoring strategy.

**System prompt (from `bots.md`):**
```
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

**Purpose:** Evaluate the rewritten resume for ATS compatibility and fix issues.

**System prompt (from `bots.md`):**
```
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

**Critical fix:** Currently only sends `rewritten[:300]` — must send the FULL resume text so the agent can evaluate keyword coverage, formatting, and section structure across the entire document.

**Files changed:** new file `client/agents/ats_compliance.py`

---

## Phase 4: Polish & Cover Letter (Agents 6-7)

### 4.1 Create Tone Polishing Agent (`client/agents/tone_polishing.py`)

**Purpose:** Improve tone and professionalism without changing facts.

**System prompt (from `bots.md`):**
```
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

**Purpose:** Generate a tailored cover letter.

**System prompt (from `bots.md`):**
```
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
- Keep length between 250-350 words.
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

**What exists now:** Stub that raises `NotImplementedError`.

**What to do:**

1. Store a `ModelClient` instance alongside the agents dict
2. Implement `run_agent()`:
   ```python
   def run_agent(self, name: str, inputs: dict[str, Any]) -> dict[str, Any]:
       if name not in self.agents:
           raise KeyError(f"Agent '{name}' not found")
       agent = self.agents[name]
       try:
           result = asyncio.run(agent.run(inputs))
           return result
       except Exception as e:
           logging.error(f"Agent '{name}' failed: {e}")
           raise
   ```
3. Since `run_resume_pipeline` is sync but agents are async, change `run_resume_pipeline` to `async def run_resume_pipeline(...)` and use `await agent.run(inputs)` directly
4. Add `import logging` and a logger at module level
5. Add timing: log how long each agent takes

**Files changed:** `pipeline.py`

---

### 5.2 Wire up the 7-agent pipeline

1. Update `client/agents/__init__.py` to export all agents:
   ```python
   from client.agents.jd_parsing import JDParsingAgent
   from client.agents.resume_parsing import ResumeParsingAgent
   from client.agents.gap_analysis import GapAnalysisAgent
   from client.agents.resume_rewrite import ResumeRewriteAgent
   from client.agents.ats_compliance import ATSComplianceAgent
   from client.agents.tone_polishing import TonePolishingAgent
   from client.agents.cover_letter import CoverLetterAgent
   ```

2. Update `pipeline.py` `__main__` block to instantiate real agents:
   ```python
   from client.ollama_client import OllamaClient
   from client.agents import (
       JDParsingAgent, ResumeParsingAgent, GapAnalysisAgent,
       ResumeRewriteAgent, ATSComplianceAgent, TonePolishingAgent,
       CoverLetterAgent,
   )

   client = OllamaClient("qwen3.5")
   agents = {
       "jd_parsing_agent": JDParsingAgent(client),
       "resume_parsing_agent": ResumeParsingAgent(client),
       "gap_analysis_agent": GapAnalysisAgent(client),
       "resume_rewrite_agent": ResumeRewriteAgent(client),
       "ats_compliance_agent": ATSComplianceAgent(client),
       "tone_polishing_agent": TonePolishingAgent(client),
       "cover_letter_agent": CoverLetterAgent(client),
   }
   ```

3. Update `run_resume_pipeline` to pass structured data between agents (not raw strings):
   - Agent 1 output → Agent 3 input (`parsed_job_description`)
   - Agent 2 output → Agent 3 input (`parsed_resume`)
   - Agent 3 output → Agent 4 input (`tailoring_strategy`)
   - Agent 4 output → Agent 5 input (`rewritten_resume`)
   - Agent 5 output → Agent 6 input (`ats_optimized_resume`)
   - Agents 1+2+3 output → Agent 7 input

**Files changed:** `pipeline.py`, `client/agents/__init__.py`

---

### 5.3 Deprecate `client/resume_processor.py`

**What to do:**
1. Add a deprecation warning at the top of `optimize_resume()`:
   ```python
   import warnings
   warnings.warn(
       "ResumeProcessor is deprecated. Use pipeline.run_resume_pipeline() instead.",
       DeprecationWarning, stacklevel=2,
   )
   ```
2. Keep it functional for backward compatibility but do not extend it further.
3. Update `test_real_files.py` to use `pipeline.py` instead.

**Files changed:** `client/resume_processor.py`, `test_real_files.py`

---

## Phase 6: Output & Validation

### 6.1 Add Pydantic models (`client/models.py`)

Create a shared models module with all schemas:

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

**Files changed:** new file `client/models.py`

---

### 6.2 Add output formatting utilities (`client/formatter.py`)

Create a formatter that converts structured output to clean documents:

```python
def format_resume_markdown(rewrite: RewriteOutput) -> str:
    """Convert structured resume to clean Markdown."""

def format_resume_plain ATS(ats: ATSComplianceOutput) -> str:
    """Convert to plain-text ATS-friendly format (no Markdown)."""

def format_cover_letter(text: str) -> str:
    """Clean up cover letter text (normalize whitespace, fix encoding)."""
```

**Files changed:** new file `client/formatter.py`

---

## Phase 7: Testing & Docs

### 7.1 Update `test_real_files.py`

1. Switch from `ResumeProcessor` to `pipeline.run_resume_pipeline()`
2. Assert all 7 output keys are present
3. Assert `parsed_job_description` has `role_title` and `required_skills`
4. Assert `parsed_resume` has `experience` as a list
5. Assert `tailoring_strategy` has `missing_skills`
6. Assert `ats_optimized_resume` is not empty
7. Assert `polished_resume` is not empty
8. Assert `cover_letter` is 250-350 words
9. Assert experiences are in chronological order (most recent first)
10. Assert no new experiences were added (compare with input resume)
11. Assert all certifications from input resume are present in output
12. Print summary of results

**Files changed:** `test_real_files.py`

---

### 7.2 Add unit tests (`tests/`)

Create `tests/` directory with:

1. **`tests/test_format_detector.py`:**
   - Test `_extract_name()` with Markdown and plain text
   - Test `_extract_list_section()` with various heading patterns
   - Test `_extract_bullet_points()` with multiple keyword patterns
   - Test `_extract_metrics()` with percentages, dollar amounts, team sizes
   - Test `parse_resume()` with a sample Markdown resume
   - Test `parse_job_description()` with a sample JD

2. **`tests/test_agents.py`:**
   - Test each agent's `run()` method with a mock `ModelClient`
   - Verify the LLM is called with the correct system prompt
   - Verify JSON parsing and Pydantic validation
   - Test retry logic on invalid JSON
   - Test fallback behavior on second failure

3. **`tests/test_pipeline.py`:**
   - Test `run_resume_pipeline()` end-to-end with all agents mocked
   - Verify data flows correctly between agents
   - Test error propagation when an agent fails

**Files changed:** new directory `tests/`, new files `tests/__init__.py`, `tests/test_format_detector.py`, `tests/test_agents.py`, `tests/test_pipeline.py`

---

### 7.3 Populate `docs/`

1. **`docs/architecture.md`:** System overview, data flow diagram, agent chain
2. **`docs/agents.md`:** Each agent's purpose, prompt, input/output schema
3. **`docs/usage.md`:** How to run the pipeline, configure models, add custom agents
4. **`docs/api.md`:** `ModelClient`, `BaseAgent`, `AgentRunner` interfaces

**Files changed:** new files `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`

---

## File Structure (Target)

```
client/
  __init__.py
  errors.py                  # NEW - custom exceptions
  model_client.py            # MODIFIED - proper ABC
  ollama_client.py           # MODIFIED - error handling
  open_ai_client.py          # MODIFIED - error handling
  format_detector.py         # MODIFIED - expanded parsing
  resume_processor.py        # MODIFIED - deprecated
  models.py                  # NEW - Pydantic schemas
  formatter.py               # NEW - output formatting
  agents/
    __init__.py              # NEW - agent exports
    base.py                  # NEW - BaseAgent ABC
    jd_parsing.py            # NEW - Agent 1
    resume_parsing.py        # NEW - Agent 2
    gap_analysis.py          # NEW - Agent 3
    resume_rewrite.py        # NEW - Agent 4
    ats_compliance.py        # NEW - Agent 5
    tone_polishing.py        # NEW - Agent 6
    cover_letter.py          # NEW - Agent 7
tests/
  __init__.py                # NEW
  test_format_detector.py    # NEW
  test_agents.py             # NEW
  test_pipeline.py           # NEW
docs/
  architecture.md            # NEW
  agents.md                  # NEW
  usage.md                   # NEW
  api.md                     # NEW
pipeline.py                  # MODIFIED - working orchestration
basic.py                     # UNCHANGED
test_real_files.py           # MODIFIED - uses pipeline
resume-todo.md               # THIS FILE
bots.md                      # UNCHANGED (reference)
requirements.txt             # MODIFIED - clean deps
```

---

## Execution Order

| Step | Phase | Depends On | Estimated Files Changed |
|------|-------|------------|------------------------|
| 1 | Phase 1.1: Refactor ModelClient | None | 1 |
| 2 | Phase 1.2: Error handling + errors.py | Step 1 | 4 |
| 3 | Phase 1.3: Clean requirements.txt | None | 1 |
| 4 | Phase 2.1: Expand FormatDetector | None | 1 |
| 5 | Phase 2.2: BaseAgent + agents/ | Step 1 | 2 |
| 6 | Phase 2.3: JD Parsing Agent | Steps 4, 5 | 1 |
| 7 | Phase 2.4: Resume Parsing Agent | Steps 4, 5 | 1 |
| 8 | Phase 3.1: Gap Analysis Agent | Steps 5, 6, 7 | 1 |
| 9 | Phase 3.2: Resume Rewrite Agent | Steps 5, 7, 8 | 1 |
| 10 | Phase 3.3: ATS Compliance Agent | Steps 5, 9 | 1 |
| 11 | Phase 4.1: Tone Polishing Agent | Steps 5, 10 | 1 |
| 12 | Phase 4.2: Cover Letter Agent | Steps 5, 6, 7, 8 | 1 |
| 13 | Phase 5.1: Implement AgentRunner | Steps 2, 5-12 | 1 |
| 14 | Phase 5.2: Wire up pipeline | Steps 6-12, 13 | 2 |
| 15 | Phase 5.3: Deprecate resume_processor | Step 14 | 2 |
| 16 | Phase 6.1: Pydantic models | Steps 6-12 | 1 |
| 17 | Phase 6.2: Output formatter | Step 16 | 1 |
| 18 | Phase 7.1: Update test_real_files | Steps 14, 17 | 1 |
| 19 | Phase 7.2: Unit tests | Steps 16, 17 | 3 |
| 20 | Phase 7.3: Documentation | All | 4 |
