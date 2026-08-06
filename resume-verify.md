# Resume Pipeline - Verification Plan (resume-verify.md)

Purpose: systematically confirm that **every claim in resume-done.md** is actually
true in the codebase, and fix or re-archive anything that is not. Each item below
has a **Verify** step (how to check) and a **Fix** step (what to do if it fails).
Results are tracked in the table at the bottom.

Running this plan does **not** modify source code unless a claim fails. The only
unconditional edits are doc-count hygiene (stale numbers) already known to be out
of date - see **Section 0. Findings so far**.

---

## Section 0. Baseline measured during planning (2026-08-06)

Already verified live and passing:

| Check | Command | Result |
|---|---|---|
| Import all modules | `uv run python -c "import ..."` | 16/16 OK (client.*, config, pipeline, basic, logging_config) |
| Pydantic models present | `hasattr(client.models, ...)` | 10/10 present |
| Formatter helpers | `hasattr(client.formatter, ...)` | `format_resume_markdown/plain`, `format_cover_letter`, `_fix_encoding` present |
| Renderer | `client.templates.renderer` | `ResumeRenderer` + all 8 render/build methods present |
| SkillNormalizer | `client.skills` | `SkillNormalizer`, `normalizer.py`, `taxonomy.json` present |
| JSON utils | `client.json_utils` | `parse_json_response`, `model_to_json_schema` present |
| Agent classes | `client.agents` | 7/7 dedicated classes present |
| FormatDetector | `client.format_detector` | 16 methods incl. contact `_extract_phone/email/linkedin/github` present |
| Lint | `uv run ruff check .` | clean |
| Typecheck | `uv run pyright` | 0 errors / 0 warnings |
| Tests | `uv run pytest` | 362 passed |

**Stale items in resume-done.md (hard counts, not code)** - the *known* things to fix:

| Loc | Stale text | Current truth |
|---|---|---|
| 4.3.D | "227 tests total" | 362 total |
| 4.3.E | "227 passed" | 362 passed |
| 4.3.F notes | "19 / 56 / 91 tests" for jd/rewrite/cover | 19 / 63 / 109 |
| Phase 8 (Contact Info) Verification | "322 passed ... 91 cover letter, 43 renderer" | 362 total; cover 109; renderer 43 |
| Phase 9.4 | "350 passed" | 362 passed |
| File Structure (tests/) | `test_resume_rewrite_validation.py` (56), `test_cover_letter_validation.py` (91) | 63 / 109 |
| File Structure | missing `client/skills/` (3 files) + `tests/test_skill_normalizer.py` (15) | files exist |

> NOTE: AGENTS.md and README.md already read 362 across 9 files. resume-todo.md
> Overview also reads 362. Only resume-done.md lags.

---

## Section 0a. Fix the known stale doc counts (unconditional)

**Fix resume-done.md:** correct every row in the table above (227->362, 56->63,
91->109, 350->362), add `client/skills/{__init__,normalizer}.py` +
`client/skills/taxonomy.json` and `tests/test_skill_normalizer.py (15 tests)` to
the File Structure block. Run `git diff` to confirm nothing else changed.

---

## Section 1. Phase 1 - Core Infrastructure (1.1-1.3)

Claims:
- 1.1 `client/model_client.py` is a clean ABC with `@abstractmethod async def chat(...)`.
- 1.2 `client/errors.py` defines `LLMError/LLMConnectionError/LLMResponseError/LLMTimeoutError`;
     Ollama and OpenAI clients wrap the documented error types.
- 1.3 `requirements.txt` has 3 deps: `ollama`, `openai`, `pydantic`.

**Verify:**
- `uv run python -c "from client.model_client import ModelClient; import inspect; print(inspect.isabstract(ModelClient), list(ModelClient.__abstractmethods__))"` -> abstractmethods includes `chat`.
- `uv run python -c "from client import errors; print([e.__name__ for e in (errors.LLMError, errors.LLMConnectionError, errors.LLMResponseError, errors.LLMTimeoutError)])"`.
- Grep `client/ollama_client.py` for `RequestError|ResponseError|TimeoutError`; `client/open_ai_client.py` for `AuthenticationError|RateLimitError|APIConnectionError|APIError|TimeoutError`.
- Inspect `requirements.txt` -> expect at most 3 lines.

**Fix if not done:** these are architecture-level; do not rewrite wholesale. Record
the delta in the results table and, if a documented error wrapper is missing, add it.

---

## Section 2. Phase 2 - Document Parsing (2.1-2.4)

Claims: `FormatDetector` has `_extract_projects/_extract_metrics/extract_keywords/
_detect_format/_section_pattern/_extract_bullet_points/_extract_name/_extract_title/
_extract_section/_normalize_list_fields/_safe_json` and `parse_resume/
parse_job_description`; LLM fallback connected; `ParsedResume` has `projects`/
`keywords`; agents 1 and 2 exist with the documented run -> _try_llm -> parse ->
validation -> fallback contract.

**Verify:**
- Symbol presence: Section 0 table already confirmed the FormatDetector methods.
- Contract scan across `client/agents/*.py`: each agent defines `run()`, `_try_llm()`,
  a `_parse_json`-style helper, and passes `response_format="json"` +
  `json_schema=model_to_json_schema(<OutputModel>)`.
  - `rg "def run\(\|def _try_llm\|def _parse_json\|response_format=\"json\"\|json_schema=" client/agents/*.py -n`
- `uv run pytest tests/test_format_detector.py tests/test_jd_parsing.py tests/test_resume_parsing.py -q` -> passes (46 + 19 + resume parsing counts).

**Fix if not done:** if any agent lacks `run`/`_try_llm`/JSON mode/`json_schema`,
implement per the AGENTS.md agent-class pattern and add a unit test; re-run the subset.

---

## Section 3. Phases 3 and 4 - Analysis, Rewriting, Polish (3.1-3.3, 4.1-4.2)

Claims: agents 3-7 exist with documented in/out schemas and fallbacks.

**Verify:**
- Output schema fields against `client/models.py`:
  `uv run python -c "from client.models import GapAnalysisOutput, RewriteOutput, ATSComplianceOutput, TonePolishingOutput, CoverLetterOutput as M; [print(n, list(M.model_fields)) for n,M in []..."` and manually check each keyed field named in resume-done.md is present.
- Fallback existence: `GapAnalysisAgent` must have NO regex fallback (LLM only) -
  confirm `_regex_fallback` is absent there but present in the two parsing agents.
- Word/length logic: grep `_validate_length`, `_validate_role`, `_check_company`,
  `_check_skills` in `cover_letter.py`; `ats_score` clamp in `ats_compliance.py`.

**Fix if not implemented:** add missing model fields or implement the documented
post-validation / default result; add a unit test.

---

## Section 4. Phase 4.3 - LLM fallback falsehoods (A-F)

Claims (behavior; hardest to assert by grep):
- A. `_sanitize_skills` (drop fabricated skills; reject if >50% dropped),
  `_validate_companies` (reject fabricated company), `_validate_chronological`.
- B/C. `_validate_role`, `_check_company` (warn), `_check_skills` (warn),
  `_validate_length` (<200/>800 reject), fallback `_build_fallback_cover_letter`,
  `_parsed_to_rewrite` + `_tailor_skills`.
- D. INFO logging on success/fallback ("Fallback: ...", "LLM ... succeeded").
- E. Prompts ASCII-only, no fabrication-inviting metric rule; stray `\\u5f15\\u53ef` removed.
- F. `JDParsingOutput.company_name` + `_sync_company_name` + `_extract_company_name`.

**Verify:**
- Presence: import the helpers
  `from client.agents.cover_letter import _build_fallback_cover_letter, _validate_length, _check_company, _check_skills, _apply_company_name, _apply_candidate_name, _contact_from_resume, _apply_contact_info`
  and `from client.agents.resume_rewrite import _tailor_skills, _sanitize_skills, _parsed_to_rewrite, _ensure_chronological`.
- ASCII-only prompts: `uv run python -c "import client.agents.cover_letter as c, re; s=c._SYSTEM_PROMPT; print(bool(re.search(r'[^\\x00-\\x7f]', s)), '\u5f15\u53ef' in s)"` -> expect `False False`. Repeat for every agent's `_SYSTEM_PROMPT`.
- `JDParsingOutput.model_fields` contains `company_name`.
- Behavior tests already exist and must pass:
  `uv run pytest tests/test_cover_letter_validation.py tests/test_resume_rewrite_validation.py tests/test_jd_parsing.py -q` -> 109 + 63 + 19.

**Fix if not done:** (a) replace lingering non-ASCII in a prompt; (b) reinstate any
dropped threshold; (c) backfill a unit test per failing check; if counts differ from
the doc, correct the doc counts (Section 0a).

---

## Section 5. Phase 5 - Orchestration (5.1-5.2)

Claims: `AgentRunner` in `pipeline.py`; `DEFAULT_AGENT_CLASSES` = 7 classes;
`run_resume_pipeline()` returns 7 output keys + `output_files`; `_extract_field()`
handles dict and model.

**Verify:**
- `uv run python -c "from pipeline import AgentRunner, PipelineAgent, run_resume_pipeline, DEFAULT_AGENT_CLASSES, create_runner_from_config; print(list(DEFAULT_AGENT_CLASSES))"` -> the 7 agent keys in order.
- `get_model_summary()` returns 7 rows: `uv run python -c "from config.agents import get_model_summary; print(len(get_model_summary()))"`.

**Fix if not done:** rewire `DEFAULT_AGENT_CLASSES`/`create_runner_from_config`; add
`output_files` key. (Full pipeline-mock tests are the Phase 7.2.2 gap tracked in
resume-todo.md, not yet covered.)

---

## Section 6. Phase 6 - Output and Validation (6.1-6.3, 6.10)

Claims: models; formatter helpers; `ResumeRenderer` all 8 methods; DOCX/PDF deps;
`render_all` writes 6 output keys; `build_output_path` naming.

**Verify:**
- `uv run pytest tests/test_formatter.py tests/test_renderer.py -q` -> 41 + 43.
- DOCX/PDF smoke must NOT be skipped because deps are missing:
  `uv run python -c "import docx; print('python-docx OK')"` and
  `uv run python -c "import reportlab; print('reportlab OK')"`.
- `pyproject.toml` deps present: `jinja2`, `python-docx`, `reportlab`; confirm
  `markdown` is NOT a dependency.

**Fix if not implemented:** add missing dep to `pyproject.toml` + `uv sync`; implement
missing renderer method; update the 6.10 caveats.

---

## Section 7. Phase 8 (Contact Info)

Claims: `ResumeParsingOutput.phone/email/linkedin/github` + same on `ParsedResume`;
renderer `contact_line`; agent `_contact_from_resume`/`_apply_contact_info`/
`_contact_signature_line`; tests.

**Verify:**
- `uv run python -c "from client.models import ResumeParsingOutput; print([f for f in ('phone','email','linkedin','github') if f in ResumeParsingOutput.model_fields])"` -> 4/4.
- Presence of the cover-letter contact functions + renderer kwargs (grep `contact_line`,
  `phone`, `email`, `linkedin`, `github` in `renderer.py` and `cover_letter.py`).

**Fix if not implemented:** thread contact fields end-to-end (models -> FormatDetector
-> resume agent -> cover agent -> renderer), following the 8.x sub-claims; add tests.

---

## Section 8. Phase 8.5 - Skill Normalization (8.5.1-8.5.6)

**Verify:**
- `client/skills/{__init__,normalizer}.py` + `client/skills/taxonomy.json` +
  `tests/test_skill_normalizer.py` present.
- `uv run pytest tests/test_skill_normalizer.py -q` -> 15.
- `_NORMALIZER = SkillNormalizer()` singleton in each of the 5 consumers
  (jd, resume, gap, rewrite, cover): grep `_NORMALIZER`.
- Each integration claim: `normalize_list` on both LLM + regex paths, LLM prompt
  canonical rule, post-process via `model_copy`.

**Fix if not implemented:** align each agent to the shared normalizer and delete
leftover local `_normalize_skill`/`_skill_matches`; update doc.

---

## Section 9. Live / integration claims (need runtimes)

Several verification statements in resume-done.md are MANUAL live-check claims that
cannot be proven by `pytest`:

- 4.3.E manual runs: `uv run python wip_testing/test_cover_letter.py`,
  `wip_testing/test_resume_rewrite.py` with `LOG_LEVEL=DEBUG`.
- 4.3.F groundedness cross-check (0 ungrounded numbers) - only re-run if the metric
  rules changed.
- 5.2 / Phase 9 manual chain: full 1-7 giving a real name/signature, company honored,
  contacts injected, chronological order.
- 8.6 / 8.7 manual "first-attempt success and no fallbacks" with Ollama; OpenAI
  gpt-4o "not verified (no key)".
- `run_resume_pipeline()` end-to-end render (`candidate_name`/`company_name`)
  producing real `output/` files.

**Verify (live; requires Ollama on :11434):**
```
uv run python wip_testing/test_cover_letter.py        # full chain
uv run python wip_testing/test_resume_rewrite.py      # agents 1-4
uv run python wip_testing/test_job_description.py     # agent 1
uv run python pipeline.py                             # full pipeline -> output/* files
```
Confirm no fallbacks at `LOG_LEVEL=DEBUG`; confirm `output/` files exist and are non-empty.

**Fix if not implemented:** each of these is a *claim*, not a hard requirement. Mark in
the tracker as "not re-verifiable without live Ollama/OpenAI key". Do NOT fabricate a
"verified" status. If any live check fails, capture the log, fix the root cause, and
file a new bug/Phase entry.

---

## Section 9. Cross-doc consistency sweep

**Verify:** word/test counts match across `AGENTS.md`, `README.md`, `resume-todo.md`,
`resume-done.md`, and the actual `uv run pytest` total.

```
rg -n "tests across|passed|/n tests" AGENTS.md README.md resume-todo.md resume-done.md
```
Every hard-coded total must equal the pytest-collected count (currently **362**).
Recompute live:
```
uv run pytest --collect-only -q 2>$null | Measure-Object -Line
```

**Fix:** replace stale numbers in whichever doc lags (expected: `resume-done.md` only).

---

## Command matrix (run order)

| Step | Command | Pass equals |
|---|---|---|
| 1 | `uv run pytest -q` | 362 passed |
| 2 | `uv run ruff check .` | clean |
| 3 | `uv run ruff format --check .` | clean |
| 4 | `uv run pyright` | 0 errors |
| 5 | file-by-file tests | 46/19/63/45/11/15/41/43/15 |
| 6 | symbol checks (Sections 1-8) | all present |
| 7 | ASCII prompt scan | no non-ASCII |
| 8 | deps import: `docx`, `reportlab`, `jinja2` | import OK |
| 9 | live: `wip_testing/*.py` + `pipeline.py` | INFO success, files written |
| 10 | doc count sweep | 362 everywhere |

---

## Results tracker

Fill in as you execute. One row per claim. Mark **verified**, **unverifiable live**,
or **failed -> fixed** and link any new bug/Phase entry.

| # | Claim | Status | Notes / Fix |
|---|-------|--------|-------------|
| 0a | doc-count hygiene | [ ] | 227->362, 56->63, 91->109, 350->362; add client/skills + test_skill_normalizer |
| 1.1 | ModelClient ABC + abstract chat | [ ] | |
| 1.2 | errors + client wrappers | [ ] | |
| 1.3 | requirements.txt = 3 deps | [ ] | |
| 2.1 | FormatDetector methods | [ ] | 16 methods confirmed present |
| 2.2 | agent infra contract | [ ] | run/_try_llm/_parse_json/json+json_schema |
| 2.3 | JD Parsing agent | [ ] | test_jd_parsing = 19 |
| 2.4 | Resume Parsing agent | [ ] | |
| 3.1-3.2 | Gap + Rewrite agents | [ ] | |
| 3.3 | ATS agent | [ ] | ats_score clamp |
| 4.1-4.2 | Tone + Cover agents | [ ] | length/company/skill checks |
| 4.3A | rewrite post-validation | [ ] | |
| 4.3B | cover post-validation | [ ] | |
| 4.3C | fallback templates | [ ] | |
| 4.3D | fallback logging | [ ] | |
| 4.3E | ASCII prompts / no fabrication | [ ] | |
| 4.3F | company_name + sync | [ ] | |
| 5.1 | AgentRunner | [ ] | |
| 5.2 | 7-agent wiring + output_files | [ ] | |
| 6.1 | models | [ ] | 10/10 present |
| 6.2/6.3 | formatter + renderer | [ ] | 41 + 43 tests |
| 6.10 | deps + caveats | [ ] | docx/reportlab/jinja2 |
| 8CI | contact fields (phone/email/github/linkedin) | [ ] | |
| 8.5 | skill normalizer, 6 integrations | [ ] | 15 tests |
| 9 | Phase 9 fixes present | [ ] | tests pass; live Ollama run separate |
| live | end-to-end Ollama, wip_testing | [ ] | requires Ollama |
| cross | cross-doc count consistency | [ ] | expected: only resume-done.md lags |

---

## Definition of done

- Every row in the tracker is marked **verified**, **unverifiable live**, or
  **fixed**, with no unchecked or assumed items left.
- One full `pytest + ruff + pyright` green run at the end.
- A short `## Verification Results (YYYY-MM-DD)` section appended to this file
  recording the final results and any new bug/Phase entries moved to resume-todo.md.