"""
pipeline.py
Multi-agent resume optimization pipeline.

Defines ``AgentRunner`` (agent orchestration) and ``run_resume_pipeline``,
which chains 7 specialized agents to transform a raw job description and
resume into an ATS-optimized resume and tailored cover letter.

All 7 stages run as dedicated classes (``JDParsingAgent`` through
``CoverLetterAgent``); generic ``PipelineAgent`` wrappers remain supported
for compatibility.  Per-agent model assignment is provided via
``ModelClientRegistry`` and ``create_runner_from_config``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
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

    Conforms to the ``Agent`` Protocol so it can be used with ``AgentRunner``.

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

        # If agent is a class (not instantiated), instantiate with registry client
        if isinstance(agent, type) and self.registry is not None:
            client = self.registry.get_client_for_agent(name)
            agent = agent(client)
            self.agents[name] = agent  # Cache the instance

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


def run_resume_pipeline(
    runner: AgentRunner,
    job_description: str,
    resume: str,
    *,
    candidate_name: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    """Run the full 7-agent resume optimization pipeline.

    Args:
        runner: An ``AgentRunner`` instance with all 7 agents registered.
        job_description: Raw job description text.
        resume: Raw resume text.
        candidate_name: Candidate name for rendered output headers and
            filenames.  When empty, file rendering is skipped.
        company_name: Target company name for rendered output filenames.

    Returns:
        Dictionary with keys: ``parsed_job_description``, ``parsed_resume``,
        ``tailoring_strategy``, ``rewritten_resume``, ``ats_optimized_resume``,
        ``polished_resume``, ``cover_letter``, and ``output_files`` (a
        ``dict[str, Path]`` mapping format name to written file, empty when
        ``candidate_name`` was not provided).
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
        )
    )


async def _run_pipeline_core(
    runner: AgentRunner,
    job_description: str,
    resume: str,
    *,
    candidate_name: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    """Async core of :func:`run_resume_pipeline` executed on one event loop."""

    total_agents = 7
    pipeline_start = time.monotonic()

    logger.info("Pipeline starting")
    agent_names = list(runner.agents.keys())
    logger.info("Agents configured: %s", ", ".join(agent_names))

    # 1. JD Parsing Agent
    jd_result = await runner.run_agent_async(
        "jd_parsing_agent",
        {
            "job_description": job_description,
        },
    )
    parsed_job_description: Any = _extract_field(jd_result, "parsed_job_description")

    # 2. Resume Parsing Agent
    resume_result = await runner.run_agent_async(
        "resume_parsing_agent",
        {
            "resume": resume,
        },
    )
    parsed_resume: Any = resume_result

    # 3. Gap Analysis Agent
    gap_result = await runner.run_agent_async(
        "gap_analysis_agent",
        {
            "prompt": (
                "Compare the job description and resume. Produce a tailoring strategy."
            ),
            "output": ["tailoring_strategy"],
            "rules": ["Be specific and actionable"],
            "parsed_job_description": parsed_job_description,
            "parsed_resume": parsed_resume,
        },
    )
    tailoring_strategy: Any = _extract_field(gap_result, "tailoring_strategy")

    # 4. Resume Rewrite Agent
    rewrite_result = await runner.run_agent_async(
        "resume_rewrite_agent",
        {
            "prompt": (
                "Rewrite the resume to match the job requirements using this strategy."
            ),
            "output": ["rewritten_resume"],
            "rules": ["Keep formatting", "Use strong action verbs"],
            "parsed_resume": parsed_resume,
            "tailoring_strategy": tailoring_strategy,
        },
    )
    rewritten_resume: Any = _extract_field(rewrite_result, "rewritten_resume")

    # 5. ATS Compliance Agent
    ats_result = await runner.run_agent_async(
        "ats_compliance_agent",
        {
            "prompt": "Check and optimize this resume for ATS systems.",
            "output": ["ats_optimized_resume"],
            "rules": ["Maintain content accuracy", "Optimize keywords"],
            "rewritten_resume": rewritten_resume,
        },
    )
    ats_optimized_resume: Any = _extract_field(
        ats_result, "ats_optimized_resume", "final_resume"
    )

    # 6. Tone Polishing Agent
    tone_result = await runner.run_agent_async(
        "tone_polishing_agent",
        {
            "prompt": "Polish the tone and clarity of this resume.",
            "output": ["polished_resume"],
            "rules": ["Maintain professional tone", "Be concise"],
            "ats_optimized_resume": ats_optimized_resume,
        },
    )
    polished_resume: Any = _extract_field(tone_result, "polished_resume")

    # 7. Cover Letter Agent
    cover_result = await runner.run_agent_async(
        "cover_letter_agent",
        {
            "prompt": "Generate a tailored cover letter for this job application.",
            "output": ["cover_letter"],
            "rules": ["Match the resume tone", "Address key requirements"],
            "parsed_job_description": parsed_job_description,
            "parsed_resume": parsed_resume,
            "tailoring_strategy": tailoring_strategy,
        },
    )
    cover_letter: Any = _extract_field(cover_result, "cover_letter")

    # Optional file output via ResumeRenderer.  Skipped when no candidate
    # name was provided (candidate_name is the gate for rendering).
    output_files: dict[str, Path] = {}
    if candidate_name:
        resume_data = _to_rewrite_output(parsed_resume)
        letter_data = (
            CoverLetterOutput(cover_letter=cover_letter) if cover_letter else None
        )
        output_dir = Path("output")
        renderer = ResumeRenderer()
        output_files = renderer.render_all(
            resume_data,
            letter_data,
            candidate_name=candidate_name,
            company_name=company_name,
            output_dir=output_dir,
        )
        logger.info("Rendered %d output file(s) into %s", len(output_files), output_dir)
    else:
        logger.info("Skipping file rendering (candidate_name is empty)")

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


def create_runner_from_config(
    agent_classes: dict[str, Any] | None = None,
) -> AgentRunner:
    """Create an ``AgentRunner`` using environment-based configuration.

    Reads model assignments from environment variables (see ``config.agents``
    for details) and builds a ``ModelClientRegistry`` with per-agent clients.

    Args:
        agent_classes: Optional mapping of agent names to agent classes.
            When ``None``, all 7 dedicated pipeline agents are wired up
            (see :data:`DEFAULT_AGENT_CLASSES`).

    Returns:
        A configured ``AgentRunner`` with the registry attached.

    Example::

        from pipeline import create_runner_from_config, run_resume_pipeline

        runner = create_runner_from_config()
        results = run_resume_pipeline(runner, jd_text, resume_text)
    """
    registry = build_registry()
    return AgentRunner(agent_classes or DEFAULT_AGENT_CLASSES, registry=registry)


def sample_run() -> None:
    """Demonstrate the full 7-agent pipeline end-to-end.

    Builds a ``ModelClientRegistry`` from the environment (see
    ``config.agents``) and wires all 7 dedicated agent classes into an
    ``AgentRunner`` via ``create_runner_from_config``.  The agents are
    executed sequentially via ``run_resume_pipeline``.

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
    args = parser.parse_args(argv)

    # No file arguments -> backward-compatible demo run with placeholders.
    if not args.resume and not args.job_description:
        sample_run()
        return 0

    # File mode requires both inputs.
    missing: list[str] = []
    if not args.resume:
        missing.append("--resume")
    if not args.job_description:
        missing.append("--job-description")
    if missing:
        parser.error(f"missing required argument(s): {', '.join(missing)}")

    resume_path = Path(args.resume)
    jd_path = Path(args.job_description)

    if not resume_path.is_file():
        parser.error(f"resume file not found: {resume_path}")
    if not jd_path.is_file():
        parser.error(f"job description file not found: {jd_path}")

    resume_text = resume_path.read_text(encoding="utf-8")
    jd_text = jd_path.read_text(encoding="utf-8")

    runner_instance = create_runner_from_config()
    results = run_resume_pipeline(
        runner_instance,
        jd_text,
        resume_text,
        candidate_name=args.candidate_name,
        company_name=args.company_name,
    )

    print("=== Polished Resume ===")
    print(results["polished_resume"])
    print("\n=== Cover Letter ===")
    print(results["cover_letter"])

    output_files: dict[str, Path] = results.get("output_files") or {}
    if output_files:
        print("\n=== Rendered Files ===")
        for format_name, path in sorted(output_files.items()):
            print(f"{format_name}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
