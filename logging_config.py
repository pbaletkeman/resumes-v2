"""
logging_config.py
Centralized logging configuration for the resume pipeline.

Uses ``logging.config.dictConfig`` to set up a console handler with
timestamp formatting and per-module level control.  Call
``configure_logging()`` once at pipeline entry points before any agents
run.

Verbosity is controlled via the ``LOG_LEVEL`` environment variable
(default ``INFO``).
"""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any


def configure_logging() -> None:
    """Configure the root logger and module-specific loggers.

    Reads ``LOG_LEVEL`` from the environment (default ``INFO``).
    LLM client loggers are hard-coded to ``DEBUG`` so that API traffic
    is visible when the root level is set to ``DEBUG``.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    config: dict[str, Any] = {
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
            "ollama": {"level": "WARNING"},
            "openai": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
        },
    }
    logging.config.dictConfig(config)
