"""
agents.py
Agent-to-model configuration mapping.

Defines which LLM model each agent in the pipeline uses. Agents can be
assigned different models based on their requirements (e.g. a fast model
for parsing, a more capable model for creative writing).

Usage::

    from config.agents import get_agent_config, build_registry

    # Get the full configuration
    config = get_agent_config()

    # Build a ready-to-use registry
    registry = build_registry()
"""

from __future__ import annotations

import os
from typing import Any

from client.model_registry import ModelClientRegistry


def get_agent_config() -> dict[str, Any]:
    """Return the agent-to-model configuration.

    Reads from environment variables with fallback defaults:

    - ``MODEL_PROVIDER``: ``"ollama"`` or ``"openai"`` (default: ``"ollama"``)
    - ``MODEL_NAME``: Model name for the default provider
      (default: ``"qwen2.5:7b-instruct"``)
    - ``OPENAI_API_KEY``: API key for OpenAI provider
    - ``DEFAULT_PROVIDER``: Override the default provider for all agents
    - ``<AGENT>_PROVIDER``: Override provider for a specific agent
      (e.g. ``COVER_LETTER_AGENT_PROVIDER=openai``)
    - ``<AGENT>_MODEL``: Override model for a specific agent
      (e.g. ``COVER_LETTER_AGENT_MODEL=gpt-4o``)

    Returns:
        Configuration dictionary ready for ``ModelClientRegistry.from_config()``.
    """
    provider = os.getenv("MODEL_PROVIDER", "ollama")
    model = os.getenv("MODEL_NAME", "qwen2.5:7b-instruct")
    api_key = os.getenv("OPENAI_API_KEY", "")

    # Agent names for environment variable lookup
    agent_names = [
        "jd_parsing_agent",
        "resume_parsing_agent",
        "gap_analysis_agent",
        "resume_rewrite_agent",
        "ats_compliance_agent",
        "tone_polishing_agent",
        "cover_letter_agent",
    ]

    # Build clients configuration
    clients: dict[str, dict[str, str]] = {}

    # Default client
    default_name = "default"
    clients[default_name] = {
        "provider": provider,
        "model": model,
        **({"api_key": api_key} if provider == "openai" else {}),
    }

    # Per-agent clients (only create if overridden)
    for agent_name in agent_names:
        env_prefix = agent_name.upper()
        agent_provider = os.getenv(f"{env_prefix}_PROVIDER")
        agent_model = os.getenv(f"{env_prefix}_MODEL")

        if agent_provider or agent_model:
            client_name = f"{agent_name}_client"
            clients[client_name] = {
                "provider": agent_provider or provider,
                "model": agent_model or model,
                **(
                    {"api_key": api_key}
                    if (agent_provider or provider) == "openai"
                    else {}
                ),
            }

    # Build agent assignments
    agents: dict[str, str] = {}
    for agent_name in agent_names:
        env_prefix = agent_name.upper()
        agent_provider = os.getenv(f"{env_prefix}_PROVIDER")
        agent_model = os.getenv(f"{env_prefix}_MODEL")

        if agent_provider or agent_model:
            agents[agent_name] = f"{agent_name}_client"

    return {
        "clients": clients,
        "default": default_name,
        "agents": agents,
    }


def build_registry() -> ModelClientRegistry:
    """Build a ``ModelClientRegistry`` from the current environment.

    Returns:
        A configured ``ModelClientRegistry`` with all clients registered.
    """
    config = get_agent_config()
    registry = ModelClientRegistry()
    registry.from_config(config)
    return registry


def get_model_summary() -> list[dict[str, str]]:
    """Return a summary of which model each agent uses.

    Returns:
        List of dicts with ``agent``, ``provider``, and ``model`` keys.
    """
    config = get_agent_config()
    summary: list[dict[str, str]] = []

    agent_names = [
        "jd_parsing_agent",
        "resume_parsing_agent",
        "gap_analysis_agent",
        "resume_rewrite_agent",
        "ats_compliance_agent",
        "tone_polishing_agent",
        "cover_letter_agent",
    ]

    default_client = config["clients"].get(config["default"], {})

    for agent_name in agent_names:
        client_name = config["agents"].get(agent_name, config["default"])
        client_cfg = config["clients"].get(client_name, default_client)

        summary.append(
            {
                "agent": agent_name,
                "provider": client_cfg.get("provider", "unknown"),
                "model": client_cfg.get("model", "unknown"),
            }
        )

    return summary
