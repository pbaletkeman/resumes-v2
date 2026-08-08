# Usage

This guide covers three things: getting the pipeline running end-to-end, configuring which models the agents use, and adding a custom agent to the chain.

The system is a 7-agent resume optimization pipeline (see `docs/architecture.md`). You feed it a job description and a resume; it produces an ATS-optimized resume and a tailored cover letter, then optionally renders them to files.

## 1. Quickstart

### Prerequisites

1. **Ollama running** on `localhost:11434`.
2. **Model pulled** — at minimum `qwen2.5:7b-instruct`:
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. **uv installed** — create the environment and install dependencies:
   ```bash
   uv sync
   ```
   This installs the project dependencies including `ollama`, `openai`, `pydantic`, `fastapi`, `python-docx`, `reportlab`, and `jinja2`.

If you prefer the OpenAI provider instead of local Ollama, set `MODEL_PROVIDER=openai` and `OPENAI_API_KEY` (see section 2). No infrastructure is needed for Ollama besides the local server.

### First runs

| Command | What it does |
|---------|--------------|
| `uv run python basic.py` | Single-agent smoke test. Runs one `SimpleAgent` chat call against Ollama (or OpenAI) in JSON mode and pretty-prints the response. |
| `uv run python pipeline.py` | Runs `sample_run()`: builds the full runner from the environment and runs `run_resume_pipeline` on placeholder text. Shows the polished resume and cover letter on stdout. |
| `uv run python test_real_files.py` | Live end-to-end integration test: runs the true 7-agent chain against `sample/jobs/3Pillar.txt` and `sample/resume/Peter-Letkeman-Resume.txt` (requires a running Ollama), then prints a per-check PASS/FAIL summary. |
| `uv run pytest` | Deterministic unit suite (`tests/`, 477 tests) — does **not** require a live LLM. |
| `uv run uvicorn app.main:app --reload` | Runs the FastAPI web API (pipeline, tasks, files, outputs endpoints). |

### Running the full pipeline

The pipeline is exposed as `run_resume_pipeline(runner, job_description, resume, *, candidate_name, company_name)`:

```python
from pipeline import create_runner_from_config, run_resume_pipeline

runner = create_runner_from_config()  # wires all 7 agents from the environment

results = run_resume_pipeline(
    runner,
    job_description=...,
    resume=...,
    candidate_name="Your Name",  # enables file rendering
    company_name="Acme Corp",  # used in output filenames
)
```

**Expected outputs:**

- The returned dict always has 7 keys:
  `parsed_job_description`, `parsed_resume`, `tailoring_strategy`, `rewritten_resume`, `ats_optimized_resume`, `polished_resume`, `cover_letter`.
- When `candidate_name` is non-empty, an eighth key `output_files` maps format names to the written `Path`s. `ResumeRenderer.render_all()` writes into `output/`:

  | Key | Extension |
  |-----|-----------|
  | `resume_plaintext` | `.txt` |
  | `resume_markdown` | `.md` |
  | `resume_docx` | `.docx` |
  | `resume_pdf` | `.pdf` |
  | `cover_letter_plaintext` | `.txt` (only when letter text is non-empty) |
  | `cover_letter_markdown` | `.md` (only when letter text is non-empty) |

  Files are named with `ResumeRenderer.build_output_path()`:
  `{YYYYMMDD_HHMM}_{candidate}_{company}_{document_type}.{ext}` (slugs are filesystem-safe).

- When `candidate_name` is empty, rendering is skipped and `output_files` is `{}`.

## 2. Model Configuration

Which provider and model each agent uses is decided at runtime by `config/agents.py`, which reads environment variables. There is no config file to edit; everything is env-driven.

### Global overrides

| Variable | Default | Meaning |
|----------|---------|---------|
| `MODEL_PROVIDER` | `"ollama"` | Provider for the default client: `"ollama"` or `"openai"` |
| `MODEL_NAME` | `"qwen2.5:7b-instruct"` | Model for the default client |
| `OPENAI_API_KEY` | `""` | Required when the default provider or any agent's provider is `openai` |
| `DEFAULT_PROVIDER` | — | (reserved) override of the default provider for all agents |

### Per-agent overrides

Every agent has a `<AGENT>` name (`jd_parsing_agent`, `resume_parsing_agent`, `gap_analysis_agent`, `resume_rewrite_agent`, `ats_compliance_agent`, `tone_polishing_agent`, `cover_letter_agent`). You can give any agent a different provider and/or model:

| Variable | Example |
|----------|---------|
| `<AGENT>_PROVIDER` | `COVER_LETTER_AGENT_PROVIDER=openai` |
| `<AGENT>_MODEL` | `COVER_LETTER_AGENT_MODEL=gpt-4o` |

The prefix is the **uppercased agent name**. Setting either variable for an agent creates a distinct client entry (`<agent_name>_client`) in the registry. Setting one without the other inherits the default for the missing part.

### How `config/agents.py` picks them

`get_agent_config()` builds a dict shaped:

```python
{
    "clients": {
        "default": {"provider": "...", "model": "..."},
        "cover_letter_agent_client": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "...",
        },
    },
    "default": "default",
    "agents": {"cover_letter_agent": "cover_letter_agent_client"},
}
```

Steps:

1. The default client always exists from `MODEL_PROVIDER` + `MODEL_NAME` (+ `api_key` when provider is `openai`).
2. For each of the 7 agent names, if either `<AGENT>_PROVIDER` or `<AGENT>_MODEL` is set, a per-agent client is added and the agent is mapped to it.
3. `build_registry()` (`config/agents.py`) builds a `ModelClientRegistry` from this dict via `from_config()`, registering the `OllamaClient` / `OpenAIClient` instances and setting per-agent assignments.
4. `AgentRunner`/`create_runner_from_config()` uses `registry.get_client_for_agent(name)` to give each dedicated agent its client when it is instantiated.

Verify what each agent resolves to with:

```bash
uv run python -c "from config.agents import get_model_summary; [print(f'{a[\"agent\"]}: {a[\"provider\"]}/{a[\"model\"]}') for a in get_model_summary()]"
```

## 3. Adding a Custom Agent

A custom agent slots into the chain as long as it satisfies two contracts: the **`Agent` protocol** and the **`ModelClient` call contract**.

### The contract a new class must satisfy

1. **Constructor**: `__init__(self, client: ModelClient)` — the runner instantiates it with the resolved client (when wired via the registry).
2. **`async def run(self, inputs: dict[str, Any]) -> Any`** — return the stage's output (typically a Pydantic model or a string).
3. **Fallback discipline** (optional but recommended): try `self.client.chat(...)` and, on any `LLMConnectionError` / `LLMResponseError` / `LLMTimeoutError` (or invalid/validation-failed output), return a deterministic fallback. See `docs/agents.md` for the built-in pattern.

The runner accepts either **pre-instantiated agents** or **agent classes** plus a `ModelClientRegistry` (see `pipeline.py` `AgentRunner`).

### Steps

1. **Create the class** in `client/agents/` (or anywhere) implementing the contract above. Give it a clear `purpose`/system prompt and Pydantic output model following `client/models.py` style.
2. **Wire it into the registry** — either per-agent env override (section 2) or by registering explicitly:
   ```python
   from client.model_registry import ModelClientRegistry

   registry = ModelClientRegistry()
   registry.register("default", OllamaClient("qwen2.5:7b-instruct"))
   registry.set_default_client("default")
   ```
3. **Add it to `DEFAULT_AGENT_CLASSES`** in `pipeline.py` (or pass a substitute mapping to `create_runner_from_config`), keyed by the snake_case agent name, e.g.:
   ```python
   DEFAULT_AGENT_CLASSES = {
       "jd_parsing_agent": JDParsingAgent,
       ...
       "my_new_agent": MyNewAgent,
   }
   ```
   The key is also the env-var prefix (`MY_NEW_AGENT_MODEL`, `MY_NEW_AGENT_PROVIDER`).

4. **Add an `AgentRunner` wiring** in `_run_pipeline_core` (or a custom orchestrator) so the new stage receives the right `inputs` and its output feeds the next stage.

### Registry harness

`ModelClientRegistry` (`client/model_registry.py`) is the seam used by both the runner and `config/agents.py`:

- `register(name, client)` / `get(name)`
- `set_default_client(name)` / `set_agent_client(agent_name, client_name)`
- `get_client_for_agent(agent_name)` (falls back to default)
- `from_config(config_dict)` — builds from the env-config shape above.

For a full working example, see `basic.py`'s `per_agent_model_example()` and `pipeline.py`'s `create_runner_from_config()` + `sample_run()`.

### Adding a true 8th *replacement* stage

The 7 staged agents are hard-wired in `_run_pipeline_core` by name. To *insert* a new stage into the chain, add a call to `runner.run_agent_async("<agent_name>", {...})` at the right point in that coroutine and thread its output into the next agent's inputs — the runner does not otherwise know about ordering.

## References

- `config/agents.py` — environment-driven configuration and `build_registry()`.
- `client/model_registry.py` — `ModelClientRegistry`, per-agent client resolution.
- `client/model_client.py` — the `ModelClient` ABC every agent/custom agent talks to.
- `client/ollama_client.py`, `client/open_ai_client.py` — concrete providers.
- `pipeline.py` — `AgentRunner`, `run_resume_pipeline`, `_run_pipeline_core`, `create_runner_from_config`, `DEFAULT_AGENT_CLASSES`, `sample_run`.
- `basic.py` — single-agent + registry demo.
- `test_real_files.py` — live end-to-end runnable demo (the repo's documented "test_pipeline.py"-style entry point).
- `docs/architecture.md` — system overview and data flow.
- `docs/agents.md` — the seven built-in agents and their prompts/fallbacks.
- `docs/TESTING.md` — manual verification section-by-section, including the regex-only FormatDetector runs.