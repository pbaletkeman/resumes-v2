# resumes-v2

Multi-agent resume optimization pipeline. 7 sequential agents transform a job description + resume into an ATS-optimized resume and tailored cover letter. The pipeline is also exposed as a FastAPI web API (`app/`) with sync/async runs plus file listing and management.

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
| --- | --- |
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
| Typecheck | `uv run pyright` (no `.` — passes `.` recurses into `.venv/`) |
| Test | `uv run pytest` |
| Test (verbose) | `uv run pytest -v` |
| Test (single file) | `uv run pytest tests/test_format_detector.py` |
| Run web API | `uv run uvicorn app.main:app --reload` |

See `docs/TESTING.md` for detailed testing instructions (individual agents, OpenAI provider, model registry).

## Web API

The pipeline is also exposed as a FastAPI application (`app/main.py`). Start it with:

```bash
uv run uvicorn app.main:app --reload
```

OpenAPI docs are at `http://localhost:8000/docs`.

### Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/api/models` | List configured models per agent |
| `POST` | `/api/pipeline` | Run the full 7-agent pipeline (sync) |
| `POST` | `/api/pipeline/async` | Launch a background pipeline run |
| `GET` | `/api/tasks/{task_id}` | Poll a background task's status/result |
| `GET` | `/api/outputs/{filename}` | Download a rendered output file |
| `GET` | `/api/files/generated` | List generated files (`output/`) — filter + paged |
| `GET` | `/api/files/uploaded` | List uploaded files (`uploads/`) — filter + paged |
| `DELETE` | `/api/files` | Delete selected files (from either listing) |

Pipeline inputs are multipart fields: `job_description` / `resume` (pasted text) or `job_file` / `resume_file` (uploads), plus optional `candidate_name` / `company_name`. Exactly one of text-or-file is required per input; text wins when both are supplied. Uploaded files are persisted to `uploads/` and rendered outputs to `output/` (both git-ignored).

### Testing the API with REST Client

To call the API from VS Code, install the **REST Client** extension:
[rest-client-free](https://marketplace.visualstudio.com/items?itemName=SergeyEgorov.rest-client-free)

1. Install the extension from the Marketplace link above.
2. Create a request file and open it in VS Code. Note: this extension stores requests in a **`.fetch-client`** directory/file (not the `.http` extension).
3. Each block is a request; press the **Send Request** link above each one to run it.

Example request (start the server first, then send this):

```http
@base = http://localhost:8000

### Health check
GET {{base}}/health

### List configured models
GET {{base}}/api/models
```

Request files are plain text and git-friendly, so keep them in the repo and modify them freely.

## Pipeline flow

```mermaid
flowchart TD
    %% --- Swimlanes (using subgraphs) ---
    subgraph JD_Lane [JD Track]
        JD([JD])
        A[1. JD Parsing]
    end

    subgraph Resume_Lane [Resume Track]
        Resume([Resume])
        B[2. Resume Parsing]
    end

    subgraph Analysis_Lane [Analysis & Rewrite]
        C[3. Gap Analysis]
        D[4. Resume Rewrite]
        E[5. ATS Compliance]
        F[6. Tone Polishing]
    end

    subgraph Output_Lane [Outputs]
        polished_resume([polished_resume])
        G[7. Cover Letter]
        cover_letter([cover_letter])
    end

    %% --- Flows ---
    JD --> A
    A --> B
    Resume --> B

    B --> C
    C --> D
    D --> E
    E --> F
    F --> polished_resume

    F --> G
    G --> cover_letter

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
  formatter.py         # Output formatting helpers (format_resume_markdown/plain, format_cover_letter)
  models.py            # All Pydantic models
  agents/
    jd_parsing.py        # JD Parsing Agent (Agent 1) - dedicated class
    resume_parsing.py    # Resume Parsing Agent (Agent 2) - dedicated class
    gap_analysis.py      # Gap Analysis Agent (Agent 3) - dedicated class
    resume_rewrite.py    # Resume Rewrite Agent (Agent 4) - dedicated class
    ats_compliance.py    # ATS Compliance Agent (Agent 5) - dedicated class
    tone_polishing.py    # Tone Polishing Agent (Agent 6) - dedicated class
    cover_letter.py      # Cover Letter Agent (Agent 7) - dedicated class
  skills/                # Shared SkillNormalizer (canonical skill taxonomy)
    normalizer.py        # SkillNormalizer: canonical normalization/localization
    taxonomy.json        # Canonical skill taxonomy data
  templates/             # Jinja2 templates (modern/classic/minimal/cover_letter)
    renderer.py          # ResumeRenderer: plaintext/markdown/cover-letter/docx/pdf + render_all()
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
wip_testing/
  test_job_description.py  # JD Parsing Agent test
  test_resume_parsing.py   # Resume Parsing Agent test
  test_gap_analysis.py     # Gap Analysis Agent test
  test_resume_rewrite.py   # Resume Rewrite Agent test
  test_ats_compliance.py   # ATS Compliance Agent test
  test_tone_polishing.py   # Tone Polishing Agent test
  test_cover_letter.py     # Cover Letter Agent test
  test_parsing.py          # Regex + LLM parsing demo
app/                       # FastAPI web API layer
  main.py                  # App + lifespan + all routes
  schemas.py               # Pydantic request/response models
  upload.py                # .txt/.docx/.pdf text extraction
  tasks.py                 # In-memory background task registry
  files.py                 # File listing/filter/paging + delete helpers
```

## Configuration

- **Default model:** `qwen2.5:7b-instruct` on Ollama
- **Per-agent overrides** via env vars: `COVER_LETTER_AGENT_MODEL=gpt-4o`, `COVER_LETTER_AGENT_PROVIDER=openai`
- **Global override:** `MODEL_PROVIDER` and `MODEL_NAME`
- **Logging:** `LOG_LEVEL` env var (default `INFO`). Set to `DEBUG` for verbose LLM traffic.

## Project structure

- `sample/jobs/` - Sample job descriptions for testing
- `sample/resume/` - Sample resume for testing
- `client/skills/` - Shared `SkillNormalizer` + canonical skill taxonomy
- `client/templates/` - Jinja2 templates (modern, classic, minimal, cover letter) + `renderer.py` (`ResumeRenderer`)
- `docs/models.md` - Quick reference for all Pydantic models
- `docs/TESTING.md` - Detailed testing guide
- `docs/logging-info.md` - Logging implementation plan and status
- `resume-done.md` - Completed work archive
- `resume-todo.md` - Remaining implementation work
- `web-files-todo.md` - File-management endpoint work log
