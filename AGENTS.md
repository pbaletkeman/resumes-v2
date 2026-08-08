# AGENTS.md

## What this repo is

Python multi-agent resume optimization pipeline. 7 sequential agents transform a job description + resume into an ATS-optimized resume and tailored cover letter. Uses Ollama (local) or OpenAI as LLM providers. Includes a FastAPI web API (`app/`).

## Prerequisites

- Ollama running on `localhost:11434`
- Model pulled: `ollama pull qwen2.5:7b-instruct`
- uv installed (`uv sync` to set up venv)

## Quick commands

| What | Command |
|---|---|
| Install/sync deps | `uv sync` |
| Basic agent test | `uv run python basic.py` |
| Full 7-agent pipeline | `uv run python pipeline.py` |
| Run web API | `uv run uvicorn app.main:app --reload` |
| Regex parsing test (no LLM) | See `docs/TESTING.md` section 2 |
| Check which model each agent uses | `uv run python -c "from config.agents import get_model_summary; [print(f'{a[\"agent\"]}: {a[\"provider\"]}/{a[\"model\"]}') for a in get_model_summary()]"` |
| Lint | `uv run ruff check .` |
| Lint (auto-fix) | `uv run ruff check --fix .` |
| Format check | `uv run ruff format --check .` |
| Format (auto-fix) | `uv run ruff format .` |
| Typecheck | `uv run pyright` (no `.` — see Toolchain quirks) |
| Test | `uv run pytest` |
| Test (verbose) | `uv run pytest -v` |
| Test (single file) | `uv run pytest tests/test_format_detector.py` |

No CI is configured. No `Makefile` exists.

## Architecture

```plaintext
pipeline.py          # AgentRunner, PipelineAgent, run_resume_pipeline()
basic.py             # Single-agent demo
logging_config.py    # Centralized logging (dictConfig, LOG_LEVEL env var)
config/agents.py     # Env-var-based agent-to-model configuration
client/
  errors.py           # LLMError hierarchy (LLMConnectionError, LLMResponseError, LLMTimeoutError)
  model_client.py    # ABC for LLM clients (chat() requires response_format; optional json_schema)
  ollama_client.py   # Ollama implementation (configurable timeout, default 300s; format="json" always)
  open_ai_client.py  # OpenAI implementation (response_format json_object / json_schema envelope)
  model_registry.py  # Per-agent model assignment (ModelClientRegistry)
  json_utils.py      # Shared parse_json_response + model_to_json_schema helpers
  format_detector.py # Regex parser with LLM fallback (connected)
  formatter.py       # Output formatting helpers (format_resume_markdown/plain, format_cover_letter)
  models.py          # All Pydantic models (Parsed*, JDParsingOutput, ResumeParsingOutput, etc.)
  templates/         # Jinja2 templates (modern/classic/minimal/cover_letter) + renderer.py
    renderer.py      # ResumeRenderer: plaintext/markdown/cover-letter/docx/pdf + render_all()
  agents/
    jd_parsing.py    # JD Parsing Agent (Agent 1) - dedicated class, LLM + regex fallback
    resume_parsing.py # Resume Parsing Agent (Agent 2) - dedicated class, LLM + regex fallback
    gap_analysis.py  # Gap Analysis Agent (Agent 3) - dedicated class, LLM only
    resume_rewrite.py # Resume Rewrite Agent (Agent 4) - dedicated class, LLM only
    ats_compliance.py # ATS Compliance Agent (Agent 5) - dedicated class, LLM only
    tone_polishing.py # Tone Polishing Agent (Agent 6) - dedicated class, LLM only
    cover_letter.py  # Cover Letter Agent (Agent 7) - dedicated class, LLM only
  skills/            # Shared SkillNormalizer (canonical skill taxonomy)
    __init__.py
    normalizer.py    # SkillNormalizer: canonical normalization/localization
    taxonomy.json    # Canonical skill taxonomy data — see docs/skill-taxonomy.md
tests/
  test_format_detector.py          # FormatDetector regex parsing tests (46 tests)
  test_jd_parsing.py               # JD Parsing company_name extraction/sync tests (19 tests)
  test_resume_rewrite_validation.py # Resume Rewrite post-validation tests (63 tests)
  test_cover_letter_validation.py  # Cover Letter post-validation tests (109 tests)
  test_model_clients.py            # response_format + Structured Outputs plumbing tests (11 tests)
  test_json_utils.py               # shared parser + JSON Schema helper tests (15 tests)
  test_formatter.py                # format_* helpers (41 tests)
  test_renderer.py                 # ResumeRenderer plaintext/markdown/docx/pdf/render_all (43 tests)
  test_skill_normalizer.py         # SkillNormalizer canonical taxonomy tests (15 tests)
  test_agent_jd_parsing.py         # Agent 1 contract tests (7 tests, mocked ModelClient)
  test_agent_resume_parsing.py     # Agent 2 contract tests (9 tests, mocked ModelClient)
  test_agent_gap_analysis.py       # Agent 3 contract tests (7 tests, mocked ModelClient)
  test_agent_resume_rewrite.py     # Agent 4 contract tests (8 tests, mocked ModelClient)
  test_agent_ats_compliance.py     # Agent 5 contract tests (8 tests, mocked ModelClient)
  test_agent_tone_polishing.py     # Agent 6 contract tests (6 tests, mocked ModelClient)
  test_agent_cover_letter.py       # Agent 7 contract tests (10 tests, mocked ModelClient)
  test_pipeline.py                 # AgentRunner / run_resume_pipeline orchestration (17 tests, stub agents)
  test_web_health.py               # Web health + models routes (2 tests)
  test_web_pipeline.py             # Web sync + async pipeline routes (9 tests)
  test_web_tasks.py                # TaskRegistry + tasks routes (9 tests)
  test_web_outputs.py              # Output file serving (3 tests)
  test_web_files.py                # File listing + deletion (11 tests)
  test_web_upload.py               # Text extraction unit (9 tests)
test_real_files.py                  # Live 7-agent E2E test (requires Ollama; RUN_LIVE_PIPELINE guard)
docs/
  TESTING.md                       # Manual testing guide
  models.md                        # Pydantic model reference
  logging-info.md                  # Logging implementation notes
  skill-taxonomy.md                # Skill taxonomy reference
  architecture.md                  # System overview + Mermaid data-flow (Phase 7.3)
  agents.md                        # Agent-by-agent reference (prompts, schemas, fallbacks)
  usage.md                         # Quickstart, model config, custom agents
  api.md                           # API reference (ModelClient, agents, renderer, formatter)
wip_testing/
  test_parsing.py            # Regex + LLM parsing demo (both modes)
  test_job_description.py  # JD Parsing Agent test
  test_resume_parsing.py   # Resume Parsing Agent test
  test_gap_analysis.py     # Gap Analysis Agent test (chains agents 1-3)
  test_resume_rewrite.py   # Resume Rewrite Agent test (chains agents 1-4)
  test_ats_compliance.py   # ATS Compliance Agent test (chains agents 1-5)
  test_tone_polishing.py   # Tone Polishing Agent test (chains agents 1-6)
  test_cover_letter.py     # Cover Letter Agent test (chains agents 1-7)
app/                       # FastAPI web API layer
  __init__.py              # Package marker
  main.py                  # App + lifespan + routes (health/models/pipeline/tasks/outputs/files)
  schemas.py               # Pydantic request/response models (PipelineRun*, Task*, File*)
  upload.py                # extract_text(): .txt/.docx/.pdf -> str, 400 on unmime
  tasks.py                 # In-memory background task registry (TaskRegistry)
  files.py                 # File listing/filter/paging + safe delete helpers
```

## Key conventions

- **Agent names** are snake_case with `_agent` suffix: `jd_parsing_agent`, `resume_parsing_agent`, etc. These are the keys used everywhere (env vars, registry, pipeline wiring).
- **Model overrides** via env vars: `COVER_LETTER_AGENT_MODEL=gpt-4o`, `COVER_LETTER_AGENT_PROVIDER=openai`. Prefix is the uppercased agent name.
- **Default model**: `qwen2.5:7b-instruct` on Ollama. Override globally with `MODEL_PROVIDER` and `MODEL_NAME`. OpenAI provider requires `OPENAI_API_KEY` — read in `config/agents.py`, not in the client.
- **Agent class pattern**: each dedicated agent follows `run()` → `_try_llm()` → `_parse_json()` → Pydantic validation → deterministic fallback. The LLM call is `self.client.chat(purpose=..., prompt=..., output=["json"], rules=..., inputs=[...], response_format="json", json_schema=model_to_json_schema(<OutputModel>))` inside `_try_llm` (there is no `_chat` method). `run()` retries once with `strict=True`; `_try_llm` catches `LLMConnectionError`/`LLMResponseError`/`LLMTimeoutError` from `client/errors.py` and returns `None`.
- **Shared JSON parsing**: all `_parse_json`/`_safe_json` helpers are one-line wrappers over `client/json_utils.py: parse_json_response()` (strip fences, `json.loads`, log failure). `client/json_utils.py: model_to_json_schema()` builds strict-mode provider JSON Schemas from Pydantic models for Structured Outputs (every agent passes its output model's schema to `chat()`; fallback to plain JSON mode stays available by omitting `json_schema=`).
- **No extended characters** in LLM output: `"` not `""`, `->` not `→`. Enforced in agent prompts.
- **FormatDetector** tries regex first, falls back to LLM only if regex returns sparse results and a client is available. Pass `client=None` for regex-only mode. LLM is now connected — `wip_testing/test_parsing.py` demonstrates both modes.
- **LLM output coercion**: Pydantic validators in `client/models.py` handle LLMs returning dicts where strings/lists are expected (e.g., `tone_guidance` as a dict, `keyword_strategy` as a dict). See `_coerce_str_list`, `_coerce_tone_guidance`, `_coerce_final_resume`.
- **Deterministic post-processors (Phase 9)**: after Pydantic validation, `_try_llm()` runs pure-Python post-processors that never call the LLM or mutate state — `_ensure_chronological()` in `resume_rewrite.py` (sort experience most-recent-first, don't reject), and `_apply_company_name()` + `_apply_candidate_name()` in `cover_letter.py` (JD company + `ResumeParsingOutput.name`, substituting ASCII placeholder tokens `[Company Name]`/`[Your Name]`). Results are returned via `model_copy`, never mutated in place.

## Logging

`logging_config.py` provides `configure_logging()` using `dictConfig`. Called at pipeline entry points (`pipeline.py`, `basic.py`) before agents run.

- **`LOG_LEVEL` env var** controls root logger (default `INFO`). Set to `DEBUG` for verbose output.
- LLM client loggers (`client.ollama_client`, `client.open_ai_client`) are hard-coded to `DEBUG`.
- Third-party loggers (`ollama`, `openai`, `httpx`, `httpcore`) suppressed to `WARNING`.
- All log calls use lazy `%s` formatting, never f-strings.
- Exception paths use `exc_info=True` for full tracebacks.

## Pipeline flow

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

Agents 1-7 (JD Parsing, Resume Parsing, Gap Analysis, Resume Rewrite, ATS Compliance, Tone Polishing, Cover Letter) have dedicated classes with LLM + validation + fallback logic.

## Toolchain quirks

- **pyright** runs in `strict` mode and **excludes `tests/`**. New code under `tests/` won't be type-checked. Use `uv run pyright` with **no path arg** — passing `.` makes pyright recurse into `.venv/` and spew thousands of third-party errors. `pyproject.toml` sets `include = ["app", "client", "config", "pipeline.py", "basic.py"]`.
- **ruff** selects rules: `E`, `F`, `I`, `UP`, `B`, `SIM`. Line length 88.
- **pytest** uses `asyncio_mode = "auto"` — async test functions run without decorators.
- Python 3.14+ required (`pyproject.toml`).
- **B008 avoided** in FastAPI routes via `Annotated[..., Form()/File()/Query()/Depends()]` defaults (ruff `B008` flags function calls in default args).

## Testing

pytest with `asyncio_mode = "auto"` for async tests. Tests in `tests/` — 477 tests across 23 files (FormatDetector regex, JD parsing, resume rewrite validation, cover letter validation, model clients, JSON utils, formatter, renderer, skill normalizer, per-agent contract tests, pipeline orchestration, web API tests). Sample files in `sample/jobs/` and `sample/resume/`.

Manual agent tests in `wip_testing/` chain agents sequentially (e.g., `test_ats_compliance.py` runs agents 1-5). Run with `uv run python wip_testing/test_<agent>.py`.

Live end-to-end test `test_real_files.py` (repo root, not in `tests/`) runs the full 7-agent chain against the real sample files with Ollama. Run with `uv run python test_real_files.py` or `uv run pytest test_real_files.py`; guarded by the `RUN_LIVE_PIPELINE` env/module flag so a plain `pytest` run skips it when Ollama is down.

## Status

Agents 1-7 (JD Parsing, Resume Parsing, Gap Analysis, Resume Rewrite, ATS Compliance, Tone Polishing, Cover Letter) have dedicated classes. Agent output Pydantic schemas (`client/models.py`) are complete — all 7 agent output models exist. Every LLM call uses provider-native JSON mode (`response_format="json"`), with optional Strict Structured Outputs via `json_schema=model_to_json_schema(<OutputModel>)` (see `client/json_utils.py`). All 7 agents are wired as dedicated classes in `sample_run()` and `create_runner_from_config()` (which defaults to `DEFAULT_AGENT_CLASSES`). Phase 4.3 (LLM fallback falsehoods: validation, fallback templates, logging, prompt strengthening, `company_name`), Phase 6 (output formatting: `client/formatter.py` + `ResumeRenderer` with `render_all()`), Phase 8 contact info (contact extraction via `FormatDetector` + contact header/signature line in cover letters), Phase 8.5 (skill normalization via `client/skills/SkillNormalizer`), and Phase 9 (cover letter fixes) are complete. `run_resume_pipeline()` takes optional `candidate_name`/`company_name` and writes rendered files to `Path("output")`, returned under the `"output_files"` result key. `run_resume_pipeline()` runs the whole 7-agent chain on a single event loop through `_run_pipeline_core()` (see `run_agent_async()` on `AgentRunner`) so the shared async `ModelClient` loop is not closed between agents. A FastAPI web layer (`app/`) exposes the pipeline synchronously and in the background, plus file listing/management for `output/` (generated) and `uploads/` (persisted uploads); endpoints must call `_run_pipeline_core()` directly (`pipeline.py:324`) and never `run_resume_pipeline()` (`pipeline.py:313`, wraps in `asyncio.run`) to avoid re-entering the event loop. Phase 7 (Testing & Docs) is also complete: `test_real_files.py` live E2E test, per-agent + pipeline + web API tests (477 total), and four docs guides (`architecture.md`, `agents.md`, `usage.md`, `api.md`). See `resume-done.md` for the completed-work archive; `resume-todo.md` records that no remaining work exists.
