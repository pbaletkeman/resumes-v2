# Testing Guide

## Prerequisites

1. **Ollama running** on `localhost:11434`
2. **Model pulled** — at minimum `qwen2.5:7b-instruct`:
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. **uv installed** — run `uv sync` to set up the venv

---

## 1. Basic Agent (SimpleAgent)

Test the single-agent LLM call:

```bash
uv run python basic.py
```

Expected: prints "Agent: <json>" followed by a parsed JSON object. Since Phase 8, `basic.py` runs in JSON mode (`response_format="json"`) — it prints the raw JSON response and a pretty-printed parsed version.

---

## 2. FormatDetector (Regex Parsing)

Test document parsing without LLM:

```bash
uv run python -c "
import asyncio
from client.format_detector import FormatDetector

fd = FormatDetector()  # no LLM, regex only

with open('sample/resume/Peter-Letkeman-Resume.txt') as f:
    resume = f.read()

result = asyncio.run(fd.parse_resume(resume))
print('Name:', result.name)
print('Skills:', result.skills)
print('Experience entries:', len(result.experience))
"
```

Test JD parsing:

```bash
uv run python -c "
import asyncio
from client.format_detector import FormatDetector

fd = FormatDetector()

with open('sample/jobs/3Pillar.txt') as f:
    jd = f.read()

result = asyncio.run(fd.parse_job_description(jd))
print('Title:', result.title)
print('Requirements:', result.requirements)
"
```

---

## 3. Full Pipeline (7 Agents)

Runs all 7 agents sequentially. `pipeline.py` exercises the pipeline end-to-end via `sample_run()`:

```bash
uv run python pipeline.py
```

This will:

1. Parse the JD (placeholder text — see below)
2. Parse the resume (placeholder text)
3. Run gap analysis, rewrite, ATS check, tone polish, cover letter

**To use real files**, edit the JD/resume placeholder text in `sample_run()` (pipeline.py `sample_run`, near the bottom), or use the chain test scripts in `wip_testing/` — e.g. `wip_testing/test_cover_letter.py` runs the full 1-7 agent chain against real files:

```python
# save as test_pipeline.py
import asyncio
from client.agents import (
    JDParsingAgent,
    ResumeParsingAgent,
    GapAnalysisAgent,
    ResumeRewriteAgent,
    ATSComplianceAgent,
    TonePolishingAgent,
    CoverLetterAgent,
)
from client.ollama_client import OllamaClient
from pipeline import AgentRunner, run_resume_pipeline
from config.agents import build_registry

client = OllamaClient("qwen2.5:7b-instruct")

agents = {
    "jd_parsing_agent": JDParsingAgent(client),
    "resume_parsing_agent": ResumeParsingAgent(client),
    "gap_analysis_agent": GapAnalysisAgent(client),
    "resume_rewrite_agent": ResumeRewriteAgent(client),
    "ats_compliance_agent": ATSComplianceAgent(client),
    "tone_polishing_agent": TonePolishingAgent(client),
    "cover_letter_agent": CoverLetterAgent(client),
}

registry = build_registry()
runner = AgentRunner(agents, registry=registry)

with open("sample/jobs/3Pillar.txt") as f:
    jd = f.read()
with open("sample/resume/Peter-Letkeman-Resume.txt") as f:
    resume = f.read()

results = run_resume_pipeline(runner, jd, resume)
print(results["polished_resume"])
```

> **Note:** All 7 agents are implemented as dedicated classes (see `client/agents/`). The `wip_testing/` scripts chain them with real files; run with `uv run python wip_testing/test_<agent>.py`.

---

## 4. Individual Agent Testing

As each agent is created in `client/agents/`, test it in isolation:

```python
# Example: test JD Parsing Agent
import asyncio
from client.ollama_client import OllamaClient
from client.agents.jd_parsing import JDParsingAgent

client = OllamaClient("qwen2.5:7b-instruct")
agent = JDParsingAgent(client)

with open("sample/jobs/3Pillar.txt") as f:
    jd = f.read()

result = asyncio.run(agent.run({"job_description": jd}))
print(result)
```

Replace `jd_parsing` / `JDParsingAgent` with whichever agent you're testing. Each agent has a ready-made chain script in `wip_testing/` (e.g., `test_resume_rewrite.py` runs agents 1-4).

---

## 5. Model Client Registry

Test per-agent model assignment:

```bash
uv run python -c "from config.agents import get_model_summary; [print(f'{a[\"agent\"]}: {a[\"provider\"]}/{a[\"model\"]}') for a in get_model_summary()]"
```

Override a specific agent's model via environment variable:

```bash
$env:COVER_LETTER_AGENT_MODEL = "gpt-4o"
$env:COVER_LETTER_AGENT_PROVIDER = "openai"
uv run python -c "from config.agents import get_model_summary; print([a for a in get_model_summary() if 'cover' in a['agent']])"
```

---

## 6. OpenAI Provider

If using OpenAI instead of Ollama:

```bash
$env:MODEL_PROVIDER = "openai"
$env:MODEL_NAME = "gpt-4o-mini"
$env:OPENAI_API_KEY = "sk-..."
uv run python basic.py
```

---

## 7. Unit Tests (pytest) + Coverage

Run the full test suite:

```bash
uv run pytest
```

Verbose output:

```bash
uv run pytest -v
```

Single file:

```bash
uv run pytest tests/test_format_detector.py
```

### Coverage reporting

`pytest-cov` is available for coverage reporting. Configuration is in
`pyproject.toml` under `[tool.coverage.run]` / `[tool.coverage.report]`
and measures `app/`, `client/`, `config/`, and `pipeline.py` (tests and
`wip_testing/` are excluded). Branch coverage is on.

```bash
# Terminal summary (the default)
uv run pytest --cov

# Terminal summary with line numbers of uncovered statements
uv run pytest --cov --cov-report=term-missing

# HTML report written to htmlcov/ (browse by file/line in a browser)
uv run pytest --cov --cov-report=html

# Coverage for a subset (e.g. just the rendering module)
uv run pytest --cov=client.templates.renderer --cov-report=term-missing

# XML report (for CI / other tooling)
uv run pytest --cov --cov-report=xml
```

Artifacts: `.coverage` (data file) and `htmlcov/` (HTML report); both are
git-ignored.

Currently **537 tests across 26 files** (deterministic, no live LLM required):

- `tests/test_format_detector.py` — 46 tests (FormatDetector regex parsing)
- `tests/test_jd_parsing.py` — 19 tests (JD parsing company_name extraction/sync)
- `tests/test_resume_rewrite_validation.py` — 63 tests (rewrite post-validation + skill tailoring + fallback logging)
- `tests/test_cover_letter_validation.py` — 109 tests (cover letter post-validation + fallback builder + fallback logging + contact-info post-processing)
- `tests/test_model_clients.py` — 11 tests (response_format + Structured Outputs plumbing)
- `tests/test_json_utils.py` — 23 tests (shared parser + `load_json_safe` + JSON Schema helpers)
- `tests/test_formatter.py` — 41 tests (format_* helpers)
- `tests/test_renderer.py` — 55 tests (ResumeRenderer plaintext/markdown/docx/pdf/render_all + single/multi-template render_all + cover-letter DOCX/PDF + contact-line rendering)
- `tests/test_skill_normalizer.py` — 15 tests (SkillNormalizer canonical taxonomy)
- `tests/test_agent_jd_parsing.py` — 7 tests (Agent 1 contract, mocked ModelClient)
- `tests/test_agent_resume_parsing.py` — 9 tests (Agent 2 contract, mocked ModelClient)
- `tests/test_agent_gap_analysis.py` — 7 tests (Agent 3 contract, mocked ModelClient)
- `tests/test_agent_resume_rewrite.py` — 8 tests (Agent 4 contract, mocked ModelClient)
- `tests/test_agent_ats_compliance.py` — 8 tests (Agent 5 contract, mocked ModelClient)
- `tests/test_agent_tone_polishing.py` — 6 tests (Agent 6 contract, mocked ModelClient)
- `tests/test_agent_cover_letter.py` — 10 tests (Agent 7 contract, mocked ModelClient)
- `tests/test_pipeline.py` — 20 tests (AgentRunner / run_resume_pipeline orchestration, stub agents, resume template passthrough)
- `tests/test_model_store.py` — 11 tests (SQLite agent model override store)
- `tests/test_web_health.py` — 2 tests (web health + models routes)
- `tests/test_web_models_edit.py` — 14 tests (web model/provider edit + reset routes)
- `tests/test_web_pipeline.py` — 13 tests (web sync + async pipeline routes, resume template validation/forwarding)
- `tests/test_web_tasks.py` — 9 tests (TaskRegistry + tasks routes)
- `tests/test_web_outputs.py` — 3 tests (output file serving)
- `tests/test_web_files.py` — 11 tests (file listing + deletion)
- `tests/test_web_upload.py` — 9 tests (text extraction unit)
- `tests/test_web_spa.py` — 8 tests (built-SPA mount + catch-all fallback)

---

## Quick Reference

| What to test | Command |
|---|---|
| Basic agent | `uv run python basic.py` |
| Resume parsing (regex) | See section 2 |
| Full pipeline | `uv run python pipeline.py` |
| Individual agent | See section 4 |
| Model config | See section 5 |
| OpenAI provider | See section 6 |
| Unit tests | `uv run pytest` |
