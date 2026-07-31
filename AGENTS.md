# AGENTS.md

## What this repo is

Python multi-agent resume optimization pipeline. 7 sequential agents transform a job description + resume into an ATS-optimized resume and tailored cover letter. Uses Ollama (local) or OpenAI as LLM providers.

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
| Regex parsing test (no LLM) | See `docs/TESTING.md` section 2 |
| Check which model each agent uses | `uv run python -c "from config.agents import get_model_summary; [print(f'{a[\"agent\"]}: {a[\"provider\"]}/{a[\"model\"]}') for a in get_model_summary()]"` |
| Lint | `uv run ruff check .` |
| Lint (auto-fix) | `uv run ruff check --fix .` |
| Format check | `uv run ruff format --check .` |
| Format (auto-fix) | `uv run ruff format .` |
| Typecheck | `uv run pyright .` |
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
  model_client.py    # ABC for LLM clients
  ollama_client.py   # Ollama implementation (configurable timeout, default 300s)
  open_ai_client.py  # OpenAI implementation
  model_registry.py  # Per-agent model assignment (ModelClientRegistry)
  format_detector.py # Regex parser with LLM fallback (connected)
  models.py          # All Pydantic models (Parsed*, JDParsingOutput, ResumeParsingOutput, etc.)
  templates/         # Jinja2 resume/cover letter templates (no renderer yet)
  agents/
    jd_parsing.py    # JD Parsing Agent (Agent 1) - dedicated class, LLM + regex fallback
    resume_parsing.py # Resume Parsing Agent (Agent 2) - dedicated class, LLM + regex fallback
    gap_analysis.py  # Gap Analysis Agent (Agent 3) - dedicated class, LLM only
    resume_rewrite.py # Resume Rewrite Agent (Agent 4) - dedicated class, LLM only
    ats_compliance.py # ATS Compliance Agent (Agent 5) - dedicated class, LLM only
tests/
  test_format_detector.py  # FormatDetector regex parsing tests (46 tests)
wip_testing/
  test_job_description.py  # JD Parsing Agent test
  test_resume_parsing.py   # Resume Parsing Agent test
  test_gap_analysis.py     # Gap Analysis Agent test (chains agents 1-3)
  test_resume_rewrite.py   # Resume Rewrite Agent test (chains agents 1-4)
  test_ats_compliance.py   # ATS Compliance Agent test (chains agents 1-5)
```

## Key conventions

- **Agent names** are snake_case with `_agent` suffix: `jd_parsing_agent`, `resume_parsing_agent`, etc. These are the keys used everywhere (env vars, registry, pipeline wiring).
- **Model overrides** via env vars: `COVER_LETTER_AGENT_MODEL=gpt-4o`, `COVER_LETTER_AGENT_PROVIDER=openai`. Prefix is the uppercased agent name.
- **Default model**: `qwen2.5:7b-instruct` on Ollama. Override globally with `MODEL_PROVIDER` and `MODEL_NAME`.
- **No extended characters** in LLM output: `"` not `""`, `->` not `→`. Enforced in agent prompts.
- **FormatDetector** tries regex first, falls back to LLM only if regex returns sparse results and a client is available. Pass `client=None` for regex-only mode. LLM is now connected — `wip_testing/parsing.py` demonstrates both modes.
- **LLM output coercion**: Pydantic validators in `client/models.py` handle LLMs returning dicts where strings/lists are expected (e.g., `tone_guidance` as a dict, `keyword_strategy` as a dict). See `_coerce_str_list`, `_coerce_tone_guidance`, `_coerce_final_resume`.

## Logging

`logging_config.py` provides `configure_logging()` using `dictConfig`. Called at pipeline entry points (`pipeline.py`, `basic.py`) before agents run.

- **`LOG_LEVEL` env var** controls root logger (default `INFO`). Set to `DEBUG` for verbose output.
- LLM client loggers (`client.ollama_client`, `client.open_ai_client`) are hard-coded to `DEBUG`.
- Third-party loggers (`ollama`, `openai`, `httpx`, `httpcore`) suppressed to `WARNING`.
- All log calls use lazy `%s` formatting, never f-strings.
- Exception paths use `exc_info=True` for full tracebacks.

## Pipeline flow

```
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

Agents 1-5 have dedicated classes with LLM + validation + fallback logic. Agents 6-7 (Tone Polishing, Cover Letter) still use generic `PipelineAgent` stubs — see `resume-todo.md` for remaining work.

## Toolchain quirks

- **pyright** runs in `strict` mode and **excludes `tests/`**. New code under `tests/` won't be type-checked.
- **ruff** selects rules: `E`, `F`, `I`, `UP`, `B`, `SIM`. Line length 88.
- **pytest** uses `asyncio_mode = "auto"` — async test functions run without decorators.
- Python 3.14+ required (`pyproject.toml`).

## Testing

pytest with `asyncio_mode = "auto"` for async tests. Tests in `tests/`. Currently covers `FormatDetector` regex parsing (46 tests). Sample files in `sample/jobs/` and `sample/resume/`.

Manual agent tests in `wip_testing/` chain agents sequentially (e.g., `test_ats_compliance.py` runs agents 1-5). Run with `uv run python wip_testing/test_<agent>.py`.

## Status

Agents 1-5 (JD Parsing, Resume Parsing, Gap Analysis, Resume Rewrite, ATS Compliance) have dedicated classes. Agents 6-7 (Tone Polishing, Cover Letter) use generic `PipelineAgent` stubs. Agent output Pydantic schemas (`client/models.py`) are complete — all 7 agent output models exist. Pipeline runs end-to-end but Agents 6-7 use generic prompts. See `resume-todo.md` for remaining work.
