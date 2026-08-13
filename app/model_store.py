"""SQLite-backed persistence for per-agent model/provider overrides.

Phase 22: the web API lets users change which LLM model/provider each
pipeline agent uses.  Those overrides are persisted in a small SQLite
database (``db.sqlite3`` by default) so they survive server restarts,
and are layered on top of the environment-variable defaults from
``config.agents`` (a persisted override wins over the env-var override;
``NULL`` columns inherit the env default).

The default database path is read from the ``MODEL_DB_PATH`` env var so
deployments and tests can point the store at a writable location.  A fresh
SQLite connection is opened per operation, which keeps the store safe to
use from multiple threads.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_model_overrides (
    agent TEXT PRIMARY KEY,
    provider TEXT,
    model TEXT,
    updated_at TEXT NOT NULL
)
"""


def _default_db_path() -> Path:
    """Return the configured database path (``MODEL_DB_PATH`` or ``db.sqlite3``)."""
    return Path(os.getenv("MODEL_DB_PATH", "db.sqlite3"))


def _now() -> str:
    """Return the current UTC time as an ISO string for the ``updated_at`` column."""
    return datetime.now(UTC).isoformat(timespec="seconds")


class ModelStore:
    """Store and query per-agent LLM provider/model overrides in SQLite.

    Each row holds the optional ``provider`` and ``model`` the user picked
    for one agent.  A ``None`` column means "no override for that dimension",
    so the environment-variable default is used instead (see
    ``config.agents.get_agent_config``).  A row whose provider and model are
    both ``None`` is deleted rather than stored, which is exactly the "reset
    to defaults" operation.

    Args:
        db_path: Path to the SQLite file.  Defaults to ``MODEL_DB_PATH`` env
            var, then ``db.sqlite3`` in the working directory.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Open (creating if needed) the database and ensure the table exists."""
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        logger.info("Model store ready at %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        """Return a new connection with row access by column name."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create the overrides table when it does not exist."""
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    def set_override(self, agent: str, provider: str | None, model: str | None) -> None:
        """Store an agent's provider/model override, or clear it when both are ``None``.

        A ``None`` dimension is a merge-no-op: it keeps the previously stored
        value (or stays unset on a fresh row) so the other dimension inherits
        the default.  When both dimensions are ``None`` the row is deleted
        (equivalent to reset).

        Args:
            agent: The agent name (e.g. ``"cover_letter_agent"``).
            provider: Provider name (``"ollama"`` / ``"openai"``) or ``None``.
            model: Model name or ``None``.
        """
        if provider is None and model is None:
            self.clear(agent)
            return
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO agent_model_overrides
                    (agent, provider, model, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent) DO UPDATE SET
                    provider = COALESCE(
                        excluded.provider, agent_model_overrides.provider
                    ),
                    model = COALESCE(excluded.model, agent_model_overrides.model),
                    updated_at = excluded.updated_at
                """,
                (agent, provider, model, _now()),
            )
        logger.info(
            "Model override set: %s provider=%s model=%s", agent, provider, model
        )

    def clear(self, agent: str) -> None:
        """Delete an agent's override row so it falls back to the defaults."""
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM agent_model_overrides WHERE agent = ?", (agent,))
        logger.info("Model override cleared: %s", agent)

    def get(self, agent: str) -> dict[str, str | None] | None:
        """Return an agent's override row, or ``None`` when it has none.

        Returns:
            ``{"provider": ..., "model": ...}`` with ``None`` for unset
            dimensions, or ``None`` when the agent has no override row.
        """
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT provider, model FROM agent_model_overrides WHERE agent = ?",
                (agent,),
            ).fetchone()
        if row is None:
            return None
        return {"provider": row["provider"], "model": row["model"]}

    def has_override(self, agent: str) -> bool:
        """Return whether the agent has an override row (of any shape)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM agent_model_overrides WHERE agent = ?", (agent,)
            ).fetchone()
        return row is not None

    def all_overrides(self) -> dict[str, dict[str, str | None]]:
        """Return every agent's override, keyed by agent name.

        Only rows that still represent a real override (at least one of
        provider/model is non-null) are included; rows where both dimensions
        are null are skipped.

        Returns:
            Mapping of ``{agent: {"provider": ..., "model": ...}}``.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT agent, provider, model FROM agent_model_overrides"
            ).fetchall()
        return {
            row["agent"]: {"provider": row["provider"], "model": row["model"]}
            for row in rows
            if row["provider"] is not None or row["model"] is not None
        }
