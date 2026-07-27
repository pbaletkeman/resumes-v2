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
from typing import Any

from client.model_client import ModelClient
from client.model_registry import ModelClientRegistry

logger = logging.getLogger(__name__)


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
        agents: dict[str, Any],
        registry: ModelClientRegistry | None = None,
    ) -> None:
        """Initialize the runner with a set of named agents.

        Args:
            agents: Dictionary mapping agent names to agent objects or
                agent classes (if ``registry`` is provided).
            registry: Optional registry for per-agent model assignment.
        """
        self.agents = agents
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
        logger.info("Running agent: %s", name)
        start = time.monotonic()

        # If agent is a class (not instantiated), instantiate with registry client
        if isinstance(agent, type) and self.registry is not None:
            client = self.registry.get_client_for_agent(name)
            agent = agent(client)
            self.agents[name] = agent  # Cache the instance

        try:
            result = asyncio.run(agent.run(inputs))
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

    Pipeline stages:
        1. **JD Parsing** — Extract structured data from the job description.
        2. **Resume Parsing** — Extract structured data from the resume.
        3. **Gap Analysis** — Compare JD vs resume, produce a tailoring strategy.
        4. **Resume Rewrite** — Rewrite the resume using the tailoring strategy.
        5. **ATS Compliance** — Optimize for applicant tracking systems.
        6. **Tone Polishing** — Improve professional tone and clarity.
        7. **Cover Letter** — Generate a tailored cover letter.

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
        {"job_description": job_description},
    )
    parsed_job_description = jd_result["parsed_job_description"]

    # 2. Resume Parsing Agent
    resume_result = runner.run_agent(
        "resume_parsing_agent",
        {"resume": resume},
    )
    parsed_resume = resume_result["parsed_resume"]

    # 3. Gap Analysis Agent
    gap_result = runner.run_agent(
        "gap_analysis_agent",
        {
            "parsed_job_description": parsed_job_description,
            "parsed_resume": parsed_resume,
        },
    )
    tailoring_strategy = gap_result["tailoring_strategy"]

    # 4. Resume Rewrite Agent
    rewrite_result = runner.run_agent(
        "resume_rewrite_agent",
        {
            "parsed_resume": parsed_resume,
            "tailoring_strategy": tailoring_strategy,
        },
    )
    rewritten_resume = rewrite_result["rewritten_resume"]

    # 5. ATS Compliance Agent
    ats_result = runner.run_agent(
        "ats_compliance_agent",
        {"rewritten_resume": rewritten_resume},
    )
    ats_optimized_resume = ats_result.get("ats_optimized_resume") or ats_result.get(
        "final_resume"
    )

    # 6. Tone Polishing Agent
    tone_result = runner.run_agent(
        "tone_polishing_agent",
        {"ats_optimized_resume": ats_optimized_resume},
    )
    polished_resume = tone_result["polished_resume"]

    # 7. Cover Letter Agent
    cover_result = runner.run_agent(
        "cover_letter_agent",
        {
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
    from config.agents import build_registry

    registry = build_registry()
    return AgentRunner(agent_classes or {}, registry=registry)


if __name__ == "__main__":
    # Example: Per-agent model configuration
    #
    # Set environment variables to assign different models to different agents:
    #
    #   # Default model for all agents
    #   set MODEL_PROVIDER=ollama
    #   set MODEL_NAME=qwen3.5
    #
    #   # Use a stronger model for creative tasks
    #   set COVER_LETTER_AGENT_PROVIDER=openai
    #   set COVER_LETTER_AGENT_MODEL=gpt-4o
    #   set TONE_POLISHING_AGENT_PROVIDER=openai
    #   set TONE_POLISHING_AGENT_MODEL=gpt-4o-mini
    #
    #   # Use a fast model for parsing
    #   set JD_PARSING_AGENT_PROVIDER=ollama
    #   set JD_PARSING_AGENT_MODEL=llama3

    # Example 1: Manual setup with different clients
    from client.ollama_client import OllamaClient

    fast_client = OllamaClient("qwen3.5")
    # smart_client = OpenAIClient("gpt-4o", api_key=os.getenv("OPENAI_API_KEY") or "")

    agents = {
        "jd_parsing_agent": None,  # Replace with real agent class
        "resume_parsing_agent": None,
        "gap_analysis_agent": None,
        "resume_rewrite_agent": None,
        "ats_compliance_agent": None,
        "tone_polishing_agent": None,
        "cover_letter_agent": None,
    }

    runner = AgentRunner(agents)

    # Example 2: Use config-based registry (uncomment to use)
    # runner = create_runner_from_config(agents)

    # Show which model is assigned to each agent
    if runner.registry:
        from config.agents import get_model_summary

        print("Agent Model Assignments:")
        for entry in get_model_summary():
            print(f"  {entry['agent']}: {entry['provider']}/{entry['model']}")

    job_description = "Paste JD here..."
    resume = "Paste resume here..."

    # Once AgentRunner.run_agent is implemented, this will run end-to-end.
    results = run_resume_pipeline(runner, job_description, resume)

    # Example: print final artifacts
    print("=== Polished Resume ===")
    print(results["polished_resume"])
    print("\n=== Cover Letter ===")
    print(results["cover_letter"])
