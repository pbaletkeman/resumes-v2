# Logging Implementation Plan

## Problem

Logging is dead code. Four files create loggers and emit 12 log calls, but with no `logging.basicConfig()` or handler configuration, all messages are silently discarded by Python. All user-facing output uses raw `print()` (47 calls across 5 files). The LLM clients (`ollama_client.py`, `open_ai_client.py`) have zero logging — API calls, retries, timeouts, and errors are invisible. There are no `debug`-level calls anywhere, so there's no trace-level visibility into the pipeline.

## Goal

Add working, configurable logging to every layer of the pipeline so that:
- Logs appear on stdout with meaningful format (timestamp, level, module)
- LLM requests/responses are visible at `DEBUG` level
- Parsing fallback decisions are traceable
- Users can control verbosity via log level

## Approach

Use stdlib `logging.config.dictConfig` via a dedicated `logging_config.py` module — no new dependencies, follows existing conventions (`logging.getLogger(__name__)`). This gives per-module level control (e.g., debug LLM traffic while keeping everything else at info) which `basicConfig()` cannot do.

### Why `dictConfig` over `basicConfig` or YAML

| Option | Pros | Cons |
|--------|------|------|
| `basicConfig()` | Simplest | No per-module level control, config scattered across entry points |
| `logging.yaml` | Clean separation | Requires `PyYAML` dependency |
| `pyproject.toml` dict | No new file | Not standard practice — `pyproject.toml` is for project metadata, not runtime config |
| **`dictConfig` in code** | No new deps, per-module control, centralized, extensible | Slightly more setup (one new file) |

---

## Tasks

### 1. Create logging configuration module

**New file:** `logging_config.py` ✅ DONE

Create a `configure_logging()` function using `logging.config.dictConfig()`:

```python
import logging
import logging.config
import os


def configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": level,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "client.ollama_client": {"level": "DEBUG"},
            "client.open_ai_client": {"level": "DEBUG"},
        },
    }
    logging.config.dictConfig(config)
```

Key design decisions:
- Root level reads from `LOG_LEVEL` env var (default `INFO`)
- `disable_existing_loggers: False` so loggers created before `configure_logging()` still work
- LLM client loggers hard-coded to `DEBUG` so API traffic is always visible when root is at `DEBUG`
- New per-module overrides can be added to the `loggers` dict as needed

Includes third-party suppressions (task 11): `ollama`, `openai`, `httpx`, `httpcore` all set to `WARNING`.

### 2. Call `configure_logging()` at pipeline entry points

**Files:** `pipeline.py`, `basic.py` ✅ DONE

Call `configure_logging()` at the top of each entry point, before any agents run:
- `pipeline.py` ~line 184 (`run_resume_pipeline`): add `configure_logging()` before agent execution
- `basic.py` ~line 50: add `configure_logging()` for the standalone demo entry point

Import: `from logging_config import configure_logging`

This ensures all existing `logger.info()` / `logger.warning()` / `logger.error()` calls in `format_detector.py`, `jd_parsing.py`, and `resume_parsing.py` start working immediately.

### 3. Add logging to OllamaClient

**File:** `client/ollama_client.py` ✅ DONE

Add `logger = logging.getLogger(__name__)` after imports.

Log at these points:
- `chat()` method entry (DEBUG): model name, prompt length, message count
- `chat()` method success (DEBUG): response content length, latency
- `chat()` exception paths (WARNING/ERROR): connection errors, timeouts, unexpected failures

**Lines to modify:**
- Line ~15 (after imports): add logger
- Line ~40 (`chat()`): add debug log on entry, debug log on success, warning/error on exceptions

### 4. Add logging to OpenAIClient

**File:** `client/open_ai_client.py` ✅ DONE

Add `logger = logging.getLogger(__name__)` after imports.

Log at these points:
- `chat()` method entry (DEBUG): model name, prompt length, message count
- `chat()` method success (DEBUG): response content length, latency
- `chat()` exception paths (WARNING/ERROR): `RateLimitError`, `APIConnectionError`, `AuthenticationError`, generic `APIError`, timeouts

**Lines to modify:**
- Line ~24 (after imports): add logger
- Line ~48 (`chat()`): add debug log on entry, debug log on success, warning/error on exceptions

### 5. Add debug logging to FormatDetector

**File:** `client/format_detector.py` ✅ DONE

Existing logger at line 20. Add `debug`-level calls:

- `parse_resume()` (line ~53): log detected format, section count, regex match results
- `parse_job_description()` (line ~102): log detected format, section count, regex match results
- `_detect_format()` (line ~484): log format detection result
- `_llm_parse_resume()` (line ~529): log prompt sent (truncated), response received (truncated)
- `_llm_parse_job_description()` (line ~578): log prompt sent (truncated), response received (truncated)
- `_safe_json()` (line ~637): log raw LLM output before JSON parsing attempt

**Lines to modify:** Add `logger.debug(...)` calls at the locations listed above.

### 6. Add debug logging to JD Parsing Agent

**File:** `client/agents/jd_parsing.py` ✅ DONE

Existing logger at line 22. Add `debug`-level calls:

- `run()` (line ~59): log entry with input summary
- `_try_llm()` (line ~82): log LLM prompt length, response length, validation result
- `_regex_fallback()` (line ~150): log regex extraction results (sections found, keywords extracted)
- `_parse_json()` (line ~134): log raw JSON string before parsing

**Lines to modify:** Add `logger.debug(...)` calls at the locations listed above.

### 7. Add debug logging to Resume Parsing Agent

**File:** `client/agents/resume_parsing.py` ✅ DONE

Existing logger at line 22. Add `debug`-level calls:

- `run()` (line ~60): log entry with input summary
- `_try_llm()` (line ~83): log LLM prompt length, response length, validation result
- `_regex_fallback()` (line ~151): log regex extraction results (sections found, experience entries)
- `_parse_json()` (line ~135): log raw JSON string before parsing
- `_parse_experience_line()` (line ~182): log parsing result for each line

**Lines to modify:** Add `logger.debug(...)` calls at the locations listed above.

### 8. Add logging to config loader

**File:** `config/agents.py` ✅ DONE

Add `logger = logging.getLogger(__name__)` after imports.

- `get_agent_config()` (line ~28): log resolved config at DEBUG (provider, model, timeout per agent)
- `build_registry()` (line ~107): log registry construction at INFO (number of agents configured)

**Lines to modify:**
- Line ~5 (after imports): add logger
- Line ~28, ~107: add debug/info log calls

### 9. Add logging to ModelClientRegistry

**File:** `client/model_registry.py` ✅ DONE

Add `logger = logging.getLogger(__name__)` after imports.

- Log agent-to-model assignment at DEBUG when registry is populated

**Lines to modify:**
- After imports: add logger
- In registry population logic: add `logger.debug(...)` calls

### 10. Add logging to model clients (base class awareness)

**File:** `client/model_client.py` ✅ SKIPPED

This is an ABC — no logging needed here. Skip.

### 11. Suppress noisy third-party loggers

In `logging_config.py`, add suppressions for library loggers that would otherwise spam output at DEBUG:

```python
"loggers": {
    "client.ollama_client": {"level": "DEBUG"},
    "client.open_ai_client": {"level": "DEBUG"},
    "ollama": {"level": "WARNING"},        # suppress verbose ollama internals
    "openai": {"level": "WARNING"},         # suppress verbose openai internals
    "httpx": {"level": "WARNING"},          # suppress HTTP request logs from openai SDK
    "httpcore": {"level": "WARNING"},       # suppress HTTP connection logs
},
```

Without this, `LOG_LEVEL=DEBUG` would dump raw HTTP traffic from the SDK libraries on top of the application-level logs. ✅ DONE (implemented in task 1)

### 12. Enforce lazy formatting in log calls

All log calls must use `%s` formatting, not f-strings:

```python
# Correct -- string interpolation is deferred until the message is actually emitted
logger.debug("LLM response for %s: %d chars", model_name, len(response))

# Wrong -- string is interpolated even when DEBUG is disabled
logger.debug(f"LLM response for {model_name}: {len(response)} chars")
```

Apply this rule to every `logger.debug()` / `logger.info()` call added in tasks 3-9. ✅ DONE (verified: 0 f-strings found across all log calls)

### 13. Use `exc_info=True` for exception paths

When logging exceptions in the clients and agents, always include the traceback:

```python
except LLMConnectionError as e:
    logger.error("LLM connection failed: %s", e, exc_info=True)
```

This gives full stack traces in the log output without requiring `logger.exception()`. Apply to:
- `OllamaClient.chat()` exception handlers (task 3) ✅
- `OpenAIClient.chat()` exception handlers (task 4) ✅
- `AgentRunner.run_agent()` error path (existing line 167) ✅

### 14. Add test logging configuration

**File:** `tests/conftest.py` ✅ DONE

Add a pytest fixture that configures logging for the test suite so log output is visible during test runs but doesn't clutter CI:

```python
import logging
import pytest


@pytest.fixture(autouse=True)
def configure_test_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s %(levelname)s: %(message)s",
    )
```

This keeps test output clean by default (WARNING+ only). To see debug output during a specific test run:

```bash
uv run pytest tests/test_format_detector.py -v --log-cli-level=DEBUG
```

### 15. Security: log redaction guidelines

Do NOT log:
- API keys or tokens (even partially masked)
- Full resume or JD text at INFO level (DEBUG is acceptable since it's opt-in)
- File paths that reveal directory structure on the user's machine

When in doubt, log metadata (lengths, model names, section counts) rather than content. ✅ DONE (audited: no API keys, tokens, or file paths in any log calls; resume/JD content only at DEBUG truncated)

### 16. Log startup environment configuration

**File:** `pipeline.py` ✅ DONE

At the start of `run_resume_pipeline()`, after `configure_logging()`, log the resolved configuration so users can verify their setup before agents run:

```python
logger.info("Pipeline starting")
logger.info("Provider: %s | Model: %s", provider, model)
logger.info("Agents configured: %s", ", ".join(agent_names))
```

This answers the common question "which model am I actually using?" without requiring users to read code or env vars. Log at INFO so it's visible by default.

### 17. Log pipeline completion summary

**File:** `pipeline.py` ✅ DONE

At the end of `run_resume_pipeline()`, log a summary of what happened:

```python
logger.info(
    "Pipeline completed in %.1fs — %d/%d agents succeeded",
    total_time,
    success_count,
    total_agents,
)
```

If any agents failed, log them explicitly:

```python
if failed_agents:
    logger.error("Failed agents: %s", ", ".join(failed_agents))
```

This gives users a clear pass/fail signal without reading through all intermediate log output.

### 18. Verify lint and typecheck pass

Run after all changes:
```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright .
```

---

## Summary of changes by file

| File | Current state | Changes |
|------|--------------|---------|
| `logging_config.py` | **New file** | `configure_logging()` with `dictConfig`, env-var level control, third-party suppressions |
| `pipeline.py` | Has logger, 3 calls | Call `configure_logging()`, add startup config log, add completion summary |
| `basic.py` | No logger | Call `configure_logging()` for standalone demo |
| `client/ollama_client.py` | No logger | Add logger + debug/warning calls |
| `client/open_ai_client.py` | No logger | Add logger + debug/warning calls |
| `client/format_detector.py` | Has logger, 5 calls | Add debug calls at regex/LLM paths |
| `client/agents/jd_parsing.py` | Has logger, 4 calls | Add debug calls at LLM/regex paths |
| `client/agents/resume_parsing.py` | Has logger, 4 calls | Add debug calls at LLM/regex paths |
| `config/agents.py` | No logger | Add logger + debug/info calls |
| `client/model_registry.py` | No logger | Add logger + debug call |
| `tests/conftest.py` | No logging | Add test logging fixture |

## Log level conventions

| Level | Use case |
|-------|----------|
| `DEBUG` | LLM prompts/responses (truncated), regex matches, parsing steps, config values |
| `INFO` | Agent start/completion, fallback decisions, pipeline progress |
| `WARNING` | Pydantic validation failures, JSON parse failures, LLM fallback triggers |
| `ERROR` | Agent failures, LLM connection errors, unexpected exceptions |

## Env var control

| Variable | Default | Effect |
|----------|---------|--------|
| `LOG_LEVEL` | `INFO` | Sets root logger level. Set to `DEBUG` for verbose output. |

Example: `LOG_LEVEL=DEBUG uv run python pipeline.py`

## Not in scope (future work)

- Structured logging (`structlog` or `loguru`) — stdlib `dictConfig` is sufficient for now
- Log-to-file / `RotatingFileHandler` — add a file handler to the `dictConfig` dict when needed
- `logging.yaml` — would require adding `PyYAML` as a dependency; `dictConfig` in code is equivalent with zero deps
- Replacing `print()` in `wip_testing/` scripts — these are ad-hoc test scripts, print is fine
- Per-agent `LoggerAdapter` with `extra={}` context (run ID, agent name) — useful for concurrent runs, not needed for single-threaded pipeline
- Token count / cost tracking in logs — depends on LLM provider exposing usage data
