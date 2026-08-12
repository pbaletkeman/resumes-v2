# Agents

This guide documents the seven dedicated pipeline agents. For each agent it covers:

- **Purpose** — what the stage does and where it sits in the chain.
- **Prompt** — the system prompt (`purpose`) and the user prompt sent per call.
- **Input / output schema** — the `inputs` keys it expects and the Pydantic model it returns (all in `client/models.py`).
- **Fallback path** — what happens when the LLM is unavailable, returns malformed JSON, or fails validation.

Every agent follows the same contract: `run(inputs)` → `_try_llm()` (one retry with `strict=True`) → Pydantic validation → deterministic fallback. The LLM call always uses `response_format="json"` and passes `json_schema=model_to_json_schema(<OutputModel>)` for provider Structured Outputs.

```plaintext
JD → [1. JD Parsing] → [2. Resume Parsing] ← Resume
                            ↓
                    [3. Gap Analysis]
                            ↓
                    [4. Resume Rewrite]
                            ↓
                    [5. ATS Compliance]
                            ↓
                    [6. Tone Polishing] → polished_resume
                    [7. Cover Letter] → cover_letter
```

## Common fallback mechanics

An agent falls back only after **both** LLM attempts (normal then `strict=True`) fail. Failure means any of:

- `LLMConnectionError` / `LLMResponseError` / `LLMTimeoutError` (or `NotImplementedError`) raised by the client,
- the response is not valid JSON (see `client/json_utils.parse_json_response`),
- the parsed dict fails Pydantic validation,
- the agent's own post-validation rejects the output (e.g. fabricated companies, dropped certifications).

The per-agent fallback is described in each section below.

---

## 1. JD Parsing Agent

- **File:** `client/agents/jd_parsing.py`
- **Output model:** `JDParsingOutput`

### Purpose

Extracts structured, machine-readable information from a raw job description: role title, company name, seniority level, skills, responsibilities, keywords, and company signals.

### Prompt

**System prompt** (`_SYSTEM_PROMPT`):

> You are the Job Description Parsing Agent. Your task is to extract structured, machine-readable information from a job description. Produce a JSON object with the following fields: role_title, company_name, seniority_level, required_skills, preferred_skills, responsibilities, keywords, industry_terms, company_signals. Follow these rules: Do not add information not present in the job description. Extract the company name exactly as it appears in the job description; output empty string if not present. Normalize skills (e.g., 'communication skills' -> 'communication'). Normalize all skills to their canonical form (e.g., 'JS' -> 'JavaScript', 'React.js' -> 'React', 'AWS' -> 'Amazon Web Services'). Extract all relevant keywords. Output only valid JSON.

**User prompt:** `Extract structured data from this job description:\n\n{jd_text}`

### Input

| Key | Type | Notes |
|-----|------|-------|
| `job_description` | `str` | Raw JD text |
| (pipeline) | — | no other fields are passed |

### Output schema

`JDParsingOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `role_title` | `str` |
| `company_name` | `str` |
| `seniority_level` | `str` |
| `required_skills` | `list[str]` |
| `preferred_skills` | `list[str]` |
| `responsibilities` | `list[str]` |
| `keywords` | `list[str]` |
| `industry_terms` | `list[str]` |
| `company_signals` | `dict[str, str]` |

Post-processing: `_sync_company_name()` keeps `company_name` and `company_signals["company_name"]` in agreement; required/preferred skills are canonicalized via `SkillNormalizer.normalize_list()`.

### Fallback

**Regex fallback via `FormatDetector` (`client/format_detector.py`).** `_regex_fallback()` runs `FormatDetector.parse_job_description()`, then `_extract_company_name()` scans for explicit `Company:` labels, the `<Name> is/are ...` opening pattern, and `at/for/with <Name>` references. Skills normalize via `SkillNormalizer`.

Triggers: empty input, or both LLM attempts failed (connection / parse / validation).

---

## 2. Resume Parsing Agent

- **File:** `client/agents/resume_parsing.py`
- **Class:** `ResumeParsingAgent`

### Purpose

Converts a raw resume into structured JSON: summary, skills, experience entries, projects, certifications, education, and contact details.

### Prompt

**System prompt** (`_SYSTEM_PROMPT`):

> You are the Resume Parsing Agent. Your job is to convert a resume into structured JSON. Extract the following fields: summary, skills (normalize terms), experience (list of roles with: title, company, dates, responsibilities, achievements, metrics), projects, certifications, education, name, phone, email, linkedin, github. Rules: Preserve all quantifiable metrics. Convert bullet points into structured lists. Do not infer missing information. Normalize all skills to their canonical form (e.g., 'JS' -> 'JavaScript', 'React.js' -> 'React', 'AWS' -> 'Amazon Web Services'). Extract the candidate's full name exactly as it appears at the top of the resume; empty string if absent. Extract the candidate's phone number, email address, LinkedIn profile URL, and GitHub profile URL exactly as they appear in the resume; empty string if absent. Output only valid JSON.

**User prompt:** `Extract structured data from this resume:\n\n{resume_text}`

### Input

| Key | Type | Notes |
|-----|------|-------|
| `resume` | `str` | Raw resume text |

### Output schema

`ResumeParsingOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `summary` | `str` |
| `skills` | `list[str]` |
| `experience` | `list[ExperienceEntry]` (title, company, dates, responsibilities, achievements, metrics) |
| `projects` | `list[str]` |
| `certifications` | `list[str]` |
| `education` | `list[str]` |
| `name`, `phone`, `email`, `linkedin`, `github` | `str` |

Post-processing: experience is sorted most-recent-first (`_sort_experience`), skills canonicalized.

### Fallback

**Regex fallback via `FormatDetector`.** `_regex_fallback()` runs `FormatDetector.parse_resume()`, converts flat experience lines into `ExperienceEntry` objects (`_parse_experience_line`), sorts them, and normalizes contact/name fields. `"Unknown"` names are converted to empty strings.

Triggers when: empty input, or both LLM attempts failed.

---

## 3. Gap Analysis Agent

- **File:** `client/agents/gap_analysis.py`
- **Class:** `GapAnalysisAgent`

### Purpose

Compares the parsed job description and parsed resume, then produces a tailoring strategy: missing/weak skills, strong matches, recommended emphasis, keyword strategy, bullet-point improvement plan, and tone guidance.

### Prompt

```
You are the Gap Analysis Agent. Using the parsed job description and parsed resume, produce a Tailoring Strategy with the following fields: missing_skills, weak_skills, strong_matches, recommended_emphasis, keyword_strategy, bullet_point_improvement_plan, tone_guidance. Rules: Base all analysis strictly on provided data. Identify the most impactful resume improvements. Output only valid JSON.
```

**User prompt** includes the serialized JD JSON, serialized resume JSON, and a `NORMALIZED SKILLS` context block (canonical skill forms + deterministic cross-check of missing/matched/extra skills) built by `_canonical_skills_context()`.

### Input

| Key | Type | Notes |
|-----|------|-------|
| `parsed_job_description` | `JDParsingOutput` (or dict) | serialized via `model_dump()` |
| `parsed_resume` | `ResumeParsingOutput` (or dict) | serialized via `model_dump()` |

### Output schema

`GapAnalysisOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `missing_skills` | `list[str]` |
| `weak_skills` | `list[str]` |
| `strong_matches` | `list[str]` |
| `recommended_emphasis` | `list[str]` |
| `keyword_strategy` | `list[str]` |
| `bullet_point_improvement_plan` | `list[str]` |
| `tone_guidance` | `str` |

Post-processing (`_post_process`) canonicalizes skill fields and logs a warning when the deterministic `missing_skills` set differs from the LLM's.

### Fallback

**No regex fallback** — gap analysis requires LLM reasoning. On failure returns an empty `GapAnalysisOutput()` (all empty lists). Triggers when: empty input, or both LLM attempts failed.

---

## 4. Resume Rewrite Agent

- **File:** `client/agents/resume_rewrite.py`
- **Class:** `ResumeRewriteAgent`

### Purpose

Rewrites the parsed resume using the tailoring strategy, producing a clean structured resume with ATS-aligned keywords, quantified achievements (only those in the input), and no fabricated experience.

### Prompt

**System prompt** (`_SYSTEM_PROMPT`):

> You are the Resume Rewrite Agent. Rewrite the resume using the Tailoring Strategy. Output a full resume with: Updated summary, Updated skills section, Rewritten bullet points, Quantified achievements, ATS-aligned keywords, Strong action verbs, Clear concise phrasing. Rules: Maintain factual accuracy. Do not invent employment history. Never add metrics that are not explicitly in the resume. If a metric is missing, rephrase without inventing a number. Produce clean professional formatting. All experiences MUST be listed in proper chronological order (most recent first). No new experiences can be added - use the input resume as the reference for all experience entries. All certifications from the input resume MUST be included. Do not use the extended character set: use straight quotes not curly quotes, use -> not a right arrow. Output only valid JSON.

**User prompt:** `Rewrite the following resume using the provided tailoring strategy. Return a JSON object matching the schema described in the rules.` then `TAILORING STRATEGY:` + `RESUME:` serialized JSON.

### Input

| Input | Type |
|-------|------|
| `parsed_resume` | `ResumeParsingOutput` (or dict) |
| `tailoring_strategy` | `GapAnalysisOutput` (or dict) |
| `parsed_job_description` | optional; used by the fallback tailor |

### Output schema

`RewriteOutput` (`client/models.py`): `summary`, `skills`, `experience` (`list[ExperienceEntry]`), `projects`, `certifications`, `education`.

Post-validation (`_try_llm`) rejects/sorts:

- `_validate_experience_count` — the output cannot have **more** experience entries than the input.
- `_validate_certifications` — every input certification must appear in the output.
- `_validate_companies` — every output company must match an input employer (case-insensitive substring, by name).
- `_validate_chronological` + `_ensure_chronological` — experience must be most-recent-first; out-of-order entries are **sorted** rather than rejected.
- `_sanitize_skills` — output skills are dropped unless fuzzy-matched to input skills; if more than half are foreign the output is rejected.

### Fallback

**Deterministic template fallback via `_parsed_to_rewrite()`.** The parsed resume is converted to a `RewriteOutput` with a first-attempt skills order: skills matching the JD `required_skills` (or strategy `keyword_strategy`) move to the front, and up to 5 JD `keywords` not already present are prepended. Other sections pass through unchanged.

Triggers when: empty input, both LLM attempts failed, or an output was rejected by post-validation.

---

## 5. ATS Compliance Agent

- **File:** `client/agents/ats_compliance.py`
- **Class:** `ATSComplianceAgent`

### Purpose

Evaluates the rewritten resume for ATS compatibility: scores it 0–100, lists missing keywords and formatting/clarity issues, applies fixes, and returns the full corrected resume text.

### Prompt

**System prompt** (`_SYSTEM_PROMPT`):

> You are the ATS Compliance Agent. Evaluate the rewritten resume for ATS compatibility. Output a JSON object with: ats_score (0-100), missing_keywords, formatting_issues, clarity_issues, recommended_fixes, auto_fixes_applied, final_resume (the full corrected resume text). Rules: Ensure keyword coverage. Remove ATS-unfriendly elements (tables, images, symbols). Improve clarity and consistency. Verify all certifications from the input resume are present. Verify experiences are in chronological order (most recent first). Do not add any new experiences. Output only valid JSON.

**User prompt:** `Evaluate the following resume for ATS compatibility. Provide an ATS score, identify issues, and return the corrected resume text.\n\nRESUME:\n{resume_json}`

### Input

| Input | Type |
|-------|------|
| `rewritten_resume` | `RewriteOutput` (or dict) |

### Output schema

`ATSComplianceOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `ats_score` | `int` (0–100) |
| `missing_keywords` | `list[str]` |
| `formatting_issues` | `list[str]` |
| `clarity_issues` | `list[str]` |
| `recommended_fixes` | `list[str]` |
| `auto_fixes_applied` | `list[str]` |
| `final_resume` | `str` |

Post-validation: `ats_score` is clamped to 0–100; an empty `final_resume` is backfilled with a plain-text rendering of the input (`_extract_resume_text`).

### Fallback

**`_default_result()`** — returns `ATSComplianceOutput(ats_score=30, ...)` with `formatting_issues=["Unable to evaluate -- LLM unavailable"]` and `final_resume` set from the input text unchanged. The pipeline treats the fallback's `final_resume` as the ATS-optimized resume, so content is preserved unchanged.

Triggers when: empty input, or both LLM attempts failed / rejected.

---

## 6. Tone Polishing Agent

- **File:** `client/agents/tone_polishing.py`
- **Class:** `TonePolishingAgent`

### Purpose

Improves the tone, professionalism, readability, and clarity of the ATS-optimized resume **without changing facts**.

### Prompt

```
You are the Tone Polishing Agent. Improve the tone of the resume while preserving meaning. Apply: Professional tone, Confident phrasing, Clear narrative flow, Role-appropriate voice (technical, managerial, creative). Output the polished resume. Rules: Do not change factual content. Do not add new achievements. Improve readability and cohesion. Output only valid JSON.
```

**User prompt:** `Polish the tone and professionalism of the following resume. Improve readability, confidence, and clarity without changing factual content or adding new achievements.\n\nRESUME:\n{resume_text}`

### Input

| Input | Type |
|-------|------|
| `ats_optimized_resume` | `str` (the `final_resume` text) |

### Output schema

`TonePolishingOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `polished_resume` | `str` |

Post-validation: an empty `polished_resume` is replaced with the input text.

### Fallback

**Input unchanged:** `TonePolishingOutput(polished_resume=<input text>)`. Triggers when: empty input, or both LLM attempts failed / rejected.

---

## 7. Cover Letter Agent

- **File:** `client/agents/cover_letter.py`
- **Class:** `CoverLetterAgent`

### Purpose

Writes a personalized cover letter tailored to the specific company, role, and required skills. Three-part structure (opening naming role + company, middle mapping skills to requirements with quantified achievements, closing with interest in an interview).

### Prompt

**System prompt** (`_SYSTEM_PROMPT`) — abridged:

> You are the Cover Letter Tailoring Agent. Using the job description, parsed resume, and tailoring strategy, write a compelling, personalized cover letter. Output a JSON object with a single key: cover_letter (the full cover letter text). CRITICAL: You MUST tailor the letter to the SPECIFIC company and role. ... Structure the cover letter in three parts: ... Rules: Always use the company name from the job description. Always use the exact role title ... Match your skills to the required_skills ... Do not use skills not found in the resume. Do not use words like current, now, presently, or currently. Only include dates or timeframes if they are explicitly present in the resume. Maintain professional tone. Do not fabricate achievements. Keep length between 450-600 words. No more than 4 paragraphs. Output only valid JSON with the key cover_letter. Do not use any Unicode characters outside the standard ASCII range.

**User prompt** includes the JD JSON (with a pinned `_company_directive` naming the exact target company), serialized resume JSON, candidate contact block, tailoring strategy JSON, and structured instructions mapping required skills to experience.

### Input

| Input | Type |
|-------|------|
| `parsed_job_description` | `JDParsingOutput` (or dict) |
| `parsed_resume` | `ResumeParsingOutput` (or dict) |
| `tailoring_strategy` | `GapAnalysisOutput` (or dict) |

### Output schema

`CoverLetterOutput` (`client/models.py`):

| Field | Type |
|-------|------|
| `cover_letter` | `str` |

Post-validation (`_try_llm`) enforces via pure-string phases but never re-runs the LLM:

- `_validate_role` — the JD role title (or its significant tokens) must appear; otherwise reject.
- `_check_company` — warn (never reject) if the JD company name is absent.
- `_apply_company_name` — replaces placeholder tokens (`[Company Name]` etc.) and, when the letter names a company from the candidate's resume, substitutes the first wrong mention with the JD company.
- `_apply_candidate_name` — replaces `[Your Name]` placeholders with the real candidate name.
- `_check_skills` — advisory: logs when the letter mentions a skill absent from the resume.
- `_validate_length` — rejects only extreme outliers (<200 or >800 words); 200–450 and 600–800 accepted with a warning.
- `_apply_contact_info` — appends the candidate's phone/email/LinkedIn/GitHub line when the letter lacks them.

### Fallback

**Deterministic template fallback via `_build_fallback_cover_letter()`.** Builds a data-driven letter: JD role title + company name, candidate name, 2–3 JD required skills the candidate actually has (fuzzy-matched), an achievement from the most recent experience entry, and a signature line with contact details. Missing data is omitted rather than placeholder-replaced.

Triggers when: empty input, both LLM attempts failed, or the letter was rejected by post-validation.

---

## References

- `client/models.py` — all agent output models and schemas (`JDParsingOutput`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`). See also `docs/models.md`.
- `client/agents/jd_parsing.py`, `resume_parsing.py` — parsing agents with regex fallbacks.
- `client/agents/gap_analysis.py` — LLM-only reasoning; no fallback.
- `client/agents/resume_rewrite.py` — post-validation + deterministic fallback / `_parsed_to_rewrite`.
- `client/agents/ats_compliance.py` — `_default_result` fallback.
- `client/agents/tone_polishing.py` — input-unchanged fallback.
- `client/agents/cover_letter.py` — company/name/contact post-processing + `_build_fallback_cover_letter`.
- `client/format_detector.py` — regex parsing used by agents 1–2.
- `client/skills/normalizer.py` — canonical `SkillNormalizer` used across agents.
- `client/json_utils.py` — `parse_json_response`, `load_json_safe`, `model_to_json_schema`.
- `client/templates/` (Jinja2 templates) and `client/templates/renderer.py` (`ResumeRenderer`) — turn the agent outputs into files.
- `pipeline.py` — `_run_pipeline_core` orchestrates the chain (see `docs/architecture.md`).
- `docs/architecture.md` — system overview + data flow. `scratch/resume-done.md` — completed work.