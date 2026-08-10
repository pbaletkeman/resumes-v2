# Completed Phases

Completed phases from `simple.md` are moved here, one phase per section, in
order.  Each entry keeps the original phase text and adds a completion record
(what was changed and how it was verified) so the history stays reviewable.

---

## Phase 1 - Foundation: config, logging, errors, LLM clients, JSON utils  ✅ COMPLETED

**Files:** `config/agents.py`, `logging_config.py`, `client/errors.py`, `client/model_client.py`, `client/json_utils.py`, `client/ollama_client.py`, `client/open_ai_client.py`, `client/model_registry.py`

This is the shared "plumbing" layer every other module uses. Simplifying here is high leverage.

**Inspect for:**

- `config/agents.py`: environment-variable reading (provider/model defaults, per-agent overrides such as `COVER_LETTER_AGENT_MODEL`, `OPENAI_API_KEY`). Is every branch reachable and are variable names self-explanatory?
- `logging_config.py`: is `LOG_LEVEL` handling verbose enough to follow? Are the hard-coded logger-level decisions commented?
- `client/errors.py` (20 lines): confirm the 3 exception types plus base clearly document *when* each is raised.
- `client/model_client.py` (54 lines): the `chat()` ABC. The `response_format` / `json_schema` contract text should say *exactly* what providers must implement.
- `client/json_utils.py` (121): `parse_json_response()` (fence stripping + `json.loads`) and `model_to_json_schema()`. These two are the cornerstones every agent uses.
- `client/ollama_client.py` / `client/open_ai_client.py`: timeouts, `response_format`, and any duplicated send/format logic between them. Worth a docstring per method documenting provider-specific behavior.
- `client/model_registry.py` (209): per-agent registry; clarify how fallback `MODEL_PROVIDER`/`MODEL_NAME` interacts with per-agent overrides.

**Simplify toward:**

- Spell out inline one-liners that pack too much (e.g., complex ternaries in config resolution).
- If the two clients duplicate `json.loads` + error handling, route both through one shared "safe JSON decode" helper in `json_utils.py`.
- Rename short/mysterious module-level variables to intent-revealing names.
- Add a short "how agents use this file" comment at the top of `json_utils.py` and `model_client.py`.

**Documentation:** module + class + method docstrings (many exist already - verify each is accurate). Especially document the `response_format="json"` + optional `json_schema=` contract on `ModelClient.chat`.

**Verify:** ruff + pyright + `uv run pytest` (watch `tests/test_model_clients.py`, `tests/test_json_utils.py`).

### Completion record

**Changes made:**

- `client/errors.py`: expanded every exception docstring to state *when* it is raised (connection unreachable, provider error / empty content, timeout). Added a module docstring listing how each provider SDK exception maps onto the shared types and noting agents catch these in `_try_llm()` to fall back deterministically.
- `client/model_client.py`: added a "How agents use this file" module section describing the `chat(...)` contract, and extracted the duplicated prompt builder from the two clients into a shared module-level `build_task_prompt(prompt, output, rules, inputs)` helper. The `chat` docstring contract was already accurate and is unchanged.
- `client/ollama_client.py`: `chat()` now calls the shared `build_task_prompt()`; deleted the private `_build_compact_prompt` duplicate. Fixed a stale docstring that claimed `LLMTimeoutError` fires "within 90 seconds" — the Ollama timeout is `self.timeout` (default 300 s). Tidied the module docstring indentation.
- `client/open_ai_client.py`: `chat()` now calls the shared `build_task_prompt()` (deleting the inline copy of the builder). Extracted the `response_format` construction into a named `_response_format_value(json_schema)` helper that documents the plain-JSON vs Structured-Outputs envelope, so the `chat` body reads as two clear branches.
- `client/json_utils.py`: rewrote the module docstring to be self-contained (removed the stale "see resume-done.md §8.7 / §8.8" archive pointer) and explain how agents use both functions. Renamed `_FENCE_RE` -> `_JSON_FENCE_RE`.
- `client/model_registry.py`: in `get_client_for_agent`, replaced the redundant `self.get(self._agent_clients[agent_name])` with `self.get(name)`; documented that `from_config` consumes the dict produced by `config.agents.get_agent_config()`. Everything else was already well-documented.
- `config/agents.py`: added a module-level `AGENT_NAMES` tuple (kills a duplicated 7-name list), fixed the stale `DEFAULT_PROVIDER` docstring line (the env var is never read; the real default-provider variable is `MODEL_PROVIDER`), extracted intent-named helpers `_effective_provider`, `_effective_model`, `_client_config`, and merged the two per-agent loops into one pass that builds both the `clients` entries and `agents` assignments. `get_model_summary()` reuses `AGENT_NAMES`. Output dict shapes are byte-identical to before.
- `logging_config.py`: expanded the `configure_logging()` docstring to explain the hard-coded per-module levels (client loggers at DEBUG, third-party SDKs suppressed to WARNING) and added inline comments for the formatter and logger sections.

**Behavior verification:**

- `uv run ruff check .` — pass
- `uv run ruff format .` — applied (3 files reformatted; no behavior change)
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest` — 485 passed in ~10s
- Manual probes:
  - `build_task_prompt('Do work', ['json'], ['rule 1','rule 2'], ['input a','input b'])` -> `'Task: Do work\nOutput format: json\nRules: rule 1 | rule 2\nInput: input a | input b'` (identical to previous inline output)
  - Empty override run: `get_agent_config()` -> `clients=['default']`, `agents={}`, `default='default'` (identical)
  - Override run with `COVER_LETTER_AGENT_MODEL=gpt-4o` / `_PROVIDER=openai` / `OPENAI_API_KEY=sk-test` -> only `cover_letter_agent_client` created with `{'provider': 'openai', 'model': 'gpt-4o', 'api_key': 'sk-test'}` (identical)
  - `get_model_summary()` -> 7 rows, all agents on `qwen2.5:7b-instruct` / `ollama` by default (identical)

**Commit:** `simplify: phase 1 - foundation plumbing (config/logging/errors/clients/json utils)`