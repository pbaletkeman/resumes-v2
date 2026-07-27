"""
model_registry.py
Registry for managing multiple LLM model clients.

Provides a centralized way to register, retrieve, and configure
model clients for different agents in the pipeline. Supports per-agent
model assignment with a configurable default fallback.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from client.model_client import ModelClient
from client.ollama_client import OllamaClient
from client.open_ai_client import OpenAIClient


class ModelClientRegistry:
    """Registry for managing named LLM model clients.

    Allows registering multiple ``ModelClient`` instances (e.g. different
    providers or models) and assigning them to specific agents. Agents
    without an explicit assignment use the default client.

    Example::

        registry = ModelClientRegistry()
        registry.register("fast", OllamaClient("qwen3.5"))
        registry.register("smart", OpenAIClient("gpt-4o", api_key="..."))
        registry.set_default_client("fast")

        # Per-agent override
        registry.set_agent_client("cover_letter_agent", "smart")
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._clients: dict[str, ModelClient] = {}
        self._agent_clients: dict[str, str] = {}
        self._default_client_name: str | None = None

    def register(self, name: str, client: ModelClient) -> None:
        """Register a model client with a unique name.

        Args:
            name: Unique identifier for this client (e.g. ``"fast"``).
            client: The ``ModelClient`` instance to register.

        Raises:
            ValueError: If a client with this name is already registered.
        """
        if name in self._clients:
            raise ValueError(f"Model client '{name}' is already registered")
        self._clients[name] = client

    def get(self, name: str) -> ModelClient:
        """Retrieve a registered model client by name.

        Args:
            name: The registered name of the client.

        Returns:
            The ``ModelClient`` instance.

        Raises:
            KeyError: If no client with this name is registered.
        """
        if name not in self._clients:
            available = ", ".join(self._clients.keys()) or "(none)"
            raise KeyError(
                f"Model client '{name}' not found. Available: {available}"
            )
        return self._clients[name]

    def set_default_client(self, name: str) -> None:
        """Set the default model client used by agents without overrides.

        Args:
            name: The registered name of the client to use as default.

        Raises:
            KeyError: If no client with this name is registered.
        """
        if name not in self._clients:
            raise KeyError(f"Model client '{name}' not found")
        self._default_client_name = name

    def set_agent_client(self, agent_name: str, client_name: str) -> None:
        """Assign a specific model client to an agent.

        Args:
            agent_name: The agent identifier (e.g. ``"cover_letter_agent"``).
            client_name: The registered name of the model client to use.

        Raises:
            KeyError: If no client with this name is registered.
        """
        if client_name not in self._clients:
            raise KeyError(f"Model client '{client_name}' not found")
        self._agent_clients[agent_name] = client_name

    def get_client_for_agent(self, agent_name: str) -> ModelClient:
        """Get the model client assigned to a specific agent.

        Falls back to the default client if no per-agent override exists.

        Args:
            agent_name: The agent identifier.

        Returns:
            The ``ModelClient`` instance for this agent.

        Raises:
            KeyError: If no client is assigned and no default is set.
        """
        # Check for per-agent override first
        if agent_name in self._agent_clients:
            return self.get(self._agent_clients[agent_name])

        # Fall back to default
        if self._default_client_name is not None:
            return self.get(self._default_client_name)

        available = ", ".join(self._clients.keys()) or "(none)"
        raise KeyError(
            f"No model client assigned to agent '{agent_name}' and no "
            f"default client set. Registered clients: {available}"
        )

    @property
    def default_client_name(self) -> str | None:
        """Return the name of the default client, or ``None``."""
        return self._default_client_name

    @property
    def registered_clients(self) -> dict[str, ModelClient]:
        """Return a copy of all registered clients."""
        return dict(self._clients)

    @property
    def agent_assignments(self) -> dict[str, str]:
        """Return a copy of all per-agent client assignments."""
        return dict(self._agent_clients)

    def from_config(self, config: dict[str, Any]) -> None:
        """Load client registrations from a configuration dictionary.

        Expected format::

            {
                "clients": {
                    "fast": {"provider": "ollama", "model": "qwen3.5"},
                    "smart": {"provider": "openai", "model": "gpt-4o", "api_key": "..."}
                },
                "default": "fast",
                "agents": {
                    "cover_letter_agent": "smart",
                    "tone_polishing_agent": "fast"
                }
            }

        Args:
            config: Configuration dictionary.

        Raises:
            ValueError: If an unknown provider is specified.
        """
        providers: dict[str, Callable[[dict[str, Any]], ModelClient]] = {
            "ollama": lambda cfg: OllamaClient(cfg["model"]),
            "openai": lambda cfg: OpenAIClient(
                model=cfg["model"],
                api_key=cfg.get("api_key", ""),
            ),
        }

        # Register clients
        for name, client_cfg in config.get("clients", {}).items():
            provider = client_cfg.get("provider", "")
            factory = providers.get(provider)
            if factory is None:
                raise ValueError(
                    f"Unknown provider '{provider}'. "
                    f"Supported: {', '.join(providers.keys())}"
                )
            self.register(name, factory(client_cfg))

        # Set default
        if "default" in config:
            self.set_default_client(config["default"])

        # Per-agent assignments
        for agent_name, client_name in config.get("agents", {}).items():
            self.set_agent_client(agent_name, client_name)
