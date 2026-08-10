"""
agents.py
Agent-to-model configuration mapping.

Defines which LLM model each agent in the pipeline uses. Agents can be
assigned different models based on their requirements (e.g. a fast model
for parsing, a more capable model for creative writing).

Environment variables (all optional):

- ``MODEL_PROVIDER``: ``"ollama"`` or ``"openai"`` (default: ``"ollama"``)
- ``MODEL_NAME``: Model name for the default provider
  (default: ``"qwen2.5:7b-instruct"``)
- ``OPENAI_API_KEY``: API key for the OpenAI provider
- ``<AGENT>_PROVIDER`` / ``<AGENT>_MODEL``: Override provider/model for a
  specific agent (e.g. ``COVER_LETTER_AGENT_PROVIDER=openai``)

The env prefix for an agent is its uppercased name, so the seven agents
are configured with ``JD_PARSING_AGENT_*``, ``RESUME_PARSING_AGENT_*``,
``GAP_ANALYSIS_AGENT_*``, ``RESUME_REWRITE_AGENT_*``,
``ATS_COMPLIANCE_AGENT_*``, ``TONE_POLISHING_AGENT_*`` and
``COVER_LETTER_AGENT_*``.

Usage::

    from config.agents import get_agent_config, build_registry

    # Get the full configuration
    config = get_agent_config()

    # Build a ready-to-use registry
    registry = build_registry()
"""

from __future__ import annotations

import logging
import os
from typing import Any

from client.model_registry import ModelClientRegistry

logger = logging.getLogger(__name__)

# The seven pipeline agents, in pipeline order.  The uppercased name is
# the env-var prefix for per-agent overrides (e.g. ``COVER_LETTER_AGENT``).
AGENT_NAMES: tuple[str, ...] = (
    "jd_parsing_agent",
    "resume_parsing_agent",
    "gap_analysis_agent",
    "resume_rewrite_agent",
    "ats_compliance_agent",
    "tone_polishing_agent",
    "cover_letter_agent",
)


def _effective_provider(agent_provider: str | None, default_provider: str) -> str:
    """Return the provider an agent should use.

    A per-agent ``<AGENT>_PROVIDER`` override wins; otherwise the
    default provider is used.

    Args:
        agent_provider: The per-agent provider override, or ``None``.
        default_provider: The global default provider.

    Returns:
        ``"ollama"`` or ``"openai"``.
    """
    return agent_provider or default_provider


def _effective_model(agent_model: str | None, default_model: str) -> str:
    """Return the model an agent should use.

    A per-agent ``<AGENT>_MODEL`` override wins; otherwise the default
    model is used.

    Args:
        agent_model: The per-agent model override, or ``None``.
        default_model: The global default model.

    Returns:
        The chosen model name.
    """
    return agent_model or default_model


def _client_config(provider: str, model: str, api_key: str) -> dict[str, str]:
    """Build the client config dict for one provider/model pair.

    The ``api_key`` is only included for the OpenAI provider; Ollama
    clients do not need one.

    Args:
        provider: ``"ollama"`` or ``"openai"``.
        model: The model name for this client.
        api_key: The OpenAI API key (ignored for Ollama).

    Returns:
        A dict suitable for a value in ``ModelClientRegistry.from_config``'s
        ``"clients"`` map.
    """
    if provider == "openai":
        return {"provider": provider, "model": model, "api_key": api_key}
    return {"provider": provider, "model": model}


def get_agent_config() -> dict[str, Any]:
    """Return the agent-to-model configuration.

    Reads the environment and produces the config dict consumed by
    ``ModelClientRegistry.from_config()``::

        {
            "clients": {
                "default": {"provider": ..., "model": ...},
                "<agent>_client": {...}   # only for overridden agents
            },
            "default": "default",
            "agents": {"<agent>": "<agent>_client"}  # only for overridden agents
        }

    A per-agent ``<AGENT>_CLIENT`` entry (and the corresponding assignment
    in ``"agents"``) is only created when that agent has a provider or
    model override.  Agents without an override fall back to ``"default"``.

    Returns:
        Configuration dictionary ready for ``ModelClientRegistry.from_config()``.
    """
    default_provider = os.getenv("MODEL_PROVIDER", "ollama")
    default_model = os.getenv("MODEL_NAME", "qwen2.5:7b-instruct")
    api_key = os.getenv("OPENAI_API_KEY", "")

    logger.debug(
        "Agent config: provider=%s model=%s has_api_key=%s",
        default_provider,
        default_model,
        bool(api_key),
    )

    default_client_name = "default"
    clients: dict[str, dict[str, str]] = {}
    clients[default_client_name] = _client_config(
        default_provider, default_model, api_key
    )

    # Per-agent clients are only created when an agent has an override.
    agents: dict[str, str] = {}
    for agent_name in AGENT_NAMES:
        env_prefix = agent_name.upper()
        agent_provider = os.getenv(f"{env_prefix}_PROVIDER")
        agent_model = os.getenv(f"{env_prefix}_MODEL")

        if agent_provider is None and agent_model is None:
            continue

        provider = _effective_provider(agent_provider, default_provider)
        model = _effective_model(agent_model, default_model)
        client_name = f"{agent_name}_client"
        clients[client_name] = _client_config(provider, model, api_key)
        agents[agent_name] = client_name
        logger.debug(
            "Agent override: %s provider=%s model=%s", agent_name, provider, model
        )

    return {
        "clients": clients,
        "default": default_client_name,
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
    logger.info(
        "Registry built: %d clients, %d agent overrides",
        len(config["clients"]),
        len(config["agents"]),
    )
    return registry


def get_model_summary() -> list[dict[str, str]]:
    """Return a summary of which model each agent uses.

    Returns:
        List of dicts with ``agent``, ``provider``, and ``model`` keys,
        one entry per agent in pipeline order.
    """
    config = get_agent_config()
    summary: list[dict[str, str]] = []

    default_client = config["clients"].get(config["default"], {})

    for agent_name in AGENT_NAMES:
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
