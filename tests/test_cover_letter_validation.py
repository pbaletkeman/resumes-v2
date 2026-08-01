"""Tests for CoverLetterAgent post-validation helpers (no LLM)."""

import json

from client.agents.cover_letter import (
    _check_company,
    _check_skills,
    _get_company_name,
    _load_str_list,
    _normalize_skill,
    _skill_in_list,
    _skill_mentioned,
    _validate_length,
    _validate_role,
)
from client.models import CoverLetterOutput


def _jd_json(
    role_title: str = "",
    company_name: str = "",
    signals: dict[str, str] | None = None,
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "role_title": role_title,
            "company_name": company_name,
            "company_signals": signals or {},
            "required_skills": required_skills or [],
            "preferred_skills": preferred_skills or [],
        }
    )


def _resume_json(skills: list[str] | None = None) -> str:
    return json.dumps({"skills": skills or []})


def _letter(text: str) -> CoverLetterOutput:
    return CoverLetterOutput(cover_letter=text)


class TestValidateRole:
    def test_empty_role_title_passes(self) -> None:
        assert _validate_role(_letter("Dear Hiring Manager"), _jd_json())

    def test_exact_title_match(self) -> None:
        letter = "I am applying for the Data Scientist position at Acme."
        assert _validate_role(_letter(letter), _jd_json(role_title="Data Scientist"))

    def test_case_insensitive_match(self) -> None:
        letter = "I am applying for the data scientist position."
        assert _validate_role(_letter(letter), _jd_json(role_title="Data Scientist"))

    def test_filler_word_stripped_match(self) -> None:
        letter = "As a Data Scientist, I would love to join you."
        assert _validate_role(
            _letter(letter), _jd_json(role_title="Senior Data Scientist")
        )

    def test_missing_role_rejects(self) -> None:
        letter = "I am excited to work on your platform team."
        assert not _validate_role(
            _letter(letter), _jd_json(role_title="Backend Engineer")
        )

    def test_invalid_json_passes(self) -> None:
        assert _validate_role(_letter("anything"), "not json")

    def test_role_title_not_string_passes(self) -> None:
        jd = json.dumps({"role_title": 123})
        assert _validate_role(_letter("anything"), jd)


class TestGetCompanyName:
    def test_top_level_field_wins(self) -> None:
        jd = _jd_json(company_name="Acme", signals={"company_name": "Zafin"})
        assert _get_company_name(jd) == "Acme"

    def test_signals_fallback(self) -> None:
        jd = _jd_json(signals={"company_name": "Zafin"})
        assert _get_company_name(jd) == "Zafin"

    def test_empty_when_absent(self) -> None:
        assert _get_company_name(_jd_json()) == ""

    def test_invalid_json_empty(self) -> None:
        assert _get_company_name("not json") == ""


class TestCheckCompany:
    def test_company_mentioned_passes(self, caplog) -> None:
        letter = "I would love to work at Acme because of its mission."
        _check_company(_letter(letter), _jd_json(company_name="Acme"))
        assert "does not mention target company" not in caplog.text

    def test_company_omitted_warns(self, caplog) -> None:
        letter = "I would love to work at your company."
        _check_company(_letter(letter), _jd_json(company_name="Acme"))
        assert "does not mention target company" in caplog.text

    def test_partial_token_mention_passes(self, caplog) -> None:
        letter = "I admire Acme for its values."
        _check_company(_letter(letter), _jd_json(company_name="Acme Corporation"))
        assert "does not mention target company" not in caplog.text

    def test_no_company_available_no_warning(self, caplog) -> None:
        _check_company(_letter("anything"), _jd_json())
        assert "does not mention target company" not in caplog.text

    def test_invalid_json_no_warning(self, caplog) -> None:
        _check_company(_letter("anything"), "not json")
        assert "does not mention target company" not in caplog.text


class TestSkillMentioned:
    def test_whole_word_positive(self) -> None:
        assert _skill_mentioned("I use python daily", "Python")

    def test_short_token_does_not_match_substring(self) -> None:
        assert not _skill_mentioned("the work aimed high", "ai")

    def test_short_token_whole_word(self) -> None:
        assert _skill_mentioned("ai is the future", "ai")

    def test_empty_skill_false(self) -> None:
        assert not _skill_mentioned("anything", "")

    def test_multi_word_skill(self) -> None:
        assert _skill_mentioned("machine learning is fun", "Machine Learning")


class TestSkillInList:
    def test_exact_case_insensitive(self) -> None:
        assert _skill_in_list("Python", ["python", "sql"])

    def test_substring_match(self) -> None:
        assert _skill_in_list("SQL", ["PostgreSQL"])

    def test_shared_token_match(self) -> None:
        assert _skill_in_list("Machine Learning", ["ml", "machine learning"])

    def test_no_match(self) -> None:
        assert not _skill_in_list("Kubernetes", ["python", "sql"])

    def test_empty_list_false(self) -> None:
        assert not _skill_in_list("Python", [])

    def test_empty_skill_returns_true(self) -> None:
        assert _skill_in_list("", ["python"])


class TestCheckSkills:
    def test_resume_skill_mentioned_no_warning(self, caplog) -> None:
        jd = _jd_json(required_skills=["Python", "SQL"])
        resume = _resume_json(skills=["Python", "SQL"])
        letter = "I use Python and SQL in my daily work."
        _check_skills(_letter(letter), resume, jd)
        assert "mentions skills not in resume" not in caplog.text

    def test_jd_skill_absent_from_resume_warns(self, caplog) -> None:
        jd = _jd_json(required_skills=["Kubernetes"])
        resume = _resume_json(skills=["Python"])
        letter = "I deploy services with Kubernetes."
        _check_skills(_letter(letter), resume, jd)
        assert "mentions skills not in resume" in caplog.text
        assert "Kubernetes" in caplog.text

    def test_preferred_skill_absent_warns(self, caplog) -> None:
        jd = _jd_json(preferred_skills=["Docker"])
        resume = _resume_json(skills=["Python"])
        letter = "I containerize apps with Docker."
        _check_skills(_letter(letter), resume, jd)
        assert "mentions skills not in resume" in caplog.text

    def test_fuzzy_substring_does_not_warn(self, caplog) -> None:
        jd = _jd_json(required_skills=["SQL"])
        resume = _resume_json(skills=["PostgreSQL"])
        letter = "I write complex SQL queries."
        _check_skills(_letter(letter), resume, jd)
        assert "mentions skills not in resume" not in caplog.text

    def test_short_token_substring_no_false_warning(self, caplog) -> None:
        jd = _jd_json(required_skills=["AI"])
        resume = _resume_json(skills=["Python"])
        letter = "The outcome was aimed at users."
        _check_skills(_letter(letter), resume, jd)
        assert "mentions skills not in resume" not in caplog.text

    def test_no_skills_no_warning(self, caplog) -> None:
        _check_skills(_letter("anything"), _resume_json(), _jd_json())
        assert "mentions skills not in resume" not in caplog.text


class TestLoadStrList:
    def test_returns_string_items(self) -> None:
        assert _load_str_list('{"skills": ["a", "b"]}', "skills") == ["a", "b"]

    def test_ignores_non_string_items(self) -> None:
        assert _load_str_list('{"skills": ["a", 5, null]}', "skills") == ["a"]

    def test_non_list_field_empty(self) -> None:
        assert _load_str_list('{"skills": "oops"}', "skills") == []

    def test_missing_field_empty(self) -> None:
        assert _load_str_list('{"other": []}', "skills") == []

    def test_invalid_json_empty(self) -> None:
        assert _load_str_list("not json", "skills") == []


class TestNormalizeSkill:
    def test_lowercases_and_tokenizes(self) -> None:
        assert _normalize_skill("Python (Django)") == "python django"

    def test_removes_symbols(self) -> None:
        assert _normalize_skill("C++") == "c"

    def test_empty_string(self) -> None:
        assert _normalize_skill("") == ""


class TestValidateLength:
    def _letter_of_words(self, count: int) -> CoverLetterOutput:
        return _letter(" ".join(["word"] * count))

    def test_ideal_length_passes(self) -> None:
        assert _validate_length(self._letter_of_words(500))

    def test_short_but_acceptable_passes(self, caplog) -> None:
        assert _validate_length(self._letter_of_words(300))
        assert "outside 450-600 spec" in caplog.text

    def test_long_but_acceptable_passes(self, caplog) -> None:
        assert _validate_length(self._letter_of_words(700))
        assert "outside 450-600 spec" in caplog.text

    def test_extreme_short_rejects(self, caplog) -> None:
        assert not _validate_length(self._letter_of_words(150))
        assert "too short" in caplog.text

    def test_extreme_long_rejects(self, caplog) -> None:
        assert not _validate_length(self._letter_of_words(900))
        assert "too long" in caplog.text

    def test_boundary_200_passes(self) -> None:
        assert _validate_length(self._letter_of_words(200))

    def test_boundary_800_passes(self) -> None:
        assert _validate_length(self._letter_of_words(800))
