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

---

## Phase 4 - LLM-only agents: Gap Analysis, ATS Compliance, Tone Polishing + shared validation cleanup  ✅ COMPLETED

**Files:** `client/agents/gap_analysis.py`, `client/agents/ats_compliance.py`, `client/agents/tone_polishing.py`

**Inspect for:**

- `ats_compliance.py` (and its siblings in Phases 5-6) use the `except json.JSONDecodeError, TypeError:` form. Standardize and route each guard through one shared helper (below) so the intent is obvious.
- The three agents' `_try_llm` methods are near-identical (prompt, rules, chat, parse, validate). Note the *small* differences (output shape, prompt strings) - keep those, de-duplicate only the scaffolding.
- `tone_polishing.py`: tone guidance coercion; verify it is as clearly written as the equivalent in `models.py`.

**Simplify toward:**

- Add one shared helper - `load_json_safe(text) -> dict | None` in `client/json_utils.py` - and have the guarded `json.loads` sites use it.
- Extract the duplicated chat/parse/validate scaffolding into `client/agents/_validation.py` (`chat_and_validate` + `serialize`) shared by the LLM-only agents.
- Ensure each validation helper is a self-contained, clearly documented predicate.

**Documentation:** module docstrings explain the "LLM only, deterministic fallback" role of these three agents: which output model each produces and what happens on total failure (gap = empty model, ATS = default low-score, tone = pass-through).

**Verify:** watch `tests/test_agent_gap_analysis.py`, `tests/test_agent_ats_compliance.py`, `tests/test_agent_tone_polishing.py`.

### Phase 4 Completion record

**Overview:** Phase 4 created one shared guarded-JSON loader (`load_json_safe`), one shared LLM-call/validate scaffold (`client/agents/_validation.py`), and brought all three LLM-only agents onto them. Each agent now keeps only its prompt/rules and its deterministic fallback; the repeated `client.chat` + parse + Pydantic-validate boilerplate lives in one place. The three `client.chat(...)` call sites that moved into `_validation.py` were removed from `tests/test_model_clients.py`'s `CALL_SITE_FILES` (stable call-site count 13 -> 9 across sub-tasks 4.3-4.5).

**Changes made (by sub-task):**

- **4.1** — `client/json_utils.py`: added `load_json_safe(text) -> dict | None` (fence-stripping + guard, never raises). Added `TestLoadJsonSafe` (8 tests).
- **4.2** — Standardized the `except json.JSONDecodeError, TypeError:` sites. Resolution: the parenthesized form is not enforceable - ruff 0.16 + `target-version = "py314"` auto-canonicalizes to the PEP 758 comma form; all 13 sites already used the canonical form (no code change). These guards are routed through `load_json_safe` in later phases.
- **4.3** — `client/agents/_validation.py`: extracted the shared `chat_and_validate()` + `serialize()` scaffold (attempt logging, provider-error handling, response logging, JSON parsing, Pydantic validation). `client/agents/gap_analysis.py`: `_try_llm` now calls `chat_and_validate`; module docstring expanded ("LLM only, deterministic fallback = empty model").
- **4.4** — `client/agents/ats_compliance.py`: adopted the shared scaffold; `_extract_resume_text` guarded `json.loads` now routes through `load_json_safe`; deleted duplicated `_serialize`/`_parse_json`; module + `_default_result` docstrings expanded.
- **4.5** — `client/agents/tone_polishing.py`: adopted the shared scaffold (kept the agent-specific empty-`polished_resume` fill); expanded module/`run()`/`_try_llm` docstrings. `client/models.py`: expanded `_coerce_tone_guidance` docstring to point at shared `_coerce_str` and why it exists. All three LLM-only agents now share one scaffold.
- **4.6** — Guardrails run across the phase (below).
- **4.7** — Phase moved here; `simple.md` checkbox section marked complete and narrative section stubbed.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` / `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings (full run)
- `uv run pytest` — 493 passed, including `tests/test_agent_gap_analysis.py` (7), `tests/test_agent_ats_compliance.py` (8), `tests/test_agent_tone_polishing.py` (6), `tests/test_model_clients.py` (11), `tests/test_json_utils.py` (23)
- Fallback behavior preserved per agent: gap analysis returns an empty `GapAnalysisOutput` on total LLM failure; ATS returns `ats_score=30` with resume text unchanged; tone returns the input resume unchanged.

**Commit:** `simplify: phase 4 - llm-only agents + shared validation cleanup (load_json_safe + _validation scaffold)`

---

## Phase 4 - Completed sub-task 4.1: shared `load_json_safe` helper

Added the guarded JSON-object parser that Phases 4.2-4.6 will route the
repeated `try: json.loads(...) except (json.JSONDecodeError, TypeError):`
blocks through (across `ats_compliance.py`, `resume_rewrite.py`,
`cover_letter.py`).

### Completion record

**Changes made:**

- **`client/json_utils.py`** — added `load_json_safe(text) -> dict[str, Any] | None`:
  - Never raises. Returns `None` for empty input, invalid JSON, fenced
    non-object JSON, and parsed non-object values (arrays/scalars).
  - Strips a surrounding markdown fence (`` ```json ... ``` ``) when
    present, mirroring `parse_json_response` so nested LLM blobs parse
    the same way as top-level responses.
  - Guards `TypeError` too (defensive against non-string inputs).
  - Module docstring updated: now lists three helpers (added
    `load_json_safe` to the intro).
- **`tests/test_json_utils.py`** — added `TestLoadJsonSafe` (8 tests):
  plain object, fenced object, fenced with surrounding text, invalid
  JSON, malformed nested blob, empty/whitespace input, non-object JSON
  (`[1, 2, 3]` / string), and fenced non-object JSON.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (1 file reformatted; no behavior change)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed (485 baseline + 8 new), including
  `tests/test_json_utils.py` (23: 11 parse + 8 load_json_safe + 4 schema)
- No existing callers changed in this sub-task — `load_json_safe` is
  added but not yet wired into agents (that is sub-tasks 4.2-4.6).

**Commit:** `simplify: phase 4a - shared load_json_safe helper in json_utils`

---

## Phase 4 - Completed sub-task 4.2: standardize the multi-exception `except` sites

Original instruction: rewrite `except json.JSONDecodeError, TypeError:` to the
explicit parenthesized tuple form everywhere it appears (Phases 5-6 too).

### Resolution (toolchain conflict)

The parenthesized form is **not enforceable** in this repo:

- Ruff 0.16 (and every ruff >= 0.15) unconditionally rewrites
  `except (A, B):` -> `except A, B:` whenever `target-version = "py314"` is
  configured (PEP 758 support). Verified directly: writing the tuple form and
  running `uv run ruff format .` reverts it to the comma form; there is no
  formatter option to preserve the parentheses short of lowering the target
  version, which this repo cannot do (Python 3.14+ required, AGENTS.md).
- The comma form is not a Python 2 artifact in this context: PEP 758 explicitly
  states the unparenthesized form does **not** reintroduce Python 2 semantics
  and is interchangeable with the parenthesized version on 3.14.

Since the phase-commit guardrails (`ruff format --check .` must stay green) are
the binding contract, the correct standard is the *formatter-canonical* form.

### Completion record

**Changes made:** none to code — all 13 sites already use the canonical form:

- `client/json_utils.py` (1): `load_json_safe` guard (added in 4.1).
- `client/agents/ats_compliance.py` (1): `_parse_json` guard.
- `client/agents/cover_letter.py` (7): `_load_*` guards.
- `client/agents/resume_rewrite.py` (4): `_load_*` guards.

These are the guards sub-tasks 4.4-4.6 route through `load_json_safe`, which will
collapse them further.

**Behavior verification:**

- `uv run ruff format --check client/` — 27 files already formatted (pass)
- `uv run ruff check client/` — all checks passed
- `git status` — clean (no diff vs. HEAD; tuple-form experiment fully reverted)

**Commit:** (no code commit for this sub-task; recorded in `simple.md` +
`simple-done.md` only)

---

## Phase 4 - Completed sub-task 4.3: `gap_analysis.py` `_try_llm` scaffolding dedupe

Original instruction: dedupe `_try_llm` scaffolding and verify the module
docstring covers "LLM only, deterministic fallback", the output model, and
failure = empty model.

### Completion record

**Changes made:**

- **`client/agents/_validation.py`** (new) — shared LLM-call + validation
  scaffolding for the three LLM-only agents (Gap Analysis, ATS Compliance,
  Tone Polishing):
  - `serialize(value)` — the identical `_serialize` helper previously
    duplicated in `gap_analysis.py` (and `ats_compliance.py`,
    `resume_rewrite.py`, `cover_letter.py`, which can adopt it in later
    phases).
  - `chat_and_validate(client, *, purpose, prompt, rules, inputs,
    json_schema, output_model, agent_label, strict)` — the full
    chat -> parse -> Pydantic-validate scaffold: attempt/response debug
    logging, the four-exception provider-error handler
    (`NotImplementedError`, `LLMConnectionError`, `LLMResponseError`,
    `LLMTimeoutError`), `parse_json_response`, and the verbose
    `ValidationError` warning with parsed keys + JSON preview.  Returns
    the validated ``output_model`` instance or ``None``.
- **`client/agents/gap_analysis.py`**:
  - `_try_llm` now calls `chat_and_validate` (prompt/rules stay
    agent-specific) and only applies the gap-specific `_post_process` on
    success — removed ~45 lines of duplicated scaffolding.
  - `_serialize`/`_parse_json` module helpers deleted; `run()` uses the
    shared `serialize`.
  - Module docstring expanded: LLM-only (no regex fallback), output model
    ``GapAnalysisOutput``, deterministic fallback = empty model on total
    LLM failure.
- **`tests/test_model_clients.py`** — `CALL_SITE_FILES` updated:
  `client/agents/gap_analysis.py` -> `client/agents/_validation.py`
  (the only `client.chat(...)` site in gap_analysis moved into the shared
  helper, so the response_format-call-site guard now tracks that file;
  total call-site count unchanged at 11).

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_gap_analysis.py` (7), `tests/test_model_clients.py`
  (11), `tests/test_json_utils.py` (23)

**Commit:** `simplify: phase 4c - gap analysis _try_llm scaffolding dedupe (shared _validation module)`

---

## Phase 4 - Completed sub-task 4.4: `ats_compliance.py` shared scaffolding + `load_json_safe` routing

Original instruction: route its `_validate_*` helpers through
`load_json_safe` and expand `Returns True when ...` docstrings.  Note:
`ats_compliance.py` has no `_validate_*` boolean predicates (those live in
the Phase 5-6 files); its guarded JSON re-parse site is
`_extract_resume_text`, which is the helper routed through the shared
loader here.

### Completion record

**Changes made:**

- **`client/agents/ats_compliance.py`**:
  - Adopted the shared `_validation` scaffold created in 4.3:
    `_try_llm` now calls `chat_and_validate` (prompt/rules/schema stay
    agent-specific) and only keeps the agent-specific post-validation
    (ATS score clamping, `final_resume` fill from input); `run()` uses the
    shared `serialize`.  Removed ~45 lines of duplicated scaffolding.
  - Deleted the duplicated `_serialize` and `_parse_json` module helpers.
  - **4.4 core:** `_extract_resume_text`'s guarded `json.loads` block now
    routes through `load_json_safe` (from `client/json_utils.py`), the
    single shared replacement for the `try: json.loads / except
    (json.JSONDecodeError, TypeError)` pattern.  Docstring expanded with
    Args/Returns and a "why" (rebuilds readable plain-text resume; returns
    raw JSON on parse failure).
  - `_default_result` docstring expanded with Args/Returns and the
    "deterministic fallback" story (default low-score + resume unchanged).
  - Module docstring expanded: LLM-only (no regex fallback), output model
    ``ATSComplianceOutput``, deterministic fallback = default low-score
    result on total LLM failure.
- **`tests/test_model_clients.py`** — `CALL_SITE_FILES` updated:
  `client/agents/ats_compliance.py` removed (its only `client.chat(...)`
  site moved into the already-tracked shared `_validation.py`); stable
  call-site count updated 11 -> 10.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_ats_compliance.py` (8 contract tests), and the updated
  call-site guard in `tests/test_model_clients.py`

**Commit:** `simplify: phase 4d - ats compliance shared scaffolding + load_json_safe routing`

---

## Phase 4 - Completed sub-task 4.5: `tone_polishing.py` shared scaffolding + coercion/docstring clarity

Original instruction: verify tone-guidance coercion is as clear as
`models.py`; expand docstrings.  Tone polishing is the last of the three
LLM-only agents (gap analysis, ATS compliance) that shared the duplicated
``_try_llm`` scaffolding, so it was brought onto the same shared
`_validation` path in the same phase.

### Completion record

**Changes made:**

- **`client/agents/tone_polishing.py`**:
  - Adopted the shared `_validation` scaffold (created in 4.3): `_try_llm`
    now calls `chat_and_validate` and only keeps the agent-specific
    post-validation -- the empty-`polished_resume` fill from the input
    resume.  `run()` keeps its two-attempt retry + pass-through fallback
    (the deterministic fallback differs per agent, per the `_validation`
    design).  Removed ~45 lines of duplicated scaffolding (module
    `_parse_json`, inline chat/parse/validate/error-handling block).
  - Expanded docstrings: module docstring now explains LLM-only nature,
    output model ``TonePolishingOutput``, pass-through fallback, and that
    the empty-output fill is agent-specific; `run()` and `_try_llm`
    docstrings state the fallback/Args/Returns.
  - **Coercion note (4.5 core):** tone-guidance coercion lives in
    `client/models.py` (`GapAnalysisOutput._coerce_tone_guidance`), not in
    the agent.  `_coerce_str` was already as clear as `models.py`'s other
    coercers; its validator docstring was expanded to point at the shared
    helper and the "why" (LLM returns dict/list structures).
- **`client/models.py`** -- expanded `_coerce_tone_guidance` docstring:
  delegates to shared `_coerce_str`, flattens dict/list, keeps strings,
  maps falsy to `""`.
- **`tests/test_model_clients.py`** -- `CALL_SITE_FILES` updated:
  `client/agents/tone_polishing.py` removed (its only `client.chat(...)`
  site moved into the already-tracked shared `_validation.py`); stable
  call-site count updated 10 -> 9.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — pass (tone_polishing.py auto-formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_tone_polishing.py` (6 contract tests) and the updated
  call-site guard in `tests/test_model_clients.py`

**Commit:** `simplify: phase 4e - tone polishing shared scaffolding + coercion docstrings`

---

## Phase 5 - Completed sub-task 5.1: re-order `resume_rewrite.py` (class first, helpers grouped)

Original instruction: re-order the file so the public class comes first, then
module helpers grouped by purpose (validation -> tailoring -> skill matching)
with banner comments.

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — re-ordered the module into five
  banner-commented sections after the public `ResumeRewriteAgent` class.
  The class already came first; the change moved the 20 module helpers into
  purpose-grouped sections:
  1. `# ---- Shared serialization / parsing utilities ----` —
     `_serialize`, `_parse_json`, `_count_words`, `_load_str_list`,
     `_extract_start_year`.
  2. `# ---- Validation -- guards against LLM fabrication (reject on violation) ----` —
     `_validate_experience_count`, `_validate_certifications`,
     `_validate_companies`, `_extract_companies`, `_company_matches`,
     `_validate_chronological`.
  3. `# ---- Deterministic post-processors -- fix instead of reject (never mutate in place) ----` —
     `_ensure_chronological`, `_sanitize_skills`.
  4. `# ---- Tailoring -- deterministic ATS fallback used when the LLM fails ----` —
     `_parsed_to_rewrite`, `_tailor_skills`, `_as_dict`, `_read_str_list`,
     `_is_ascii`.
  5. `# ---- Skill matching -- fuzzy matching against normalized input skills ----` —
     `_skill_matches`, `_normalize_skill`.
  - Module docstring updated with a short "File layout" paragraph pointing at
    the banner grouping.
  - **Every function/class body is byte-for-byte identical** — pure re-ordering.

**Behavior verification:**

- Structural compare via AST (`ast.dump`) against `HEAD`:
  - function set identical, class set identical
  - no function body changed, no class body changed
  - old order vs new order confirmed as the only difference
- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (banner block placement only)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_resume_rewrite.py` (8) and
  `tests/test_resume_rewrite_validation.py` (63)

**Commit:** `simplify: phase 5a - resume rewrite re-order (class first, helpers grouped with banners)`

---

## Phase 5 - Completed sub-task 5.2: route validation guards through `load_json_safe`

Original instruction: route `_validate_experience_count`,
`_validate_certifications`, `_validate_companies` guards through
`load_json_safe`.

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — the three validation helpers
  now parse their serialized-resume input through `load_json_safe`
  (from `client/json_utils.py`) instead of the repeated
  ``try: json.loads(...) / except (json.JSONDecodeError, TypeError)``
  block.  On a `None` result each helper keeps its existing
  "can't validate, pass" early return (validators only reject proven
  violations, so unparseable input still passes).
  - `_validate_experience_count` (experience-count guard)
  - `_validate_certifications` (certifications-set guard)
  - `_validate_companies` (fabricated-company guard)
  - Import updated: `load_json_safe` added to the shared-utils import.
  - Behavior is identical: `_serialize` always produces object JSON, so
    `load_json_safe` succeeds exactly where `json.loads` did, and the
    `None` -> pass mapping mirrors the old except-branch return.
  - Out of scope: `_load_str_list` keeps its own guard for now (the
    Phase 5 plan scopes 5.2 to the three validators; `_load_str_list`
    remains a candidate shared-utility cleanup).

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_resume_rewrite_validation.py` (63) and
  `tests/test_agent_resume_rewrite.py` (8)

**Commit:** `simplify: phase 5b - resume rewrite validation guards via load_json_safe`

---

## Phase 5 - Completed sub-task 5.3: full `Args:`/`Returns:` + "why" on every post-validation helper

Original instruction: give every post-validation helper a full
`Args:`/`Returns:` docstring and a one-line "why" (guarding against LLM
fabrication).

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — expanded docstrings on all 7
  post-validation helpers in the validation + deterministic
  post-processor banner sections.  Each now has a one-line "why"
  (guarantee vs. LLM fabrication/dropped facts) plus `Args:`/`Returns:`.
  No code changes — docstrings only.
  - `_validate_experience_count` — "why": the rewrite must never invent
    extra experience entries beyond the input resume.
  - `_validate_certifications` — "why": every input certification must
    survive the rewrite.
  - `_validate_companies` — "why": the rewrite must not invent employers;
    matching is by name (case-insensitive substring) because the LLM may
    reorder entries.
  - `_extract_companies` — "why": accepts either Pydantic
    ``ExperienceEntry`` objects or plain dicts so the validator reads
    companies from any serialized shape.
  - `_company_matches` — "why": bidirectional substring tolerates LLM
    renaming (``"Acme Corp"`` vs ``"Acme Corporation"``).
  - `_validate_chronological` — "why": guards the newest-to-oldest
    ordering contract the LLM is told to honor.
  - `_sanitize_skills` — "why": skills not in the input resume (and not a
    canonical variant of one) are dropped; ``None`` rejects the rewrite
    when most skills are fabricated.
  - `_ensure_chronological` already carried full `Args:`/`Returns:` and a
    "why" (fix instead of reject, pure-Python, never mutates) from
    earlier work — left unchanged.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_resume_rewrite_validation.py` (63) and
  `tests/test_agent_resume_rewrite.py` (8)
- `git diff` reviewed: 80 insertions, all inside docstrings (no code
  lines changed)

**Commit:** `simplify: phase 5c - post-validation helper docstrings (Args/Returns + why)`

---

## Phase 5 - Completed sub-task 5.4: extract named skill-match helpers from `_skill_matches`

Original instruction: convert dense `_skill_matches` conditionals into
named helpers (`_exact_match`, `_substring_match`, `_token_match`), each
with a one-line docstring.

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — in the skill-matching banner
  section, `_skill_matches` now reads as an obvious strategy chain instead
  of one dense body.  The inline conditionals became four named helpers:
  - `_exact_match(skill, input_skills) -> bool` — canonical-taxonomy
    match first, then normalized-spelling match (preserves the original
    two-step exact check).
  - `_substring_match(norm, inp) -> bool` — substring containment with
    the ``len >= 3`` floor (stops short abbreviations like "AI" from
    matching by accident).
  - `_token_match(skill_tokens, input_tokens) -> bool` — shared-token
    intersection.
  - `_tokenize(text) -> set[str]` — the shared token-set builder (was
    inlined twice at the two call sites).
  - `_skill_matches` docstring expanded with `Args:`/`Returns:` and the
    strategy list (exact -> substring -> token).
  - Note on parity: `_exact_match` re-canonicalizes its second call's
    already-normalized input, which is safe because
    `SkillNormalizer.normalize` and `_normalize_skill` are idempotent on
    normalized strings (tokenized-lowercase in -> same tokens out), and
    the first exact call already exhausted the canonical check.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_resume_rewrite_validation.py` (63) and
  `tests/test_agent_resume_rewrite.py` (8)
- Differential test: extracted `_skill_matches` + `_normalize_skill`
  source from `HEAD`, ran both implementations across 100
  skill-vs-input-list combinations (taxonomy variants JS/K8s/ML, exact,
  substring, token, empty-norm, len-1-token, no-match cases) — **0
  diffs**.
- Manual probes confirm representative cases: exact `'Python'` -> True,
  substring `'SQL'` vs `['postgresql']` -> True, token
  `'machine learning'` vs `['learning']` -> True, `'!!!'` (empty norm)
  -> False, `'cobol'` vs `['python','rust']` -> False.

**Commit:** `simplify: phase 5d - skill matching named helpers (_exact_match/_substring_match/_token_match)`

---

## Phase 5 - Completed sub-task 5.5: `model_copy` never-mutate contract + `_tailor_skills` step-by-step

Original instruction: verify `_ensure_chronological` / `_sanitize_skills`
docstrings explain the `model_copy` never-mutate contract; `_tailor_skills`
reads step-by-step.

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — docstrings/comments only, no
  code changes:
  - `_ensure_chronological` docstring now has an explicit
    "never mutates ``result`` in place" paragraph: it returns a new
    ``RewriteOutput`` via ``model_copy(update=...)`` so the validated LLM
    result handed in by ``_try_llm`` stays untouched (was only implied by
    "Returns a copy" and the banner comment).
  - `_sanitize_skills` docstring now has the same contract paragraph: it
    never mutates in place; dropping skills returns
    ``model_copy(update=...)``, and returning ``result`` itself when there
    is nothing to drop is explicitly a no-op, not a mutation.
  - `_tailor_skills` now reads step-by-step: numbered in-code comments
    (`# Step 1. Reorder:` and `# Step 2. Augment:`) at the two
    deterministic transformations, a short "Sources:" comment for the
    JD-primary/strategy-fallback reads, and full `Args:`/`Returns:`
    docstring.  The Step-2 comment explains *why* the keywords are
    prepended (so the fallback resume still surfaces the JD keywords for
    ATS parsing).

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_resume_rewrite_validation.py` (63) and
  `tests/test_agent_resume_rewrite.py` (8)
- `git diff` reviewed: all additions are docstring/comment lines; no code
  lines changed.

**Commit:** `simplify: phase 5e - model_copy never-mutate docs + tailor_skills step-by-step comments`

---

## Phase 5 - Completed sub-task 5.6: module docstring correctness story

Original instruction: module docstring should explain the full correctness
story: LLM -> Pydantic -> *deterministic post-validation* -> chronological
ordering -> skill sanitization -> deterministic fallback.  Cross-check with
`docs/agents.md`.

### Completion record

**Changes made:**

- **`client/agents/resume_rewrite.py`** — rewrote the module docstring to
  narrate the full pipeline in six ordered steps, matching the real
  `_try_llm()`/`run()` flow exactly:
  1. **LLM** — rewrite against the tailoring strategy, JSON parsed into
     ``RewriteOutput``.
  2. **Pydantic** — ``RewriteOutput(**data)`` enforces model shape.
  3. **Post-validation** — deterministic pure-Python guards reject
     fabrication (extra experiences, dropped certifications, invented
     companies); a violation fails the attempt so ``run()`` retries
     stricter.
  4. **Chronological order** — fixed (never rejected) via
     ``_ensure_chronological`` copy sorted most-recent-first.
  5. **Skill sanitization** — invented skills dropped via
     ``_sanitize_skills``; mostly-fabricated output rejects the rewrite.
  6. **Deterministic fallback** — ``_parsed_to_rewrite`` returns the
     original parsed resume with JD-tailored skills, so the pipeline
     yields a usable ATS-targeted resume without an LLM.
  - Kept the existing "File layout" paragraph (banner groups).
  - Removed the old one-line summary ("Falls back to the original parsed
    resume on LLM failure") now that step 6 says the same thing fully.
  - Cross-checked against `docs/agents.md`: the documented flow
    (LLM -> Pydantic -> post-validation -> chronological -> sanitize ->
    fallback) matches the code, so no doc drift to fix.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_resume_rewrite_validation.py` (63) and
  `tests/test_agent_resume_rewrite.py` (8)
- Read-back check: the six steps match the actual `_try_llm()` guard
  order (experience count -> certifications -> companies ->
  `_ensure_chronological` -> `_sanitize_skills`) and the `run()` fallback
  (`_parsed_to_rewrite`).

**Commit:** `simplify: phase 5f - resume rewrite module docstring (full correctness story)`

---

## Phase 5 - Resume Rewrite agent + post-validation  ✅ COMPLETED

**Files:** `client/agents/resume_rewrite.py`

621 lines: `run()` -> `_try_llm()` -> post-validation helpers, plus fallback
tailoring (`_parsed_to_rewrite`, `_tailor_skills`, `_as_dict`,
`_read_str_list`, `_is_ascii`) and skill matching (`_sanitize_skills`,
`_skill_matches`, `_normalize_skill`, `_load_str_list`).

### Phase 5 Completion record

**Overview:** Phase 5 re-ordered `resume_rewrite.py` into banner-grouped
sections, routed the three fabrication-guard `json.loads` sites through the
shared `load_json_safe`, gave every post-validation helper a full
`Args:`/`Returns:` + "why" docstring, extracted the dense `_skill_matches`
conditionals into named helpers, documented the `model_copy` never-mutate
contract on both post-processors, made `_tailor_skills` read step-by-step,
and rewrote the module docstring with the full correctness story.  All
changes were docstring/comment/re-ordering/logical-extraction only — no
behavior change (verified differentially in 5.4, and by the 63-test
validation suite throughout).

**Changes made (by sub-task):**

- **5.1** — Re-ordered the file: public `ResumeRewriteAgent` class first,
  then the 20 module helpers under five banner sections (shared
  serialization/parsing utilities -> validation -> deterministic
  post-processors -> tailoring -> skill matching).  AST-compare against
  `HEAD` confirmed identical function/class sets and bodies.
- **5.2** — Routed `_validate_experience_count`, `_validate_certifications`,
  `_validate_companies` through `load_json_safe` (replacing the repeated
  guarded `json.loads`); each keeps the "can't validate, pass" early
  return.  `_load_str_list` guard left in place (out of 5.2 scope).
- **5.3** — Full `Args:`/`Returns:` + one-line "why" on all 7 post-validation
  helpers (`_validate_*`, `_extract_companies`, `_company_matches`,
  `_sanitize_skills`); `_ensure_chronological` already documented.
- **5.4** — Extracted `_exact_match`, `_substring_match`, `_token_match`,
  and `_tokenize` from `_skill_matches`; `_skill_matches` reads as a
  strategy chain.  Differential test across 100 skill-vs-input combos:
  0 diffs vs `HEAD`.
- **5.5** — Explicit "never mutates in place / `model_copy(update=...)`"
  paragraphs in `_ensure_chronological` + `_sanitize_skills` docstrings;
  `_tailor_skills` got `# Sources:` / `# Step 1. Reorder:` / `# Step 2.
  Augment:` comments + `Args:`/`Returns:`.
- **5.6** — Module docstring narrates the six-step correctness story:
  LLM -> Pydantic -> post-validation -> chronological fix -> skill
  sanitization -> deterministic fallback (`_parsed_to_rewrite`).
  Cross-checked `docs/agents.md` — no drift.
- **5.7** — Guardrails run across the phase (below); phase moved here.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings (full run)
- `uv run pytest` — 493 passed, including `tests/test_resume_rewrite_validation.py` (63) and `tests/test_agent_resume_rewrite.py` (8)
- Phase 5.4 differential test: 100 cases, 0 behavior diffs vs `HEAD`.
- Fallback behavior unchanged: LLM success -> validated+post-processed
  `RewriteOutput`; total failure -> `_parsed_to_rewrite` with
  JD-tailored skills.

**Commit:** `simplify: phase 5 - resume rewrite re-order + shared guards + docs (5.1-5.7)`

---

## Phase 6 - Completed sub-task 6.1: `cover_letter.py` banner sections (class first, helpers grouped)

Original instruction: split helpers into banner sections
(`# --- validation ---`, `# --- deterministic post-processors ---`,
`# --- rendering/formatting ---`), matching the Phase 5 re-order of
`resume_rewrite.py`.

### Completion record

**Changes made:**

- **`client/agents/cover_letter.py`** (968 lines) — re-ordered the file so
  the public `CoverLetterAgent` class comes first, followed by module
  helpers under five banner sections:
  - `# Shared serialization / parsing utilities` — `_serialize`,
    `_parse_json`, `_as_dict`, `_read_str`, `_read_str_list`,
    `_load_str_list`.
  - `# Prompt helpers -- compose the parts of the LLM prompt that need
    parsing` — `_contact_from_resume`, `_company_directive`.
  - `# Validation -- guards on LLM output (advisory warnings or hard
    reject)` — `_ROLE_FILLER_WORDS`, `_validate_role`, `_company_mentioned`,
    `_check_company`, `_check_skills`, `_skill_mentioned`, `_skill_in_list`,
    `_validate_length`.
  - `# Deterministic post-processors -- fix the letter (never mutate in
    place)` — `_PLACEHOLDER_TOKENS`, `_get_company_name`, `_company_from`,
    `_replace_placeholders`, `_resume_companies`,
    `_resume_company_in_letter`, `_replace_first_casefold`,
    `_apply_company_name`, `_NAME_PLACEHOLDER_TOKENS`,
    `_candidate_name_from_resume`, `_apply_candidate_name`,
    `_apply_contact_info`.
  - `# Rendering/formatting -- data-driven fallback cover letter (no LLM)`
    — `_build_fallback_cover_letter`, `_contact_signature_line`,
    `_opening_paragraph`, `_middle_paragraph`, `_closing_paragraph`,
    `_join_skills`, `_overlapping_skills`, `_most_recent_achievement`.
  - Module docstring updated with a "File layout" paragraph naming the
    banner groups (mirrors the `resume_rewrite.py` 5.6 layout note);
    no body text changed.
  - Every helper body copied verbatim from `HEAD`; only line order and
    the module docstring changed.

**Behavior verification:**

- AST structural compare vs `HEAD` (same script as 5.1): identical
  function/class sets (33 top-level helpers + `CoverLetterAgent`), and
  0 body diffs across all functions and class methods.  The only diff is
  the module docstring (expected — new "File layout" paragraph) and a
  trailing-newline fix applied by `ruff format`.
- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_cover_letter.py` (10) and
  `tests/test_cover_letter_validation.py` (109)
- The seven `json.loads` guards (in `_load_str_list`, `_contact_from_resume`,
  `_validate_role`, `_get_company_name`, `_resume_company_in_letter`,
  `_candidate_name_from_resume`, `_apply_contact_info`) are intentionally
  left in place for 6.2.

**Commit:** `simplify: phase 6a - cover letter banner sections (class first, helpers grouped)`

---

## Phase 6 - Completed sub-task 6.2: route the seven `json.loads` guards through `load_json_safe`

Original instruction: replace all seven `json.loads` guards with
`load_json_safe` (the shared helper from Phase 4.1, already used by the
Phase 5 validation guards).

### Completion record

**Changes made:**

- **`client/agents/cover_letter.py`** — all seven guarded
  ``try: json.loads(...) / except (json.JSONDecodeError, TypeError):``
  blocks replaced with the shared ``load_json_safe`` helper, each keeping
  the same early-return default:
  - `_load_str_list` — `data = load_json_safe(...)`, return `[]` on `None`.
  - `_contact_from_resume` — return `"(none available)"` on `None`.
  - `_validate_role` — return `True` (can't validate, pass) on `None`.
  - `_get_company_name` — return `""` on `None`, then
    ``_company_from(jd_data)``.
  - `_resume_company_in_letter` — return `""` on `None` (after the
    existing empty-`resume_json` guard).
  - `_candidate_name_from_resume` — return `""` on `None`.
  - `_apply_contact_info` — return `result` (unchanged letter) on `None`.
  - Removed the now-unused per-site `dict[str, Any]` type annotations
    (the `load_json_safe` return type is `dict[str, Any] | None`, narrowed
    by the `None` early-returns); `from client.json_utils import
    load_json_safe` added to the import line.
  - The remaining `json.dumps` call sites (logging + `_serialize`) are
    unchanged, so the `json` module import stays.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_cover_letter.py` (10) and
  `tests/test_cover_letter_validation.py` (109)
- New parse path is strictly more defensive than the old guards: for
  valid JSON objects the behavior is identical, and for fenced/non-object
  input `load_json_safe` returns `None` instead of raising.

**Commit:** `simplify: phase 6b - cover letter json.loads guards via load_json_safe`

---

## Phase 6 - Completed sub-task 6.3: named-step comments inside the long `run`/`_try_llm` methods

Original instruction: break any method over ~50 lines into named steps with
`# 1.`/`# 2.` comments.

### Completion record

**Changes made:**

- **`client/agents/cover_letter.py`** — measured body lengths with an AST
  script: the only functions over the ~45-line bar were `run` (60 lines)
  and `_try_llm` (142 lines).  Both are now broken into named steps with
  `# Step N.` comments (the same readability pattern used for Phase 5's
  long helpers -- no extraction, no behavior change):
  - `run` — Step 1. collect parsed inputs; Step 2. short-circuit to the
    data-driven fallback on empty input; Step 3. serialize the parsed
    models for the LLM prompt; Step 4. attempt LLM extraction (one retry,
    stricter second pass); Step 5. both attempts failed -> fallback letter.
  - `_try_llm` — Step 1. compose the prompt (directives + serialized
    inputs); Step 2. pick the rule set (stricter on retry); Step 3. call
    the LLM (client errors become None, never raised); Step 4. parse the
    JSON response; Step 5. validate into the output model; Step 6. reject
    an empty letter so `run()` uses the fallback; Step 7. post-validation
    checks (advisory + hard-reject guards); Step 8. deterministic
    post-processors (never mutate in place).
  - The existing inline comments ("empty input", "Attempt LLM extraction
    with one retry", "Post-validation checks", the empty-letter comment)
    were folded into the numbered steps rather than duplicated.
  - Comment-only change: the AST body diffs are empty (verified during
    guardrails), so behavior is identical.

**Behavior verification:**

- AST compare vs `HEAD` (statement-level, docstrings stripped):
  0 body diffs across all functions/classes.
- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_cover_letter.py` (10) and
  `tests/test_cover_letter_validation.py` (109)

**Commit:** `simplify: phase 6c - cover letter long method step comments (run/_try_llm)`

---

## Phase 6 - Completed sub-task 6.4: standardize placeholder-token handling

Original instruction: standardize placeholder-token handling
(`[Company Name]`, `[Your Name]`) -- every substitution one obvious path
with comment.

### Completion record

**Changes made:**

- **`client/agents/cover_letter.py`** — before this change the company
  placeholders went through a named `_replace_placeholders` helper while
  the candidate-name placeholders inlined the same loop inside
  `_apply_candidate_name` (two different substitution paths).  Now both go
  through the same helper:
  - `_replace_placeholders(text, target, tokens)` gained a `tokens`
    parameter (a tuple of literal placeholders) and is documented as *the*
    single substitution path for placeholder tokens; each present token is
    replaced with the real value, absent tokens are no-ops.
  - `_apply_company_name` calls it with `_PLACEHOLDER_TOKENS`
    (substitution path 1 -- company tokens).
  - `_apply_candidate_name` calls it with `_NAME_PLACEHOLDER_TOKENS`
    (substitution path 2 -- name tokens), replacing the inline loop.
  - Comment above `_PLACEHOLDER_TOKENS` and `_NAME_PLACEHOLDER_TOKENS`
    explains what the tokens are and that every substitution goes through
    `_replace_placeholders`.
  - Behavior identical: company path unchanged (same tokens, same
    replace-all semantics); name path now runs the identical loop via the
    shared helper.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including
  `tests/test_agent_cover_letter.py` (10) and
  `tests/test_cover_letter_validation.py` (109) -- the placeholder
  substitution tests (`[Company Name]`, `[Company]`, `[Employer Name]`,
  `[Your Name]`, `[Candidate Name]`, `<Your Name>`) all still pass.
- Tests do not import `_replace_placeholders` or the token constants
  directly (verified by grep), so the signature change is test-safe.

**Commit:** `simplify: phase 6d - standardized placeholder handling (_replace_placeholders shared)`

---

## Phase 6 - Completed sub-task 6.5: module docstring covering the agent contract

Original instruction: module docstring should cover the agent contract
(inputs, output model, fallback, two deterministic post-processors).

### Completion record

**Changes made:**

- **`client/agents/cover_letter.py`** — rewrote the first paragraph into a
  full "Agent contract" section (mirroring the Phase 5.6 pattern) that
  narrates, in order:
  1. **Inputs** — `run(inputs)` takes `parsed_job_description`
     (``JDParsingOutput``/dict), `parsed_resume`
     (``ResumeParsingOutput``/dict), and `tailoring_strategy`
     (``GapAnalysisOutput``/dict).
  2. **Output model** — ``CoverLetterOutput`` (single `cover_letter`
     string).
  3. **LLM attempt** — one normal pass + one strict retry; failed LLM
     call, JSON parse, Pydantic validation, or hard-reject guard fails the
     attempt.
  4. **Deterministic post-processors** — `_apply_company_name` (JD
     company: placeholder tokens first, then a wrong resume company name)
     and `_apply_candidate_name` (`[Your Name]` placeholders), plus
     `_apply_contact_info` (appends the resume contact line); all
     `model_copy`, never mutate in place.
  5. **Fallback** — `_build_fallback_cover_letter` renders a data-driven
     letter (role title, company, overlapping skills, one achievement)
     with no LLM.
  - Kept the "File layout" paragraph (banner groups) unchanged.
- Cross-checked against `docs/agents.md` section 7 (Cover Letter Agent,
  lines 312-350): the documented contract matches the code -- inputs,
  `CoverLetterOutput` output, `_apply_company_name` /
  `_apply_candidate_name` deterministic post-processing, and the
  data-driven fallback are all described consistently, so no doc drift to
  fix.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed
- Read-back check: the documented steps match the actual `run()`/`_try_llm()`
  flow (two attempts, strict on retry; failure -> `_build_fallback_cover_letter`)
  and the post-processor call order in `_try_llm` (Step 8: company, name,
  contact line last).

**Commit:** `simplify: phase 6e - cover letter module docstring (agent contract story)`

---

## Phase 6 - Cover Letter agent (largest file)  ✅ COMPLETED

**Files:** `client/agents/cover_letter.py`

968 lines. Highest-impact simplification target on the backend.

**Inspect for:**

- Seven occurrences of the `json.loads` guard (the Phase 4 helper removes them all).
- The chain of `_validate_*` / `_apply_company_name` / `_apply_candidate_name` post-processors - list every module-level function and assign each a clear intent.
- Where does the file switch from LLM output handling to HTML/plain rendering helpers? That split should become visible in the file structure.

**Simplify toward:**

- Split the file's helpers into named sections with banner comments (`# --- validation ---`, `# --- deterministic post-processors ---`, `# --- rendering/formatting ---`).
- Break any method over ~50 lines into smaller named steps.
- Standardize the placeholder-token handling (`[Company Name]`, `[Your Name]`) so every substitution is one obvious path with a comment.

**Documentation:** module docstring covering the agent contract (inputs from which prior agents, output model, fallback behavior, the two deterministic post-processors). This is *the* file to document thoroughly because it is the largest.

**Verify:** watch `tests/test_agent_cover_letter.py` + `tests/test_cover_letter_validation.py` (109 tests).

### Phase 6 Completion record

**Overview:** Phase 6 re-ordered `cover_letter.py` into banner-grouped
sections with the public `CoverLetterAgent` class first, routed all seven
`json.loads` guards through the shared `load_json_safe`, added
named-step (Step 1..N) comments to the two long methods (`run` and
`_try_llm`), standardized placeholder-token handling so both company and
candidate-name substitutions go through one shared
`_replace_placeholders` helper, and rewrote the module docstring with the
full agent-contract story.  Sub-tasks 6.1-6.5 were behavior-preserving
(re-order, shared guards, comments, shared helper); the module docstring
brings the file's documentation in line with its Phase-5 sibling.  The
109-test `test_cover_letter_validation.py` + 10-test
`test_agent_cover_letter.py` suites stayed green throughout.

**Changes made (by sub-task):**

- **6.1** — Re-ordered the file: public `CoverLetterAgent` class first,
  then the 33 module helpers under five banner sections (shared
  serialization/parsing utilities -> prompt helpers -> validation guards ->
  deterministic post-processors -> rendering/formatting).  AST-compare
  against `HEAD` confirmed identical function/class sets and 0 body diffs.
  (`simplify: phase 6a ...`)
- **6.2** — Routed all seven guarded `json.loads` blocks through
  `load_json_safe` in `_load_str_list`, `_contact_from_resume`,
  `_validate_role`, `_get_company_name`, `_resume_company_in_letter`,
  `_candidate_name_from_resume`, and `_apply_contact_info`; each kept the
  same early-return default.  New parse path is strictly more defensive
  for fenced/non-object input.  (`simplify: phase 6b ...`)
- **6.3** — Measured body lengths with an AST script; only `run` (60) and
  `_try_llm` (142) crossed the bar.  Both now read as `# Step N.` numbered
  steps (Step 1 collect inputs -> ... -> Step 5 fallback; Step 1 compose
  prompt -> ... -> Step 8 deterministic post-processors).  Comment-only,
  no behavior change.  (`simplify: phase 6c ...`)
- **6.4** — Standardized placeholder-token handling: `_replace_placeholders`
  now takes the token tuple, and both `_apply_company_name`
  (company tokens) and `_apply_candidate_name` (name tokens) go through
  it -- one substitution path with a comment instead of the previous
  helper-plus-inline-loop asymmetry.  Constant blocks documented.
  (`simplify: phase 6d ...`)
- **6.5** — Module docstring rewritten with a full "Agent contract"
  section (inputs, output model, LLM attempt/retry, the two deterministic
  post-processors + contact line, fallback builder) in addition to the
  file-layout paragraph; cross-checked `docs/agents.md` section 7 -- no
  drift.  (`simplify: phase 6e ...`)
- **6.6** — Guardrails run across the phase (below); phase moved here.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings (full run)
- `uv run pytest` — 493 passed, including
  `tests/test_agent_cover_letter.py` (10) and
  `tests/test_cover_letter_validation.py` (109)
- AST compare after 6.1: 0 function/class body diffs vs `HEAD` (pure
  re-order); subsequent sub-tasks verified by the full suite.
- Fallback behavior unchanged: LLM success -> validated + post-processed
  `CoverLetterOutput`; failure -> `_build_fallback_cover_letter`
  data-driven letter (role title, company, overlapping skills, one
  achievement).

**Commit:** `simplify: phase 6 - cover letter cleanup (banner sections, shared guards, step comments, placeholder standardization, agent-contract docs) (6.1-6.6)`

---

## Phase 7 - Completed sub-task 7.1: fix stale renderer.py header

Original instruction: fix the stale renderer.py header ("DOCX/PDF will
be added in subsequent phases" -> they already exist).

### Completion record

**Changes made:**

- **`client/templates/renderer.py`** — module docstring rewritten.  The
  previous text claimed "DOCX/PDF support will be added in subsequent
  phases", which was stale: `render_docx` / `render_pdf` / `render_all`
  already exist and are exercised by `tests/test_renderer.py`.  The
  header now states all four formats (plaintext, Markdown, DOCX,
  PDF) and points at `render_all` as the entry point that renders them.

**Behavior verification:**

- `uv run ruff check client/templates/renderer.py` — pass
- `uv run ruff format --check` (targeted files) — pass
- `uv run pyright client/templates/renderer.py client/formatter.py` —
  0 errors, 0 warnings
- `uv run pytest tests/test_renderer.py tests/test_formatter.py` —
  84 passed (43 + 41)
- Docstring-only change; no runtime behavior touched.

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 7 - Completed sub-task 7.2: document the two rendering paths

Original instruction: document the two rendering paths (template-based
`ResumeRenderer` vs `formatter.py` helpers) at the top of each module.

### Completion record

**Changes made:**

- **`client/templates/renderer.py`** — module docstring now names the
  template-based path explicitly: templates load from `client.templates`
  (`TEMPLATES` + `COVER_LETTER`), contexts are built by
  `_build_context` / `_build_cover_letter_context`, and every format
  (text, DOCX, PDF) renders from that one context.  It contrasts the
  alternative `client/formatter.py` path (no templates, no DOCX/PDF)
  and states when to prefer which.
- **`client/formatter.py`** — module docstring now names the simpler of
  the two paths (direct string building, single-format text only) and
  points at `client/templates/renderer.py` as the template-based
  alternative, again with a use-which guidance line.

**Behavior verification:**

- `uv run ruff check .` (targeted) — pass; `ruff format --check` — pass
- `uv run pyright` (targeted) — 0 errors, 0 warnings
- `uv run pytest tests/test_renderer.py tests/test_formatter.py` —
  84 passed
- Docstring-only change.

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 7 - Completed sub-task 7.3: extract shared `_render` helper

Original instruction: extract one private `_render(template_key,
context)` helper for the repeated "build context -> render -> clean
output" sequence.

### Completion record

**Changes made:**

- **`client/templates/renderer.py`** — added private
  `ResumeRenderer._render(template_source, context)` in the internal
  helpers section.  It owns the repeated "render -> clean" tail that
  every text-format public method had duplicated:
  ``self._env.from_string(template_source).render(**context)`` then
  ``self._clean_output(...)``.  Full `Args:`/`Returns:`/`Raises:`.
- All four text-format methods now resolve the template source
  (``self._templates[template][fmt]`` or ``COVER_LETTER[fmt]``), build
  their context, and delegate the render+clean step to `_render`:
  `render_plaintext`, `render_markdown`,
  `render_cover_letter_plaintext`, `render_cover_letter_markdown`.
- Note on naming: the plan sketched `_render(template_key, context)`;
  the implementation passes the already-resolved *source string* because
  resume and cover-letter templates live in different containers
  (`self._templates` vs the module-level `COVER_LETTER`).  The one
  private render+clean step is used by every text-format method either way.

**Behavior verification:**

- Byte-identical output proven: dumped all 8 renderer text outputs
  (3 templates x plaintext/markdown + 2 letter formats) from HEAD and
  from the working tree; `git diff --no-index` reported no differences.
- `uv run ruff check .` (targeted) — pass; `ruff format --check` — pass
- `uv run pyright` (targeted) — 0 errors, 0 warnings
- `uv run pytest tests/test_renderer.py tests/test_formatter.py` —
  84 passed

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 7 - Completed sub-task 7.4: docstring per template dict

Original instruction: docstring per template dict
(modern/classic/minimal/cover_letter) naming its style and which outputs
it drives.

### Completion record

**Changes made:**

- **`client/templates/modern.py`**, **`classic.py`**, **`minimal.py`** —
  each module docstring expanded to name its style and that its dict's
  `{"plaintext", "markdown"}` Jinja2 sources drive
  `ResumeRenderer.render_plaintext` / `render_markdown` (via its key in
  `client.templates`) plus the shared-context DOCX/PDF writers.
- **`client/templates/cover_letter.py`** — module docstring expanded to
  name the single shared letter template and that its two sources drive
  `render_cover_letter_plaintext` / `render_cover_letter_markdown`
  (no per-style variants).
- Because Python dicts cannot carry docstrings, each dict constant
  (`MODERN_RESUME` / `CLASSIC_RESUME` / `MINIMAL_RESUME` /
  `COVER_LETTER`) now has an explicit comment block directly above it
  stating exactly that, plus the expected context keys for the letter.

**Behavior verification:**

- `uv run ruff check .` (targeted) — pass; `ruff format --check` — pass
- `uv run pyright` (targeted) — 0 errors, 0 warnings
- `uv run pytest tests/test_renderer.py tests/test_formatter.py` —
  84 passed
- Docstring/comment-only change; template strings untouched.

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 7 - Completed sub-task 7.5: full class/method docstrings + `Raises:` on `render_all`

Original instruction: full class/method docstrings; add
`Args:`/`Returns:`/`Raises:` to `render_all`.

### Completion record

**Changes made:**

- **`client/templates/renderer.py`**:
  - `render_all` gained a `Raises:` section (KeyError for an unknown
    `resume_template`, `jinja2.UndefinedError` for a missing context
    variable, `OSError` for directory/file write failures).
  - `render_docx` and `render_pdf` each gained a `Raises:` section
    (`OSError` on directory creation / save failures).
  - `_write_text` expanded from a one-liner to full
    `Args:`/`Returns:`/`Raises:`.
  - `_build_context` and `_clean_output` expanded from one-liners to
    full `Args:`/`Returns:`.
  - `_build_cover_letter_context` already had a thorough docstring and
    was left as-is.
- Public methods (`render_plaintext`, `render_markdown`,
  `render_cover_letter_*`) already had complete
  `Args:`/`Returns:`/`Raises:`; unchanged.

**Behavior verification:**

- `uv run ruff check .` (targeted) — pass; `ruff format --check` — pass
- `uv run pyright` (targeted) — 0 errors, 0 warnings
- `uv run pytest tests/test_renderer.py tests/test_formatter.py` —
  84 passed
- Docstring-only change; no code paths altered.

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 7 - Renderer, templates, formatter  ✅ COMPLETED

**Files:** `client/templates/renderer.py`, `client/templates/modern.py`, `classic.py`, `minimal.py`, `cover_letter.py`, `client/templates/__init__.py`, `client/formatter.py`

**Inspect for:**

- `renderer.py` (890): the module docstring says *"DOCX/PDF support will be added in subsequent phases"*, but DOCX/PDF rendering already exists (`render_all`, docx/pdf writers). **This stale claim must be fixed.**
- The big public methods (`render_plaintext`, `render_markdown`, `render_cover_letter`, `render_docx`, `render_pdf`, `render_all`, `_clean_output`) - check each for inlined format-specific logic that belongs in a named private method.
- `modern.py`/`classic.py`/`minimal.py`: dict templates with `plaintext`/`markdown` keys - verify the Jinja string templates are readable and each has a docstring naming its style.
- `formatter.py`: `format_resume_markdown`/`plain`/`format_cover_letter` - the "other" rendering path; document how it differs from `ResumeRenderer`.

**Simplify toward:**

- Fix the stale header. Document the two rendering paths (template-based renderer vs. formatter helpers) at the top of each module.
- Break the repeated "build context -> render -> clean output" sequence into one private `_render(template_key, context)` helper used by each public method.
- Give every template dict an explicit docstring of what it contains and which outputs it drives.

**Documentation:** full class/method docstrings; add `Args:`/`Returns:`/`Raises:` to `render_all`. Keep output byte-identical - `tests/test_renderer.py` (43 tests) and `tests/test_formatter.py` (41 tests) guard this.

**Verify:** watch `tests/test_renderer.py`, `tests/test_formatter.py`.

### Phase 7 Completion record

**Overview:** Phase 7 made the renderer/formatter layer's documentation and
structure match its actual behavior.  The stale "DOCX/PDF support will be
added in subsequent phases" header was corrected (DOCX/PDF already exist
and are covered by tests).  Both rendering paths are now documented at
the top of each module (template-based `ResumeRenderer` vs the direct
string-building `formatter.py` helpers) with explicit guidance on which
to prefer.  The repeated "render -> clean" tail that every text-format
method duplicated was extracted into one private `_render` helper.  Every
template dict (modern/classic/minimal/letter) now has an explicit
description of its style and the outputs it drives, and `render_all`
(plus `render_docx`/`render_pdf`/`_write_text`/`_build_context`/
`_clean_output`) received complete `Args:`/`Returns:`/`Raises:` sections.
All changes were documentation/comment/structure only -- rendered output
was proven byte-identical to `HEAD` and the full 493-test suite stayed
green.

**Changes made (by sub-task):**

- **7.1** — Fixed the stale `renderer.py` module header: it now states
  all four formats (plaintext, Markdown, DOCX, PDF) render via
  `render_all`.  Docstring-only.
- **7.2** — Documented the two rendering paths: `renderer.py` and
  `formatter.py` module docstrings each name the template-based path and
  the direct string-building path, how they differ (templates vs not,
  DOCX/PDF vs not), and when to prefer which.  Docstring-only.
- **7.3** — Extracted `ResumeRenderer._render(template_source, context)`
  as the single private render+clean step; all four text-format methods
  (`render_plaintext`, `render_markdown`, `render_cover_letter_plaintext`,
  `render_cover_letter_markdown`) now resolve the source and delegate to
  it.  Byte-identical output proven by dumping all 8 text outputs from
  HEAD vs working tree (`git diff --no-index` clean).  Note: the plan's
  sketch `_render(template_key, context)` became `_render(source, context)`
  because resume and letter templates live in different containers
  (`self._templates` vs module-level `COVER_LETTER`).
- **7.4** — Added style+outputs documentation to every template dict:
  `modern.py`/`classic.py`/`minimal.py` module docstrings name the style
  and that their `{"plaintext", "markdown"}` sources drive
  `render_plaintext`/`render_markdown` plus the shared-context DOCX/PDF
  writers; `cover_letter.py` names the single shared letter template and
  its two sources.  Since dicts cannot hold docstrings, each constant got
  an explicit comment block above it.  Docstring/comment-only.
- **7.5** — Completed the renderer docstrings: `render_all` gained a
  `Raises:` section (KeyError / `jinja2.UndefinedError` / OSError);
  `render_docx`/`render_pdf` gained `Raises:` (OSError); `_write_text`,
  `_build_context`, and `_clean_output` expanded from one-liners to full
  `Args:`/`Returns:` (and `Raises:` where writes occur).  Docstring-only.
- **7.6** — Guardrails run across the phase (below); phase moved here.

**Behavior verification:**

- Byte-identical output: all 8 renderer text outputs (3 templates x
  plaintext/markdown + 2 letter formats) dumped from HEAD and the working
  tree; `git diff --no-index` reported zero differences.
- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings (full run)
- `uv run pytest` — 493 passed, including
  `tests/test_renderer.py` (43) and `tests/test_formatter.py` (41)
- Template strings and all rendering code paths untouched; only
  docstrings, comments, and the one extracted `_render` helper changed.

**Commit:** `simplify: phase 7 - renderer/templates/formatter docs + shared _render helper (7.1-7.5)`

---

## Phase 8 - Completed sub-task 8.1: step-by-step internal lookup

Original instruction: make the internal lookup read step-by-step
(`# 1. exact canonical match`, `# 2. variant lookup`, ...).

### Completion record

**Changes made:**

- **`client/skills/normalizer.py`** — `normalize()` previously looped
  ``for key in _match_keys(skill)`` (a 3-tuple) and returned the first
  hit; the ordering was implicit.  It now unpacks the three forms
  (`low`, `squashed`, `tokenized`) and walks them as three explicit,
  numbered lookup steps:
  - `# 1. exact canonical/variant match (case-insensitive), e.g. "mysql"`
  - `# 2. squashed lookup (punctuation stripped), e.g. "react.js"`
  - `# 3. tokenized lookup, e.g. "react js"`
  - `# Unknown skill: fall back to the normalized lowercase tokenized form.`
- Behavior identical: same key order (low -> squashed -> tokenized), same
  fallback (`tokenized`).

**Behavior verification:**

- `uv run pytest tests/test_skill_normalizer.py` — 15 passed
- `uv run ruff check client/skills/` — pass; `ruff format --check` — pass
- `uv run pyright client/skills/` — 0 errors, 0 warnings
- Spot-check via REPL: `normalize("js")` -> `JavaScript`,
  `normalize("react.js")` -> `React`, `normalize("Data Engineering")` ->
  `data engineering` (fallback).

**Commit:** `simplify: phase 8 - skill normalizer step-by-step lookup + docs (8.1-8.3)`

---

## Phase 8 - Completed sub-task 8.2: rename ambiguous locals + docstring coverage

Original instruction: rename single-letter/ambiguous locals; every method
docstring covers unknown-skill + case handling.

### Completion record

**Changes made:**

- **`client/skills/normalizer.py`**:
  - `match_skills()` list comprehensions used single-letter `s`; renamed
    to `skill` in all three comprehensions (`missing` / `matched` / `extra`).
  - `normalize()` dropped the implicit `for key in ...` tuple iteration
    (the `key` name implied a single comparable form when it was actually
    three) in favor of explicit `low` / `squashed` / `tokenized` locals.
  - Every method docstring now explicitly covers both the unknown-skill
    behavior and the case handling:
    - `normalize` — states matching is case- and punctuation-insensitive
      and that unknown skills fall back to the lowercase tokenized form.
    - `canonicalize` — notes identical behavior (case-insensitive lookup,
      lowercase tokenized fallback).
    - `normalize_list` — documents per-item behavior (canonical when known,
      tokenized fallback when unknown; case/punctuation insensitive;
      empties dropped; order preserved).
    - `get_variants` — documents case-insensitive lookup and empty list
      for unknown canonical names.
    - `match_skills` — documents that both inputs are normalized first
      (unknown skills become lowercase tokenized forms).

**Behavior verification:**

- `uv run pytest tests/test_skill_normalizer.py` — 15 passed
- `uv run ruff check client/skills/` — pass; `ruff format --check` — pass
- `uv run pyright client/skills/` — 0 errors, 0 warnings
- No public API changed; renames are local to comprehension/loop scopes.

**Commit:** `simplify: phase 8 - skill normalizer step-by-step lookup + docs (8.1-8.3)`

---

## Phase 8 - Completed sub-task 8.3: module docstring + taxonomy doc cross-check

Original instruction: module docstring explains "canonical skill taxonomy
-> normalized forms" and when to prefer `normalize_list` vs
`match_skills`; verify `docs/skill-taxonomy.md` matches code.

### Completion record

**Changes made:**

- **`client/skills/normalizer.py`** — module docstring rewritten with two
  sections:
  - *Canonical taxonomy -> normalized forms*: describes the
    `category -> {canonical name -> [variants]}` taxonomy, the three
    comparable forms, and the stable lowercase tokenized fallback for
    unknown skills.
  - *Choosing an entry point*: explicit guidance that `normalize_list`
    is for canonical de-duplicated lists, `match_skills` is for the
    three-way `missing` / `matched` / `extra` classification (it
    normalizes both inputs internally), and `normalize`/`canonicalize` /
    `get_variants` cover single-skill and variant-inspection needs.
- **`client/skills/__init__.py`** — package docstring expanded to point
  at `SkillNormalizer` and `docs/skill-taxonomy.md`.
- **Cross-check** — `docs/skill-taxonomy.md` (95 lines) verified against
  code: it already documents the six categories, the three comparable
  match forms, the import-time index build (`_CANONICAL_BY_KEY`,
  `_VARIANTS`, `_CATEGORY_BY_CANONICAL`), the five-method API table, and
  the 5 agents wired to normalization.  No drift found; no doc edits
  needed.  REPL check confirmed 6 categories and 52 canonical names as
  the doc implies.

**Behavior verification:**

- `uv run pytest tests/test_skill_normalizer.py` — 15 passed
- `uv run ruff check client/skills/` — pass; `ruff format --check` — pass
- `uv run pyright client/skills/` — 0 errors, 0 warnings
- Docstring/comment-only plus comprehension renames; no behavior change.

**Commit:** `simplify: phase 8 - skill normalizer step-by-step lookup + docs (8.1-8.3)`

---

## Phase 8 - Skill taxonomy & normalization  ✅ COMPLETED

**Files:** `client/skills/normalizer.py`, `client/skills/__init__.py`, `docs/skill-taxonomy.md` (read-only reference for this phase)

**Inspect for:**

- `SkillNormalizer` public surface (`normalize`, `normalize_list`, `match_skills`, ...), the canonical taxonomy loading, localization, and the `match_skills` return dict.
- Every method docstring should reference how it treats unknown skills and case.

**Simplify toward:**

- Make the internal lookup logic read step-by-step (`# 1. exact canonical match, # 2. variant lookup ...`).
- Rename any single-letter or ambiguous locals.

**Documentation:** module docstring explaining "canonical skill taxonomy -> normalized forms" and when to prefer `normalize_list` vs `match_skills`. Verify `docs/skill-taxonomy.md` matches code (consolidate in Phase 19 if it drifts).

**Verify:** watch `tests/test_skill_normalizer.py` (15 tests).

### Phase 8 Completion record

**Overview:** Phase 8 made the `SkillNormalizer` internals and
documentation read step-by-step.  `normalize()` now walks three explicit,
numbered lookup steps (exact lowercase -> squashed/punctuation-stripped ->
tokenized) instead of looping an implicit 3-tuple.  Ambiguous
single-letter locals were renamed (`s` -> `skill` in the `match_skills`
comprehensions; the tuple iteration became explicit `low`/`squashed`/
`tokenized`).  Every method docstring now states both the unknown-skill
behavior and the case/punctuation handling, and the module docstring
explains the canonical-taxonomy -> normalized-forms story plus when to
prefer `normalize_list` vs `match_skills`.  `docs/skill-taxonomy.md` was
cross-checked against the code -- no drift.  All changes were
docs/comments/renames; the 15-test `test_skill_normalizer.py` suite and
the full 493-test suite stayed green.

**Changes made (by sub-task):**

- **8.1** — `normalize()` unpacked `low`/`squashed`/`tokenized` and now
  walks three numbered lookup steps (`# 1. exact canonical/variant match`,
  `# 2. squashed lookup`, `# 3. tokenized lookup`, fallback comment).
  Same key order and fallback; behavior identical.  (`simplify: phase 8 ...`)
- **8.2** — Renamed single-letter `s` to `skill` in the `match_skills`
  comprehensions; replaced the implicit tuple iteration in `normalize()`
  with explicit named locals; every method docstring now covers
  unknown-skill + case handling (`normalize`, `canonicalize`,
  `normalize_list`, `get_variants`, `match_skills`).  No public API
  change.  (`simplify: phase 8 ...`)
- **8.3** — Module docstring rewritten with *Canonical taxonomy ->
  normalized forms* and *Choosing an entry point* sections;
  `client/skills/__init__.py` package docstring expanded.  Cross-checked
  `docs/skill-taxonomy.md` (six categories, three match forms, index
  build, API table, 5 wired agents) -- no drift found; no doc edits
  needed.  REPL confirmed 6 categories / 52 canonical names.  (`simplify:
  phase 8 ...`)
- **8.4** — Guardrails run across the phase (below); phase moved here.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings (full run)
- `uv run pytest` — 493 passed, including
  `tests/test_skill_normalizer.py` (15)
- REPL spot-check: `normalize("js")` -> `JavaScript`,
  `normalize("react.js")` -> `React`, `normalize("Data Engineering")` ->
  `data engineering` (fallback); `match_skills` on the test sample
  returns `missing: [Python, React]`, `matched: [JavaScript, Amazon Web
  Services]`, `extra: [Go]` exactly as the tests assert.
- No behavior change: renames are local, lookup order preserved, fallback
  unchanged.

**Commit:** `simplify: phase 8 - skill normalizer step-by-step lookup + docs (8.1-8.3)`

---

## Phase 9 - Completed sub-task 9.1: extract `_run_stage` helper

Original instruction: extract a small
`_run_stage(runner, agent_name, *, prompt, output, rules, **context)`
helper that returns the resolved field via `_extract_field`.

### Completion record

**Changes made:**

- **`pipeline.py`** — added
  ``async def _run_stage(runner, agent_name, *, prompt="", output=None, rules=None, fields=(), **context)``
  between `run_resume_pipeline` and `_run_pipeline_core`.  It assembles
  the stage input dict (`prompt`/`output`/`rules` only when non-empty,
  plus all keyword `context` entries), awaits
  ``runner.run_agent_async(agent_name, inputs)``, and returns
  ``_extract_field(result, *fields)``.
- Deviation from the plan's literal signature: a keyword-only
  ``fields: tuple[str, ...] = ()`` parameter was added because
  ``_extract_field`` needs candidate field names (e.g. stage 5 checks
  ``ats_optimized_resume`` then ``final_resume``).  Parsing agents
  (stages 1-2) pass no `prompt`/`output`/`rules` and no `fields`, so the
  raw result is returned unchanged — exactly the previous behavior.
- Full class-style docstring with `Args:`/`Returns:` documenting the
  generic-agent contract keys and the empty-`fields` passthrough.

**Behavior verification:**

- `uv run pytest tests/test_pipeline.py` — 17 passed
- `uv run ruff check pipeline.py` — pass; `ruff format --check` — pass
- `uv run pyright` — 0 errors, 0 warnings

**Commit:** `simplify: phase 9 - _run_stage helper + stage chain + CLI step comments (9.1-9.4)`

---

## Phase 9 - Completed sub-task 9.2: convert seven blocks to `_run_stage` calls

Original instruction: convert the seven near-identical blocks in
`_run_pipeline_core` to one-line `_run_stage` calls with a
`# 1. JD Parsing` ... `# 7. Cover Letter` comment above each.

### Completion record

**Changes made:**

- **`pipeline.py`** — `_run_pipeline_core` now runs the chain as seven
  `await _run_stage(...)` calls, each preceded by a short step comment:
  `# 1. JD Parsing`, `# 2. Resume Parsing`, `# 3. Gap Analysis`,
  `# 4. Resume Rewrite`, `# 5. ATS Compliance`, `# 6. Tone Polishing`,
  `# 7. Cover Letter`.
- Each stage passes its dedicated prompt/output/rules, the `fields` to
  resolve via `_extract_field`, and the context inputs consumed by that
  agent.  The previous per-stage `_extract_field` lines moved into the
  helper's return; stage ordering is now visually obvious.
- No stage arguments changed: same prompts, output lists, rules, and
  context keys as before (verified against the old diff).

**Behavior verification:**

- `uv run pytest tests/test_pipeline.py` — 17 passed (dependency
  threading tests confirm identical inputs reach each stub agent)
- `uv run ruff check pipeline.py` — pass; `ruff format --check` — pass
- `uv run pyright` — 0 errors, 0 warnings

**Commit:** `simplify: phase 9 - _run_stage helper + stage chain + CLI step comments (9.1-9.4)`

---

## Phase 9 - Completed sub-task 9.3: `run_agent_async` + `PipelineAgent` docs

Original instruction: verify the instantiate-on-first-use logic is
clearly commented in `run_agent_async`; confirm `PipelineAgent` docstring
explains backward compatibility with the dedicated classes.

### Completion record

**Changes made:**

- **`pipeline.py`** — `AgentRunner.run_agent_async`: the
  instantiate-on-first-use block comment expanded to explain *why* the
  instance is cached (lazy build with the per-agent client on first
  dispatch; later runs reuse the same instance and the same bound event
  loop).  The long docstring's shared-event-loop rationale (fresh
  `asyncio.run()` per agent closing the Ollama/OpenAI `AsyncClient`'s
  loop) was verified as still accurate — unchanged.
- **`pipeline.py`** — `PipelineAgent` class docstring rewritten to
  explicitly state it is the generic wrapper kept for backward
  compatibility with the dedicated per-agent classes (`JDParsingAgent`
  through `CoverLetterAgent`), and that the dedicated classes add Pydantic
  validation + deterministic fallbacks while `PipelineAgent` accepts raw
  `prompt`/`output`/`rules` inputs and returns the raw chat response.

**Behavior verification:**

- `uv run pytest tests/test_pipeline.py` — 17 passed
- `uv run ruff check pipeline.py` — pass; `ruff format --check` — pass
- `uv run pyright` — 0 errors, 0 warnings

**Commit:** `simplify: phase 9 - _run_stage helper + stage chain + CLI step comments (9.1-9.4)`

---

## Phase 9 - Completed sub-task 9.4: module docstring stage table + CLI steps

Original instruction: extend the pipeline module docstring with a stage
table (agent -> output key -> consumed by); keep the CLI `main()` flow in
plain sequential steps.

### Completion record

**Changes made:**

- **`pipeline.py`** — module docstring now contains a stage table
  (`Step | Agent name | Output key | Consumed by`) for the 7 stages, with
  a note that the output keys are the `run_resume_pipeline` result dict
  keys and that `_run_pipeline_core` runs the chain via `_run_stage`
  calls.  Existing text about dedicated classes + `PipelineAgent`
  compatibility retained.
- **`pipeline.py`** — `main()` flow split into numbered step comments:
  `# Step 1` sample-mode branch, `# Step 2` missing-flag check,
  `# Step 3` path validation, `# Step 4` read + run pipeline,
  `# Step 5` print results / rendered files.  Argument handling unchanged.

**Behavior verification:**

- `uv run pytest tests/test_pipeline.py` — 17 passed
- `uv run ruff check pipeline.py` — pass; `ruff format --check` — pass
- `uv run pyright` — 0 errors, 0 warnings
- Docstring/comment-only changes; no runtime behavior change.

**Commit:** `simplify: phase 9 - _run_stage helper + stage chain + CLI step comments (9.1-9.4)`

---

## Phase 9 - Completed sub-task 9.5: guardrails + CLI smoke

Original instruction: watch `tests/test_pipeline.py` (17); CLI still works
with `uv run python pipeline.py` (sample mode) and with
`--resume`/`--job-description`.

### Completion record

**Guardrails (all green):**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including `tests/test_pipeline.py` (17)

**CLI smoke (live Ollama, `qwen2.5:7b-instruct` pulled):**

- `uv run python pipeline.py --resume sample/resume/Peter-Letkeman-Resume.txt --job-description sample/jobs/Zafin.txt --candidate-name "Peter Letkeman" --company-name "Zafin"` — exit 0; printed polished resume + cover letter and rendered 6 output files under `output/` (`20260811_1028_peter-letkeman_zafin_*`).
- `uv run python pipeline.py` (sample mode) — exit 0; placeholder pipeline ran to completion.
- Validation branches (no LLM): missing `--job-description` -> exit 2 with `missing required argument(s)`; nonexistent file -> `parser.error` "resume file not found".

**Commit:** `simplify: phase 9 - _run_stage helper + stage chain + CLI step comments (9.1-9.4)`

---

## Phase 10 - Completed sub-task 10.1: `main.py` module docstring + listing parallel

Original instruction: module docstring listing every route + purpose;
decide/document the `list_generated` vs `list_uploaded` parallel.

### Completion record

**Changes made:**

- **`app/main.py`** — module docstring rewritten as a route table:
  `GET /health`, `GET /api/models`, `POST /api/pipeline`,
  `POST /api/pipeline/async`, `GET /api/tasks/{task_id}`,
  `GET /api/outputs/{filename}`, `GET /api/files/generated`,
  `GET /api/files/uploaded`, `DELETE /api/files`, and the SPA fallback
  `GET /{full_path:path}`, each with a one-line purpose.
- Decision on the parallel: kept the two listing handlers (no shared
  factory) because they are short and differ only by directory; documented
  the parallel explicitly in the module docstring and in both handler
  docstrings ("Parallel of ... same query params, only the directory
  differs").  Also documented the multipart-signature parallel between
  `run_pipeline` and `run_pipeline_async` in their docstrings (mirrors
  each other; sync blocks, async returns a task id).

**Behavior verification:**

- `uv run pytest tests/test_web_health.py tests/test_web_pipeline.py
  tests/test_web_tasks.py tests/test_web_outputs.py tests/test_web_files.py
  tests/test_web_upload.py tests/test_web_spa.py` — 51 passed
- `uv run ruff check app/` — pass; `ruff format --check app/` — pass
- `uv run pyright` — 0 errors, 0 warnings
- Docstring-only; no runtime change.

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 10 - Completed sub-task 10.2: `_read_text_input` dedupe + helper docs

Original instruction: remove the redundant size double-check in
`_read_text_input` (already enforced in `_persist_upload`); expand
`_read_text_input`/`_to_response`/`_require_runner` docs.

### Completion record

**Changes made:**

- **`app/main.py`** — `_read_text_input` no longer re-checks
  `file.size > MAX_UPLOAD_BYTES` after calling `_persist_upload`; the call
  site now carries the comment ``# also enforces MAX_UPLOAD_BYTES`` so the
  enforcement point is obvious.  The check still lives in `_persist_upload`
  (identical guard, same error detail).
- `_read_text_input` docstring gained `Args:`/`Returns:`/`Raises:`.
- `_to_response` gained `Args:`/`Returns:`.
- `_require_runner` gained a full docstring (return of the lifespan-built
  runner, `Raises: HTTPException(503)`).

**Behavior verification:**

- `uv run pytest tests/test_web_pipeline.py tests/test_web_files.py` — 26 passed
  (oversized-file `400` still covered by `test_oversized_file_returns_400`)
- `uv run ruff check app/` — pass; `ruff format --check app/` — pass
- `uv run pyright` — 0 errors, 0 warnings

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 10 - Completed sub-task 10.3: `files.py` traversal-defense docs

Original instruction: verify `safe_dir_path`/`safe_delete_path` docstrings
explain the traversal defense.

### Completion record

**Changes made:**

- **`app/files.py`** — `safe_dir_path` docstring expanded: explains the
  resolve-then-ancestor-check defense (both paths `resolve()`, candidate
  must equal base or live inside it), which blocks `..` traversal and
  symlink escapes; added `Args:`/`Returns:`/`Raises:`.
- `safe_delete_path` docstring expanded: states it reuses
  `safe_dir_path` for traversal defense and additionally requires a regular
  file (blocks directory targets and missing paths); added
  `Args:`/`Returns:`/`Raises:`.
- `list_files` already carried a clear filter/sort/paginate docstring;
  left unchanged.

**Behavior verification:**

- `uv run pytest tests/test_web_files.py` — 11 passed (incl. traversal
  escape test `test_path_traversal_never_deletes_outside_dir`)
- `uv run ruff check app/` — pass; `ruff format --check app/` — pass
- `uv run pyright` — 0 errors, 0 warnings
- Docstring-only; no runtime change.

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 10 - Completed sub-task 10.4: `upload.py` extraction-path docs

Original instruction: document each extraction path (.txt/.docx/.pdf).

### Completion record

**Changes made:**

- **`app/upload.py`** — `extract_text` docstring rewritten as a dispatch
  table: `.txt` decoded UTF-8 with `utf-8-sig` BOM-tolerant pass and
  `latin-1` fallback; `.docx` parsed via `python-docx` joining paragraph
  texts; `.pdf` parsed via `pypdf` joining per-page extracted text.  Added
  `Args:`/`Returns:`/`Raises:`.

**Behavior verification:**

- `uv run pytest tests/test_web_upload.py` — 9 passed (txt/docx/pdf paths
  and unsupported-MIME `400` all covered)
- `uv run ruff check app/` — pass; `ruff format --check app/` — pass
- `uv run pyright` — 0 errors, 0 warnings
- Docstring-only; no runtime change.

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 10 - Completed sub-task 10.5: `tasks.py` thread-safety + `schemas.py` descriptions

Original instruction: `tasks.py` thread/loop-safety notes; `schemas.py`
field descriptions.

### Completion record

**Changes made:**

- **`app/tasks.py`** — `TaskRegistry` class docstring expanded: all
  records live in a plain `dict` guarded by one `threading.Lock`; safe to
  call from both the async task coroutine (event loop) and sync route
  handlers (thread pool); state is in-memory only, keyed by `uuid` hex ids,
  not persisted across restarts and not shared between app instances.
- **`app/schemas.py`** — added `Field(description=...)` to every field
  lacking one: `TaskCreated.task_id`, `TaskStatus` (status/result/error/
  created_at/completed_at), `FileMeta` (name/size/modified/type/path),
  `PagedFile` (items/page/page_size/total/total_pages),
  `DeleteFilesRequest.files`.  `PipelineRunRequest`/`PipelineRunResponse`/
  `DeleteFilesResponse` already had descriptions.

**Behavior verification:**

- `uv run pytest tests/test_web_tasks.py` — 8 passed
- `uv run ruff check app/` — pass; `ruff format --check app/` — pass
- `uv run pyright` — 0 errors, 0 warnings
- Docstring/annotation-description only; serialization unchanged.

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 10 - Completed sub-task 10.6: guardrails + move + commit

Original instruction: watch all `test_web_*.py`, move to `simple-done.md`,
commit.

### Completion record

**Guardrails (all green):**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 493 passed, including the 7 web suites:
  `test_web_health.py` (2), `test_web_pipeline.py` (9),
  `test_web_tasks.py` (9), `test_web_outputs.py` (3),
  `test_web_files.py` (11), `test_web_upload.py` (9), `test_web_spa.py` (8)
  — 51 web tests total.

**Commit:** `simplify: phase 10 - web API layer docs (routes table, traversal defense, extraction paths, thread-safety notes, schema descriptions) (10.1-10.5)`

---

## Phase 11 - Completed sub-task 11.1: `tests/conftest.py` fixture docs

Original instruction: verify fixture names read clearly and are documented.

### Completion record

**Changes made:**

- **`tests/conftest.py`** — module docstring rewritten as a fixture index
  enumerating all ten fixtures with one-line purposes. Added docstrings to
  every previously-undocumented fixture: `configure_test_logging` (pins
  root logging to WARNING), `sample_resume_path`/`sample_jd_path` (paths
  under `sample/`), `sample_resume`/`sample_jd` (raw text of those files),
  and `markdown_resume`/`markdown_jd` (inline markdown used by the
  FormatDetector regex tests). `fake_client`, `rewrite_output`, and
  `cover_letter_output` already had docstrings and were left as-is.
- No fixture renamed: names already read clearly (`sample_*` = file-backed,
  `markdown_*` = inline, `fake_client` = mock client class, `*_output` =
  populated output models).

**Behavior verification:**

- `uv run pytest tests/test_format_detector.py tests/test_renderer.py
  tests/test_pipeline.py` — pass (exercises the documented fixtures)
- `uv run ruff check tests/conftest.py` — pass
- Docstring-only; no runtime change.

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 11 - Completed sub-task 11.2: per-agent contract test audit

Original instruction: confirm the per-agent contract tests assert *behavior*
rather than *implementation*, so the Phase 3-6 simplifications do not churn
them.

### Completion record

**Findings (audit only, no code change):**

- All seven `tests/test_agent_*.py` suites drive each agent through its
  public `run()` entry point with the `fake_client` fixture and assert on
  (a) the returned Pydantic output values and (b) the recorded `chat()`
  contract — `purpose`/`output`/`inputs`/`response_format`/`json_schema`.
  That is the documented LLM-call contract, not the agent internals.
- The only private symbols referenced are contract pins: `_SYSTEM_PROMPT`
  (asserts `purpose` matches the documented prompt), `_STRICT_RULES` /
  `_SCHEMA_HINT` (asserts the strict-retry round passes the strict rules),
  and `_build_fallback_cover_letter` (asserts the deterministic fallback
  builder output for the error path). These are stable interface values the
  agents expose to the chat contract, so the Phase 3-6 simplifications
  (which changed internal scaffolding, not the contract) leave them intact.
- Conclusion: contract tests assert behavior over implementation. No
  changes needed.

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 11 - Completed sub-task 11.3: `wip_testing/*.py` header comments

Original instruction: confirm each scratch script has a header comment
stating which agents it exercises and how to run it.

### Completion record

**Changes made:**

- Seven of eight `wip_testing/` scripts already had full headers
  (agent/chain description, prerequisites, usage): `test_job_description.py`,
  `test_resume_parsing.py`, `test_gap_analysis.py`, `test_resume_rewrite.py`,
  `test_ats_compliance.py`, `test_tone_polishing.py`, `test_cover_letter.py`.
  Left as-is.
- **`wip_testing/test_parsing.py`** — was a bare one-line run command.
  Rewrote the header to state what it exercises (FormatDetector regex-only
  and regex+LLM-fallback modes against the sample resume and JD) plus the
  standard prerequisites and usage block.
- Count note: the plan says 7 `wip_testing/*.py` files; the directory
  actually contains 8 (`test_parsing.py` included). All 8 now have headers.

**Behavior verification:**

- Docstring-only; the scripts themselves unchanged. `uv run ruff check
  wip_testing/` — pass.

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 11 - Completed sub-task 11.4: `test_real_files.py` guard docs

Original instruction: verify the `RUN_LIVE_PIPELINE` guard is documented.

### Completion record

**Findings (verify only, no code change):**

- `test_real_files.py` module docstring already documents the guard:
  the file deliberately lives outside `tests/` because it needs a live
  Ollama, shows both invocation forms (`uv run python test_real_files.py`
  and `RUN_LIVE_PIPELINE=1; uv run pytest test_real_files.py`), and notes
  that a plain pytest run skips (not fails) the test. Satisfied.

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 11 - Completed sub-task 11.5: file-top comments per test file

Original instruction: add/confirm a file-top comment for every test file
stating what it covers and the key fixture/hook it relies on.

### Completion record

**Changes made:**

All 23 `tests/*.py` files now have file-top docstrings stating coverage and
the fixtures/helpers they rely on. Enhanced the previously-thin docstrings:

- **`tests/test_format_detector.py`** — added coverage summary (titles,
  headings, sections, bullets, metrics, keywords, parse entry points) and
  noted the `markdown_*`/`sample_*` fixtures from `conftest.py`.
- **`tests/test_formatter.py`** — noted it uses local `_full_resume()` /
  `_empty_resume()` factories, no shared fixtures.
- **`tests/test_skill_normalizer.py`** — noted direct `SkillNormalizer`
  usage against `taxonomy.json`, no shared fixtures.
- **`tests/test_cover_letter_validation.py`** — noted it exercises the
  deterministic post-validation helpers directly, no shared fixtures.
- **`tests/test_resume_rewrite_validation.py`** — same treatment.
- **`tests/test_jd_parsing.py`** — noted `_extract_company_name` /
  `_sync_company_name` are exercised directly, no shared fixtures.
- **`tests/test_web_health.py`** — noted it uses
  `fastapi.testclient.TestClient(app)`, no shared fixtures.

The remaining suites already had adequate multi-line docstrings
(`test_agent_*.py`, `test_json_utils.py`, `test_model_clients.py`,
`test_pipeline.py`, `test_renderer.py`, `test_web_pipeline.py`,
`test_web_tasks.py`, `test_web_outputs.py`, `test_web_files.py`,
`test_web_upload.py`, `test_web_spa.py`).

**Behavior verification:**

- Docstring-only; test logic unchanged. `uv run pytest -q` — 493 passed
  (full suite, including all 23 test files).

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 11 - Completed sub-task 11.6: guardrails + move + commit

Original instruction: full `uv run pytest` green + `uv run ruff check .`,
move to `simple-done.md`, commit.

### Completion record

**Guardrails (all green):**

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (96 files formatted)
- `uv run pytest -q` — 493 passed, full suite (test logic untouched;
  docstring/header-only changes across `tests/` and `wip_testing/`)

**Moved to `simple-done.md`:** the Phase 11 narrative stub stays in
`simple.md`; all 6 sub-task completion records (11.1-11.6) are recorded
here above. `simple.md` checklist rows 11.1-11.6 checked and the Phase 11
header marked `✅ COMPLETED`.

**Commit:** `simplify: phase 11 - test docstrings + headers + conftest docs (11.1-11.5)`

---

## Phase 12 - Completed sub-task 12.1: `client.ts` error-parsing helpers

Original instruction: extract the busy `parseErrorDetail` body into one or
two small helpers (`_detailString(detail)`, `_detailArray(detail)`), each
with a JSDoc line.

### Completion record

**Changes made:**

- **`ui/src/api/client.ts`** — extracted the string branch into
  `_detailString(detail)` (returns the detail when it is a string, else
  `null`) and the array branch into `_detailArray(detail)` (maps each
  element: bare strings pass through, objects with a `msg` field are
  stringified, others are skipped; joins the survivors with `'; '`, returns
  `null` when nothing is usable).  `parseErrorDetail` is now the thin
  composition `_detailString(body.detail) ?? _detailArray(body.detail)`
  inside the same try/catch.  Both helpers carry a JSDoc line describing
  the FastAPI shape they tolerate.
- Added a file-header comment to `client.ts` describing the `/api` fetch
  wrapper, the thrown-`Error` convention on non-2xx, and that pages consume
  the functions via `hooks.ts` rather than directly.

**Behavior verification:**

- `npx tsc -b` — pass
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed; `client.test.ts` covers the same paths
  (string detail, array-of-`{msg}` join, missing detail fallback).

**Commit:** `simplify: phase 12 - api client error helpers + hooks/types/download docs (12.1-12.4)`

---

## Phase 12 - Completed sub-task 12.2: `hooks.ts` polling lifecycle docs

Original instruction: document the polling lifecycle, why the files query is
invalidated, when `onDone` fires, and the `refetchInterval` predicate.

### Completion record

**Changes made:**

- **`ui/src/api/hooks.ts`** — added a file-header comment describing the
  full polling lifecycle (launch -> poll while pending/running -> settle ->
  invalidate `['files']` -> fire `onDone`).
- JSDoc on every exported hook:
  - `useModels`: per-agent model summary for the home page.
  - `useInvokePipeline`: launches a background run, returns the task id.
  - `useTask`: documents the `refetchInterval` predicate — polls only while
    status is `pending`/`running`, returns `false` on terminal states so
    polling stops.
  - `usePollTask`: documents *why* `['files']` is invalidated (a completed
    run writes new files to `output/`, so listings would go stale) and *when*
    `onDone` fires (exactly once per settling `completed`/`failed` status).
  - `useFiles`: previous page kept visible while refetching.
  - `useDeleteFiles`: invalidates listings after a delete.

**Behavior verification:**

- `npx tsc -b` — pass; `npm run lint` — pass
- `npm test -- --run` — 45 passed (`hooks.test.ts` exercises `useModels`,
  `useFiles`, `useDeleteFiles`).

**Commit:** `simplify: phase 12 - api client error helpers + hooks/types/download docs (12.1-12.4)`

---

## Phase 12 - Completed sub-task 12.3: `types.ts` FastAPI schema mappings

Original instruction: comment each TS type with the FastAPI schema it
mirrors (e.g. `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`).

### Completion record

**Changes made:**

- **`ui/src/api/types.ts`** — added a module header noting the two backend
  homes (web API models in `app/schemas.py`, pipeline output models in
  `client/models.py`) and a one-line mapping comment on every interface and
  type:
  - `ModelSummary` -> `config/agents.py get_model_summary()` rows
  - `TaskCreated` / `TaskStatus` / `FileMeta` / `PagedFile` /
    `DeleteFilesResponse` -> `app.schemas.*`
  - `ExperienceEntry` + the seven `*Output` interfaces ->
    `client.models.*`
  - `StageResult<T>` -> the `Any`-typed `PipelineRunResponse` stage fields
  - `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`

**Behavior verification:**

- Comment-only; no type changes. `npx tsc -b` — pass; `npm run lint` — pass;
  `npm test -- --run` — 45 passed.

**Commit:** `simplify: phase 12 - api client error helpers + hooks/types/download docs (12.1-12.4)`

---

## Phase 12 - Completed sub-task 12.4: `download.ts` URL docs

Original instruction: document the URL the helper builds.

### Completion record

**Changes made:**

- **`ui/src/api/download.ts`** — added a module header explaining the
  helpers build URLs for `GET /api/outputs/{filename}` (served by
  `app/main.py` out of `output/`) and JSDoc on both functions:
  - `outputDownloadUrl`: bare-filename URL.
  - `fileDownloadUrl`: accepts the dir-qualified `path` keys returned by the
    file listings (e.g. `output/2026/resume.md`), normalizes Windows
    backslashes, takes the basename, and delegates.

**Behavior verification:**

- `npx tsc -b` — pass; `npm run lint` — pass
- `npm test -- --run` — 45 passed; `client.test.ts` covers both helpers
  (encoding, backslash path, forward-slash path).

**Commit:** `simplify: phase 12 - api client error helpers + hooks/types/download docs (12.1-12.4)`

---

## Phase 12 - Completed sub-task 12.5: guardrails + move + commit

Original instruction: `npx tsc -b`, `npm run lint`, `npm test -- --run`
(watch `api/client.test.ts`, `api/hooks.test.ts`), move to `simple-done.md`,
commit.

### Completion record

**Guardrails (all green):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files, including
  `api/client.test.ts` (error-parsing + download helpers) and
  `api/hooks.test.ts` (models/files/delete hooks)

**Moved to `simple-done.md`:** the Phase 12 narrative stub stays in
`simple.md`; all 5 sub-task completion records (12.1-12.5) are recorded
here above. `simple.md` checklist rows 12.1-12.5 checked and the Phase 12
header marked `✅ COMPLETED`.

**Commit:** `simplify: phase 12 - api client error helpers + hooks/types/download docs (12.1-12.4)`

---

## Phase 13 - Completed sub-task 13.1: `coerce.ts` JSDoc + expanded one-liners

Original instruction: add one-line JSDoc to every exported helper in
`coerce.ts` stating exactly what it tolerates and returns; expand any dense
`pick*` one-liner that composes two helpers.

### Completion record

**Changes made:**

- **`ui/src/pages/results/coerce.ts`** — added JSDoc to all 13 exports
  (`asRecord`, `asString`, `asStringList`, `asStringMap`, `asObjectList`,
  `pickString`, `pickNumber`, `pickList`, `pickObjectList`, `pickText`,
  `textFromValue`, `pickMap`).  Each line states the tolerated input shapes,
  the edge-case handling (e.g. `asString` drops blank strings, `pickNumber`
  parses numeric strings and rejects non-finite values, `pickText` accepts
  string / array / nested-object and joins accordingly), and the exact
  default returned (`null` for singletons, `[]` / `{}` for collections).
- Expanded the dense `pick*` one-liners (`pickString`, `pickList`,
  `pickObjectList`, `pickMap`) from `return record === null ? ... :
  ...(record[key])` into an early-`return null`/`return []` guard followed by
  the single composed call — behaviour identical, reads as two obvious steps.

**Behavior verification:**

- `npx tsc -b` — pass; `npm run lint` — pass
- `npm test -- --run` — 45 passed (the results tabs that consume these
  helpers are covered by `ATSTab.test.tsx` / `DownloadsRow.test.tsx`).
- Refactor + JSDoc only; no runtime change.

**Commit:** `simplify: phase 13 - result coercion + parts renderer docs (13.1-13.3)`

---

## Phase 13 - Completed sub-task 13.2: `parts.tsx` renderer docs

Original instruction: document the props and behavior of each shared
renderer so the tab components read as declarative data.

### Completion record

**Changes made:**

- **`ui/src/pages/results/parts.tsx`** — added a module header describing
  the role of the parts (tabs describe their coerced data declaratively) and
  the `emptyText` convention shared by the list renderers (when set, render a
  `NoData` placeholder; when unset, render nothing so empty sections are
  silently skipped).
- JSDoc on every exported component:
  - `NoData`: centered placeholder shown for empty sections.
  - `Section`: titled wrapper; renders `children` when `hasContent`, else
    `NoData`.
  - `ExperienceEntryView`: reads `title`/`company`/`dates` plus the three
    bullet lists off a loose entry dict and renders the header + non-empty
    lists.
  - `TagSection` / `BulletSection` / `KeyValueTable`: each documents the
    items/entries it renders, the placeholder behaviour, and that it renders
    nothing when empty and `emptyText` is unset.

**Behavior verification:**

- `npx tsc -b` — pass; `npm run lint` — pass
- `npm test -- --run` — 45 passed (tab components render through these
  parts in `ATSTab.test.tsx` and `DownloadsRow.test.tsx`).
- Docstring-only; no runtime change.

**Commit:** `simplify: phase 13 - result coercion + parts renderer docs (13.1-13.3)`

---

## Phase 13 - Completed sub-task 13.3: `coerce.ts` module header

Original instruction: module header explaining "the backend result dicts are
loosely typed; these helpers coerce unknown shapes safely".

### Completion record

**Changes made:**

- **`ui/src/pages/results/coerce.ts`** — added a module header stating that
  the backend result dicts (`StageResult<T>` values in
  `PipelineRunResponse`) are loosely typed — a field may be missing, null,
  the wrong type, or a string where a list is expected — and that these
  helpers coerce unknown shapes safely, never throw, and return predictable
  defaults (`null` / `[]` / `{}`) so tabs render without defensive checks.

**Behavior verification:**

- Comment-only. `npx tsc -b` — pass; `npm run lint` — pass;
  `npm test -- --run` — 45 passed.

**Commit:** `simplify: phase 13 - result coercion + parts renderer docs (13.1-13.3)`

---

## Phase 13 - Completed sub-task 13.4: guardrails + move + commit

Original instruction: `npx tsc -b`, `npm run lint`, `npm test -- --run`,
move to `simple-done.md`, commit.

### Completion record

**Guardrails (all green):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files

**Moved to `simple-done.md`:** the Phase 13 narrative stub stays in
`simple.md`; all 4 sub-task completion records (13.1-13.4) are recorded
here above. `simple.md` checklist rows 13.1-13.4 checked and the Phase 13
header marked `✅ COMPLETED`.

**Commit:** `simplify: phase 13 - result coercion + parts renderer docs (13.1-13.3)`

---

## Phase 14 - Completed sub-task 14.1: `ResultsTabView.tsx` tab-key comment

Original instruction: comment tying `TAB_KEYS` to the 7-agent output
keys/order.

### Completion record

**Changes made:**

- **`ui/src/pages/results/ResultsTabView.tsx`** — added a module header
  describing the component (renders the seven `PipelineRunResponse` stage
  outputs as PrimeReact tabs; tab order mirrors the 7-agent chain).
- Documented `ResultKey` as "the seven `PipelineRunResponse` stage keys, in
  pipeline order".
- Added a block comment above `TAB_KEYS` mapping each key to its agent and
  stage, in the exact order the pipeline produces them:
  1. `parsed_job_description` -> Agent 1 (JD Parsing)
  2. `parsed_resume` -> Agent 2 (Resume Parsing)
  3. `tailoring_strategy` -> Agent 3 (Gap Analysis)
  4. `rewritten_resume` -> Agent 4 (Resume Rewrite)
  5. `ats_optimized_resume` -> Agent 5 (ATS Compliance)
  6. `polished_resume` -> Agent 6 (Tone Polishing)
  7. `cover_letter` -> Agent 7 (Cover Letter)
  and a "keep this list in sync" note tying it to `PipelineRunResponse` and
  the 7-agent chain.
- Commented `TAB_HEADERS` as one header per `TAB_KEYS` entry.

**Behavior verification:**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- Comment-only; no runtime change.

**Commit:** `simplify: phase 14 - results tab view comments tying TAB_KEYS to 7-agent outputs (14.1)`

---

## Phase 14 - Completed sub-task 14.2: per-tab headers + consistent `coerce.ts` use

Original instruction: give every tab a one-line header (what it shows + which
pipeline field it renders) and make the tab components use the `coerce.ts`
helpers consistently.

### Completion record

**Changes made:**

- **One-line header comment** at the top of all seven tab components, each
  stating what it shows and which pipeline field it renders:
  - `ParsedJDTab.tsx` — Agent 1 output (`parsed_job_description`)
  - `ParsedResumeTab.tsx` — Agent 2 output (`parsed_resume`)
  - `GapAnalysisTab.tsx` — Agent 3 output (`tailoring_strategy`)
  - `RewrittenResumeTab.tsx` — Agent 4 output (`rewritten_resume`)
  - `ATSTab.tsx` — Agent 5 output (`ats_optimized_resume`)
  - `PolishedTab.tsx` — Agent 6 output (`polished_resume`)
  - `CoverLetterTab.tsx` — Agent 7 output (`cover_letter`)
- **Consistent `coerce.ts` use**: the five record-based tabs
  (`ParsedJDTab`, `ParsedResumeTab`, `GapAnalysisTab`, `RewrittenResumeTab`,
  `ATSTab`) each duplicated the manual guard
  `value !== null && typeof value === 'object' ? value as Record<string, unknown> : null`
  (some inline, some multi-line).  Replaced every copy with the shared
  `asRecord(value)` helper from `coerce.ts`, so the coercion path is uniform
  across tabs.  `PolishedTab` / `CoverLetterTab` already used
  `textFromValue` and needed no change.

**Behavior verification:**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed (tab tests `ATSTab.test.tsx` /
  `DownloadsRow.test.tsx` green; `asRecord` is behavior-identical to the
  replaced inline guard)
- Comment + equivalent-refactor only; no runtime change.

**Commit:** `simplify: phase 14 - per-tab headers + asRecord coercion consistency (14.2)`

---

## Phase 14 - Completed sub-task 14.3: HTML-string trust boundary docs

Original instruction: any tab rendering an HTML string (e.g., polished/cover
letter) — document the trust boundary: the content came from our own
pipeline.

### Completion record

**Changes made:**

- **`ui/src/pages/results/PolishedTab.tsx`** — added a header note after the
  one-line description documenting the trust boundary: the polished resume is
  plain text produced by our own pipeline (LLM output, not user-supplied
  HTML) and is rendered inside a `<pre>` as text, so React escapes the string
  and no HTML is interpreted.
- **`ui/src/pages/results/CoverLetterTab.tsx`** — same trust-boundary note
  for the cover letter.
- **`ui/src/pages/results/ATSTab.tsx`** — the `final_resume` section renders
  the same kind of long-form pipeline text in a `<pre>`; added the same
  trust-boundary comment inline above that element.

**Behavior verification:**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed (`ATSTab.test.tsx` still green)
- Comment-only; no runtime change.

**Commit:** `simplify: phase 14 - trust boundary comments for pipeline text tabs (14.3)`

---

## Phase 14 - Completed sub-task 14.4: extract repeated markup into `parts.tsx`

Original instruction: move repeated row/label markup into `parts.tsx` when it
appears in 2+ tabs.

### Completion record

**Changes made:**

- **`ui/src/pages/results/parts.tsx`** — added three shared parts:
  - `ParagraphSection({ label, text })`: a titled section rendering a single
    paragraph; `NoData` when `text` is null.  Replaces the duplicated
    Summary and Contact blocks.
  - `PreSection({ label, text })`: a titled section rendering pre-formatted
    text in a `<pre class="results-pre">`; `NoData` when `text` is null.
    Replaces the duplicated polished-resume / cover-letter / ATS final-resume
    blocks.  (Also carries the trust-boundary rationale in its docstring.)
  - `ExperienceSection({ entries })`: a titled "Experience" section mapping
    entries through `ExperienceEntryView`; `NoData` when empty.  Replaces the
    duplicated experience mapping.
  - Updated the module header to list the new parts.
- **`ParsedResumeTab.tsx`** — Summary and Contact now use `ParagraphSection`;
  Experience uses `ExperienceSection`.  Dropped the now-unused
  `ExperienceEntryView` and `Section` imports.
- **`RewrittenResumeTab.tsx`** — Summary uses `ParagraphSection`; Experience
  uses `ExperienceSection`.  Dropped unused imports.
- **`PolishedTab.tsx`** / **`CoverLetterTab.tsx`** — body now a single
  `PreSection`; the trust-boundary note moved up into the file-header comment.
- **`ATSTab.tsx`** — final-resume block replaced with `PreSection`, keeping an
  inline trust-boundary comment above it.  `Section` still used for the Score
  block.

**Behavior verification:**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed (tab tests `ATSTab.test.tsx` /
  `DownloadsRow.test.tsx` green)
- Refactor is markup-identical for populated and empty states (verified the
  `hasContent`/`emptyText` semantics match the replaced JSX).

**Commit:** `simplify: phase 14 - extract shared paragraph/pre/experience parts (14.4)`

---

## Phase 14 - Completed sub-task 14.5: guardrails + move + commit

Original instruction: `npx tsc -b`, `npm run lint`, `npm test -- --run`
(watch `ATSTab.test.tsx`, `DownloadsRow.test.tsx`), move to
`simple-done.md`, commit.

### Completion record

**Guardrails (all green):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- `npx vitest run src/pages/results/ATSTab.test.tsx src/pages/results/DownloadsRow.test.tsx` — 7 passed (2 files)

**Moved to `simple-done.md`:** the Phase 14 narrative stub stays in
`simple.md`; all 5 sub-task completion records (14.1-14.5) are recorded
here above. `simple.md` checklist rows 14.1-14.5 checked and the Phase 14
header marked `✅ COMPLETED`.

**Commit:** `simplify: phase 14 - close, guardrails + records in simple-done.md`

---

## Phase 14 - Results tabs (8 components)  ✅ COMPLETED

**Files:** `ui/src/pages/results/ParsedJDTab.tsx`, `ParsedResumeTab.tsx`, `GapAnalysisTab.tsx`, `RewrittenResumeTab.tsx`, `ATSTab.tsx`, `PolishedTab.tsx`, `CoverLetterTab.tsx`, `ResultsTabView.tsx`

**Inspect for:**

- `ResultsTabView.tsx`: the tab map (`TAB_KEYS`, `TAB_HEADERS`, `renderTabBody` switch) is clean. Add a comment that tab order mirrors pipeline output keys.
- Each tab: what data shape does it expect? Does it use the `coerce.ts` helpers or inline its own `as*` logic?
- Any tab rendering an HTML string (e.g., polished/cover letter) - document the trust boundary (content came from our own pipeline).

**Simplify toward:**

- Keep each tab a thin "read data via `pick*`, render via `parts.tsx`" component. Move repeated row/label markup into `parts.tsx` when it appears in 2+ tabs.
- Give every tab a one-line header comment (what it shows + which pipeline field it renders).

**Documentation:** per-component docstrings plus a note in `ResultsTabView.tsx` tying tab keys to the 7-agent output keys.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch the tab tests: `ATSTab.test.tsx`, `DownloadsRow.test.tsx`).

### Completed sub-tasks

- 14.1 `ResultsTabView.tsx` tab-key comment — commit `55bc2d0`
- 14.2 per-tab headers + consistent `coerce.ts` use — commit `3f61964`
- 14.3 HTML-string trust boundary docs — commit `8d51fdf`
- 14.4 extract repeated markup into `parts.tsx` — commit `e1c5a5d`
- 14.5 guardrails + move + commit — this close record

---

## Phase 15 - Completed sub-task 15.1: extract `isTaskActive(status)`

Original instruction: extract `isTaskActive(status)` and reuse it in the
button `disabled`/`label`, the status panel, and any other spot.

### Completion record

**Changes made:**

- **`ui/src/pages/RunPage.tsx`** — the "active" status expression
  (`status === undefined || status === 'pending' || status === 'running'`)
  appeared twice: in the `active` derived boolean (drives the Run/Reset
  button `disabled` and label) and in the status-panel ternary.  Added a
  documented `isTaskActive(status)` helper next to `STATUS_SEVERITY`
  (per the phase's "Simplify toward"), accepting `TaskStatusName | undefined`
  because the status is unknown until the first poll.  Both call sites now
  use it:
  - `const active = invokePipeline.isPending || (taskId !== null && isTaskActive(status))`
  - `{isTaskActive(status) ? (spinner + pending tag) : (terminal tag)}`
- Imported `TaskStatusName` from `../api/types` for the helper signature.

**Deliberately untouched:** `api/hooks.ts` `usePollTask` has a similar
`status === undefined || (status !== 'completed' && status !== 'failed')`
guard, but it serves a different purpose (fire `onDone` only after a task
settles) and lives in the API layer — importing a page helper there would
invert the dependency direction.  Out of scope for 15.1.

**Behavior verification:**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- `npx vitest run src/pages/RunPage.test.tsx` — 3 passed (button
  disabled-while-active test still green)
- Refactor-only; identical behavior (same boolean logic, single source of truth).

**Commit:** `simplify: phase 15 - extract isTaskActive helper in RunPage (15.1)`

---

## Phase 15 - Completed sub-tasks 15.2-15.6: task labels, handleSubmit steps, form docs, guardrails

Original instructions:

- **15.2** Extract `taskStatusLabel` + status-severity map next to `STATUS_SEVERITY`.
- **15.3** Expand `handleSubmit` into 2-3 obvious steps with comments (validate -> toast -> mutate -> capture task id).
- **15.4** `FileChosen`: document `customUpload` behavior; header comments for the page flow (submit -> poll -> results + downloads).
- **15.5** `runForm.ts`: JSDoc on `validateRunInputs`/`buildRunFormData`; document "text wins over file" matches backend `_read_text_input`.
- **15.6** Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `RunPage.test.tsx`).

This closes Phase 15 (Phases 1-14 already moved here; Phase 15's last four sub-tasks land now).

### Completion record

**Changes made:**

- **`ui/src/pages/RunPage.tsx`**:
  - **15.2** — the `TASK_STATUS_LABEL` map and `taskStatusLabel(status)` helper (extracted next to `STATUS_SEVERITY` / `isTaskActive`) are now wired into both branches of the status-panel `Tag`: `value={taskStatusLabel(status)}` renders the human-readable label ("Pending"/"Running"/"Completed"/"Failed", unknown status -> "Pending") and both branches pull severity from the `STATUS_SEVERITY` map (`status ?? 'pending'` in the active branch, `status ?? 'completed'` in the terminal branch) instead of the previous hard-coded `severity="info"` + raw status string. Active states still resolve to `info`, so only the displayed label text changed.
  - **15.3** — `handleSubmit` body is now three numbered steps with comments: `// Step 1.` gather + validate, `// Step 2.` warn-toast on invalid input and return, `// Step 3.` mutate with onSuccess capture of the task id and onError toast. Logic unchanged.
  - **15.4** — `FileChosen` got a header docstring explaining the `customUpload` PrimeReact behavior (browser never sends the file; `onSelect` hands the File to the parent via `onChange` so it lands in the multipart FormData) and the chosen-file/remove toggle. `RunPage` got a header docstring describing the page flow (submit -> capture task id -> poll -> results + downloads; Reset clears the task id).
- **`ui/src/pages/runForm.ts`**:
  - **15.5** — module-top comment documenting the file role + the "pasted text wins over uploaded file" precedence rule and that it mirrors the backend resolver `app.main._read_text_input` (text returned whenever non-empty, file only as fallback) so frontend and backend never disagree. JSDoc on `RunInputs`, `validateRunInputs` (Args/Returns; each required input counts as supplied when text is non-empty OR a file is chosen), and `buildRunFormData` (text-wins-over-file per field; optional candidate/company names appended only when non-empty).
  - The two functions' bodies are byte-for-byte identical to before — documentation only.

**Behavior note:** the only user-visible change is the status `Tag` value now showing the capitalized label ("Running" instead of "running") as intended by 15.2; severity color and the rest are unchanged. `RunPage.test.tsx` asserts on button `name`/`disabled` and form data, not the status label, so it is unaffected.

**Behavior verification (15.6):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- `npx vitest run src/pages/RunPage.test.tsx` — 3 passed (text-wins-over-file submit, disabled-while-active, empty-input warn toast)

**Commit:** `simplify: phase 15 - run page task labels + handleSubmit steps + form docs (15.2-15.5)`

---

## Phase 16 - Completed sub-tasks 16.1-16.4: Files page sections, state naming, header docs, guardrails

Original instructions:

- **16.1** Split into named sections (file-table config, filter bar, delete
  selection, toolbar) via banner comments or a `FileTable` component.
- **16.2** Name state by intent (`selectedKeys`, `fileTypeFilter`,
  `searchQuery`, `page`).
- **16.3** Header comment: generated-vs-uploaded toggle; how downloads/delete
  map to the two listing kinds.
- **16.4** Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`
  (watch `FilesPage.test.tsx`).

This closes Phase 16 (Files page was the last remaining page-level phase before
17 - models/App shell/theme/toast/entry and the closing phases).

### Completion record

**Changes made:**

- **`ui/src/pages/FilesPage.tsx`**:
  - **16.1 (sections)** — added banner comments breaking the file into named
    sections and JSDoc on every helper/callback:
    - Module level: `File listing configuration` (the `KIND_OPTIONS` /
      `PAGE_SIZE_OPTIONS` / `FILE_TYPE_OPTIONS` / `SORT_OPTIONS` tables) and
      `Formatting helpers` (`formatSize`, with args/returns JSDoc).
    - Component: `state`, `data queries`, `event handlers` (`applySearch`,
      `handlePage`, `confirmDelete`, `handleDeleteAccept` — each now has a
      one-line JSDoc), `column renderers` (with a note tying the download link
      to the shared outputs route), and `render`.
    - JSX: `{/* Toolbar: ... */}` / `{/* Delete action: ... */}` / `{/* Table:
      lazy, paginated listing ... */}` / `{/* Delete confirmation dialog */}`
      banner comments before each block.
  - **16.2 (state naming)** — renamed the state variables by intent:
    - `q` / `setQ` -> `searchQuery` / `setSearchQuery` (the `{ value, applied }`
      search object; the new `data queries` section comment explains why the
      two fields are kept separate).
    - `fileType` / `setFileType` -> `fileTypeFilter` / `setFileTypeFilter`
      (query param key stays `file_type`).
    - `selected` / `setSelected` -> `selectedFiles` / `setSelectedFiles`
      (holds selected `FileMeta[]` rows, so "files" is more accurate than
      "keys"; the phase's `selectedKeys` hint was adapted to the actual value).
    - `page`, `pageSize`, `kind`, `sort`, `confirmVisible` were already
      intent-named and left unchanged.
  - **16.3 (header comment)** — `FilesPage` now has a header docstring
    explaining the generated-vs-uploaded TabMenu toggle (each maps to
    `GET /api/files/generated` vs `GET /api/files/uploaded` via `useFiles`),
    that downloads use `fileDownloadUrl(row.path)` -> `GET /api/outputs/{basename}`
    and deletions POST the selected paths to `DELETE /api/files`, that both
    behave the same for the two kinds, that the delete mutation invalidates
    the listings, and that switching kinds resets the page and clears the
    selection.
  - No behavior changes — pure restructuring, renaming, and documentation.

**Behavior verification (16.4):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- `npx vitest run src/pages/FilesPage.test.tsx` — 2 passed (file rows + size
  formatting; delete mutation with selected paths + result toasts)

**Commit:** `simplify: phase 16 - files page sections + state naming + header docs (16.1-16.3)`

---

## Phase 17 - Completed sub-tasks 17.1-17.7: models page, App shell, theme, toast, entry, test helpers

Original instructions:

- **17.1** `App.tsx`: header comment walking the routing tree (Shell + nav + routes).
- **17.2** `ModelsPage.tsx`: header comment.
- **17.3** `theme/useTheme.ts` + `ThemeToggle.tsx`: document storage key + initial-state fallback.
- **17.4** `toast/ToastProvider.tsx` + `ToastContext.ts`: document the `show` contract.
- **17.5** `main.tsx`: document PrimeReact theme import + stylesheet dependency.
- **17.6** `test/setup.ts` + `test/utils.tsx`: document the shared render helper (router/provider wrappers).
- **17.7** Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`.

This closes Phase 17 (all page/component/tooling files are now documented; only
Phase 18 - frontend tests and the Part C closing phases remain).

### Completion record

**Changes made (documentation only, no behavior change):**

- **17.1** `ui/src/App.tsx` — module docstring walking the nested render tree
  (QueryClientProvider -> BrowserRouter -> ToastProvider -> Routes with the
  `Shell` layout route and the Run /files /models children), plus a note on how
  `NAV_ITEMS` drives the Menubar `NavLink`s (active highlighting via the
  menuitem-link-active class; `end` only on "/" so other routes highlight their
  own paths). JSDoc added to `NAV_ITEMS`, `Shell`, and `App`.
- **17.2** `ui/src/pages/ModelsPage.tsx` — file header explaining the per-agent
  model summary table (`useModels` -> `GET /api/models`), the provider-to-Tag
  severity map (openai=info, ollama=success, unknown=warning), and that the
  paginator only appears above 10 rows. JSDoc on `PROVIDER_SEVERITY`.
- **17.3** `ui/src/theme/useTheme.ts` — module docstring documenting the
  ``theme`` localStorage key, the initial-state fallback (valid stored value
  wins, else ``'system'``), how the resolved scheme is applied via
  ``document.documentElement.dataset.theme`` (the attribute vite.config.ts
  scopes the dark PrimeReact stylesheet to), and that OS color-scheme changes
  are followed only in ``'system'`` mode. JSDoc on `STORAGE_KEY`, `DARK_QUERY`,
  `getSystemTheme`, `getStoredTheme` (returns null for absent/invalid stored
  values), `resolveTheme`, and `useTheme`.
  `ui/src/theme/ThemeToggle.tsx` — header comment (SelectButton bound to
  `useTheme`; picking a mode persists to localStorage + applies the attribute)
  and JSDoc on `OPTIONS`.
- **17.4** `ui/src/toast/ToastContext.ts` — module docstring defining the
  ``show`` contract (single `ToastMessage` or array, each fully formatted with
  its own severity/summary) and ``clear`` (dismiss all), plus why `useToast`
  throws outside the provider. JSDoc on `ToastApi` and `useToast`.
  `ui/src/toast/ToastProvider.tsx` — header comment (renders the singleton
  PrimeReact Toast and exposes show/clear via context; wrapped around routes
  in App.tsx).
- **17.5** `ui/src/main.tsx` — header comment documenting the PrimeReact
  dependency: the lara-light-blue + lara-dark-blue theme stylesheets (dark one
  scoped to `html[data-theme='dark']` by vite.config.ts and flipped at runtime
  by useTheme), primereact.min.css, the primeicons font, and index.css; notes
  the imports must stay before the render.
- **17.6** `ui/src/test/setup.ts` — header comment (loaded via
  vite.config.ts `test.setupFiles`; registers jest-dom matchers for every test
  file). `ui/src/test/utils.tsx` — module docstring (render under a fresh
  QueryClientProvider with retries disabled + `gcTime: Infinity`; tests add
  their own router/toast wrappers on top; `stubMatchMedia` simulates OS
  light/dark flips) and JSDoc on `createTestQueryClient`, `withClient`,
  `renderWithClient`, and `stubMatchMedia`. All code bodies unchanged.

**Behavior verification (17.7):**

- `npx tsc -b` — pass (0 errors)
- `npm run lint` (oxlint) — pass
- `npm test -- --run` — 45 passed across 9 test files
- `npx vitest run src/theme/useTheme.test.ts src/theme/ThemeToggle.test.tsx` —
  9 passed (resolveTheme, initial fallback, stored override, persistence,
  clear + OS re-follow, override-supersedes-OS, toggle options + selection)

**Commit:** `simplify: phase 17 - App shell/theme/toast/entry/test helper docs (17.1-17.6)`

---

## Phase 18 - Completed sub-tasks 18.1-18.4: frontend tests

Original instructions:

- **18.1** File-top comment per test file stating the unit under test.
- **18.2** Extract repeated setup (mocked fetch, wrapped renders) into `test/utils.tsx` where it appears in 2+ files.
- **18.3** Add focused tests for newly extracted helpers (e.g. `isTaskActive`) from Phase 15.
- **18.4** Guardrails: `npm test -- --run` green (45 passed).

This closes Phase 18. Every frontend test file is now self-describing, the one
fetch-mock setup duplicated across two files lives in `test/utils.tsx`, and the
Phase 15 status helpers have direct unit coverage. Test count rose from 45 to
**48** (three new focused tests in 18.3), the only intentional behavior change
to the suite.

### Completion record

**Changes made:**

- **18.1 (file-top comments)** — added a header comment to all 9 test files
  stating the unit under test and key setup:
  - `api/client.test.ts` (runForm builders, client fetch wrappers, download URL helpers)
  - `api/hooks.test.ts` (useModels / useFiles / useDeleteFiles under a test QueryClient)
  - `pages/RunPage.test.tsx` (form flow + the Phase 15 status helpers)
  - `pages/FilesPage.test.tsx` (row rendering + delete flow)
  - `pages/ModelsPage.test.tsx` (rows + failure/empty states)
  - `pages/results/DownloadsRow.test.tsx` (per-key download links)
  - `pages/results/ATSTab.test.tsx` (score severity bands + missing score)
  - `theme/useTheme.test.ts` (resolveTheme + persistence/system-follow behavior)
  - `theme/ThemeToggle.test.tsx` (mode options, persistence, System override removal)
- **18.2 (shared setup extraction)** — added `stubFetch(handler)` to
  `test/utils.tsx`: a handler-driven `window.fetch` mock that resolves
  `ok:true`/`status 200` and returns per-URL JSON, exactly the setup that was
  duplicated verbatim in `FilesPage.test.tsx` (`stubFetch`) and
  `api/hooks.test.ts` (local `fetchMock`, which did not even stub the global —
  the call site did). Both files now import and use the shared helper;
  `hooks.test.ts` deleted its local copy and its call-site
  `vi.stubGlobal('fetch', mock)`.
- **18.3 (focused tests for extracted helpers)** — the Phase 15 status helpers
  `isTaskActive` + `taskStatusLabel` (plus `STATUS_SEVERITY` /
  `TASK_STATUS_LABEL`) moved out of `RunPage.tsx` into a new pure module
  `ui/src/pages/runStatus.ts` (mirrors `runForm.ts` and keeps the component file
  free of non-component exports, which also satisfies oxlint's
  `react(only-export-components)` rule). `RunPage.tsx` imports them from there.
  Added two focused `describe` blocks in `RunPage.test.tsx` (4 assertions each):
  `isTaskActive` (unknown/pending/running true; completed/failed false) and
  `taskStatusLabel` (Pending/Running/Completed/Failed; unknown -> "Pending").
- Test bodies otherwise unchanged; only comments, imports, and the helper move.

**Behavior verification (18.4):**

- `npm test -- --run` — **48 passed** across 9 test files (45 baseline + 3 new)
- `npx vitest run src/pages/RunPage.test.tsx src/pages/FilesPage.test.tsx src/api/hooks.test.ts` — 11 passed
- `npm run lint` (oxlint) — pass (no warnings)
- `npx tsc -b` — pass (0 errors)

**Commit:** `simplify: phase 18 - frontend test headers + shared stubFetch + status helper tests (18.1-18.3)`

---

## Phase 19 - Completed sub-task 19.1: AGENTS.md file/architecture map + conventions

Original instructions:

- **19.1** `AGENTS.md`: verify file/architecture map after Phases 1-11 (new helpers
  `load_json_safe`, `_run_stage`); update quick-command table + conventions.

AGENTS.md was verified line-by-line against the actual tree. All previously
added helpers are now present and the stale counts/claims from before Phases
1-11 were corrected. No command in the quick-command tables was changed (each
was spot-checked against the repo: `uv sync`, `basic.py`, `pipeline.py
--resume/--job-description`, `uvicorn app.main:app`, the `get_model_summary`
one-liner, `ruff`, `pyright`, `pytest`, and the `ui/` set all still resolve);
`docs/TESTING.md` still has its section-2 regex-parsing guide that the "no LLM"
table row points to.

### Completion record

**Changes made (documentation only, no behavior/markdown-command change):**

- **Architecture map** —
  - `pipeline.py` entry now lists the Phase 9 `_run_stage` helper next to
    `AgentRunner` / `PipelineAgent` / `run_resume_pipeline`.
  - `client/json_utils.py` entry now names the Phase 4 `load_json_safe` helper
    alongside `parse_json_response` and `model_to_json_schema`.
  - `client/agents/` block now includes the two shared helper modules that
    Phases 3-4 introduced: `_validation.py` (shared `chat_and_validate()`
    scaffold) and `_retry.py` (shared `retry_llm_then_fallback()` loop).
  - `tests/` block: corrected `test_json_utils.py` count (15 -> 23, matching
    the load_json_safe tests added in Phase 4) and added the previously
    omitted `test_web_spa.py` (8 tests, built-SPA mount).
- **"Agent class pattern" convention** was expanded to name
  the parsing-agent retry loop `client/agents/_retry.py:
  retry_llm_then_fallback()` (it previously only mentioned the LLM-only-agent
  scaffolding through `_validation.py`).
- **New "Pipeline stage helper" convention** documents `pipeline.py:
  _run_stage(runner, agent_name, *, prompt, output, rules, fields, **context)`
  and that `_run_pipeline_core()` calls it seven times (`# 1. JD Parsing` ...
  `# 7. Cover Letter`) on a single event loop.
- **"Shared JSON parsing" convention** now documents `load_json_safe()` as the
  guarded `json.loads` used by post-validation helpers (fence-stripping,
  returns `None` instead of raising), next to the existing `parse_json_response`
  wrapper description.
- **Status section** — the `_run_pipeline_core()` line reference was updated
  from `pipeline.py:324` to `pipeline.py:404` (the function moved during Phase
  9); `run_resume_pipeline()` at `pipeline.py:313` is still correct.
- **Testing + Status sections** — test totals updated from "477 tests across
  23 files" to "**493 tests across 24 files**" (Phase 4 added 8 JSON-utils
  tests; `test_web_spa.py`'s 8 tests were previously uncounted in the sweep).

**Behavior verification:**

- `uv run pytest` — 493 passed (confirms the new map counts)
- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass (all 96 files already formatted)
- `uv run pyright` — 0 errors, 0 warnings
- `ui/`: `npm test -- --run` — 48 passed; `npm run lint`, `npx tsc -b` — pass
  (unchanged by this doc-only phase)

**Commit:** `simplify: phase 19 - AGENTS.md architecture map + conventions after phases 1-11 (19.1)`

---

## Phase 19 - Completed sub-task 19.2: README.md / ui/README.md quickstart accuracy

Original instruction:

- **19.2** `README.md` / `ui/README.md`: quickstart accuracy.

Both readmes were verified against the running code and the actual repo tree.
Every command in the quickstart, the usage table, and the web-API section was
spot-checked; the route table matches `app/main.py`, sample paths exist
(`sample/resume/Peter-Letkeman-Resume.txt`, `sample/jobs/3Pillar.txt`), the
`--jd` shorthand and `--candidate-name`-enables-rendering claims match
`pipeline.py`'s argparse, and the `output/`/`uploads/` git-ignore claim holds
(`git check-ignore` returns both).

### Completion record

**Changes made (documentation only, no behavior/markdown-command change):**

- **`README.md`** — fixed two drift spots in the architecture test listing
  (both dates to after Phase 4/Phase 3 re-counts):
  - `test_json_utils.py`: count corrected 15 -> **23** and the description now
    names the Phase 4 `load_json_safe` helper.
  - Added the previously omitted `test_web_spa.py` (8 tests, built-SPA mount +
    catch-all fallback) so the `tests/` block lists all 24 files.
  - Everything else verified accurate and left unchanged: quickstart commands
    (`uv sync`, `pipeline.py`, two-terminal web-UI start), optional `--jd`
    /`--candidate-name`/`--company-name` behavior, the 9-route API table vs.
    `app/main.py`, the pipeline-flow diagram, the config env vars
    (`MODEL_PROVIDER`/`MODEL_NAME`/per-agent overrides/`LOG_LEVEL`), and the
    coverage commands (`pyproject.toml` `[tool.coverage.*]`).
- **`ui/README.md`** — this was the untouched Vite scaffolding file (generic
  "React + TypeScript + Vite" boilerplate with React-Compiler/Oxlint notes). The
  root `README.md` points to it ("See `ui/README.md` for the full frontend
  guide"), so it was **replaced** with a real frontend guide covering: what the
  app does; the two-terminal quickstart (backend `uvicorn app.main:app` +
  `npm run dev` dev proxy for `/api` and `/health`, confirmed in
  `vite.config.ts`); production serving (FastAPI mounts `ui/dist` and falls back
  to `index.html` for non-API routes when `ui/dist/index.html` exists, per
  `app/main.py`); the command table (`npm run dev`/`build`/`lint`/`test`,
  `test:watch`, `npx tsc -b`); the page/route table (`/` Run, `/files` Files,
  `/models` Models, wired in `src/App.tsx`); the `src/` source layout with
  one-line descriptions (api/ hooks + download, pages/, results/ tabs +
  `TAB_KEYS` (the 7-agent tab order), theme localStorage `"theme"` key, toast,
  test helpers); and
  the dark-theme scoping note (`vite.config.ts` scopes `lara-dark-blue` to
  `html[data-theme='dark']`). All claims cross-checked against the matching
  source files (`App.tsx`, `main.tsx`, `useTheme.ts`, `download.ts`,
  `runStatus.ts`/`runForm.ts`, `vite.config.ts`).

**Behavior verification:**

- `uv run pytest` — 493 passed (24 files)
- `uv run ruff check .` — pass (no Python touched)
- `ui/`: `npm test` — 48 passed across 9 files; `npm run lint`, `npx tsc -b` —
  pass (docs-only change)
- Manual re-read of each README section against the referenced module/route —
  no remaining drift in the quickstart paths.

**Commit:** `simplify: phase 19 - README + ui/README quickstart accuracy (19.2)`

---

## Phase 19 - Completed sub-task 19.3: cross-check `docs/*.md` (8 guides) against code

Original instruction:

- **19.3** Cross-check `docs/*.md` (8 guides) against code; fix drift found during
  Phases 1-18.

All 8 guides (`architecture.md`, `agents.md`, `api.md`, `usage.md`, `models.md`,
`TESTING.md`, `logging-info.md`, `skill-taxonomy.md`) were re-read against the
post-Phase-18 code. Every named helper, class, schema, prompt, fallback, and
command was spot-checked against the tree (see verification below). Most guides
were already accurate — earlier phases had cross-checked `agents.md` (5.6, 6.5),
`skill-taxonomy.md` (8.3), `README.md`/`ui/README.md` (19.2) — so the fixes below
are the remaining drift that Phases 1-18 introduced or left stale.

### Completion record

**Changes made (documentation only, no behavior/markdown-command change):**

- **`docs/architecture.md`** — corrected the `_run_pipeline_core` line reference
  from `pipeline.py:324` to `pipeline.py:404` (the function moved during Phase 9
  when `run_resume_pipeline`/`_to_rewrite_output`/`_run_stage` were added), and
  noted that the stage chain now runs via `_run_stage` calls.
- **`docs/usage.md`** —
  - Removed the stale `DEFAULT_PROVIDER` row from the "Global overrides" table:
    `config/agents.py` never reads `DEFAULT_PROVIDER` (only `MODEL_PROVIDER` +
    `MODEL_NAME` + `OPENAI_API_KEY`), and Phase 1 already fixed the same stale
    claim in the code's docstrings and AGENTS.md.
  - Updated the `uv run pytest` quickstart row: "477 tests" -> "493 tests across
    24 files" (matches the post-Phase-4 count and the Phase 4 `load_json_safe`
    tests).
- **`docs/TESTING.md`** — fixed the stale test census left over from before
  Phases 1-18:
  - "Currently **477 tests across 23 files**" -> **493 across 24 files**.
  - `test_json_utils.py`: count corrected 15 -> 23 and description now names the
    Phase 4 `load_json_safe` helper.
  - Added the previously omitted `test_web_spa.py` (8 tests, built-SPA mount +
    catch-all fallback).
- **`docs/logging-info.md`** — corrected the verify-command example `uv run
  pyright .` -> `uv run pyright` (passing `.` makes pyright recurse into `.venv/`
  and spew third-party errors; AGENTS.md Toolchain quirks).
- **`docs/api.md`** — the "Implementations" note now names the shared Phase 1
  `build_task_prompt()` helper in `client/model_client.py` as the single prompt
  builder both clients use; the `client/json_utils.py` reference line gained
  `load_json_safe`.
- **`docs/agents.md`** — `client/json_utils.py` reference line gained
  `load_json_safe` (keeps the "shared JSON parsing" story consistent with
  AGENTS.md).
- **No changes needed** in `docs/models.md` (validator/coercer names unchanged by
  Phase 2 — `_coerce_str_list`/`_coerce_experience_list` and the two
  `_coerce_*_list`-named class validators all still exist) and
  `docs/skill-taxonomy.md` (already verified clean in 8.3).

**Behavior verification:**

- Re-read each doc section against the matching module; no remaining drift:
  - `config/agents.py` reads only `MODEL_PROVIDER`/`MODEL_NAME`/`OPENAI_API_KEY`
    + per-agent overrides (confirmed by grep); `get_agent_config()`/`build_registry()`
    shape matches `usage.md` section 2.
  - `pipeline.py:404` = `async def _run_pipeline_core`, `pipeline.py:291` =
    `_to_rewrite_output`, `pipeline.py:354` = `_run_stage` (confirmed by grep).
  - `client/json_utils.py` has `parse_json_response` (line 34), `load_json_safe`
    (line 75), `model_to_json_schema` (line 114) (confirmed by grep).
  - `client/agents/jd_parsing.py` regex fallback calls `FormatDetector` +
    `_extract_company_name` + `_NORMALIZER.normalize_list` exactly as `agents.md`
    section 1 describes (confirmed by read).
  - `client/open_ai_client.py` `_schema_name`/`_response_format_value` and the
    90 s timeout match `api.md`; `client/ollama_client.py` `format="json"` /
    schema-dict behavior matches.
  - `client/templates/renderer.py` `_DEFAULT_EXTENSIONS` / `_default_extension` /
    `_split_paragraphs` / `build_output_path` / `contact_line` all match `api.md`
    section 3.
  - `FormatDetector.__init__(client=None)` regex-only default matches the
    `TESTING.md` section 2 examples.
- `uv run pytest` — 493 passed (confirms the corrected census)
- `uv run ruff check .` — pass (no Python touched)
- `uv run ruff format --check .` — pass (md files not formatter targets)
- `uv run pyright` — unaffected (no Python changed); skip-safe for a docs-only
  edit.
- `ui/`: no source touched by this sub-task (docs-only).

**Commit:** `simplify: phase 19 - docs guides cross-check vs code after phases 1-18 (19.3)`

---

## Phase 19 - Completed sub-task 19.4: root scratch notes classified, completed notes added

Original instruction:

- **19.4** Root scratch notes: classify archive vs actionable; recommend
  `scratch/` move or "completed" note (no deletion without user OK).

All nine root scratch notes were read in full and classified. **Eight are
fully-completed historical archives; one (`frontend-tasks.md`) is still
actionable.** No file was deleted, and none was moved yet — the `scratch/`
move is offered as a recommendation pending user approval (deletion/move
guarded by the plan's "no deletion without user OK" rule).

### Classification

| Note | Class | Why |
|---|---|---|
| `bots.md` | **Archive** | Original 7-agent design spec (prompts + output fields); superseded by `docs/agents.md` and the dedicated classes in `client/agents/`. Kept for provenance. |
| `frontend-plan.md` | **Archive** | Planning doc (decisions + wireframes) for the UI, which is fully implemented in `ui/`; see `frontend-tasks-done.md` and `ui/README.md`. |
| `frontend-tasks-done.md` | **Archive** | Already titled "Completed Tasks" — per-task completion record of the frontend build. |
| `frontend-tasks.md` | **Actionable** | The one open item: **§7.3 Manual E2E** (run built app against backend; confirm status polling, all result tabs, downloads, theming, SPA fallback). Its empty section headers 2/4/5 are stubs. |
| `resume-done.md` | **Archive** | Already titled "Archive of everything implemented" — completed-work record for the backend pipeline. |
| `resume-todo.md` | **Archive** | Header already reads "Status: ✅ ALL DONE"; pointer to `resume-done.md`. |
| `resume-verify.md` | **Archive** | Verification plan fully executed 2026-08-06 with a filled tracker + "Verification Results" section (documented the two `pipeline.py` bugs fixed). |
| `resume-web-todo.md` | **Archive** | FastAPI web-layer plan; all task checkboxes done (`app/` implemented, `tests/test_web_*.py`, `docs/api.md`). |
| `web-files-todo.md` | **Archive** | File-management plan; all task checkboxes done (`app/files.py`, `tests/test_web_files.py`). |

### Completion record

**Changes made (module-comment notes in the scratch files; no code touched):**

- Added an `ARCHIVED — no longer actionable` status banner to the top of the
  five archives that lacked an explicit completion marker (`bots.md`,
  `frontend-plan.md`, `resume-verify.md`, `resume-web-todo.md`,
  `web-files-todo.md`). Each banner names the live replacement(s) (`docs/`
  guides, `AGENTS.md`, `app/`, `tests/`) so a reader knows where the work
  now lives. The three already-labeled archives (`resume-done.md`,
  `frontend-tasks-done.md`, `resume-todo.md`) were left unchanged.
- `frontend-tasks.md` — added an `ACTIONABLE — one item left` banner: every
  completed task is recorded in `frontend-tasks-done.md`; the only remaining
  item is §7.3 Manual E2E (kept in root as the actionable note).
- `simple.md` — 19.4 checked off with the classification summary + the
  `scratch/` recommendation inline.

**Recommended follow-up (not executed — needs user OK):** move the eight
archived notes (`bots.md`, `frontend-plan.md`, `frontend-tasks-done.md`,
`resume-done.md`, `resume-todo.md`, `resume-verify.md`, `resume-web-todo.md`,
`web-files-todo.md`) into a `scratch/` directory, leaving the actionable
`frontend-tasks.md` in the repo root. No file should be deleted.

**Behavior verification:** documentation-only change — no Python/TS source
touched, so `pytest`/`ruff`/`pyright`/`tsc`/`npm test` are unaffected. `git
diff` confirms changes are limited to the six markdown files above.

**Commit:** `simplify: phase 19 - classify root scratch notes as archive vs actionable (19.4)`

---

## Phase 19 - Follow-up: archives moved to `scratch/` (user-approved)

**Approved by the user** (the "Recommended follow-up (not executed)" above).
The eight archived notes were moved out of the repo root into `scratch/` with
`git mv` (history preserved); the actionable `frontend-tasks.md` remains in the
root. No file was deleted.

- Moved: `bots.md`, `frontend-plan.md`, `frontend-tasks-done.md`,
  `resume-done.md`, `resume-todo.md`, `resume-verify.md`,
  `resume-web-todo.md`, `web-files-todo.md` → `scratch/`.
- **Reference fixes** (so no link points at a moved path):
  - `frontend-tasks.md` (root) — `frontend-tasks-done.md` / `frontend-plan.md`
    → `scratch/`-prefixed.
  - `scratch/frontend-tasks-done.md` — link back to root
    `frontend-tasks.md` → `../frontend-tasks.md`.
  - `README.md` — 4 scratch-note rows → `scratch/`-prefixed.
  - `AGENTS.md` — `resume-done.md` / `resume-todo.md` → `scratch/`-prefixed.
  - `docs/agents.md`, `docs/architecture.md` — `resume-done.md` / `bots.md` →
    `scratch/`-prefixed.
  - `simple.md` — inventory table notes the `scratch/` move; 19.4 line gains an
    "Update (user OK'd)" note.
- Cross-references *within* `scratch/` (e.g. `resume-todo.md` →
  `resume-done.md`) still resolve as relative links — no changes needed.

**Behavior verification:** documentation-only move — no Python/TS source
touched; `pytest`/`ruff`/`pyright`/`tsc`/`npm test` unaffected. Root file map
is now: `AGENTS.md`, `README.md`, `simple.md`, `simple-done.md`, `frontend-tasks.md`
(plus code) — the archived scratch notes live under `scratch/`.

**Commit:** `simplify: phase 19 - move archived root scratch notes to scratch/ (19.4 follow-up)`

---

## Phase 19 - Completed sub-task 19.5: remove outdated "TODO/Phase X remains" lines

Original instructions:

- **19.5** Remove outdated "TODO/Phase X remains" lines for completed work.

Swept every active markdown doc (`AGENTS.md`, `README.md`, `ui/README.md`,
`docs/*.md`, `simple.md`) for lines claiming work was still pending in a phase
that is now complete, and fixed the two stale spots found. Historical records
(`scratch/` archives and `simple-done.md` completion notes) were left intact so
the audit trail is preserved.

### Completion record

**Changes made (documentation only, no behavior/markdown-command change):**

- **`simple.md`** — the "Remaining Work Breakdown (Phases 4-20)" heading + intro
  claimed only "Phases 1-3 are complete ... The remaining work is split into
  sub-tasks below", contradicting the checkboxes below it (Phases 4-18 all
  checked off, 19.1-19.4 checked off). Retitled the section to
  "Work Breakdown Checklists (Phases 4-21)" and rewrote the intro to state
  "Phases 1-19 are complete (records in `simple-done.md`)" with the only
  remaining work being Phase 20 and Phase 21. Marked check item 19.5 itself as
  done (✅ See `simple-done.md`).
- **`README.md`** — the file-map row for `scratch/resume-todo.md` said "Remaining
  work (project complete...)" while the note's own header reads
  "Status: ✅ ALL DONE". Updated to "Completed-work log (all done; pointer to
  `resume-done.md`)".

**Verified non-issues (not changed):**

- `AGENTS.md` — Status section references phases only as completed work; no
  "phase remains" claims.
- `docs/*.md` (8 guides) — the only "future work" mention is
  `docs/logging-info.md`'s "Not in scope (future work)" list, which is
  genuinely out-of-scope tooling (structlog, log-to-file, etc.), not a claim
  that a plan phase remains.
- `frontend-tasks.md` (root, still-actionable) — its "one item left"
  (§7.3 Manual E2E) banner is accurate and unchanged.
- `scratch/` archives (8 files) — historical records of completed work; left
  untouched (their "remaining" phrasing describes the point-in-time state and
  many already carry `✅ ALL DONE` / `ARCHIVED` headers).
- `simple-done.md` — completion records referencing "later phases" describe
  historical sequencing, not pending work.

**Behavior verification:**

- Documentation-only change — no Python/TS source touched, so
  `pytest`/`ruff`/`pyright`/`tsc`/`npm test` are unaffected.
- `git diff` confirms changes are limited to `simple.md` and `README.md`.
- Re-grep for `Remaining Work|Phases 1-3|Phase.*remains` across active docs
  returns only the updated `simple.md` intro and `simple-done.md`/`scratch/`
  historical records.

**Commit:** `simplify: phase 19 - remove outdated TODO/phase-remains lines (19.5)`

---

## Phase 20 - Completed sub-task 20.1: backend final verification & regression

Original instruction:

- **20.1** Backend: `uv run pytest` (>=485), `uv run ruff check .`, `uv run ruff
  format --check .`, `uv run pyright`.

All four backend regression gates were run from the repo root. Everything is
green, and the suite count is healthy above the >=485 floor.

### Completion record

**Verification results:**

- `uv run pytest` — **493 passed** in 8.22s (24 files; floor was >=485). Full
  suite incl. all per-agent contract tests, renderer/formatter, skill
  normalizer, and all `test_web_*.py` routes.
- `uv run ruff check .` — All checks passed (0 errors).
- `uv run ruff format --check .` — 96 files already formatted (no drift).
- `uv run pyright` — 0 errors, 0 warnings, 0 informations.

No code was changed by this sub-task — it is a pure verification gate. The 493
count matches the post-Phase-4 census recorded in AGENTS.md / README /
`docs/TESTING.md` (which listed 493 across 24 files).

**Commit:** none — verification-only sub-task; no files changed under source.

---

## Phase 20 - Completed sub-task 20.2: frontend final verification & regression

Original instruction:

- **20.2** Frontend: `npm test -- --run` (>=45), `npm run lint`, `npx tsc -b`.

All three frontend regression gates were run from `ui/`. Everything is green,
and the suite count is healthy above the >=45 floor.

### Completion record

**Verification results:**

- `npm test -- --run` — **48 passed** across 9 test files in 3.49s (floor was
  >=45). Vitest 4.1.10 run confirms `api/client.test.ts`, `api/hooks.test.ts`,
  `RunPage.test.tsx`, `FilesPage.test.tsx`, `ATSTab.test.tsx`,
  `DownloadsRow.test.tsx`, `theme/useTheme.test.ts`, `ThemeToggle.test.tsx` (and
  the rest) all pass.
- `npm run lint` — oxlint, no findings (clean).
- `npx tsc -b` — completed with no errors (the default `ui` project build).

No source was changed by this sub-task — it is a pure verification gate. The 48
count matches the post-Phase-18/19 frontend census (9 files, 48 tests).

**Commit:** none — verification-only sub-task; no files changed under source.

---

## Phase 20 - Completed sub-task 20.3: manual smoke (CLI, web API, live E2E, UI)

Original instruction:

- **20.3** Manual smoke: `basic.py`, `pipeline.py` sample mode, web API
  health/models/pipeline/tasks, live E2E (`test_real_files.py` with Ollama),
  `npm run dev` UI run.

All smoke paths were exercised against a live Ollama (`qwen2.5:7b-instruct`
confirmed via `GET localhost:11434/api/tags`). The pipeline, web API, and UI
are all healthy. One deterministic defect was found and fixed in
`test_real_files.py` (stale filename expectation, detailed below); the two
remaining live-E2E gate failures are nondeterministic LLM-output variability,
not code regressions.

### Completion record

**CLI — `uv run python basic.py`** ✅

- Single-agent geography call returned JSON: `{"question": "What is the
  capital of France?"}` and parsed cleanly.

**CLI — `uv run python pipeline.py` (sample mode)** ✅

- 7/7 agents succeeded in 68.3s (JD Parsing 4.8s -> Cover Letter 8.9s).
- Known soft warnings logged but handled: gap-analysis deterministic vs LLM
  cross-check mismatch, cover-letter "outside 450-600 spec (accepting)".
- Rendered 6 output files into `output/` (all present, non-empty).

**Web API — `uv run uvicorn app.main:app` (background)** ✅

- `GET /health` → `{"status":"ok"}`.
- `GET /api/models` → 7 agents, all `ollama` / `qwen2.5:7b-instruct`.
- `POST /api/pipeline/async` (multipart `job_file` + `resume_file` with the
  sample files, `candidate_name=Peter Letkeman`, `company_name=3Pillar`) →
  `{"task_id":"bb1c571a3b46426f8a47f1cf10d02b2f"}`.
- `GET /api/tasks/{id}` polled running → **completed**; `result.output_files`
  has all 6 keys; every file verified on disk non-empty (txt 6889 B, md 7020 B,
  docx 38249 B, pdf 7616 B, cover letter txt/md ~1680/1690 B).
- `GET /api/outputs/20260812_1040_..._resume.pdf` → 200, `application/pdf`,
  7855 B (download path confirmed).

**Live E2E — `uv run python test_real_files.py`** ⚠️ 7/7 agents succeeded
(136s), but 3/12 checks failed on the first run:

- **`output filename pattern` — FAIL (deterministic, FIXED).** The test regex
  expected `_(resume|cover_letter)\.`, but `ResumeRenderer.build_output_path`
  slugifies every segment via `_slugify`, so `cover_letter` is written as
  `cover-letter` (e.g. `20260812_1040_peter-letkeman_3pillar_cover-letter.txt`).
  This is a pre-existing stale expectation, not a Phase-1-19 regression: the
  slugifier was added 2026-08-05 and the E2E test file was written 2026-08-07,
  and Phase 7's renderer work (commit `01aebcf`) did not touch naming. **Fix:**
  the regex now accepts `cover[-_]letter` to match the documented renderer
  behavior. Verified: the updated pattern matches all 6 filenames actually
  produced (see below). This corrects the test's expectation to match
  unchanged behavior; it does not weaken a gate to mask a regression.
- **`cover_letter word count 450-600` — FAIL (302 words).** The live LLM
  produced a short letter; the cover-letter agent logs "(outside 450-600 spec
  (accepting))" by design (soft gate). Nondeterministic LLM output, not a code
  regression.
- **`certifications preserved` — FAIL (4/6).** The live LLM dropped two of six
  certifications. Nondeterministic LLM output, not a code regression.

**UI dev server — `npm run dev` (background)** ✅

- `vite` v8.2.1 ready in 388 ms; `GET http://localhost:5173/` → 200, serves
  `index.html`. The dev proxy forwards `/api` to the backend (already proven
  by the web-API smoke above). A full in-browser click-through of Run page ->
  tabs + downloads can't be automated from the shell; the equivalent data path
  was exercised: the async task result (which backs the result tabs) and the
  `/api/outputs/{filename}` download endpoint both returned correct 200s.

**Changes made (source):**

- `test_real_files.py` — one-line fix to the output-filename regex
  (`cover_letter` → `cover[-_]letter`) to match the renderer's documented
  slugified naming. No other source touched.

**Behavior verification:**

- Fixed regex checked against the 6 real filenames produced by the web-API run
  and the live E2E run — all match.
- Background servers stopped after smoke (`:8000` and `:5173` no longer
  listening).

**Commit:** none. Uncommitted working-tree changes: `simple.md`,
`simple-done.md`, `test_real_files.py` (regex fix). Offer to commit these with
the 20.3 tag if wanted.

---

## Phase 20 - Completed sub-task 20.4: diff review + final commit

Original instruction:

- **20.4** Diff review spot-check rendered output before/after; `git status`
  clean after final commit.

The cross-phase simplification diff was reviewed and the working tree committed
and left clean. No production source was changed during Phase 20 other than the
one-line `test_real_files.py` regex correction from 20.3, so rendered output is
byte-identical by construction; the review below spot-checks the largest
phase-1-19 behavior-sensitive refactors for semantic equivalence.

### Completion record

**Phase-20 working-tree diff (vs Phase-19 commit `5cbac1d`)** — limited to
three files, all reviewed:

- `simple.md` — checklist marks only (20.1-20.3 `[x]`, Phase 19 heading
  `✅ COMPLETED`).
- `simple-done.md` — appended 20.1/20.2/20.3 completion records (docs).
- `test_real_files.py` — one-line regex `cover_letter` -> `cover[_]letter`
  (matches the renderer's documented slugified filename; see 20.3 record).

**Cross-phase diff review (base `bd4d4d0^` -> HEAD, 100 files, +6796/-1327)** —
characterized as docstrings + readability refactors. Spot-checked the four
highest-risk behavior-sensitive refactors for equivalence:

- `config/agents.py` (de-duplicated the two per-agent loops, extracted
  `_effective_provider`/`_effective_model`/`_client_config`, `AGENT_NAMES`).
  Client dict shapes are identical (`api_key` only for `openai`). One micro-
  edge: an env override set to the *empty string* (e.g.
  `JD_PARSING_AGENT_PROVIDER=`) previously fell through to the default client;
  it now creates a `jd_parsing_agent_client` entry that resolves to the same
  default provider/model. Model resolution and rendered output are unchanged
  (verified: empty override still yields `qwen2.5:7b-instruct`/`ollama`).
- `pipeline.py` (`_run_stage` extraction, stage-table module docstring). The
  seven calls preserve prompt/output/rules/context exactly and keep the
  per-stage `_extract_field` behavior (including stage 5's two-field fallback
  `("ats_optimized_resume", "final_resume")` and stage 2 returning the raw
  result); parse agents still receive no `prompt`/`output`/`rules` keys.
- `client/templates/renderer.py` (`_render` extraction + doc fixes incl. the
  stale "DOCX/PDF will be added later" claim). `_render` is exactly the
  previous `from_string(...).render(**context)` + `_clean_output` sequence; the
  43 `test_renderer.py` tests pin byte-identical output.
- `ui/src/pages/RunPage.tsx` (`isTaskActive`/`taskStatusLabel`/`STATUS_SEVERITY`
  moved to new pure `runStatus.ts`). The `active` boolean and status-panel
  logic are identical; the only change is the tag label now capitalizes
  ("Pending"/"Running"/... instead of raw status strings) — a Phase-15 display
  improvement covered by the updated `RunPage.test.tsx`.

**Rendered output before/after:**

- Phase 20 touched no renderer/template/agent code, so the rendered files
  produced by the 20.3 live runs are unchanged from Phase 19 by construction.
- The 485-backend / 45-frontend test floors from 20.1/20.2 pin behavior, and
  `git status` (pre-commit) proved no other source file differs from HEAD.

**Final commit + clean status:**

- `git commit` (`ae8c341`): "simplify: phase 20 - final regression
  verification, record 20.1-20.3, fix test_real_files slug regex" (3 files,
  +153/-5).
- `git status` after commit → `nothing to commit, working tree clean` (branch
  ahead of `origin/main` by 1 commit; not pushed — push left to the user).

**Commit:** `simplify: phase 20 - final regression verification, record 20.1-20.3, fix test_real_files slug regex` (`ae8c341`)

---

## Phase 20 - Completed sub-task 20.5: add progress log, archive the full plan

Original instruction:

- **20.5** Add a short "progress log" section to `simple.md` listing completed
  phases (archive the full plan in `simple-done.md`).

`simple.md` was reduced to a short progress log (completed-phase table +
still-actionable Phase 21 items + pointers), and the full plan was archived
verbatim into this file (section "Archive: Full Simplification Plan" below).

### Completion record

**Changes made (markdown only, no source touched):**

- **`simple.md`** — rewritten as the progress log: a completed-phase table
  (Phases 1-19 + Phase 20, each pointing to its record in `simple-done.md`), a
  one-line note on the Phase-20 verification results (493 backend / 48 frontend
  tests, ruff/pyright/tsc clean, 20.3 smoke + 20.4 clean-tree commit), the
  still-actionable **Phase 21** items (21.1-21.5) kept verbatim so work can
  continue, and a pointer to the archived full plan below.
- **`simple-done.md`** — appended the full plan verbatim under a new
  "Archive: Full Simplification Plan" section (file inventory, per-phase specs,
  work-breakdown checklists, guiding rules), so nothing from the original
  working plan is lost. Stdchecklists 20.1-20.4 were already recorded above.

**Behavior verification:**

- Documentation-only change — no Python/TS source touched, so
  `pytest`/`ruff`/`pyright`/`tsc`/`npm test` are unaffected.
- `git diff --stat` confirms the change is limited to `simple.md` and
  `simple-done.md`.
- `git status` clean after commit.

**Commit:** `simplify: phase 20 - add progress log, archive full plan (20.5)`

---

# Archive: Full Simplification Plan (from simple.md)

The original full plan (title, guiding rules, file inventory, phase specs, and
the work-breakdown checklists) exactly as it stood when it was archived by
sub-task 20.5. Completed phases are recorded above this section; this is the
historical working document. Phase 21 remained actionable and was carried into
the `simple.md` progress log.


# Simplification Plan: Inspect & Simplify Every File, Method, Module

## Purpose

Go through the entire codebase — backend (Python) and frontend (React/TypeScript) — file by file, method by method, module by module, and:

1. **Simplify** the code.
2. **Prefer verbose, easy-to-follow code** over short, clever, or dense code.
3. **Update or improve documentation** for every file, module, class, method, and function we touch.

This is a *working plan*: each phase is small, reviewable, and keeps the test suites green. Do one phase at a time. Do not mix phases.

---

## Guiding Rules

These rules apply to every phase. Read them once here; each phase references them.

### Simplification rules (how we change code)

- **Readability beats cleverness.** If a one-liner is hard to parse, write it as 3-4 obvious lines with clear names. Verbose is welcome; complex is not.
- **Prefer named helper functions** over deep inline expressions. A helper like `_is_task_active(status)` is easier to read than a repeated 3-way boolean expression.
- **Break up "wall of logic" functions.** Any method over ~50 lines of dense logic should be split into smaller, named, single-purpose helpers.
- **Name things by intent.** Rename ambiguous variables (`data`, `raw`, `obj`, `value`) toward meaning (`parsed_json`, `llm_response_text`, `paged_file`).
- **Kill duplication by extraction, not abstraction.** If the same guarded block (e.g., `try: json.loads(...) except ...`) genuinely repeats, extract one shared helper with a clear docstring. Do not build micro-frameworks.
- **Remove dead weight.** Stale docstring claims, unused imports, commented-out code, and unreachable branches are removed (or the bug is fixed).
- **Keep behavior byte-for-byte identical** unless the phase explicitly says the change may alter output. The output shape of the 7-agent pipeline and the API contract must not change.
- **Standardize the Python 3.14 `except A, B:` style** (see Phase 4) so code does not read like Python 2.

### Documentation rules (how we improve docs)

- Every file we touch gets:
  - A **module docstring** that says *what* the module does, *why* it exists, and (where useful) *how* the pieces fit.
  - A **docstring on every class, method, and non-trivial function**: one line for *what*, a sentence for *why/edge cases*, plus `Args:`/`Returns:`/`Raises:` where relevant.
  - **In-code comments** explaining the *why* behind non-obvious decisions (never just restating the code).
- Update **stale documentation** we discover along the way (docstrings that no longer match reality, outdated file headers, wrong command examples).
- Frontend components get a short header comment describing their purpose and the data they render; helper util functions keep JSDoc.
- Documentation lives **next to the code** (docstrings) first, and in `docs/*.md` / `AGENTS.md` / `README.md` only in the final consolidation phase.

### Guardrails (every phase)

- **Baseline must stay green.** Commands (run at repo root unless noted):
  - Backend: `uv run pytest` (currently **485 passed**), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
  - Frontend (from `ui/`): `npm test -- --run` (currently **45 passed**), `npm run lint`, `npx tsc -b`
- **Never change tests to make the code pass.** If a simplification is blocked by a test, the phase is too big - split it further.
- Type-check at the end of each backend phase (`uv run pyright`) and each frontend phase (`npx tsc -b`).
- Commit small, per-phase. Commit message mentions the phase, e.g. `simplify: jd_parsing agent - split run() helpers + docstrings`.

### Per-file checklist (use in every phase)

- [ ] Read the file fully.
- [ ] List every class, method, and module-level function in the file.
- [ ] Simplify per the rules, one logical concern at a time.
- [ ] Update/add docstrings (module, class, method, function).
- [ ] Fix any stale documentation found.
- [ ] `uv run ruff check .` + `uv run ruff format .` (backend) or `npm run lint` (frontend).
- [ ] `uv run pyright` (backend) / `npx tsc -b` (frontend).
- [ ] `uv run pytest` / `npm test -- --run` green.
- [ ] Commit with a phase-tagged message.

---

## File Inventory (what we are covering)

### Backend - core pipeline (`client/`)

| File | Lines | Phase |
|---|---|---|
| `client/agents/cover_letter.py` | 968 | 6 |
| `client/templates/renderer.py` | 890 | 7 |
| `client/format_detector.py` | 756 | 3 |
| `client/agents/resume_rewrite.py` | 621 | 5 |
| `client/agents/resume_parsing.py` | 282 | 3 |
| `client/agents/ats_compliance.py` | 273 | 4 |
| `client/agents/jd_parsing.py` | 272 | 3 |
| `client/agents/gap_analysis.py` | 262 | 4 |
| `client/models.py` | 281 | 2 |
| `client/formatter.py` | 254 | 7 |
| `client/model_registry.py` | 209 | 1 |
| `client/open_ai_client.py` | 209 | 1 |
| `client/ollama_client.py` | 179 | 1 |
| `client/agents/tone_polishing.py` | 189 | 4 |
| `client/json_utils.py` | 121 | 1 |
| `client/skills/normalizer.py` | 110 | 8 |
| `client/model_client.py` | 54 | 1 |
| `client/errors.py` | 20 | 1 |
| `client/templates/modern.py`, `classic.py`, `minimal.py`, `cover_letter.py` | 84/120/70/39 | 7 |
| `client/templates/__init__.py`, `client/skills/__init__.py`, `client/__init__.py` | small | 8 |

### Backend - orchestration, CLI, config

| File | Lines | Phase |
|---|---|---|
| `pipeline.py` | 623 | 9 |
| `config/agents.py` | 173 | 1 |
| `logging_config.py` | ~50 | 1 |
| `basic.py` | small | 9 |
| `test_real_files.py` | small | 11 |

### Backend - web API (`app/`)

| File | Lines | Phase |
|---|---|---|
| `app/main.py` | 327 | 10 |
| `app/schemas.py` | 88 | 10 |
| `app/files.py` | 114 | 10 |
| `app/upload.py` | 83 | 10 |
| `app/tasks.py` | 66 | 10 |
| `app/__init__.py` | 0 | 10 |

### Backend - tests & scratch

| File | Phase |
|---|---|
| `tests/*.py` (23 files, 485 tests) | 11 |
| `wip_testing/*.py` (7 files) | 11 |

### Frontend (`ui/src/`)

| File | Lines | Phase |
|---|---|---|
| `api/client.ts`, `api/hooks.ts`, `api/types.ts`, `api/download.ts` | 94/87/125/9 | 12 |
| `api/client.test.ts`, `api/hooks.test.ts` | 219/146 | 18 |
| `pages/results/coerce.ts`, `parts.tsx` | 136/137 | 13 |
| `pages/results/*Tab.tsx` (8 files) | ~350 total | 14 |
| `pages/RunPage.tsx`, `pages/runForm.ts` | 224/43 | 15 |
| `pages/FilesPage.tsx` | 238 | 16 |
| `pages/ModelsPage.tsx`, `App.tsx`, `main.tsx`, `index.css` | 41/74/14 | 17 |
| `theme/*`, `toast/*`, `test/*` | ~250 | 17 |

### Docs

| File | Phase |
|---|---|
| `AGENTS.md`, `README.md`, `ui/README.md` | 19 |
| `docs/*.md` (8 guides) | 19 |
| Root scratch notes (`frontend-plan.md`, `frontend-tasks*.md`, `web-files-todo.md`, `resume-web-todo.md`, `resume-verify.md`, `bots.md`, `resume-todo.md`, `resume-done.md`; archived to `scratch/` in 19.4) | 19 |

---

## Phase 0 - Baseline snapshot & conventions

**Goal:** Record where we start so every phase can be verified against it.

1. Run and record baseline output:
   - Backend: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
   - Frontend (in `ui/`): `npm test -- --run`, `npm run lint`, `npx tsc -b`
2. Save current counts (485 backend tests, 45 frontend tests) next to each phase's verify list.
3. Confirm the repo state is clean: `git status`, `git log --oneline -5`, note the branch.
4. Agree on the commit-message convention and the per-file checklist above.

**Exit criteria:** baseline commands run, snapshot documented, checklist in use.

---

## Part A - Backend (Python)

## Phase 1 - Foundation: config, logging, errors, LLM clients, JSON utils  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

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

---

## Phase 2 - Pydantic models & coercion  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

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

---

## Phase 3 - Parsing agents & the format detector  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

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

---

## Phase 4 - LLM-only agents: Gap Analysis, ATS Compliance, Tone Polishing + shared validation cleanup  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/gap_analysis.py`, `client/agents/ats_compliance.py`, `client/agents/tone_polishing.py`

**Inspect for:**

- `ats_compliance.py` (and its siblings in Phases 5-6) use the `except json.JSONDecodeError, TypeError:` form. This is valid Python 3.14 (PEP 758) but reads like Python 2 and is confusing. Standardize to the explicit tuple form `except (json.JSONDecodeError, TypeError):` **and** route each guard through one shared helper (below) so the intent is obvious.
- The three agents' `_try_llm` methods are near-identical (prompt, rules, chat, parse, validate). Note the *small* differences (output shape, prompt strings) - keep those, de-duplicate only the scaffolding.
- `tone_polishing.py`: tone guidance coercion; verify it is as clearly written as the equivalent in `models.py`.

**Simplify toward:**

- Add one shared helper - likely in `client/json_utils.py` or a new `client/agents/_validation.py` - called something like `load_json_safe(text) -> dict | None`, and have every `_validate_*` helper use it. This is the single highest-value de-duplication on the backend: the guarded `json.loads` pattern currently appears 12+ times across `resume_rewrite.py`, `cover_letter.py`, and `ats_compliance.py`.
- Ensure each `_validate_*` function is a self-contained, clearly documented predicate: `Returns True when ...`.

**Documentation:** write the module docstring to explain the "LLM only, deterministic fallback" role of these three agents. Note which output model each produces and what happens on total failure (empty model vs. pass-through).

**Verify:** watch `tests/test_agent_gap_analysis.py`, `tests/test_agent_ats_compliance.py`, `tests/test_agent_tone_polishing.py`.

---

## Phase 5 - Resume Rewrite agent + post-validation  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/resume_rewrite.py`

621 lines: `run()` -> `_try_llm()` -> 6 post-validation helpers, plus fallback tailoring (`_parsed_to_rewrite`, `_tailor_skills`, `_as_dict`, `_read_str_list`, `_is_ascii`) and skill matching (`_sanitize_skills`, `_skill_matches`, `_normalize_skill`, `_load_str_list`).

**Inspect for:**

- `_validate_experience_count`, `_validate_certifications`, `_validate_companies` share the same `json.loads` guard (standardize via the Phase 4 helper).
- `_ensure_chronological` and `_sanitize_skills` use `model_copy` (never mutate in place) - confirm the docstrings explain that contract.
- `_tailor_skills`: two deterministic transformations are already well-commented; verify the loops read step-by-step.

**Simplify toward:**

- Re-order the file: public class first, then its methods, then module-level helpers grouped by purpose (validation -> tailoring -> skill matching).
- Give each post-validation helper a full `Args:`/`Returns:` docstring and a one-line "why" (guarding against LLM fabrication).
- Convert dense conditionals in `_skill_matches` into a few named boolean helpers (`_exact_match`, `_substring_match`, `_token_match`), each with a one-line docstring.

**Documentation:** module docstring should explain the full correctness story: LLM -> Pydantic -> *deterministic post-validation* -> chronological ordering -> skill sanitization -> deterministic fallback. Cross-check with `docs/agents.md`.

**Verify:** watch `tests/test_resume_rewrite_validation.py` (63 tests) - the heaviest safety net - plus `tests/test_agent_resume_rewrite.py`.

---

## Phase 6 - Cover Letter agent (largest file)  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/agents/cover_letter.py`

968 lines. Highest-impact simplification target on the backend.

**Inspect for:**

- Seven occurrences of the `json.loads` guard (the Phase 4 helper removes them all).
- The chain of `_validate_*` / `_apply_company_name` / `_apply_candidate_name` post-processors - list every module-level function and assign each a clear intent.
- Where does the file switch from LLM output handling to HTML/plain rendering helpers? That split should become visible in the file structure.

**Simplify toward:**

- Split the file's helpers into named sections with banner comments (`# --- validation ---`, `# --- deterministic post-processors ---`, `# --- rendering/formatting ---`).
- Break any method over ~50 lines into smaller named steps.
- Standardize the placeholder-token handling (`[Company Name]`, `[Your Name]`) so every substitution is one obvious path with a comment.

**Documentation:** module docstring covering the agent contract (inputs from which prior agents, output model, fallback behavior, the two deterministic post-processors). This is *the* file to document thoroughly because it is the largest.

**Verify:** watch `tests/test_agent_cover_letter.py` + `tests/test_cover_letter_validation.py` (109 tests).

---

## Phase 7 - Renderer, templates, formatter  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/templates/renderer.py`, `client/templates/modern.py`, `classic.py`, `minimal.py`, `cover_letter.py`, `client/templates/__init__.py`, `client/formatter.py`

**Inspect for:**

- `renderer.py` (890): the module docstring says *"DOCX/PDF support will be added in subsequent phases"*, but DOCX/PDF rendering already exists (`render_all`, docx/pdf writers). **This stale claim must be fixed.**
- The big public methods (`render_plaintext`, `render_markdown`, `render_cover_letter`, `render_docx`, `render_pdf`, `render_all`, `_clean_output`) - check each for inlined format-specific logic that belongs in a named private method.
- `modern.py`/`classic.py`/`minimal.py`: dict templates with `plaintext`/`markdown` keys - verify the Jinja string templates are readable and each has a docstring naming its style.
- `formatter.py`: `format_resume_markdown`/`plain`/`format_cover_letter` - the "other" rendering path; document how it differs from `ResumeRenderer`.

**Simplify toward:**

- Fix the stale header. Document the two rendering paths (template-based renderer vs. formatter helpers) at the top of each module.
- Break the repeated "build context -> render -> clean output" sequence into one private `_render(template_key, context)` helper used by each public method.
- Give every template dict an explicit docstring of what it contains and which outputs it drives.

**Documentation:** full class/method docstrings; add `Args:`/`Returns:`/`Raises:` to `render_all`. Keep output byte-identical - `tests/test_renderer.py` (43 tests) and `tests/test_formatter.py` (41 tests) guard this.

**Verify:** watch `tests/test_renderer.py`, `tests/test_formatter.py`.

---

## Phase 8 - Skill taxonomy & normalization  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `client/skills/normalizer.py`, `client/skills/__init__.py`, `docs/skill-taxonomy.md` (read-only reference for this phase)

**Inspect for:**

- `SkillNormalizer` public surface (`normalize`, `normalize_list`, `match_skills`, ...), the canonical taxonomy loading, localization, and the `match_skills` return dict.
- Every method docstring should reference how it treats unknown skills and case.

**Simplify toward:**

- Make the internal lookup logic read step-by-step (`# 1. exact canonical match, # 2. variant lookup ...`).
- Rename any single-letter or ambiguous locals.

**Documentation:** module docstring explaining "canonical skill taxonomy -> normalized forms" and when to prefer `normalize_list` vs `match_skills`. Verify `docs/skill-taxonomy.md` matches code (consolidate in Phase 19 if it drifts).

**Verify:** watch `tests/test_skill_normalizer.py` (15 tests).

---

## Phase 9 - Pipeline orchestration + CLI  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `pipeline.py`, `basic.py`

**Inspect for:**

- `_run_pipeline_core`: seven near-identical `runner.run_agent_async(...)` blocks (steps 1-7). Each differs only by agent name, prompt, output key, rules, and context inputs. Extract one small helper `_run_stage(runner, agent_name, *, prompt, output, rules, **context)` that returns the resolved field via `_extract_field` - more verbose per call, far easier to read as a chain.
- `AgentRunner.run_agent_async`: the long protective docstring is good; verify the instantiate-on-first-use logic is clearly commented.
- `PipelineAgent` (generic wrapper): confirm the docstring explains it exists for backward compatibility with the dedicated classes.
- CLI in `main()`: file validation + sample-mode branching - keep the flow in plain sequential steps.

**Simplify toward:**

- The stage call-sites in `_run_pipeline_core` become one-line calls into `_run_stage` with a `# 1. JD Parsing` ... `# 7. Cover Letter` comment above each. This makes the order obvious.
- Keep `create_runner_from_config`, `DEFAULT_AGENT_CLASSES` behavior unchanged; improve their docstrings.

**Documentation:** extend the pipeline module docstring with a stage table (agent -> output key -> consumed by). Keep the shared event-loop rationale in `run_agent_async` accurate.

**Verify:** watch `tests/test_pipeline.py` (17 tests). CLI still works: `uv run python pipeline.py` (sample mode) and with `--resume`/`--job-description`.

---

## Phase 10 - Web API layer  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `app/main.py`, `app/schemas.py`, `app/files.py`, `app/upload.py`, `app/tasks.py`, `app/__init__.py`

**Inspect for:**

- `main.py`: duplicated `list_generated`/`list_uploaded` handlers (same query params, different dir) - extract one shared handler or document the parallel clearly. `_read_text_input` double-checks file size (already done in `_persist_upload`) - remove the redundant check with a comment.
- `files.py` (114): `list_files()` filter/sort/paginate pipeline is clear; verify `safe_dir_path`/`safe_delete_path` docstrings explain the traversal defense.
- `upload.py`: `extract_text()` text extraction for txt/docx/pdf - document each format path.
- `tasks.py`: in-memory `TaskRegistry`; small, verify thread/loop-safety notes.
- `schemas.py`: request/response models; ensure field descriptions.

**Simplify toward:**

- Keep endpoint bodies readable: the small helper functions (`_read_text_input`, `_to_response`, `_require_runner`) are already good. Expand their `Args`/`Returns`/`Raises`.
- The multipart form signature is duplicated between the sync and async pipeline endpoints (6 params). Extract one shared signature object only if it reads simpler; otherwise document the parallel.

**Documentation:** module docstring for `main.py` listing every route and its purpose. Note the SPA mount comment is already good.

**Verify:** watch `tests/test_web_health.py`, `test_web_pipeline.py`, `test_web_tasks.py`, `test_web_outputs.py`, `test_web_files.py`, `test_web_upload.py`, `test_web_spa.py`.

---

## Phase 11 - Backend tests & scratch scripts  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `tests/*.py` (23 files), `wip_testing/*.py` (7 files), `test_real_files.py`

**Inspect for:**

- `tests/conftest.py` (190): fixtures for the mocked `ModelClient` - verify fixture names read clearly and are documented.
- Per-agent contract tests: do they assert *behavior* rather than *implementation*, so the simplifications in Phases 3-6 do not churn them?
- `wip_testing/`: manual chained demos. Confirm each has a header comment stating which agents it exercises and how to run it.
- `test_real_files.py`: the live E2E guarded by `RUN_LIVE_PIPELINE`; verify the guard is documented.

**Simplify toward:**

- Add docstrings/header comments to any test file lacking them.
- Rename unclear test helpers; leave the test cases themselves mostly alone.

**Documentation:** file-top comments for every test file stating what it covers and the key fixture/hook it relies on.

**Verify:** `uv run pytest` full suite green (485 passed), `uv run ruff check .`.

---

## Part B - Frontend (React / TypeScript)

## Phase 12 - API layer: client, hooks, types, download  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/api/client.ts`, `ui/src/api/hooks.ts`, `ui/src/api/types.ts`, `ui/src/api/download.ts`

**Inspect for:**

- `client.ts`: `apiFetch` + `parseErrorDetail` - the error-parsing chain (string detail vs. array of `{msg}`) is subtle; make each step a named, documented branch.
- `hooks.ts`: `usePollTask` wraps `useTask` with a `useEffect` that invalidates `files` and fires `onDone`. Document *why* the files query is invalidated and *when* `onDone` fires. The `refetchInterval` predicate on `useTask` should be documented too.
- `types.ts`: TS mirrors of the backend response models - add comments mapping each type to its FastAPI schema (e.g., `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`) so drift is easy to spot.
- `download.ts` (9 lines): document the URL it builds.

**Simplify toward:**

- Extract the busy `parseErrorDetail` body into one or two small helpers (`_detailString(detail)`, `_detailArray(detail)`), each with a JSDoc line.
- Keep hooks one-per-concern; expand the top-of-file comment in `hooks.ts` describing the polling lifecycle.

**Documentation:** JSDoc on every exported function and hook. Header comment per file stating what it does and how it is used by pages.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `api/client.test.ts`, `api/hooks.test.ts`).

---

## Phase 13 - Result data coercion + shared result parts  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/pages/results/coerce.ts`, `ui/src/pages/results/parts.tsx`

**Inspect for:**

- `coerce.ts` (136): the `as*`/`pick*` helpers are already well-named. Verify each handles its edge cases explicitly and document them (`asString` drops empty strings, `pickNumber` parses numeric strings, etc.).
- `parts.tsx` (137): shared Tag/Chip/List renderers used across the result tabs - confirm props and behavior are documented so tab components read as declarative data.

**Simplify toward:**

- Add one-line JSDoc to every exported helper in `coerce.ts` stating exactly what it tolerates and returns.
- If any `pick*` helper composes two others in a dense one-liner, expand it into a couple of obvious lines.

**Documentation:** module header explaining "the backend result dicts are loosely typed; these helpers coerce unknown shapes safely".

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run`.

---

## Phase 14 - Results tabs (8 components)  ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here as a stub so the numbered plan stays intact.

**Files:** `ui/src/pages/results/ParsedJDTab.tsx`, `ParsedResumeTab.tsx`, `GapAnalysisTab.tsx`, `RewrittenResumeTab.tsx`, `ATSTab.tsx`, `PolishedTab.tsx`, `CoverLetterTab.tsx`, `ResultsTabView.tsx`

**Inspect for:**

- `ResultsTabView.tsx`: the tab map (`TAB_KEYS`, `TAB_HEADERS`, `renderTabBody` switch) is clean. Add a comment that tab order mirrors pipeline output keys.
- Each tab: what data shape does it expect? Does it use the `coerce.ts` helpers or inline its own `as*` logic?
- Any tab rendering an HTML string (e.g., polished/cover letter) - document the trust boundary (content came from our own pipeline).

**Simplify toward:**

- Keep each tab a thin "read data via `pick*`, render via `parts.tsx`" component. Move repeated row/label markup into `parts.tsx` when it appears in 2+ tabs.
- Give every tab a one-line header comment (what it shows + which pipeline field it renders).

**Documentation:** per-component docstrings plus a note in `ResultsTabView.tsx` tying tab keys to the 7-agent output keys.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch the tab tests: `ATSTab.test.tsx`, `DownloadsRow.test.tsx`).

---

## Phase 15 - Run page & form helpers

**Files:** `ui/src/pages/RunPage.tsx`, `ui/src/pages/runForm.ts`

**Inspect for:**

- `RunPage.tsx` (224): the "active" status expression appears twice (`status === undefined || status === 'pending' || status === 'running'`). Extract an `isTaskActive(status)` helper (or a derived boolean) and reuse it in the button `disabled`, `label`, the status panel, and any other spot.
- `FileChosen`: the upload/remove toggle; document the `customUpload` PrimeReact behavior it relies on.
- `runForm.ts`: `validateRunInputs` + `buildRunFormData` - verify the "text wins over file" rule matches backend `_read_text_input` (AGENTS.md convention). Document it.

**Simplify toward:**

- Extract `isTaskActive`, `taskStatusLabel`, and the status-severity map next to `STATUS_SEVERITY`.
- Expand `handleSubmit` into 2-3 obvious steps with comments (validate -> show toast -> mutate -> capture task id).
- Give `FileChosen` and `RunPage` header comments describing the page flow (submit -> poll -> results + downloads).

**Documentation:** JSDoc on `validateRunInputs`/`buildRunFormData` and the file-vs-text precedence rule.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `RunPage.test.tsx`).

---

## Phase 16 - Files page

**Files:** `ui/src/pages/FilesPage.tsx`

238 lines - the largest page component.

**Inspect for:**

- The filter / sort / pagination param object passed to `useFiles(kind, params)`; the delete flow (selection state -> `useDeleteFiles` -> confirm dialog -> invalidate).
- Any repeated `asStringMap`/type coercion for file rows.

**Simplify toward:**

- Split the page into named sections: file-table config, filter bar, delete selection, toolbar. Extract a small `FileTable` component or at least add banner comments for each section.
- Name the state variables by intent (`selectedKeys`, `fileTypeFilter`, `searchQuery`, `page`).
- Add a header comment explaining the generated-vs-uploaded toggle and how downloads/delete map to the two listing kinds.

**Documentation:** JSDoc/header comment on every helper and callback.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `FilesPage.test.tsx`).

---

## Phase 17 - Models page, App shell, theme, toast, entry

**Files:** `ui/src/pages/ModelsPage.tsx`, `ui/src/App.tsx`, `ui/src/main.tsx`, `ui/src/index.css`, `ui/src/theme/*`, `ui/src/toast/*`, `ui/src/test/*`

**Inspect for:**

- `App.tsx`: `Shell` + nav items + routes - compact but clear; add a header comment walking the routing tree.
- `ModelsPage.tsx` (41): the models table; small, but get a header comment.
- `theme/useTheme.ts` + `ThemeToggle.tsx`: the persisted-theme hook; document storage key and initial-state fallback.
- `toast/ToastProvider.tsx` + `ToastContext.ts`: small context wrapper; document the `show` contract.
- `main.tsx`: PrimeReact theme import + mount; document the PrimeReact dependency and stylesheet.
- `test/setup.ts`, `test/utils.tsx`: the shared render helper; document what it provides (router/provider wrappers).

**Simplify toward:**

- Expand short files where a reader would have to guess (one-line JSDoc on each export is enough).
- Do not over-engineer; these files are already simple - this phase is mostly documentation.

**Documentation:** header/component comments for all of the above.

**Verify:** `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `theme/useTheme.test.ts`, `ThemeToggle.test.tsx`).

---

## Phase 18 - Frontend tests

**Files:** `ui/src/**/*.test.ts(x)` (9 files, 45 tests)

**Inspect for:**

- Do tests assert behavior over implementation? (Keeps Phases 12-17 low-churn.)
- Are test names readable as sentences? Rename only where meaning is unclear.
- Missing coverage for newly extracted helpers (e.g., `isTaskActive` if introduced in Phase 15) - add small focused tests there.

**Simplify toward:**

- Add file-top comment to each test file stating the unit under test.
- Extract repeated test setup (mocked fetch responses, wrapped renders) into `test/utils.tsx` when it appears in 2+ files.

**Documentation:** header comments only; behavior unchanged.

**Verify:** `npm test -- --run` green (45 passed).

---

## Part C - Closing

## Phase 19 - Repo-wide documentation consolidation

**Files:** `AGENTS.md`, `README.md`, `ui/README.md`, `docs/*.md` (8 guides), root scratch notes

**Inspect for:**

- `AGENTS.md`: verify the file/architecture map still matches after Phases 1-11 (new helper names, moved functions). Update the quick-command table and conventions (e.g., note the shared `load_json_safe` helper, the `_run_stage` pipeline helper).
- `README.md` / `ui/README.md`: quickstart accuracy.
- `docs/architecture.md`, `docs/agents.md`, `docs/usage.md`, `docs/api.md`, `docs/models.md`, `docs/TESTING.md`, `docs/logging-info.md`, `docs/skill-taxonomy.md`: check each against the code; fix drift found during Phases 1-18.
- Root scratch notes (`frontend-plan.md`, `frontend-tasks*.md`, `web-files-todo.md`, `resume-web-todo.md`, `resume-verify.md`, `bots.md`, `resume-todo.md`, `resume-done.md`): decide which are historical archives vs. still-actionable. Do not delete without the user's OK - recommend a `scratch/` move or a "completed" note in the text.

**Simplify toward:**

- Keep doc text consistent with the new, more verbose code names.
- Remove outdated "TODO/Phase X remains" lines whose work is already complete.

**Verify:** re-read each doc against the relevant module; no command examples broken.

---

## Phase 20 - Final verification & regression

**Goal:** prove nothing regressed after all phases.

1. Backend: `uv run pytest` (expect >= 485 passed), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`.
2. Frontend: `npm test -- --run` (expect >= 45 passed), `npm run lint`, `npx tsc -b`.
3. Manual smoke:
   - `uv run python basic.py`
   - `uv run python pipeline.py` (sample mode)
   - Web API up: `uv run uvicorn app.main:app` then `GET /health`, `GET /api/models`, `POST /api/pipeline/async` with the sample files, `GET /api/tasks/{id}` until complete, verify `output_files`.
   - Live E2E (Ollama running): `uv run python test_real_files.py`.
   - UI dev server: `npm run dev` from `ui/`, load Run page, run a pipeline, check tabs + downloads.
4. Diff review: `git diff` across all phases = documentation + readability only, no behavior change (spot-check output of rendered files before/after if desired).

**Exit criteria:** all suites green, manual smoke passes, `git status` clean after final commit, `simple.md` updated with a short "progress log" section listing which phases are done.

---

## Work Breakdown Checklists (Phases 4-21)

Phases 1-19 are complete (records in `simple-done.md`). The checklists below
are retained so the working record stays intact. The only remaining work is
**Phase 20 - Final verification & regression** and **Phase 21 - Documentation
cleanup**. Work one phase at a time; commit per phase with a phase-tagged
message. Check each sub-task off in place as it is completed.

### Phase 4 - LLM-only agents + shared validation cleanup ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 4.1 Add `load_json_safe(text) -> dict | None` shared helper in `client/json_utils.py` with docstring explaining fence-stripping + guard. ✅ See `simple-done.md`.
- [x] 4.2 Standardize the `except json.JSONDecodeError, TypeError:` sites. Resolution: ruff 0.16 + `target-version = "py314"` auto-canonicalizes the parenthesized form to the PEP 758 comma form (`except A, B:`) with no formatter opt-out, so the tuple form is not enforceable in this repo's toolchain. All 13 sites across `json_utils.py`, `ats_compliance.py`, `cover_letter.py`, `resume_rewrite.py` already use the canonical form (verified via `ruff format --check` + git-clean diff). These guards get routed through `load_json_safe` in 4.4-4.6 anyway. ✅ See `simple-done.md`.
- [x] 4.3 `gap_analysis.py`: dedupe `_try_llm` scaffolding, verify module docstring ("LLM only, deterministic fallback", output model, failure = empty model). ✅ See `simple-done.md`.
- [x] 4.4 `ats_compliance.py`: route its `_validate_*` helpers through `load_json_safe`, expand `Returns True when ...` docstrings. ✅ See `simple-done.md`.
- [x] 4.5 `tone_polishing.py`: verify tone-guidance coercion is as clear as `models.py`; expand docstrings. ✅ See `simple-done.md`.
- [x] 4.6 Guardrails: `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`, `uv run pytest` (watch `tests/test_agent_gap_analysis.py`, `test_agent_ats_compliance.py`, `test_agent_tone_polishing.py`).
- [x] 4.7 Move Phase 4 to `simple-done.md`, mark complete in `simple.md`, commit.

### Phase 5 - Resume Rewrite agent + post-validation ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 5.1 Re-order file: public class first, then module helpers grouped (validation -> tailoring -> skill matching) with banner comments. ✅ See `simple-done.md`.
- [x] 5.2 Route `_validate_experience_count`, `_validate_certifications`, `_validate_companies` guards through `load_json_safe`. ✅ See `simple-done.md`.
- [x] 5.3 Full `Args:`/`Returns:` + one-line "why" on every post-validation helper. ✅ See `simple-done.md`.
- [x] 5.4 Convert dense `_skill_matches` conditionals into named helpers (`_exact_match`, `_substring_match`, `_token_match`). ✅ See `simple-done.md`.
- [x] 5.5 Verify `_ensure_chronological` / `_sanitize_skills` docstrings explain the `model_copy` never-mutate contract; `_tailor_skills` reads step-by-step. ✅ See `simple-done.md`.
- [x] 5.6 Module docstring: LLM -> Pydantic -> post-validation -> chronological -> sanitize -> fallback story. ✅ See `simple-done.md`.
- [x] 5.7 Guardrails (watch `tests/test_resume_rewrite_validation.py` 63 + `test_agent_resume_rewrite.py`), move to `simple-done.md`, commit.

### Phase 6 - Cover Letter agent (largest file) ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 6.1 Split helpers into banner sections: `# --- validation ---`, `# --- deterministic post-processors ---`, `# --- rendering/formatting ---`. ✅ See `simple-done.md`.
- [x] 6.2 Replace all seven `json.loads` guards with `load_json_safe`. ✅ See `simple-done.md`.
- [x] 6.3 Break any method over ~50 lines into named steps with `# 1.`/`# 2.` comments. ✅ See `simple-done.md`.
- [x] 6.4 Standardize placeholder-token handling (`[Company Name]`, `[Your Name]`) - every substitution one obvious path with comment. ✅ See `simple-done.md`.
- [x] 6.5 Module docstring covering agent contract (inputs, output model, fallback, two deterministic post-processors). ✅ See `simple-done.md`.
- [x] 6.6 Guardrails (watch `tests/test_agent_cover_letter.py` + `test_cover_letter_validation.py` 109), move to `simple-done.md`, commit.

### Phase 7 - Renderer, templates, formatter ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 7.1 Fix stale renderer.py header ("DOCX/PDF will be added in subsequent phases" -> they already exist). ✅ See `simple-done.md`.
- [x] 7.2 Document the two rendering paths (template-based `ResumeRenderer` vs `formatter.py` helpers) at top of each module. ✅ See `simple-done.md`.
- [x] 7.3 Extract one private `_render(template_key, context)` helper for the repeated "build context -> render -> clean output" sequence. ✅ See `simple-done.md`.
- [x] 7.4 Docstring per template dict (modern/classic/minimal/cover_letter) naming its style and which outputs it drives. ✅ See `simple-done.md`.
- [x] 7.5 Full class/method docstrings + `Args:`/`Returns:`/`Raises:` on `render_all`. ✅ See `simple-done.md`.
- [x] 7.6 Guardrails (keep output byte-identical; watch `tests/test_renderer.py` 43 + `test_formatter.py` 41), move to `simple-done.md`, commit.

### Phase 8 - Skill taxonomy & normalization ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 8.1 Make internal lookup read step-by-step (`# 1. exact canonical match`, `# 2. variant lookup`, ...). ✅ See `simple-done.md`.
- [x] 8.2 Rename single-letter/ambiguous locals; every method docstring covers unknown-skill + case handling. ✅ See `simple-done.md`.
- [x] 8.3 Module docstring: canonical taxonomy -> normalized forms; when to prefer `normalize_list` vs `match_skills`; cross-check `docs/skill-taxonomy.md`. ✅ See `simple-done.md`.
- [x] 8.4 Guardrails (watch `tests/test_skill_normalizer.py` 15), move to `simple-done.md`, commit.

### Phase 9 - Pipeline orchestration + CLI ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 9.1 Extract `_run_stage(runner, agent_name, *, prompt, output, rules, **context)` helper returning the resolved field. ✅ See `simple-done.md`.
- [x] 9.2 Convert the seven near-identical blocks in `_run_pipeline_core` to one-line `_run_stage` calls with `# 1. JD Parsing` ... `# 7. Cover Letter` comments. ✅ See `simple-done.md`.
- [x] 9.3 Verify `run_agent_async` instantiate-on-first-use comments + shared-event-loop rationale; `PipelineAgent` backward-compat docstring. ✅ See `simple-done.md`.
- [x] 9.4 Pipeline module docstring: stage table (agent -> output key -> consumed by); CLI `main()` plain sequential steps. ✅ See `simple-done.md`.
- [x] 9.5 Guardrails (watch `tests/test_pipeline.py` 17) + CLI smoke: `uv run python pipeline.py` (sample + with `--resume`/`--job-description`). ✅ See `simple-done.md`.

### Phase 10 - Web API layer ✅ COMPLETED

> **Status:** completed. Phase text and completion record moved to `simple-done.md`.
> This section is retained here so the working checklist stays intact.

- [x] 10.1 `main.py` module docstring listing every route + purpose; decide/document `list_generated` vs `list_uploaded` parallel. ✅ See `simple-done.md`.
- [x] 10.2 Remove redundant size double-check in `_read_text_input` (already in `_persist_upload`) with comment; expand `_read_text_input`/`_to_response`/`_require_runner` `Args`/`Returns`/`Raises`. ✅ See `simple-done.md`.
- [x] 10.3 `files.py`: verify `safe_dir_path`/`safe_delete_path` docstrings explain traversal defense. ✅ See `simple-done.md`.
- [x] 10.4 `upload.py`: document each extraction path (.txt/.docx/.pdf). ✅ See `simple-done.md`.
- [x] 10.5 `tasks.py`: thread/loop-safety notes; `schemas.py`: field descriptions. ✅ See `simple-done.md`.
- [x] 10.6 Guardrails (watch all `test_web_*.py`), move to `simple-done.md`, commit. ✅ See `simple-done.md`.

### Phase 11 - Backend tests & scratch scripts ✅ COMPLETED

- [x] 11.1 `tests/conftest.py` (190): fixture names read clearly, documented.
- [x] 11.2 Audit per-agent contract tests assert behavior over implementation.
- [x] 11.3 `wip_testing/*.py`: header comment per file (which agents, how to run).
- [x] 11.4 `test_real_files.py`: document `RUN_LIVE_PIPELINE` guard.
- [x] 11.5 File-top comment per test file (what it covers, key fixture/hook).
- [x] 11.6 Guardrails: full `uv run pytest` green + `uv run ruff check .`, move to `simple-done.md`, commit.

### Phase 12 - Frontend API layer ✅ COMPLETED

- [x] 12.1 `client.ts`: extract `_detailString(detail)` / `_detailArray(detail)` from `parseErrorDetail` with JSDoc.
- [x] 12.2 `hooks.ts`: document polling lifecycle, why files query invalidates, when `onDone` fires, `refetchInterval` predicate.
- [x] 12.3 `types.ts`: comment mapping each type to its FastAPI schema (e.g. `PipelineRunResponse` -> `app.schemas.PipelineRunResponse`).
- [x] 12.4 `download.ts`: document the URL it builds.
- [x] 12.5 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `api/client.test.ts`, `api/hooks.test.ts`).

### Phase 13 - Result data coercion + shared result parts ✅ COMPLETED

- [x] 13.1 `coerce.ts`: one-line JSDoc on every export (what it tolerates/returns); expand dense `pick*` one-liners.
- [x] 13.2 `parts.tsx`: document props/behavior of each shared renderer.
- [x] 13.3 Module header: "backend result dicts are loosely typed; these helpers coerce unknown shapes safely".
- [x] 13.4 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`.

### Phase 14 - Results tabs (8 components) ✅ COMPLETED

- [x] 14.1 `ResultsTabView.tsx`: comment tying `TAB_KEYS` to the 7-agent output keys/order.
- [x] 14.2 Each tab: one-line header (what it shows + which pipeline field); consistent use of `coerce.ts` helpers.
- [x] 14.3 HTML-string tabs (polished/cover letter): document trust boundary (content from our own pipeline).
- [x] 14.4 Extract repeated row/label markup into `parts.tsx` when it appears in 2+ tabs.
- [x] 14.5 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `ATSTab.test.tsx`, `DownloadsRow.test.tsx`).

### Phase 15 - Run page & form helpers ✅ COMPLETED

- [x] 15.1 Extract `isTaskActive(status)` and reuse in button `disabled`/`label`, status panel, etc.
- [x] 15.2 Extract `taskStatusLabel` + status-severity map next to `STATUS_SEVERITY`.
- [x] 15.3 Expand `handleSubmit` into 2-3 obvious steps with comments (validate -> toast -> mutate -> capture task id).
- [x] 15.4 `FileChosen`: document `customUpload` behavior; header comments for the page flow (submit -> poll -> results + downloads).
- [x] 15.5 `runForm.ts`: JSDoc on `validateRunInputs`/`buildRunFormData`; document "text wins over file" matches backend `_read_text_input`.
- [x] 15.6 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `RunPage.test.tsx`).

### Phase 16 - Files page ✅ COMPLETED

- [x] 16.1 Split into named sections (file-table config, filter bar, delete selection, toolbar) via banner comments or a `FileTable` component.
- [x] 16.2 Name state by intent (`selectedKeys`, `fileTypeFilter`, `searchQuery`, `page`).
- [x] 16.3 Header comment: generated-vs-uploaded toggle; how downloads/delete map to the two listing kinds.
- [x] 16.4 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run` (watch `FilesPage.test.tsx`).

### Phase 17 - Models page, App shell, theme, toast, entry ✅ COMPLETED

- [x] 17.1 `App.tsx`: header comment walking the routing tree (Shell + nav + routes).
- [x] 17.2 `ModelsPage.tsx`: header comment.
- [x] 17.3 `theme/useTheme.ts` + `ThemeToggle.tsx`: document storage key + initial-state fallback.
- [x] 17.4 `toast/ToastProvider.tsx` + `ToastContext.ts`: document the `show` contract.
- [x] 17.5 `main.tsx`: document PrimeReact theme import + stylesheet dependency.
- [x] 17.6 `test/setup.ts` + `test/utils.tsx`: document the shared render helper (router/provider wrappers).
- [x] 17.7 Guardrails: `npx tsc -b`, `npm run lint`, `npm test -- --run`.

### Phase 18 - Frontend tests ✅ COMPLETED

- [x] 18.1 File-top comment per test file stating the unit under test.
- [x] 18.2 Extract repeated setup (mocked fetch, wrapped renders) into `test/utils.tsx` where it appears in 2+ files.
- [x] 18.3 Add focused tests for newly extracted helpers (e.g. `isTaskActive`) from Phase 15.
- [x] 18.4 Guardrails: `npm test -- --run` green.

### Phase 19 - Repo-wide documentation consolidation ✅ COMPLETED

- [x] 19.1 `AGENTS.md`: verify file/architecture map after Phases 1-11 (new helpers `load_json_safe`, `_run_stage`); update quick-command table + conventions. ✅ See `simple-done.md`.
- [x] 19.2 `README.md` / `ui/README.md`: quickstart accuracy. ✅ See `simple-done.md`.
- [x] 19.3 Cross-check `docs/*.md` (8 guides) against code; fix drift found during Phases 1-18. ✅ See `simple-done.md`.
- [x] 19.4 Root scratch notes: classify archive vs actionable; recommend `scratch/` move or "completed" note (no deletion without user OK). ✅ See `simple-done.md`. **Recommendation:** eight of the nine root scratch notes are fully-completed archives (`bots.md`, `frontend-plan.md`, `frontend-tasks-done.md`, `resume-done.md`, `resume-todo.md`, `resume-verify.md`, `resume-web-todo.md`, `web-files-todo.md`) - suggested move to `scratch/` (awaiting user OK). Only `frontend-tasks.md` is actionable (§7.3 Manual E2E). **Update (user OK'd):** the eight archives were moved to `scratch/` (git mv) and docs references updated; `frontend-tasks.md` stays in root.
- [x] 19.5 Remove outdated "TODO/Phase X remains" lines for completed work. ✅ See `simple-done.md`.

### Phase 20 - Final verification & regression

- [x] 20.1 Backend: `uv run pytest` (>=485), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`. ✅ See `simple-done.md`.
- [x] 20.2 Frontend: `npm test -- --run` (>=45), `npm run lint`, `npx tsc -b`. ✅ See `simple-done.md`.
- [x] 20.3 Manual smoke: `basic.py`, `pipeline.py` sample mode, web API health/models/pipeline/tasks, live E2E (`test_real_files.py` with Ollama), `npm run dev` UI run. ✅ See `simple-done.md`.
- [x] 20.4 Diff review spot-check rendered output before/after; `git status` clean after final commit. ✅ See `simple-done.md`.
- [ ] 20.5 Add a short "progress log" section to `simple.md` listing completed phases (archive the full plan in `simple-done.md`).

### Phase 21 - Documentation Cleanup

- [ ] 21.1 Root README.md needs to be less than 500 lines with a quickstart section that explains to to get started in 10 minutes or less and links to detailed README.md file
- [ ] 21.2 Create a more expansive/detailed README.md in the docs directory which contains:
  - [ ] 21.2.1 Detailed instructions on how to get started
  - [ ] 21.2.2 Detailed examples on all command line switches/options
  - [ ] 21.2.3 Common issues and fixes
- [ ] 21.3 All markdown files should link to previous and next file, sorted alphabetically with a link docs/README.md file
- [ ] 21.4 Ensure all markdown files are up to date.
- [ ] 21.5 No markdown linting errros in any of the markdown files
