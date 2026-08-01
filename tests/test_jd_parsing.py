"""Tests for JDParsingAgent company-name helpers (no LLM)."""

from client.agents.jd_parsing import _extract_company_name, _sync_company_name
from client.models import JDParsingOutput


class TestExtractCompanyName:
    def test_opening_sentence_pattern(self) -> None:
        jd = "3Pillar is an AI transformation partner on a mission..."
        assert _extract_company_name(jd) == "3Pillar"

    def test_opening_sentence_multi_word(self) -> None:
        jd = "Acme Corporation is a leading provider of widgets."
        assert _extract_company_name(jd) == "Acme Corporation"

    def test_explicit_company_label(self) -> None:
        jd = "Position: Senior Engineer\nCompany: Globex LLC\nRequirements: ..."
        assert _extract_company_name(jd) == "Globex LLC"

    def test_at_reference(self) -> None:
        jd = "As a Software Engineer at Zafin, you will design software."
        assert _extract_company_name(jd) == "Zafin"

    def test_at_multi_word_reference(self) -> None:
        jd = "Join the team at Northwind Traders and grow your career."
        assert _extract_company_name(jd) == "Northwind Traders"

    def test_leading_bom_and_blank_lines(self) -> None:
        jd = "\ufeff\n\nZafin is an AI platform company helping institutions."
        assert _extract_company_name(jd) == "Zafin"

    def test_no_company_name_returns_empty(self) -> None:
        jd = "We are looking for a developer to join our team."
        assert _extract_company_name(jd) == ""

    def test_pronoun_opener_skipped(self) -> None:
        jd = "Our company is hiring across all departments."
        assert _extract_company_name(jd) == ""

    def test_pure_number_token_ignored(self) -> None:
        jd = "You can reach us at 555-1234 for more information."
        assert _extract_company_name(jd) == ""

    def test_digit_leading_company_name(self) -> None:
        jd = "Join us to work at 3Pillar and build enterprise AI."
        assert _extract_company_name(jd) == "3Pillar"

    def test_empty_text_returns_empty(self) -> None:
        assert _extract_company_name("") == ""

    def test_lowercase_at_reference_ignored(self) -> None:
        jd = "You will work at least 5 hours per week."
        assert _extract_company_name(jd) == ""


class TestSyncCompanyName:
    def test_field_flows_into_signals(self) -> None:
        result = JDParsingOutput(company_name="Acme")
        synced = _sync_company_name(result)
        assert synced.company_name == "Acme"
        assert synced.company_signals["company_name"] == "Acme"

    def test_signal_flows_into_field(self) -> None:
        result = JDParsingOutput(company_signals={"company_name": "Globex"})
        synced = _sync_company_name(result)
        assert synced.company_name == "Globex"
        assert synced.company_signals["company_name"] == "Globex"

    def test_field_preferred_over_signal(self) -> None:
        result = JDParsingOutput(
            company_name="Acme", company_signals={"company_name": "Globex"}
        )
        synced = _sync_company_name(result)
        assert synced.company_name == "Acme"
        assert synced.company_signals["company_name"] == "Acme"

    def test_preserves_other_signals(self) -> None:
        result = JDParsingOutput(
            company_name="Acme",
            company_signals={"culture": "innovative", "values": "integrity"},
        )
        synced = _sync_company_name(result)
        assert synced.company_signals["culture"] == "innovative"
        assert synced.company_signals["values"] == "integrity"
        assert synced.company_signals["company_name"] == "Acme"

    def test_empty_signal_name_removes_key(self) -> None:
        result = JDParsingOutput(company_signals={"company_name": ""})
        synced = _sync_company_name(result)
        assert synced.company_name == ""
        assert "company_name" not in synced.company_signals

    def test_empty_model_is_unchanged(self) -> None:
        synced = _sync_company_name(JDParsingOutput())
        assert synced.company_name == ""
        assert synced.company_signals == {}

    def test_sync_is_immutable(self) -> None:
        result = JDParsingOutput(company_name="Acme", company_signals={})
        _sync_company_name(result)
        assert result.company_signals == {}
        assert result.company_name == "Acme"
