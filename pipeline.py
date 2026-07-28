"""
pipeline.py
Multi-agent resume optimization pipeline.

Defines ``AgentRunner`` (a placeholder for agent orchestration) and
``run_resume_pipeline``, which chains 7 specialized agents to transform
a raw job description and resume into an ATS-optimized resume and
tailored cover letter.

Supports per-agent model assignment via ``ModelClientRegistry``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any, Protocol

from client.model_client import ModelClient
from client.model_registry import ModelClientRegistry
from config.agents import build_registry

logger = logging.getLogger(__name__)


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
        return await self.client.chat(self.purpose, prompt, output, rules, context)


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

    def run_agent(self, name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run a named agent with the given inputs.

        Args:
            name: The agent name (must exist in ``self.agents``).
            inputs: Dictionary of input data for the agent.

        Returns:
            The agent's output dictionary.

        Raises:
            KeyError: If the agent name is not registered.
            NotImplementedError: Always (placeholder for real integration).
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
            result: dict[str, Any] = asyncio.run(agent.run(inputs))
            elapsed = time.monotonic() - start
            logger.info("Agent %s completed in %.1fs", name, elapsed)
            return result
        except Exception as e:
            logger.error("Agent '%s' failed: %s", name, e)
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


def run_resume_pipeline(
    runner: AgentRunner,
    job_description: str,
    resume: str,
) -> dict[str, Any]:
    """Run the full 7-agent resume optimization pipeline.

    Args:
        runner: An ``AgentRunner`` instance with all 7 agents registered.
        job_description: Raw job description text.
        resume: Raw resume text.

    Returns:
        Dictionary with keys: ``parsed_job_description``, ``parsed_resume``,
        ``tailoring_strategy``, ``rewritten_resume``, ``ats_optimized_resume``,
        ``polished_resume``, ``cover_letter``.
    """
    # 1. JD Parsing Agent
    jd_result = runner.run_agent(
        "jd_parsing_agent",
        {
            "prompt": "Extract structured data from this job description.",
            "output": ["parsed_job_description"],
            "rules": ["Return valid JSON"],
            "job_description": job_description,
        },
    )
    parsed_job_description = jd_result["parsed_job_description"]

    # 2. Resume Parsing Agent
    resume_result = runner.run_agent(
        "resume_parsing_agent",
        {
            "prompt": "Extract structured data from this resume.",
            "output": ["parsed_resume"],
            "rules": ["Return valid JSON"],
            "resume": resume,
        },
    )
    parsed_resume = resume_result["parsed_resume"]

    # 3. Gap Analysis Agent
    gap_result = runner.run_agent(
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
    tailoring_strategy = gap_result["tailoring_strategy"]

    # 4. Resume Rewrite Agent
    rewrite_result = runner.run_agent(
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
    rewritten_resume = rewrite_result["rewritten_resume"]

    # 5. ATS Compliance Agent
    ats_result = runner.run_agent(
        "ats_compliance_agent",
        {
            "prompt": "Check and optimize this resume for ATS systems.",
            "output": ["ats_optimized_resume"],
            "rules": ["Maintain content accuracy", "Optimize keywords"],
            "rewritten_resume": rewritten_resume,
        },
    )
    ats_optimized_resume = ats_result.get("ats_optimized_resume") or ats_result.get(
        "final_resume"
    )

    # 6. Tone Polishing Agent
    tone_result = runner.run_agent(
        "tone_polishing_agent",
        {
            "prompt": "Polish the tone and clarity of this resume.",
            "output": ["polished_resume"],
            "rules": ["Maintain professional tone", "Be concise"],
            "ats_optimized_resume": ats_optimized_resume,
        },
    )
    polished_resume = tone_result["polished_resume"]

    # 7. Cover Letter Agent
    cover_result = runner.run_agent(
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
    cover_letter = cover_result["cover_letter"]

    return {
        "parsed_job_description": parsed_job_description,
        "parsed_resume": parsed_resume,
        "tailoring_strategy": tailoring_strategy,
        "rewritten_resume": rewritten_resume,
        "ats_optimized_resume": ats_optimized_resume,
        "polished_resume": polished_resume,
        "cover_letter": cover_letter,
    }


def create_runner_from_config(
    agent_classes: dict[str, Any] | None = None,
) -> AgentRunner:
    """Create an ``AgentRunner`` using environment-based configuration.

    Reads model assignments from environment variables (see ``config.agents``
    for details) and builds a ``ModelClientRegistry`` with per-agent clients.

    Args:
        agent_classes: Optional mapping of agent names to agent classes.
            If ``None``, returns a runner with empty agents (for manual setup).

    Returns:
        A configured ``AgentRunner`` with the registry attached.

    Example::

        from config.agents import build_registry
        from client.agents import (
            JDParsingAgent, ResumeParsingAgent, GapAnalysisAgent,
            ResumeRewriteAgent, ATSComplianceAgent, TonePolishingAgent,
            CoverLetterAgent,
        )

        registry = build_registry()
        agents = {
            "jd_parsing_agent": JDParsingAgent,
            "resume_parsing_agent": ResumeParsingAgent,
            "gap_analysis_agent": GapAnalysisAgent,
            "resume_rewrite_agent": ResumeRewriteAgent,
            "ats_compliance_agent": ATSComplianceAgent,
            "tone_polishing_agent": TonePolishingAgent,
            "cover_letter_agent": CoverLetterAgent,
        }
        runner = AgentRunner(agents, registry=registry)
    """
    registry = build_registry()
    return AgentRunner(agent_classes or {}, registry=registry)


def sample_run() -> None:
    """Demonstrate the full resume optimization pipeline end-to-end.

    Creates a ``PipelineAgent`` for each of the 7 pipeline stages, all backed
    by a single Ollama ``qwen3.5`` client.  The agents are wired into an
    ``AgentRunner`` and executed sequentially via ``run_resume_pipeline``.

    Replace the placeholder JD and resume text with real content to see
    meaningful output.
    """
    from client.ollama_client import OllamaClient

    client = OllamaClient("qwen3.5")

    agents_map = {
        "jd_parsing_agent": PipelineAgent(
            client, "Extract structured data from job descriptions"
        ),
        "resume_parsing_agent": PipelineAgent(
            client, "Extract structured data from resumes"
        ),
        "gap_analysis_agent": PipelineAgent(
            client, "Compare JD vs resume, produce a tailoring strategy"
        ),
        "resume_rewrite_agent": PipelineAgent(
            client, "Rewrite resume to match job requirements"
        ),
        "ats_compliance_agent": PipelineAgent(
            client, "Check and optimize resume for ATS systems"
        ),
        "tone_polishing_agent": PipelineAgent(client, "Polish resume tone and clarity"),
        "cover_letter_agent": PipelineAgent(client, "Generate tailored cover letters"),
    }

    runner_instance = AgentRunner(agents_map)

    jd_text = "Paste JD here..."
    resume_text = "Paste resume here..."

    results = run_resume_pipeline(runner_instance, jd_text, resume_text)

    print("=== Polished Resume ===")
    print(results["polished_resume"])
    print("\n=== Cover Letter ===")
    print(results["cover_letter"])


if __name__ == "__main__":
    sample_run()
