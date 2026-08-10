# Completed Phases

Completed phases from `simple.md` are moved here, one phase per section, in
order.  Each entry keeps the original phase text and adds a completion record
(what was changed and how it was verified) so the history stays reviewable.

---

## Phase 1 - Foundation: config, logging, errors, LLM clients, JSON utils  ✅ COMPLETED

**Files:** `config/agents.py`, `logging_config.py`, `client/errors.py`, `client/model_client.py`, `client/json_utils.py`, `client/ollama_client.py`, `client/open_ai_client.py`, `client/model_registry.py`

This is the shared "plumbing" layer every other module uses. Simplifying here is high leverage.

**Inspect for:**

- `config/agents.py`: environment-variable reading (provider/model defaults, per-agent overrides such as `COVER_LETTER_AGENT_MODEL`, `OPENAI_API_KEY`). Is every branch reachable and are variable names self-explanatory?
- `logging_config.py`: is `LOG_LEVEL` handling verbose enough to follow? Are the hard-coded logger-level decisions commented?
- `client/errors.py` (20 lines): confirm the 3 exception types plus base clearly document *when* each is raised.
- `client/model_client.py` (54 lines): the `chat()` ABC. The `response_format` / `json_schema` contract text should say *exactly* what providers must implement.
- `client/json_utils.py` (121): `parse_json_response()` (fence stripping + `json.loads`) and `model_to_json_schema()`. These two are the cornerstones every agent uses.
- `client/ollama_client.py` / `client/open_ai_client.py`: timeouts, `response_format`, and any duplicated send/format logic between them. Worth a docstring per method documenting provider-specific behavior.
- `client/model_registry.py` (209): per-agent registry; clarify how fallback `MODEL_PROVIDER`/`MODEL_NAME` interacts with per-agent overrides.

**Simplify toward:**

- Spell out inline one-liners that pack too much (e.g., complex ternaries in config resolution).
- If the two clients duplicate `json.loads` + error handling, route both through one shared "safe JSON decode" helper in `json_utils.py`.
- Rename short/mysterious module-level variables to intent-revealing names.
- Add a short "how agents use this file" comment at the top of `json_utils.py` and `model_client.py`.

**Documentation:** module + class + method docstrings (many exist already - verify each is accurate). Especially document the `response_format="json"` + optional `json_schema=` contract on `ModelClient.chat`.

**Verify:** ruff + pyright + `uv run pytest` (watch `tests/test_model_clients.py`, `tests/test_json_utils.py`).

### Phase 1 Completion record

**Changes made:**

- `client/errors.py`: expanded every exception docstring to state *when* it is raised (connection unreachable, provider error / empty content, timeout). Added a module docstring listing how each provider SDK exception maps onto the shared types and noting agents catch these in `_try_llm()` to fall back deterministically.
- `client/model_client.py`: added a "How agents use this file" module section describing the `chat(...)` contract, and extracted the duplicated prompt builder from the two clients into a shared module-level `build_task_prompt(prompt, output, rules, inputs)` helper. The `chat` docstring contract was already accurate and is unchanged.
- `client/ollama_client.py`: `chat()` now calls the shared `build_task_prompt()`; deleted the private `_build_compact_prompt` duplicate. Fixed a stale docstring that claimed `LLMTimeoutError` fires "within 90 seconds" — the Ollama timeout is `self.timeout` (default 300 s). Tidied the module docstring indentation.
- `client/open_ai_client.py`: `chat()` now calls the shared `build_task_prompt()` (deleting the inline copy of the builder). Extracted the `response_format` construction into a named `_response_format_value(json_schema)` helper that documents the plain-JSON vs Structured-Outputs envelope, so the `chat` body reads as two clear branches.
- `client/json_utils.py`: rewrote the module docstring to be self-contained (removed the stale "see resume-done.md §8.7 / §8.8" archive pointer) and explain how agents use both functions. Renamed `_FENCE_RE` -> `_JSON_FENCE_RE`.
- `client/model_registry.py`: in `get_client_for_agent`, replaced the redundant `self.get(self._agent_clients[agent_name])` with `self.get(name)`; documented that `from_config` consumes the dict produced by `config.agents.get_agent_config()`. Everything else was already well-documented.
- `config/agents.py`: added a module-level `AGENT_NAMES` tuple (kills a duplicated 7-name list), fixed the stale `DEFAULT_PROVIDER` docstring line (the env var is never read; the real default-provider variable is `MODEL_PROVIDER`), extracted intent-named helpers `_effective_provider`, `_effective_model`, `_client_config`, and merged the two per-agent loops into one pass that builds both the `clients` entries and `agents` assignments. `get_model_summary()` reuses `AGENT_NAMES`. Output dict shapes are byte-identical to before.
- `logging_config.py`: expanded the `configure_logging()` docstring to explain the hard-coded per-module levels (client loggers at DEBUG, third-party SDKs suppressed to WARNING) and added inline comments for the formatter and logger sections.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (3 files reformatted; no behavior change)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 485 passed in ~10s
- Manual probes:
  - `build_task_prompt('Do work', ['json'], ['rule 1','rule 2'], ['input a','input b'])` -> `'Task: Do work\nOutput format: json\nRules: rule 1 | rule 2\nInput: input a | input b'` (identical to previous inline output)
  - Empty override run: `get_agent_config()` -> `clients=['default']`, `agents={}`, `default='default'` (identical)
  - Override run with `COVER_LETTER_AGENT_MODEL=gpt-4o` / `_PROVIDER=openai` / `OPENAI_API_KEY=sk-test` -> only `cover_letter_agent_client` created with `{'provider': 'openai', 'model': 'gpt-4o', 'api_key': 'sk-test'}` (identical)
  - `get_model_summary()` -> 7 rows, all agents on `qwen2.5:7b-instruct` / `ollama` by default (identical)

**Commit:** `simplify: phase 1 - foundation plumbing (config/logging/errors/clients/json utils)`

---

## Phase 2 - Pydantic models & coercion  ✅ COMPLETED

**Files:** `client/models.py`

Holds every agent output model plus the coercion validators (`_coerce_str_list`, `_coerce_tone_guidance`, `_coerce_final_resume`, etc.) that forgive LLMs returning dicts where strings/lists are expected.

**Inspect for:**

- Does every model and every field have a description written for a human (what the LLM populates) rather than restating the field name?
- The coercion validators: are they written in clear multi-step logic or terse `dict.get` chains? Are the edge cases (empty dict, `None`, list of dicts) explicit?

**Simplify toward:**

- Break any validator longer than ~25 lines into named helper functions (`_to_str_list`, `_to_str`, `_to_str_list_from_dict_value`).
- Use explicit `if/else` over complex boolean expressions so a reader can trace each fallback.
- Add a short comment at the top of the file explaining the *reason* coercion exists (LLMs produce inconsistent shapes; we forgive at the model boundary).
- Keep `model_dump`/`model_validate` output shapes identical - the pipeline and API depend on them.

**Documentation:** field descriptions on every field of every output model (`JDParsingOutput`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`, and the `Parsed*` format-detector models). Cross-check with `docs/models.md` (consolidated in Phase 19).

**Verify:** ruff + pyright + `uv run pytest` (watch `tests/test_cover_letter_validation.py`, `tests/test_resume_rewrite_validation.py`).

### Phase 2 Completion record

**Changes made:**

- **Module docstring** — rewrote to be self-contained. Added a "Why coercion exists" section explaining that providers are asked for JSON matching the models but do not always comply, so `mode="before"` validators forgive the LLM at the model boundary; helpers are pure/deterministic; `model_dump()` shape is stable and consumed by downstream agents + the web API.
- **Field descriptions** — every field of every model now carries a human-readable `Field(description=...)` explaining *what the LLM populates* (e.g. `ats_score` = "ATS compatibility score from 0 to 100", `company_name` = "Employer name exactly as written in the JD; empty if absent"). Covers `ParsedResume`, `ParsedJobDescription`, `JDParsingOutput`, `ExperienceEntry`, `ResumeParsingOutput`, `GapAnalysisOutput`, `RewriteOutput`, `ATSComplianceOutput`, `TonePolishingOutput`, `CoverLetterOutput`.
- **Killed validator duplication** — `GapAnalysisOutput._coerce_tone_guidance` was a **verbatim copy** of the `_coerce_str` helper (same dict-flatten + list-join + falsy logic). It now delegates to `_coerce_str()`, so the two code paths can never drift.
- **Cleaned the coercion helpers** (`_coerce_str_list`, `_coerce_str`, `_coerce_experience_list`, `_coerce_company_signals`, `_coerce_final_resume`) — replaced scattered `# type: ignore` noise with explicit `cast()` calls (`cast(list[Any], v)`, `cast(dict[str, Any], item)`), named locals (`item_dict`, `entry_data`, `joined`, `lines`), and step-by-step comments. Behavior is byte-for-byte identical (verified by probe below).
- **`ExperienceEntry` list fields** — switched `default_factory=list` to `default_factory=list[ExperienceEntry]` for the two `list[ExperienceEntry]` fields so pyright strict mode infers `list[ExperienceEntry]` instead of `list[Unknown]` (no behavior change; the factory still returns `[]`).
- **Repo-wide helper names preserved** — kept `_coerce_str_list` / `_coerce_str` / `_coerce_tone_guidance` / `_coerce_final_resume` names because AGENTS.md and docs reference them; consolidation happens in Phase 19.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (1 file reformatted; no behavior change)
- `uv run pyright` — 0 errors, 0 warnings (full run, not just `models.py`)
- `uv run pytest` — 485 passed in ~9s
- Manual probes (identical to previous behavior):
  - `JDParsingOutput(company_signals=['growing startup','Series B'])` -> `{'1': 'growing startup', '2': 'Series B'}`
  - `GapAnalysisOutput(tone_guidance={'tone': 'confident'})` -> `'tone: confident'` (delegated `_coerce_str`)
  - `ATSComplianceOutput(final_resume={'summary': 'hi'})` -> pretty-printed JSON string
  - `ResumeParsingOutput(experience=['Led team', 'Built API'])` -> 2 `ExperienceEntry` with `responsibilities=['Led team']`
  - `ResumeParsingOutput(skills=['Python', {'a': 'JS'}])` -> `['Python', 'JS']`
  - `ResumeParsingOutput(email={'work': 'a@b.com'})` -> `'work: a@b.com'`
  - Empty defaults unchanged: `RewriteOutput().summary == ''`, `ATSComplianceOutput().ats_score == 0`

**Commit:** `simplify: phase 2 - pydantic models & coercion (field descriptions + dedupe tone_guidance)`

---

## Phase 3 - Parsing agents & the format detector  ✅ COMPLETED

**Files:** `client/agents/jd_parsing.py`, `client/agents/resume_parsing.py`, `client/format_detector.py`

These three are the "input parsers" shared by the pipeline and the regex fallbacks.

**Inspect for:**

- `jd_parsing.py`: `_extract_company_name` and the three compiled regexes (`_COMPANY_LABEL_RE`, `_COMPANY_FIRST_SENTENCE_RE`, `_COMPANY_AT_RE`) are dense. `_sync_company_name` is a good small pure helper - make sure it has a full docstring.
- `resume_parsing.py`: same structure (LLM attempt -> retry -> regex fallback). Verify the fallback path mirrors JD parsing and both read cleanly.
- `format_detector.py` (756 lines): the largest parser. Many private static helpers (`_extract_name`, `_extract_title`, `_extract_section`, `_extract_list_section`, ...). Check the big parse methods for chained one-liners and the LLM fallback for a duplicated retry loop.

**Simplify toward:**

- Introduce (or document) a shared, named "attempt LLM twice, then fall back" loop so each agent reads the same way. Do not abstract the whole agent - just the loop scaffolding.
- Build regex pattern strings piece by piece with named variables (as `_COMPANY_TOKEN` etc. already do - extend that style to other patterns).
- Break large helpers into small steps with `# 1. ...`, `# 2. ...` comments.
- Rename regex variables to state *what they match* (`_heading_pattern`, `_bullet_item_pattern`).

**Documentation:** every private helper gets `Args:`/`Returns:` docstrings. Add a file-top note explaining "regex first, LLM only if sparse" and *why* (deterministic fallback, offline-safe).

**Verify:** watch `tests/test_format_detector.py`, `tests/test_jd_parsing.py`, `tests/test_agent_jd_parsing.py`, `tests/test_agent_resume_parsing.py`.

### Completion record

**Changes made:**

- **New shared retry loop** `client/agents/_retry.py` — `retry_llm_then_fallback[T]()` implements the "try LLM once, retry once with `strict=True`, then fall back to regex" scaffolding that the two parsing agents used to inline identically. The agents keep their own `_try_llm`/`_regex_fallback`; only the loop was extracted (per the "don't abstract the whole agent" rule).
- `jd_parsing.py` + `resume_parsing.py` — `run()` now calls `retry_llm_then_fallback` instead of the duplicated `for attempt in range(2)` blocks; module docstrings reference `client.agents._retry`. Expanded `_clean_company_name` and `_extract_start_year` from one-liners to full `Args:`/`Returns:` docstrings.
- `format_detector.py`:
  - **File-top rationale** added: "Why regex first, LLM only if sparse" (deterministic, dependency-free, offline-safe; the LLM is never required for a successful parse).
  - **Hoisted `_section_pattern`** out of the class to module level and prefixed the six section regex-union expressions with named constants (`_SUMMARY_SECTION_PATTERN`, `_SKILLS_SECTION_PATTERN`, `_EXPERIENCE_SECTION_PATTERN`, `_PROJECTS_SECTION_PATTERN`, `_EDUCATION_SECTION_PATTERN`, `_CERTIFICATIONS_SECTION_PATTERN`) so `parse_resume` reads as "extract the Summary section" instead of a regex-union.
  - **Named the shared line patterns** `_HEADING_PATTERN` (MULTILINE, reused by `_extract_section` and `_extract_bullet_points`), `_BULLET_ITEM_PATTERN` (replaces the inline `re.findall` in `_extract_list_section`), and `_BULLET_MARKER_PATTERN` (replaces the inline `re.sub` in `_extract_bullet_points`).
  - **Deduplicated the "count populated fields" expression** (appeared verbatim in both `parse_resume` and `parse_job_description`) into `_count_populated()`; both parse methods now follow numbered steps (`# 1. Regex pass`, `# 2. Sparse check`, `# 3. Validate`) instead of one chained block.
  - Full `Args:`/`Returns:` docstrings on `_is_insufficient_resume`, `_is_insufficient_jd`, and `_extract_projects`; stale "Phase 2.1" banner comment replaced with "Extended extraction".
- No behavior changes — regex patterns and control flow are identical; only naming/structure moved.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (2 files reformatted; no behavior change)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 485 passed in ~7s, including `tests/test_format_detector.py` (46), `tests/test_jd_parsing.py` (19), `tests/test_agent_jd_parsing.py` (7), `tests/test_agent_resume_parsing.py` (9)
- Regex-path spot-checks unchanged: `_extract_company_name` still extracts "3Pillar"/"Acme Corporation"; `_sync_company_name` still agrees; `FormatDetector._extract_section/list_section/bullet_points` output identical (covered by the 46 format-detector tests).

**Commit:** `simplify: phase 3 - parsing agents & format detector (shared retry loop, named section patterns)`
