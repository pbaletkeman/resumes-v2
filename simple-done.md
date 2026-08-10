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
