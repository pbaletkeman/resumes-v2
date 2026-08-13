"""Unit tests for the SQLite-backed model override store (``app/model_store.py``).

Phase 22.1/22.3/22.5: the web API persists per-agent model/provider edits in
SQLite.  These tests exercise the store directly against temp files: upserts,
independent provider/model dimensions, reset (delete), ``None``-inference, and
the ``all_overrides()`` projection used by the config merge.
"""

from __future__ import annotations

from pathlib import Path

from app.model_store import ModelStore


def _make_store(tmp_path: Path) -> ModelStore:
    """Build a store backed by a fresh temp SQLite file."""
    return ModelStore(db_path=tmp_path / "models.db")


def test_new_store_has_no_overrides(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    assert store.all_overrides() == {}
    assert store.get("jd_parsing_agent") is None
    assert store.has_override("jd_parsing_agent") is False


def test_set_override_persists_both_dimensions(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    store.set_override("cover_letter_agent", "openai", "gpt-4o")

    assert store.has_override("cover_letter_agent") is True
    assert store.get("cover_letter_agent") == {
        "provider": "openai",
        "model": "gpt-4o",
    }
    assert store.all_overrides() == {
        "cover_letter_agent": {"provider": "openai", "model": "gpt-4o"}
    }


def test_model_override_without_provider_inherits_default_dimension(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)

    store.set_override("gap_analysis_agent", None, "llama3.1")

    assert store.get("gap_analysis_agent") == {"provider": None, "model": "llama3.1"}
    assert store.all_overrides() == {
        "gap_analysis_agent": {"provider": None, "model": "llama3.1"}
    }


def test_provider_override_without_model_inherits_default_dimension(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)

    store.set_override("jd_parsing_agent", "openai", None)

    assert store.get("jd_parsing_agent") == {"provider": "openai", "model": None}
    assert store.all_overrides() == {
        "jd_parsing_agent": {"provider": "openai", "model": None}
    }


def test_upsert_overwrites_previous_override(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.set_override("tone_polishing_agent", "ollama", "qwen2.5:7b-instruct")
    store.set_override("tone_polishing_agent", "openai", "gpt-4o-mini")

    assert store.get("tone_polishing_agent") == {
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    assert len(store.all_overrides()) == 1


def test_upsert_keeps_unset_dimension_from_previous_row(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.set_override("resume_rewrite_agent", "openai", None)
    store.set_override("resume_rewrite_agent", None, "gpt-4o")

    assert store.get("resume_rewrite_agent") == {
        "provider": "openai",
        "model": "gpt-4o",
    }


def test_set_override_with_both_none_resets_row(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.set_override("ats_compliance_agent", "openai", "gpt-4o")

    store.set_override("ats_compliance_agent", None, None)

    assert store.get("ats_compliance_agent") is None
    assert store.has_override("ats_compliance_agent") is False
    assert store.all_overrides() == {}


def test_clear_removes_override(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.set_override("resume_parsing_agent", "openai", "gpt-4o")

    store.clear("resume_parsing_agent")

    assert store.get("resume_parsing_agent") is None
    assert store.all_overrides() == {}


def test_clear_on_missing_agent_is_a_noop(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    store.clear("jd_parsing_agent")

    assert store.all_overrides() == {}


def test_store_survives_reopen(tmp_path: Path) -> None:
    db = tmp_path / "models.db"
    ModelStore(db_path=db).set_override("cover_letter_agent", "openai", "gpt-4o")

    reopened = ModelStore(db_path=db)

    assert reopened.get("cover_letter_agent") == {
        "provider": "openai",
        "model": "gpt-4o",
    }


def test_multiple_agents_coexist(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.set_override("jd_parsing_agent", "ollama", "llama3.1")
    store.set_override("cover_letter_agent", "openai", "gpt-4o")

    assert set(store.all_overrides()) == {
        "jd_parsing_agent",
        "cover_letter_agent",
    }
