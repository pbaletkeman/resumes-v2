# resumes-v2

Multi-agent resume optimization pipeline. 7 sequential agents transform a job description + resume into an ATS-optimized resume and tailored cover letter.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) installed
- [Ollama](https://ollama.com/) running on `localhost:11434`
- Model pulled: `ollama pull qwen2.5:7b-instruct`

## Quick start

```bash
uv sync
uv run python pipeline.py
```

## Usage

| What | Command |
|---|---|
| Install/sync deps | `uv sync` |
| Full 7-agent pipeline | `uv run python pipeline.py` |
| Single-agent demo | `uv run python basic.py` |
| Test JD Parsing Agent | `uv run python wip_testing/test_job_description.py` |
| Test Resume Parsing Agent | `uv run python wip_testing/test_resume_parsing.py` |
| Test Gap Analysis Agent | `uv run python wip_testing/test_gap_analysis.py` |
| Test Resume Rewrite Agent | `uv run python wip_testing/test_resume_rewrite.py` |
| Test ATS Compliance Agent | `uv run python wip_testing/test_ats_compliance.py` |
| Test Tone Polishing Agent | `uv run python wip_testing/test_tone_polishing.py` |
| Test Cover Letter Agent | `uv run python wip_testing/test_cover_letter.py` |
| Regex parsing test (no LLM) | `uv run python wip_testing/test_parsing.py` |
| Check which model each agent uses | `uv run python -c "from config.agents import get_model_summary; [print(f'{a[\"agent\"]}: {a[\"provider\"]}/{a[\"model\"]}') for a in get_model_summary()]"` |
| Lint | `uv run ruff check .` |
| Lint (auto-fix) | `uv run ruff check --fix .` |
| Format check | `uv run ruff format --check .` |
| Format (auto-fix) | `uv run ruff format .` |
| Typecheck | `uv run pyright .` |
| Test | `uv run pytest` |
| Test (verbose) | `uv run pytest -v` |
| Test (single file) | `uv run pytest tests/test_format_detector.py` |

See `docs/TESTING.md` for detailed testing instructions (individual agents, OpenAI provider, model registry).

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

## Architecture

```plaintext
pipeline.py              # AgentRunner, PipelineAgent, run_resume_pipeline()
basic.py                 # Single-agent demo
logging_config.py        # Centralized logging (dictConfig, LOG_LEVEL env var)
config/agents.py         # Env-var-based agent-to-model configuration
client/
  errors.py            # LLMError hierarchy (LLMConnectionError, LLMResponseError, LLMTimeoutError)
  model_client.py      # ABC for LLM clients (chat() requires response_format; optional json_schema)
  ollama_client.py     # Ollama implementation (configurable timeout, default 300s; format="json" always)
  open_ai_client.py    # OpenAI implementation (response_format json_object / json_schema envelope)
  model_registry.py    # Per-agent model assignment (ModelClientRegistry)
  json_utils.py        # Shared parse_json_response + model_to_json_schema helpers
  format_detector.py   # Regex parser with LLM fallback (connected)
  models.py            # All Pydantic models
  agents/
    jd_parsing.py        # JD Parsing Agent (Agent 1) - dedicated class
    resume_parsing.py    # Resume Parsing Agent (Agent 2) - dedicated class
    gap_analysis.py      # Gap Analysis Agent (Agent 3) - dedicated class
    resume_rewrite.py    # Resume Rewrite Agent (Agent 4) - dedicated class
    ats_compliance.py    # ATS Compliance Agent (Agent 5) - dedicated class
    tone_polishing.py    # Tone Polishing Agent (Agent 6) - dedicated class
    cover_letter.py      # Cover Letter Agent (Agent 7) - dedicated class
  templates/             # Jinja2 resume/cover letter templates (no renderer yet)
tests/
  test_format_detector.py          # FormatDetector regex parsing tests (46 tests)
  test_jd_parsing.py               # JD Parsing company_name extraction/sync tests (19 tests)
  test_resume_rewrite_validation.py # Resume Rewrite post-validation tests (52 tests)
  test_cover_letter_validation.py  # Cover Letter post-validation tests (77 tests)
  test_model_clients.py            # response_format + Structured Outputs plumbing tests (11 tests)
  test_json_utils.py               # shared parser + JSON Schema helper tests (15 tests)
wip_testing/
  test_job_description.py  # JD Parsing Agent test
  test_resume_parsing.py   # Resume Parsing Agent test
  test_gap_analysis.py     # Gap Analysis Agent test
  test_resume_rewrite.py   # Resume Rewrite Agent test
  test_ats_compliance.py   # ATS Compliance Agent test
  test_tone_polishing.py   # Tone Polishing Agent test
  test_cover_letter.py     # Cover Letter Agent test
  test_parsing.py          # Regex + LLM parsing demo
```

## Configuration

- **Default model:** `qwen2.5:7b-instruct` on Ollama
- **Per-agent overrides** via env vars: `COVER_LETTER_AGENT_MODEL=gpt-4o`, `COVER_LETTER_AGENT_PROVIDER=openai`
- **Global override:** `MODEL_PROVIDER` and `MODEL_NAME`
- **Logging:** `LOG_LEVEL` env var (default `INFO`). Set to `DEBUG` for verbose LLM traffic.

## Project structure

- `sample/jobs/` - Sample job descriptions for testing
- `sample/resume/` - Sample resume for testing
- `client/templates/` - Jinja2 templates (modern, classic, minimal, cover letter)
- `docs/models.md` - Quick reference for all Pydantic models
- `docs/TESTING.md` - Detailed testing guide
- `docs/logging-info.md` - Logging implementation plan and status
- `resume-done.md` - Completed work archive
- `resume-todo.md` - Remaining implementation work
