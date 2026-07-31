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
| Regex parsing test (no LLM) | See `TESTING.md` section 2 |
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
    jd_parsing.py    # JD Parsing Agent (Agent 1)
    resume_parsing.py # Resume Parsing Agent (Agent 2)
tests/
  test_format_detector.py  # FormatDetector regex parsing tests
wip_testing/
  parsing.py         # Manual parsing test script (regex + LLM)
  debug_jd.py        # JD Parsing Agent test script
  test_resume_parsing.py # Resume Parsing Agent test script
```

## Key conventions

- **Agent names** are snake_case with `_agent` suffix: `jd_parsing_agent`, `resume_parsing_agent`, etc. These are the keys used everywhere (env vars, registry, pipeline wiring).
- **Model overrides** via env vars: `COVER_LETTER_AGENT_MODEL=gpt-4o`, `COVER_LETTER_AGENT_PROVIDER=openai`. Prefix is the uppercased agent name.
- **Default model**: `qwen2.5:7b-instruct` on Ollama. Override globally with `MODEL_PROVIDER` and `MODEL_NAME`.
- **No extended characters** in LLM output: `"` not `""`, `->` not `→`. Enforced in agent prompts.
- **FormatDetector** tries regex first, falls back to LLM only if regex returns sparse results and a client is available. Pass `client=None` for regex-only mode. LLM is now connected — `wip_testing/parsing.py` demonstrates both modes.

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

All 7 agents are currently `PipelineAgent` stubs (generic LLM wrappers), except Agent 1 (JD Parsing) and Agent 2 (Resume Parsing) which have dedicated classes. Remaining dedicated agent classes in `client/agents/` are planned (see `resume-todo.md`).

## Toolchain quirks

- **pyright** runs in `strict` mode and **excludes `tests/`**. New code under `tests/` won't be type-checked.
- **ruff** selects rules: `E`, `F`, `I`, `UP`, `B`, `SIM`. Line length 88.
- **pytest** uses `asyncio_mode = "auto"` — async test functions run without decorators.
- Python 3.14+ required (`pyproject.toml`).

## Testing

pytest with `asyncio_mode = "auto"` for async tests. Tests in `tests/`. Currently covers `FormatDetector` regex parsing (46 tests). Sample files in `sample/jobs/` and `sample/resume/`.

## Status

Many features in `resume-todo.md` are marked NOT DONE. The pipeline runs end-to-end but most agents use generic prompts. Agent 1 (JD Parsing) has a dedicated class with LLM + regex fallback. Agent 2 (Resume Parsing) has a dedicated class with LLM + regex fallback. Agent output Pydantic schemas (`client/models.py`) are complete — all 7 agent output models exist.
