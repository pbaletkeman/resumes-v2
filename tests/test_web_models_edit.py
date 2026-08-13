"""Web API tests for the model-editing routes (Phase 22.1, 22.3, 22.5).

Covers ``GET /api/models`` (now richer rows with defaults + override flag),
``PATCH /api/models/{agent}`` (edit model/provider, persisted in SQLite,
runner rebuilt), and ``DELETE /api/models/{agent}`` (reset to defaults).
Each test uses its own temp SQLite file via ``MODEL_DB_PATH`` so overrides
never leak between tests.
"""

from __future__ import annotations

from pathlib import Path
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

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen2.5:7b-instruct"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """TestClient with a pinned, isolated model store and environment.

    Pins the default provider/model and clears the OpenAI key so the runner
    rebuild always constructs Ollama clients regardless of the dev shell env.
    """
    monkeypatch.setenv("MODEL_DB_PATH", str(tmp_path / "models.db"))
    monkeypatch.setenv("MODEL_PROVIDER", DEFAULT_PROVIDER)
    monkeypatch.setenv("MODEL_NAME", DEFAULT_MODEL)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_openai_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Same as ``client`` but with a dummy OpenAI key set.

    Switching an agent to the OpenAI provider rebuilds the runner, which
    constructs an ``AsyncOpenAI`` client; that requires a non-empty
    ``OPENAI_API_KEY`` (the SDK validates it at construction).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("MODEL_PROVIDER", DEFAULT_PROVIDER)
    monkeypatch.setenv("MODEL_NAME", DEFAULT_MODEL)
    monkeypatch.setenv("MODEL_DB_PATH", str(tmp_path / "models-openai.db"))
    with TestClient(app) as test_client:
        yield test_client


def _row_for(payload: list[dict[str, Any]], agent: str) -> dict[str, Any]:
    return next(row for row in payload if row["agent"] == agent)


def _get_models(client: Any) -> list[dict[str, Any]]:
    """Fetch the full ``GET /api/models`` payload as a typed list."""
    return client.get("/api/models").json()


class TestListModels:
    """GET /api/models returns the effective + default config per agent."""

    def test_returns_seven_agents_with_defaults_and_override_flag(
        self, client: Any
    ) -> None:
        payload = _get_models(client)

        assert [row["agent"] for row in payload] == EXPECTED_AGENTS
        for row in payload:
            assert set(row) == {
                "agent",
                "provider",
                "model",
                "default_provider",
                "default_model",
                "is_overridden",
            }
            assert row["provider"] in {"ollama", "openai"}
            assert row["model"]
            assert row["default_provider"] == DEFAULT_PROVIDER
            assert row["default_model"] == DEFAULT_MODEL
            assert row["is_overridden"] is False

    def test_effective_equals_defaults_when_not_overridden(self, client: Any) -> None:
        payload = _get_models(client)

        for row in payload:
            assert row["provider"] == row["default_provider"]
            assert row["model"] == row["default_model"]


class TestPatchAgentModel:
    """PATCH /api/models/{agent} persists an edit and rebuilds the runner."""

    def test_edits_model_only(self, client: Any) -> None:
        response = client.patch(
            "/api/models/cover_letter_agent",
            json={"model": "gpt-4o-mini"},
        )

        assert response.status_code == 200
        row = response.json()
        assert row["agent"] == "cover_letter_agent"
        assert row["provider"] == DEFAULT_PROVIDER
        assert row["model"] == "gpt-4o-mini"
        assert row["default_model"] == DEFAULT_MODEL
        assert row["is_overridden"] is True

        listed = _row_for(_get_models(client), "cover_letter_agent")
        assert listed["model"] == "gpt-4o-mini"
        assert listed["is_overridden"] is True

    def test_edits_provider_only(self, client_with_openai_key: Any) -> None:
        response = client_with_openai_key.patch(
            "/api/models/gap_analysis_agent",
            json={"provider": "openai"},
        )

        assert response.status_code == 200
        row = response.json()
        assert row["agent"] == "gap_analysis_agent"
        assert row["provider"] == "openai"
        assert row["model"] == DEFAULT_MODEL
        assert row["is_overridden"] is True

    def test_edits_model_and_provider_together(
        self, client_with_openai_key: Any
    ) -> None:
        response = client_with_openai_key.patch(
            "/api/models/jd_parsing_agent",
            json={"provider": "openai", "model": "gpt-4o"},
        )

        assert response.status_code == 200
        row = response.json()
        assert row["provider"] == "openai"
        assert row["model"] == "gpt-4o"
        assert row["is_overridden"] is True

    def test_patch_unknown_agent_returns_404(self, client: Any) -> None:
        response = client.patch(
            "/api/models/bogus_agent",
            json={"model": "gpt-4o"},
        )

        assert response.status_code == 404

    def test_patch_with_no_fields_returns_400(self, client: Any) -> None:
        response = client.patch("/api/models/jd_parsing_agent", json={})

        assert response.status_code == 400
        assert "provider or model" in response.json()["detail"]

    def test_patch_with_unknown_provider_returns_400(self, client: Any) -> None:
        response = client.patch(
            "/api/models/jd_parsing_agent",
            json={"provider": "anthropic"},
        )

        assert response.status_code == 400
        assert "ollama" in response.json()["detail"]

    def test_patch_with_empty_model_returns_400(self, client: Any) -> None:
        response = client.patch(
            "/api/models/jd_parsing_agent",
            json={"model": "   "},
        )

        assert response.status_code == 400
        assert "Model must not be empty" in response.json()["detail"]

    def test_patch_to_openai_without_key_is_rejected_and_rolled_back(
        self, client: Any
    ) -> None:
        response = client.patch(
            "/api/models/tone_polishing_agent",
            json={"provider": "openai", "model": "gpt-4o"},
        )

        assert response.status_code == 400
        assert "OPENAI_API_KEY" in response.json()["detail"]

        listed = _row_for(_get_models(client), "tone_polishing_agent")
        assert listed["is_overridden"] is False
        assert listed["provider"] == DEFAULT_PROVIDER


class TestDeleteAgentModel:
    """DELETE /api/models/{agent} resets an agent to the defaults."""

    def test_reset_returns_defaults_and_clears_override(
        self, client_with_openai_key: Any
    ) -> None:
        client_with_openai_key.patch(
            "/api/models/cover_letter_agent",
            json={"provider": "openai", "model": "gpt-4o"},
        )
        assert (
            _row_for(_get_models(client_with_openai_key), "cover_letter_agent")[
                "is_overridden"
            ]
            is True
        )

        response = client_with_openai_key.delete("/api/models/cover_letter_agent")

        assert response.status_code == 200
        row = response.json()
        assert row["agent"] == "cover_letter_agent"
        assert row["provider"] == DEFAULT_PROVIDER
        assert row["model"] == DEFAULT_MODEL
        assert row["is_overridden"] is False

        listed = _row_for(_get_models(client_with_openai_key), "cover_letter_agent")
        assert listed["provider"] == DEFAULT_PROVIDER
        assert listed["model"] == DEFAULT_MODEL
        assert listed["is_overridden"] is False

    def test_reset_without_override_is_harmless(self, client: Any) -> None:
        response = client.delete("/api/models/jd_parsing_agent")

        assert response.status_code == 200
        assert response.json()["is_overridden"] is False

    def test_delete_unknown_agent_returns_404(self, client: Any) -> None:
        response = client.delete("/api/models/bogus_agent")

        assert response.status_code == 404

    def test_edit_then_reset_restores_defaults(self, client: Any) -> None:
        client.patch(
            "/api/models/resume_rewrite_agent",
            json={"model": "llama3.1"},
        )
        client.delete("/api/models/resume_rewrite_agent")

        row = _row_for(_get_models(client), "resume_rewrite_agent")
        assert row["model"] == DEFAULT_MODEL
        assert row["is_overridden"] is False
