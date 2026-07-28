gitrrrrr# Testing Guide

## Prerequisites

1. **Ollama running** on `localhost:11434`
2. **Model pulled** — at minimum `qwen3.5`:
   ```bash
   ollama pull qwen3.5
   ```

---

## 1. Basic Agent (SimpleAgent)

Test the single-agent LLM call:

```bash
python basic.py
```

Expected: prints "Agent: Paris" (or similar geography answer).

---

## 2. FormatDetector (Regex Parsing)

Test document parsing without LLM:

```python
# python -m lets you run inline code against the project
python -c "
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

```python
python -c "
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

Uses `PipelineAgent` wrappers around Ollama — runs all 7 agents sequentially:

```bash
python pipeline.py
```

This will:
1. Parse the JD (placeholder text)
2. Parse the resume (placeholder text)
3. Run gap analysis, rewrite, ATS check, tone polish, cover letter

**To use real files**, edit `pipeline.py` line 361-362 and paste your JD/resume text, or run this instead:

```python
# save as test_pipeline.py
import asyncio
from pipeline import AgentRunner, run_resume_pipeline
from client.ollama_client import OllamaClient

client = OllamaClient("qwen3.5")

agents = {
    "jd_parsing_agent": None,  # stub — will raise NotImplementedError
    "resume_parsing_agent": None,
    "gap_analysis_agent": None,
    "resume_rewrite_agent": None,
    "ats_compliance_agent": None,
    "tone_polishing_agent": None,
    "cover_letter_agent": None,
}

runner = AgentRunner(agents)

with open("sample/jobs/3Pillar.txt") as f:
    jd = f.read()
with open("sample/resume/Peter-Letkeman-Resume.txt") as f:
    resume = f.read()

results = run_resume_pipeline(runner, jd, resume)
print(results["polished_resume"])
```

> **Note:** The pipeline agents are stubs. Each `run_agent()` call raises `NotImplementedError` until the agent is implemented. You'll see this error per agent as you build them.

---

## 4. Individual Agent Testing

As each agent is created in `client/agents/`, test it in isolation:

```python
# Example: test JD Parsing Agent once implemented
import asyncio
from client.ollama_client import OllamaClient
from client.agents.jd_parsing import JDParsingAgent

client = OllamaClient("qwen3.5")
agent = JDParsingAgent(client)

with open("sample/jobs/3Pillar.txt") as f:
    jd = f.read()

result = asyncio.run(agent.run({"job_description": jd}))
print(result)
```

Replace `jd_parsing` / `JDParsingAgent` with whichever agent you're testing.

---

## 5. Model Client Registry

Test per-agent model assignment:

```python
from config.agents import get_model_summary

for agent in get_model_summary():
    print(f"{agent['agent']}: {agent['provider']}/{agent['model']}")
```

Override a specific agent's model via environment variable:

```bash
set COVER_LETTER_AGENT_MODEL=gpt-4o
set COVER_LETTER_AGENT_PROVIDER=openai
python -c "from config.agents import get_model_summary; print([a for a in get_model_summary() if 'cover' in a['agent']])"
```

---

## 6. OpenAI Provider

If using OpenAI instead of Ollama:

```bash
set MODEL_PROVIDER=openai
set MODEL_NAME=gpt-4o-mini
set OPENAI_API_KEY=sk-...
python basic.py
```

---

## Quick Reference

| What to test | Command |
|---|---|
| Basic agent | `python basic.py` |
| Resume parsing (regex) | See section 2 |
| Full pipeline | `python pipeline.py` |
| Individual agent | See section 4 |
| Model config | See section 5 |
| OpenAI provider | See section 6 |
