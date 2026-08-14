# API Reference

This page documents the public programming surface of the pipeline: the LLM client abstraction, the agent and runner classes, and the renderer plus formatter helpers. Signature details are taken directly from the code; see `docs/architecture.md` for the system view and `docs/agents.md` for how the seven built-in agents use these APIs.

## 1. `ModelClient` — the LLM abstraction

`client/model_client.py` defines the abstract base class every provider implements. Agents never talk to a provider directly; they call `ModelClient.chat(...)`.

### `ModelClient` (ABC)

```python
class ModelClient(ABC):
    @abstractmethod
    async def chat(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
        response_format: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str: ...
```

#### The `chat()` contract

| Parameter | Type | Meaning |
|-----------|------|---------|
| `purpose` | `str` | System-level role/persona for this call. Sent as the system message. |
| `prompt` | `str` | The user-facing task or question. Sent as the user message. |
| `output` | `list[str]` | Expected output field names/labels; joined into the prompt as `Output format: ...`. |
| `rules` | `list[str]` | Constraints/guidelines; joined as `Rules: ...`. |
| `inputs` | `list[str]` | Additional context/raw data; joined as `Input: ...`. |
| `response_format` | `str` | Requested provider-native response mode. **`"json"` is the only supported value** and must be passed on every call; free-text responses are not part of the contract. |
| `json_schema` | `dict[str, Any] \| None` | Optional JSON Schema dict (from `client.json_utils.model_to_json_schema`) for provider Structured Outputs. When provided, the provider is asked to conform its output to the schema instead of plain JSON mode. Defaults to `None` (plain JSON mode). |

Returns the model's text response (`str`).

### Implementations

Both concrete clients build a compact, newline-delimited prompt via the shared `build_task_prompt()` helper in `client/model_client.py` (`Task: ... | Output format: ... | Rules: ... | Input: ...`) and send it as a `system` + `user` message pair. Both wrap provider errors into the [`client/errors.py`](client/errors.py) hierarchy: `LLMConnectionError`, `LLMResponseError`, `LLMTimeoutError`.

#### `OllamaClient` — `client/ollama_client.py`

```python
class OllamaClient(ModelClient):
    def __init__(self, model: str, timeout: int = 300) -> None: ...
```

- Talks to a locally running Ollama instance via `ollama.AsyncClient`.
- `model` — Ollama model tag (e.g. `"qwen2.5:7b-instruct"`).
- `timeout` — request timeout in seconds (default 300).
- **JSON mode is always on**: when `json_schema` is `None`, sends `format="json"`; when a schema is provided, sends `format=<schema dict>` (Ollama Structured Outputs).
- Empty response raises `LLMResponseError`.

#### `OpenAIClient` — `client/open_ai_client.py`

```python
class OpenAIClient(ModelClient):
    def __init__(self, model: str, api_key: str) -> None: ...
```

- Talks to the OpenAI API via `openai.AsyncOpenAI`, fixed 90-second timeout.
- `model` — OpenAI model name (e.g. `"gpt-4o-mini"`).
- `api_key` — OpenAI API key.
- **JSON mode is always on**: without a schema sends `response_format={"type": "json_object"}`; with a schema sends OpenAI Structured Outputs via `response_format={"type": "json_schema", "json_schema": {...}}`. The schema name is derived from the schema `title` by `_schema_name()` (falling back to `"output"`), because OpenAI requires a name matching `^[a-zA-Z0-9_-]{1,64}$`.
- Error translation is explicit: `AuthenticationError`/`RateLimitError`/`APIError` become `LLMResponseError`; `APIConnectionError` becomes `LLMConnectionError`; timeouts become `LLMTimeoutError`.

### Choosing a client per agent

Clients are created and assigned by `ModelClientRegistry` (`client/model_registry.py`) and `config/agents.py` (`build_registry()`, env-var driven) — see `docs/usage.md`, section 2.

## 2. Agents and the runner — `pipeline.py`

### `Agent` (protocol)

```python
class Agent(Protocol):
    async def run(self, inputs: dict[str, Any]) -> Any: ...
```

A structural type: any object whose `run(inputs)` coroutine returns something is a valid agent. `PipelineAgent` is the built-in implementation; the seven dedicated classes and user-supplied agents conform to this shape.

### `PipelineAgent`

```python
class PipelineAgent:
    def __init__(self, client: ModelClient, purpose: str) -> None: ...
    async def run(self, inputs: dict[str, Any]) -> Any: ...
```

A thin generic agent that delegates every call to `client.chat` with a fixed `purpose`.

- `run()` splits the `inputs` dict into the structured chat parameters and domain context:
  - `inputs["prompt"]` (required) → `prompt`
  - `inputs["output"]` (list) → `output`
  - `inputs["rules"]` (list) → `rules`
  - everything else → `context` strings formatted as `"key: value"` in `inputs`
- Returns the raw text response from the model client.
- The dedicated agent classes (see `docs/agents.md`) are the primary agents; `PipelineAgent` remains supported for compatibility and as a template for custom agents (see `docs/usage.md`, section 3).

### `AgentRunner`

```python
class AgentRunner:
    def __init__(
        self,
        agents: Mapping[str, Agent | None],
        registry: ModelClientRegistry | None = None,
    ) -> None: ...
    def run_agent(self, name: str, inputs: dict[str, Any]) -> Any: ...
    async def run_agent_async(self, name: str, inputs: dict[str, Any]) -> Any: ...
    def get_client_for_agent(self, name: str) -> ModelClient | None: ...
```

- `agents` — maps agent names to either pre-instantiated agent instances or agent classes (if `registry` is provided).
- `registry` — optional `ModelClientRegistry` for per-agent model assignment. When an agent value is a class, the runner instantiates it with `registry.get_client_for_agent(name)` and caches the instance (via `self.agents[name] = agent`).
- `run_agent()` is the synchronous convenience wrapper around `asyncio.run(self.run_agent_async(...))`.
- `run_agent_async()` runs the agent on **the current event loop** — this is the important design decision: it keeps all agents (and their shared async `ModelClient`) on a single event loop. Wrapping each call in its own `asyncio.run()` would close the loop after the first agent; subsequent agents then fail with "Event loop is closed" when using Ollama/OpenAI async clients. `run_resume_pipeline()` therefore calls the async core `_run_pipeline_core()` directly (never `asyncio.run` around each agent).
- Raises `KeyError` for unknown agent names, `TypeError` when the agent value is `None`.
- `get_client_for_agent()` returns the assigned client or `None` if there is no registry.

### Pipeline function

```python
def run_resume_pipeline(
    runner: AgentRunner,
    job_description: str,
    resume: str,
    *,
    candidate_name: str = "",
    company_name: str = "",
    resume_template: str = "modern",
    resume_templates: str | list[str] | None = None,
) -> dict[str, Any]:
```

Runs the full 7-agent chain on one event loop via `_run_pipeline_core()`. Returns 7 result keys (`parsed_job_description`, `parsed_resume`, `tailoring_strategy`, `rewritten_resume`, `ats_optimized_resume`, `polished_resume`, `cover_letter`) plus `output_files` when a candidate name is available (`candidate_name`, or the name parsed from the resume). `resume_template` picks the rendered resume layout (`"modern"`/`"classic"`/`"minimal"`); pass `resume_templates` (a key or list of keys) to render several layouts in one run — their files are namespaced `resume_{template}_*` with the template embedded in the filename. See `docs/usage.md`, section 1.

```python
def create_runner_from_config(
    agent_classes: dict[str, Any] | None = None,
) -> AgentRunner:
```

Builds a `ModelClientRegistry` from the environment (`build_registry()`) and returns `AgentRunner(agent_classes or DEFAULT_AGENT_CLASSES, registry=registry)`. `DEFAULT_AGENT_CLASSES` wires the seven dedicated classes.

## 3. `ResumeRenderer` — `client/templates/renderer.py`

Renders `RewriteOutput` and `CoverLetterOutput` models into plaintext, Markdown, DOCX, and PDF. Text formats use Jinja2 templates from `client.templates`; DOCX and PDF use python-docx and ReportLab respectively.

```python
class ResumeRenderer:
    def __init__(self, template_dir: Path | None = None) -> None: ...
```

Pass `template_dir` to load custom `.j2` templates; default is the built-in template dicts from `client.templates`.

### Text formats

```python
def render_plaintext(
    self,
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
    template: str = "modern",
) -> str:
```

Renders `resume` as clean plaintext using the named template (`"modern"`, `"classic"`, or `"minimal"`). Raises `KeyError` if the template is unknown.

```python
def render_markdown(
    self,
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
    template: str = "modern",
) -> str:
```

Renders `resume` as Markdown with the named template.

### Cover letter formats

```python
def render_cover_letter_plaintext(
    self,
    cover_letter: CoverLetterOutput,
    *,
    name: str = "",
    company: str = "",
    phone: str = "",
    email: str = "",
    linkedin: str = "",
    github: str = "",
) -> str:

def render_cover_letter_markdown(
    self,
    cover_letter: CoverLetterOutput,
    *,
    name: str = "",
    company: str = "",
    phone: str = "",
    email: str = "",
    linkedin: str = "",
    github: str = "",
) -> str:

def render_cover_letter_docx(
    self,
    cover_letter: CoverLetterOutput,
    *,
    name: str = "",
    company: str = "",
    phone: str = "",
    email: str = "",
    linkedin: str = "",
    github: str = "",
    output_path: str | Path | None = None,
) -> Path:

def render_cover_letter_pdf(
    self,
    cover_letter: CoverLetterOutput,
    *,
    name: str = "",
    company: str = "",
    phone: str = "",
    email: str = "",
    linkedin: str = "",
    github: str = "",
    output_path: str | Path | None = None,
) -> Path:
```

Render the letter in plaintext, Markdown, DOCX, or PDF. Contact fields (`phone`, `email`, `linkedin`, `github`) are joined with ` | ` into a header `contact_line`. The letter text is split on blank lines into opening / body / closing paragraphs (the template renders its own salutation and signature, so leading `Dear ...` and trailing `Sincerely, ...` blocks are stripped by `_split_letter_body`, which also promotes any trailing contact line into the header). The DOCX and PDF variants mirror that layout with the same styling as the resume binary formats (letter size, 1-inch margins, name at 14pt bold) and return the written `Path` (a temp file when `output_path` is `None`).

### Binary formats

```python
def render_docx(
    self,
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
    template: str = "modern",
    output_path: str | Path | None = None,
) -> Path:

def render_pdf(
    self,
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
    template: str = "modern",
    output_path: str | Path | None = None,
) -> Path:
```

- DOCX: letter-size pages, 1-inch margins, Calibri 11pt body, name at 14pt bold. `template` is accepted for API consistency (styling is fixed).
- PDF: built with ReportLab Platypus (no HTML intermediate), letter size, 1-inch margins, Helvetica base-14 fonts, mirroring the DOCX layout. ReportLab is required; an `ImportError` is raised if it is missing (install via `uv sync`).
- Both return the `Path` written; with `output_path=None` a fresh temp file is used.

### Everything at once

```python
def render_all(
    self,
    resume: RewriteOutput,
    cover_letter: CoverLetterOutput | None,
    *,
    candidate_name: str,
    company_name: str,
    output_dir: str | Path,
    resume_template: str = "modern",
    resume_templates: str | list[str] | None = None,
    phone: str = "",
    email: str = "",
    linkedin: str = "",
    github: str = "",
) -> dict[str, Path]:
```

Writes the four resume formats (`resume_plaintext`, `resume_markdown`, `resume_docx`, `resume_pdf`) and, when `cover_letter` is non-empty, the four letter formats (`cover_letter_plaintext`, `cover_letter_markdown`, `cover_letter_docx`, `cover_letter_pdf`). Files land in `output_dir` under timestamped, slugified names built by `build_output_path`. Returns `dict[str, Path]` keyed by format name.

By default a single resume layout (`resume_template`, `"modern"`) is rendered. Pass `resume_templates` (a template key or list of keys) to render several layouts in one call: each layout's files are namespaced `resume_{template}_plaintext` … `resume_{template}_pdf` and the filename embeds the template (`resume-{template}.{ext}`) so layouts don't overwrite each other. The cover letter formats are shared and unaffected by the template selection.

### Path helper

```python
@staticmethod
def build_output_path(
    document_type: str,
    *,
    candidate_name: str,
    company_name: str,
    output_dir: str | Path,
    ext: str | None = None,
) -> Path:
```

Builds `{output_dir}/{YYYYMMDD_HHMM}_{candidate}_{company}_{document_type}.{ext}`. Name segments are slugified (`_slugify`: lowercase, non-alphanumerics → single `-`, trimmed) so the result is filesystem-safe. `ext` defaults per `_DEFAULT_EXTENSIONS` when `None`. Pure path logic — no file I/O.

## 4. `formatter` helpers — `client/formatter.py`

Standalone string formatters for pipeline outputs (complement the template renderer; usable without Jinja2).

```python
def format_resume_markdown(
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
) -> str:
```

Converts a `RewriteOutput` to a clean Markdown resume with `#`/`##`/`###` headings, bolded headers, and bullet lists for skills/experience/certifications/projects/education.

```python
def format_resume_plain(
    resume: RewriteOutput,
    *,
    name: str = "",
    title: str = "",
) -> str:
```

Converts a `RewriteOutput` to plain-text ATS-friendly format: no Markdown syntax, no decorative characters, uppercase section labels (`SUMMARY`, `SKILLS`, `EXPERIENCE`, ...).

```python
def format_cover_letter(letter: CoverLetterOutput | str) -> str:
```

Accepts a `CoverLetterOutput` or a raw string, strips surrounding whitespace, fixes common Unicode encoding artifacts (curly quotes `""''`, en/em dashes, ellipsis, non-breaking space, arrows → ASCII equivalents), collapses runs of whitespace within lines, and normalizes to single blank line between paragraphs.

## References

- `client/model_client.py` — the `ModelClient` ABC.
- `client/ollama_client.py` — `OllamaClient` implementation.
- `client/open_ai_client.py` — `OpenAIClient` implementation.
- `client/model_registry.py` — `ModelClientRegistry` per-agent client resolution.
- `client/errors.py` — `LLMConnectionError` / `LLMResponseError` / `LLMTimeoutError`.
- `client/json_utils.py` — `parse_json_response`, `load_json_safe`, `model_to_json_schema`.
- `pipeline.py` — `Agent`, `PipelineAgent`, `AgentRunner`, `run_resume_pipeline`, `_run_pipeline_core`, `create_runner_from_config`, `DEFAULT_AGENT_CLASSES`.
- `client/templates/renderer.py` — `ResumeRenderer` and module-level helpers (`_default_extension`, `_split_letter_body`, ...).
- `client/formatter.py` — `format_resume_markdown`, `format_resume_plain`, `format_cover_letter`.
- `client/models.py` — `RewriteOutput`, `CoverLetterOutput`, and the other output models.
- `docs/architecture.md`, `docs/agents.md`, `docs/usage.md` — companion guides.
- `tests/test_renderer.py`, `tests/test_formatter.py` — behavior examples for these APIs.

---

## Related

- [Previous: `agents.md`](agents.md)
- [Next: `architecture.md`](architecture.md)
- [Index: `docs/README.md`](README.md)