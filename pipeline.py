"""
pipeline.py
Multi-agent resume optimization pipeline.

Defines ``AgentRunner`` (agent orchestration) and ``run_resume_pipeline``,
which chains 7 specialized agents to transform a raw job description and
resume into an ATS-optimized resume and tailored cover letter.

Stage table (agent -> output key -> consumed by):

====================  ======================  ================================
Step  Agent name       Output key              Consumed by
====================  ======================  ================================
1     jd_parsing       parsed_job_description  gap_analysis, cover_letter
2     resume_parsing   parsed_resume           gap_analysis, resume_rewrite,
                                               cover_letter, rendering
3     gap_analysis     tailoring_strategy      resume_rewrite, cover_letter
4     resume_rewrite   rewritten_resume        ats_compliance
5     ats_compliance   ats_optimized_resume    tone_polishing
6     tone_polishing   polished_resume         final result
7     cover_letter     cover_letter            final result
====================  ======================  ================================

The output keys are the ``dict`` keys returned by :func:`run_resume_pipeline`.
Note the resume parser's model is also the final ``RewriteOutput`` basis for
rendering (see ``_to_rewrite_output``); ``_run_pipeline_core`` runs the chain
via ``_run_stage`` calls, one per row above.

All 7 stages run as dedicated classes (``JDParsingAgent`` through
``CoverLetterAgent``); generic ``PipelineAgent`` wrappers remain supported
for compatibility.  Per-agent model assignment is provided via
``ModelClientRegistry`` and ``create_runner_from_config``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

from client.agents import (
    ATSComplianceAgent,
    CoverLetterAgent,
    GapAnalysisAgent,
    JDParsingAgent,
    ResumeParsingAgent,
    ResumeRewriteAgent,
    TonePolishingAgent,
)
from client.model_client import ModelClient
from client.model_registry import ModelClientRegistry
from client.models import CoverLetterOutput, ResumeParsingOutput, RewriteOutput
from client.templates.renderer import ResumeRenderer
from config.agents import build_registry
from logging_config import configure_logging

logger = logging.getLogger(__name__)

# All 7 dedicated agent classes, keyed by their pipeline agent name.
# Used as the default wiring for ``create_runner_from_config``.
DEFAULT_AGENT_CLASSES: dict[str, Any] = {
    "jd_parsing_agent": JDParsingAgent,
    "resume_parsing_agent": ResumeParsingAgent,
    "gap_analysis_agent": GapAnalysisAgent,
    "resume_rewrite_agent": ResumeRewriteAgent,
    "ats_compliance_agent": ATSComplianceAgent,
    "tone_polishing_agent": TonePolishingAgent,
    "cover_letter_agent": CoverLetterAgent,
}


class Agent(Protocol):
    """Structural type for any agent usable with ``AgentRunner``.

    Any object implementing ``run(inputs) -> Any`` satisfies this protocol.
    ``PipelineAgent`` is the built-in implementation; custom agents (e.g.
    thin wrappers around ``SimpleAgent``) can be used as long as they
    conform to this signature.
    """

    async def run(self, inputs: dict[str, Any]) -> Any:
        """Execute the agent with the given inputs.

        Args:
            inputs: Dictionary of input data for the agent.  Keys and
                values depend on the concrete implementation.

        Returns:
            Agent-specific output; typically a dict with result fields.
        """


class PipelineAgent:
    """Agent that delegates to a ``ModelClient`` with a fixed purpose.

    This is the generic wrapper that exists for backward compatibility with
    the dedicated per-agent classes (``JDParsingAgent`` through
    ``CoverLetterAgent``).  The dedicated classes add Pydantic validation
    and deterministic fallbacks; ``PipelineAgent`` keeps working for callers
    that pass raw ``prompt``/``output``/``rules`` inputs and expect a raw
    chat response.  Conforms to the ``Agent`` Protocol so it can be used
    with ``AgentRunner``.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
        purpose: System-level role or persona for this agent.
    """

    def __init__(self, client: ModelClient, purpose: str) -> None:
        """Initialize the agent with a model client and fixed purpose.

        Args:
            client: An LLM client implementing ``ModelClient.chat``.
            purpose: System-level role or persona used for every ``chat``
                call this agent makes.
        """
        self.client = client
        self.purpose = purpose

    async def run(self, inputs: dict[str, Any]) -> Any:
        """Execute the agent by forwarding inputs to the model client.

        The ``inputs`` dict is split into structured LLM parameters
        (``prompt``, ``output``, ``rules``) and domain-specific context
        keys, which are serialised into a list of ``"key: value"`` strings.

        Args:
            inputs: Must contain at least ``"prompt"``.  Optional keys:
                ``"output"`` (list of expected field names),
                ``"rules"`` (list of constraints), plus any additional
                domain-specific keys that become context strings.

        Returns:
            The raw text response from the model client.
        """
        prompt = inputs.get("prompt", "")
        output = inputs.get("output", [])
        rules = inputs.get("rules", [])
        context = [
            f"{k}: {v}"
            for k, v in inputs.items()
            if k not in ("prompt", "output", "rules")
        ]
        return await self.client.chat(
            self.purpose, prompt, output, rules, context, response_format="json"
        )


class AgentRunner:
    """Dispatches named agents with input dictionaries.

    Supports two modes of operation:

    1. **Pre-instantiated agents**: Pass agents with their ``ModelClient``
       already assigned via constructor.
    2. **Registry-based**: Pass agent classes and a ``ModelClientRegistry``,
       and the runner will instantiate each agent with the correct client.

    Args:
        agents: Mapping of agent names to agent instances or callables.
        registry: Optional ``ModelClientRegistry`` for per-agent model
            assignment. If provided, agent classes can be passed as values
            and will be instantiated with the appropriate client.
    """

    def __init__(
        self,
        agents: Mapping[str, Agent | None],
        registry: ModelClientRegistry | None = None,
    ) -> None:
        """Initialize the runner with a set of named agents.

        Args:
            agents: Dictionary mapping agent names to agent objects or
                agent classes (if ``registry`` is provided).
            registry: Optional registry for per-agent model assignment.
        """
        self.agents = dict(agents)
        self.registry = registry

    def run_agent(self, name: str, inputs: dict[str, Any]) -> Any:
        """Run a named agent with the given inputs.

        Args:
            name: The agent name (must exist in ``self.agents``).
            inputs: Dictionary of input data for the agent.

        Returns:
            The agent's output (type depends on the agent).

        Raises:
            KeyError: If the agent name is not registered.
        """
        return asyncio.run(self.run_agent_async(name, inputs))

    async def run_agent_async(self, name: str, inputs: dict[str, Any]) -> Any:
        """Execute a named agent within the current event loop.

        This is the coroutine form of :meth:`run_agent`.  It avoids creating
        a fresh event loop per agent so that all agents share the same loop;
        the dedicated agent classes reuse a single ``ModelClient`` whose
        ``AsyncClient`` is bound to an event loop.  Wrapping every
        ``run_agent`` call in its own ``asyncio.run()`` closed that loop after
        the first agent, so subsequent agents failed with "Event loop is
        closed" when using Ollama/OpenAI async clients.

        Args:
            name: The agent name (must exist in ``self.agents``).
            inputs: Dictionary of input data for the agent.

        Returns:
            The agent's output (type depends on the agent).

        Raises:
            KeyError: If the agent name is not registered.
        """
        if name not in self.agents:
            raise KeyError(f"Agent '{name}' not found")

        agent = self.agents[name]
        if agent is None:
            raise TypeError(f"Agent '{name}' is None (not instantiated)")
        logger.info("Running agent: %s", name)
        start = time.monotonic()

        # Instantiate-on-first-use: when the registry is present, a class
        # value (as opposed to an instance) is lazily built with the
        # per-agent client on first dispatch, then cached so later runs
        # reuse the same instance (and the same bound event loop).
        if isinstance(agent, type) and self.registry is not None:
            client = self.registry.get_client_for_agent(name)
            agent = agent(client)
            self.agents[name] = agent  # Cache the instance for reuse

        try:
            result: Any = await agent.run(inputs)
            elapsed = time.monotonic() - start
            logger.info("Agent %s completed in %.1fs", name, elapsed)
            return result
        except Exception as e:
            logger.error("Agent '%s' failed: %s", name, e, exc_info=True)
            raise

    def get_client_for_agent(self, name: str) -> ModelClient | None:
        """Get the model client assigned to a specific agent.

        Args:
            name: The agent name.

        Returns:
            The ``ModelClient`` for this agent, or ``None`` if no registry.
        """
        if self.registry is None:
            return None
        return self.registry.get_client_for_agent(name)


def _extract_field(result: Any, *fields: str) -> Any:
    """Return the first present dict/attribute field from ``result``, else ``result``.

    Dedicated agents return validated Pydantic models (e.g.
    ``GapAnalysisOutput``) that are themselves the stage output, while
    generic ``PipelineAgent`` wrappers return a raw dict with named result
    keys.  This helper normalises both shapes so ``run_resume_pipeline``
    accepts a runner built from either kind of agent: it looks up the
    requested fields either on a dict or (via ``getattr``) on a model,
    falling back to returning ``result`` unchanged when none is found.

    Args:
        result: The agent's return value (dict or model).
        fields: Candidate field names to look up on the result.

    Returns:
        The first present field, otherwise ``result``.
    """
    if isinstance(result, dict):
        for field in fields:
            if field in result:
                return cast(Any, result[field])
    elif result is not None:
        for field in fields:
            if hasattr(result, field):
                return getattr(result, field)
    return cast(Any, result)


def _to_rewrite_output(parsed_resume: Any) -> RewriteOutput:
    """Convert the Resume Parsing output into a ``RewriteOutput``.

    The pipeline uses the structured ``ResumeParsingOutput`` as the basis
    for the final rendered resume (fields match ``RewriteOutput``).  Handles
    both a validated Pydantic model and a raw dict from a generic agent.

    Args:
        parsed_resume: The Resume Parsing stage output (model or dict).

    Returns:
        A ``RewriteOutput`` with the parsed resume data.
    """
    if isinstance(parsed_resume, ResumeParsingOutput):
        return RewriteOutput.model_validate(parsed_resume.model_dump())
    if isinstance(parsed_resume, RewriteOutput):
        return parsed_resume
    if isinstance(parsed_resume, dict):
        return RewriteOutput.model_validate(parsed_resume)
    return RewriteOutput()


def _resume_candidate_name(parsed_resume: Any) -> str:
    """Return the candidate name parsed from the resume, or empty.

    Reads ``ResumeParsingOutput.name`` (or the ``"name"`` key of a raw dict
    from a generic agent) so runs that omit the explicit ``candidate_name``
    field -- e.g. the web UI, where it is optional -- can still render named
    output files.
    """
    if isinstance(parsed_resume, ResumeParsingOutput):
        return parsed_resume.name.strip()
    if isinstance(parsed_resume, dict):
        name = cast(dict[str, Any], parsed_resume).get("name")
        if isinstance(name, str):
            return name.strip()
    return ""


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
    """Run the full 7-agent resume optimization pipeline.

    Args:
        runner: An ``AgentRunner`` instance with all 7 agents registered.
        job_description: Raw job description text.
        resume: Raw resume text.
        candidate_name: Candidate name for rendered output headers and
            filenames.  When empty, the name parsed from the resume is used;
            when neither is available, file rendering is skipped.
        company_name: Target company name for rendered output filenames.
        resume_template: Template key (``"modern"``/``"classic"``/
            ``"minimal"``) for the rendered resume, used when
            *resume_templates* is ``None``.
        resume_templates: Optional template key or list of keys to render
            several resume layouts in one run (keys become
            ``resume_{template}_*`` and files are named ``resume-{template}``).

    Returns:
        Dictionary with keys: ``parsed_job_description``, ``parsed_resume``,
        ``tailoring_strategy``, ``rewritten_resume``, ``ats_optimized_resume``,
        ``polished_resume``, ``cover_letter``, and ``output_files`` (a
        ``dict[str, Path]`` mapping format name to written file, empty when
        no candidate name was available for rendering).
    """
    configure_logging()

    # Run the whole 7-agent chain on a single event loop so all agents share
    # one loop (and the shared async ModelClient's bound event loop).  This
    # avoids each agent opening+closing its own loop (see run_agent_async).
    return asyncio.run(
        _run_pipeline_core(
            runner,
            job_description,
            resume,
            candidate_name=candidate_name,
            company_name=company_name,
            resume_template=resume_template,
            resume_templates=resume_templates,
        )
    )


async def _run_stage(
    runner: AgentRunner,
    agent_name: str,
    *,
    prompt: str = "",
    output: list[str] | None = None,
    rules: list[str] | None = None,
    fields: tuple[str, ...] = (),
    **context: Any,
) -> Any:
    """Run one agent stage and return its resolved output field.

    Assembles the stage inputs: ``prompt``/``output``/``rules`` (the
    generic-agent contract keys, omitted when empty) plus any keyword
    ``context`` entries, runs the named agent via
    ``runner.run_agent_async``, then resolves the result through
    ``_extract_field``.  Parsing agents (stages 1-2) pass no
    ``prompt``/``output``/``rules`` and often no ``fields``; the raw result
    is then returned unchanged.

    Args:
        runner: The ``AgentRunner`` dispatching the named agent.
        agent_name: The registered agent name to invoke.
        prompt: Prompt text for chat-style agents (omitted when empty).
        output: Expected output field names for chat-style agents (omitted
            when empty).
        rules: Constraint list for chat-style agents (omitted when empty).
        fields: Candidate field names to resolve from the result via
            ``_extract_field``.  The first present field wins; when empty,
            the raw result is returned unchanged.
        **context: Additional keyword inputs forwarded verbatim into the
            agent's input dict.

    Returns:
        The resolved stage output: the requested field value when found,
        otherwise the raw agent result.
    """
    inputs: dict[str, Any] = {}
    if prompt:
        inputs["prompt"] = prompt
    if output:
        inputs["output"] = output
    if rules:
        inputs["rules"] = rules
    inputs.update(context)

    result = await runner.run_agent_async(agent_name, inputs)
    return _extract_field(result, *fields)


async def _run_pipeline_core(
    runner: AgentRunner,
    job_description: str,
    resume: str,
    *,
    candidate_name: str = "",
    company_name: str = "",
    resume_template: str = "modern",
    resume_templates: str | list[str] | None = None,
) -> dict[str, Any]:
    """Async core of :func:`run_resume_pipeline` executed on one event loop.

    Args:
        runner: An ``AgentRunner`` instance with all 7 agents registered.
        job_description: Raw job description text.
        resume: Raw resume text.
        candidate_name: Candidate name for rendered output headers and
            filenames.  When empty, the name parsed from the resume is used;
            when neither is available, file rendering is skipped.
        company_name: Target company name for rendered output filenames.
        resume_template: Template key for the rendered resume, used when
            *resume_templates* is ``None``.
        resume_templates: Optional template key or list of keys to render
            several resume layouts in one run.
    """

    total_agents = 7
    pipeline_start = time.monotonic()

    logger.info("Pipeline starting")
    agent_names = list(runner.agents.keys())
    logger.info("Agents configured: %s", ", ".join(agent_names))

    # 1. JD Parsing
    parsed_job_description: Any = await _run_stage(
        runner,
        "jd_parsing_agent",
        fields=("parsed_job_description",),
        job_description=job_description,
    )

    # 2. Resume Parsing
    parsed_resume: Any = await _run_stage(runner, "resume_parsing_agent", resume=resume)

    # 3. Gap Analysis
    tailoring_strategy: Any = await _run_stage(
        runner,
        "gap_analysis_agent",
        prompt="Compare the job description and resume. Produce a tailoring strategy.",
        output=["tailoring_strategy"],
        rules=["Be specific and actionable"],
        fields=("tailoring_strategy",),
        parsed_job_description=parsed_job_description,
        parsed_resume=parsed_resume,
    )

    # 4. Resume Rewrite
    rewritten_resume: Any = await _run_stage(
        runner,
        "resume_rewrite_agent",
        prompt="Rewrite the resume to match the job requirements using this strategy.",
        output=["rewritten_resume"],
        rules=["Keep formatting", "Use strong action verbs"],
        fields=("rewritten_resume",),
        parsed_resume=parsed_resume,
        tailoring_strategy=tailoring_strategy,
    )

    # 5. ATS Compliance
    ats_optimized_resume: Any = await _run_stage(
        runner,
        "ats_compliance_agent",
        prompt="Check and optimize this resume for ATS systems.",
        output=["ats_optimized_resume"],
        rules=["Maintain content accuracy", "Optimize keywords"],
        fields=("ats_optimized_resume", "final_resume"),
        rewritten_resume=rewritten_resume,
    )

    # 6. Tone Polishing
    polished_resume: Any = await _run_stage(
        runner,
        "tone_polishing_agent",
        prompt="Polish the tone and clarity of this resume.",
        output=["polished_resume"],
        rules=["Maintain professional tone", "Be concise"],
        fields=("polished_resume",),
        ats_optimized_resume=ats_optimized_resume,
    )

    # 7. Cover Letter
    cover_letter: Any = await _run_stage(
        runner,
        "cover_letter_agent",
        prompt="Generate a tailored cover letter for this job application.",
        output=["cover_letter"],
        rules=["Match the resume tone", "Address key requirements"],
        fields=("cover_letter",),
        parsed_job_description=parsed_job_description,
        parsed_resume=parsed_resume,
        tailoring_strategy=tailoring_strategy,
    )

    # Optional file output via ResumeRenderer.  The explicit candidate name
    # wins when provided; otherwise the name parsed from the resume is used,
    # so runs that omit the field (e.g. the web UI) still produce files.
    output_files: dict[str, Path] = {}
    render_name = candidate_name or _resume_candidate_name(parsed_resume)
    if render_name:
        resume_data = _to_rewrite_output(parsed_resume)
        letter_data = (
            CoverLetterOutput(cover_letter=cover_letter) if cover_letter else None
        )
        output_dir = Path("output")
        renderer = ResumeRenderer()
        output_files = renderer.render_all(
            resume_data,
            letter_data,
            candidate_name=render_name,
            company_name=company_name,
            output_dir=output_dir,
            resume_template=resume_template,
            resume_templates=resume_templates,
        )
        logger.info("Rendered %d output file(s) into %s", len(output_files), output_dir)
    else:
        logger.info("Skipping file rendering (no candidate name available)")

    total_time = time.monotonic() - pipeline_start
    logger.info(
        "Pipeline completed in %.1fs — %d/%d agents succeeded",
        total_time,
        total_agents,
        total_agents,
    )

    return {
        "parsed_job_description": parsed_job_description,
        "parsed_resume": parsed_resume,
        "tailoring_strategy": tailoring_strategy,
        "rewritten_resume": rewritten_resume,
        "ats_optimized_resume": ats_optimized_resume,
        "polished_resume": polished_resume,
        "cover_letter": cover_letter,
        "output_files": output_files,
    }


def _load_persisted_overrides() -> dict[str, dict[str, str | None]]:
    """Load the per-agent model overrides persisted by the web layer.

    The web API persists model/provider edits in SQLite (see
    ``app.model_store.ModelStore``).  This helper reads the same store so CLI
    runs (``main``/``sample_run``) and the API resolve the identical effective
    model configuration for identical inputs — the only thing that can make
    the two entry points produce different output is a different model set.
    When the store does not exist yet (no overrides to honor) or cannot be
    read, an empty dict is returned so the environment-variable configuration
    stays in effect.

    Returns:
        Mapping of ``{agent: {"provider": ..., "model": ...}}``, empty when
        there are no persisted overrides.
    """
    db_path = os.getenv("MODEL_DB_PATH") or "db.sqlite3"
    if not Path(db_path).is_file():
        return {}
    try:
        from app.model_store import ModelStore

        return ModelStore(db_path=db_path).all_overrides()
    except Exception:
        logger.warning(
            "Could not read persisted model overrides at %s; using environment "
            "configuration",
            db_path,
            exc_info=True,
        )
        return {}


def create_runner_from_config(
    agent_classes: dict[str, Any] | None = None,
    overrides: Mapping[str, Mapping[str, str | None]] | None = None,
) -> AgentRunner:
    """Create an ``AgentRunner`` using environment-based configuration.

    Reads model assignments from environment variables (see ``config.agents``
    for details) and builds a ``ModelClientRegistry`` with per-agent clients.

    Args:
        agent_classes: Optional mapping of agent names to agent classes.
            When ``None``, all 7 dedicated pipeline agents are wired up
            (see :data:`DEFAULT_AGENT_CLASSES`).
        overrides: Optional persisted (database) provider/model overrides
            keyed by agent name; passed through to ``config.agents`` so they
            win over the environment-var configuration.  Used by the web API
            (``app/main.py``) so model edits survive restarts.  When ``None``
            (the default), the overrides persisted by the web layer are
            loaded from the same SQLite store (see
            :func:`_load_persisted_overrides`), so CLI and API entry points
            resolve the identical effective model configuration.

    Returns:
        A configured ``AgentRunner`` with the registry attached.

    Example::

        from pipeline import create_runner_from_config, run_resume_pipeline

        runner = create_runner_from_config()
        results = run_resume_pipeline(runner, jd_text, resume_text)
    """
    if overrides is None:
        overrides = _load_persisted_overrides()
    registry = build_registry(overrides=overrides)
    return AgentRunner(agent_classes or DEFAULT_AGENT_CLASSES, registry=registry)


def sample_run() -> None:
    """Demonstrate the full 7-agent pipeline end-to-end.

    Builds a ``ModelClientRegistry`` from the environment plus any overrides
    persisted by the web layer (see ``config.agents`` and
    ``create_runner_from_config``) and wires all 7 dedicated agent classes
    into an ``AgentRunner`` via ``create_runner_from_config``.  The agents
    are executed sequentially via ``run_resume_pipeline``.

    Replace the placeholder JD and resume text with real content to see
    meaningful output.
    """
    runner_instance = create_runner_from_config()

    jd_text = "Paste JD here..."
    resume_text = "Paste resume here..."

    results = run_resume_pipeline(
        runner_instance,
        jd_text,
        resume_text,
        candidate_name="Your Name",
        company_name="Company",
    )

    print("=== Polished Resume ===")
    print(results["polished_resume"])
    print("\n=== Cover Letter ===")
    print(results["cover_letter"])


def main(argv: list[str] | None = None) -> int:
    """Run the full 7-agent pipeline from the command line.

    Two modes:

    - ``python pipeline.py`` -> runs ``sample_run()`` with placeholder text.
    - ``python pipeline.py --resume <file> --job-description <file>`` -> runs
      the real pipeline against those files and prints the polished resume,
      cover letter, and any rendered output files.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 2 on a usage / file error).
    """
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Run the 7-agent resume optimization pipeline.",
    )
    parser.add_argument(
        "--resume",
        metavar="PATH",
        help="Path to the resume text file (.txt or otherwise plain text).",
    )
    parser.add_argument(
        "--job-description",
        "--jd",
        dest="job_description",
        metavar="PATH",
        help="Path to the job description text file.",
    )
    parser.add_argument(
        "--candidate-name",
        default="",
        metavar="NAME",
        help="Candidate name for rendered output headers; enables file rendering.",
    )
    parser.add_argument(
        "--company-name",
        default="",
        metavar="NAME",
        help="Target company name used in rendered output filenames.",
    )
    parser.add_argument(
        "--template",
        default="modern",
        choices=["modern", "classic", "minimal", "all"],
        help=(
            "Resume layout template to render (modern, classic, minimal) or "
            "'all' to render every layout in one run. Defaults to modern."
        ),
    )
    args = parser.parse_args(argv)

    # Step 1: no file arguments -> backward-compatible demo run (placeholders).
    if not args.resume and not args.job_description:
        sample_run()
        return 0

    # Step 2: file mode requires both inputs; report any missing flags.
    missing: list[str] = []
    if not args.resume:
        missing.append("--resume")
    if not args.job_description:
        missing.append("--job-description")
    if missing:
        parser.error(f"missing required argument(s): {', '.join(missing)}")

    # Step 3: validate both paths exist before reading them.
    resume_path = Path(args.resume)
    jd_path = Path(args.job_description)

    if not resume_path.is_file():
        parser.error(f"resume file not found: {resume_path}")
    if not jd_path.is_file():
        parser.error(f"job description file not found: {jd_path}")

    # Step 4: read inputs and run the full pipeline.
    resume_text = resume_path.read_text(encoding="utf-8")
    jd_text = jd_path.read_text(encoding="utf-8")

    runner_instance = create_runner_from_config()
    template_args: dict[str, Any] = (
        {"resume_templates": ["modern", "classic", "minimal"]}
        if args.template == "all"
        else {"resume_template": args.template}
    )
    results = run_resume_pipeline(
        runner_instance,
        jd_text,
        resume_text,
        candidate_name=args.candidate_name,
        company_name=args.company_name,
        **template_args,
    )

    print("=== Polished Resume ===")
    print(results["polished_resume"])
    print("\n=== Cover Letter ===")
    print(results["cover_letter"])

    # Step 5: print results and any rendered output files.
    output_files: dict[str, Path] = results.get("output_files") or {}
    if output_files:
        print("\n=== Rendered Files ===")
        for format_name, path in sorted(output_files.items()):
            print(f"{format_name}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
