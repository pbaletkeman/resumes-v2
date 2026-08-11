"""Phase 7.4.1 web tests: health check and model listing routes.

Covers ``GET /health`` and ``GET /api/models`` on the FastAPI app.  Uses
``fastapi.testclient.TestClient(app)`` directly — no shared fixtures from
``conftest.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

EXPECTED_AGENTS = [
    "jd_parsing_agent",
    "resume_parsing_agent",
    "gap_analysis_agent",
    "resume_rewrite_agent",
    "ats_compliance_agent",
    "tone_polishing_agent",
    "cover_letter_agent",
]


@pytest.fixture(scope="module")
def client() -> Any:
    """TestClient with the app lifespan entered (runner built on startup)."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client: Any) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_returns_agent_summary(client: Any) -> None:
    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload, list)
    assert len(payload) == len(EXPECTED_AGENTS)
    agent_names = [entry["agent"] for entry in payload]
    assert agent_names == EXPECTED_AGENTS
    for entry in payload:
        assert set(entry) == {"agent", "provider", "model"}
        assert entry["provider"] in {"ollama", "openai"}
        assert entry["model"]
