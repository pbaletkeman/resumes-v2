"""Tests for CoverLetterAgent post-validation helpers (no LLM)."""

import json
import logging
from typing import Any

from client.agents.cover_letter import (
    CoverLetterAgent,
    _build_fallback_cover_letter,
    _check_company,
    _check_skills,
    _company_from,
    _get_company_name,
    _join_skills,
    _load_str_list,
    _most_recent_achievement,
    _normalize_skill,
    _overlapping_skills,
    _skill_in_list,
    _skill_mentioned,
    _validate_length,
    _validate_role,
)
from client.errors import LLMConnectionError
from client.models import (
    CoverLetterOutput,
    ExperienceEntry,
    GapAnalysisOutput,
    JDParsingOutput,
    ResumeParsingOutput,
)


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


class TestJoinSkills:
    def test_single(self) -> None:
        assert _join_skills(["Python"]) == "Python"

    def test_two(self) -> None:
        assert _join_skills(["Python", "SQL"]) == "Python and SQL"

    def test_three(self) -> None:
        assert _join_skills(["Python", "SQL", "Git"]) == "Python, SQL, and Git"

    def test_empty(self) -> None:
        assert _join_skills([]) == ""


class TestOverlappingSkills:
    def test_matching_skills_returned(self) -> None:
        assert _overlapping_skills(["Python", "SQL", "K8s"], ["Python", "SQL"]) == [
            "Python",
            "SQL",
        ]

    def test_fuzzy_match_counts(self) -> None:
        assert _overlapping_skills(["SQL"], ["PostgreSQL"]) == ["SQL"]

    def test_no_overlap(self) -> None:
        assert _overlapping_skills(["Docker"], ["Python"]) == []

    def test_empty(self) -> None:
        assert _overlapping_skills([], []) == []


class TestCompanyFrom:
    def test_top_level_field_wins(self) -> None:
        data = {"company_name": "Acme", "company_signals": {"company_name": "Zafin"}}
        assert _company_from(data) == "Acme"

    def test_signals_fallback(self) -> None:
        data = {"company_signals": {"company_name": "Zafin"}}
        assert _company_from(data) == "Zafin"

    def test_empty_when_absent(self) -> None:
        assert _company_from({}) == ""

    def test_non_string_ignored(self) -> None:
        assert _company_from({"company_name": 123}) == ""


class TestMostRecentAchievement:
    def _resume(
        self, experiences: list[dict[str, object]] | None = None
    ) -> dict[str, object]:
        return {"experience": experiences or []}

    def test_returns_first_achievement_of_first_entry(self) -> None:
        data = self._resume(
            [
                {"achievements": ["Reduced load 90%", "Built ETL jobs"]},
                {"achievements": ["Older achievement"]},
            ]
        )
        assert _most_recent_achievement(data) == "Reduced load 90%"

    def test_falls_back_to_responsibility(self) -> None:
        data = self._resume([{"achievements": [], "responsibilities": ["Built APIs"]}])
        assert _most_recent_achievement(data) == "Built APIs"

    def test_empty_when_no_experience(self) -> None:
        assert _most_recent_achievement(self._resume([])) == ""

    def test_empty_when_entry_has_no_text(self) -> None:
        data = self._resume([{"achievements": [""], "responsibilities": [""]}])
        assert _most_recent_achievement(data) == ""

    def test_handles_model_entries(self) -> None:
        data = {
            "experience": [
                ExperienceEntry(
                    achievements=["Reduced load 90%"],
                    responsibilities=[],
                )
            ]
        }
        assert _most_recent_achievement(data) == "Reduced load 90%"


class TestBuildFallbackCoverLetter:
    def _jd(
        self,
        role_title: str = "",
        company_name: str = "",
        required: list[str] | None = None,
    ) -> JDParsingOutput:
        return JDParsingOutput(
            role_title=role_title,
            company_name=company_name,
            required_skills=required or [],
        )

    def _resume(
        self,
        skills: list[str] | None = None,
        name: str | None = None,
        achievements: list[str] | None = None,
    ) -> ResumeParsingOutput:
        return ResumeParsingOutput(
            skills=skills or [],
            experience=[
                ExperienceEntry(
                    company="Acme",
                    dates="2024 - Present",
                    achievements=achievements or ["Reduced complexity by 90%"],
                    responsibilities=["Built APIs"],
                )
            ],
        )

    def _strategy(self, keywords: list[str] | None = None) -> GapAnalysisOutput:
        return GapAnalysisOutput(keyword_strategy=keywords or [])

    def test_uses_role_title(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Software Engineer"), self._resume(), self._strategy()
        )
        assert "Software Engineer position" in letter

    def test_uses_company_name(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(company_name="3Pillar"), self._resume(), self._strategy()
        )
        assert "3Pillar" in letter

    def test_omits_company_when_absent(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(), self._resume(), self._strategy()
        )
        assert "your company" not in letter

    def test_uses_candidate_name_when_available(self) -> None:
        resume = self._resume()
        resume_dict = resume.model_dump()
        resume_dict["name"] = "Peter Letkeman"
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), resume_dict, self._strategy()
        )
        assert "Sincerely,\nPeter Letkeman" in letter

    def test_falls_back_to_candidate_name(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), self._resume(), self._strategy()
        )
        assert "Sincerely,\nCandidate" in letter

    def test_mentions_overlapping_required_skills(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(required=["Python", "SQL", "Docker"]),
            self._resume(skills=["Python", "SQL", "Git"]),
            self._strategy(),
        )
        assert "Python and SQL" in letter

    def test_references_most_recent_achievement(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(), self._resume(), self._strategy()
        )
        assert "reduced complexity by 90%" in letter

    def test_three_paragraph_structure(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), self._resume(), self._strategy()
        )
        assert letter.startswith("Dear Hiring Manager,")
        assert "\n\n" in letter
        assert letter.count("\n\n") == 4

    def test_no_placeholder_text(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(), self._resume(), self._strategy()
        )
        assert "[Your Name]" not in letter
        assert "[Company]" not in letter
        assert "[Role]" not in letter

    def test_strategy_keywords_used_when_no_required_overlap(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(required=["Kubernetes", "Docker"]),
            self._resume(skills=["Python", "SQL"]),
            self._strategy(keywords=["Python"]),
        )
        assert "Python" in letter

    def test_accepts_plain_dicts(self) -> None:
        jd = {"role_title": "Engineer", "company_name": "Acme"}
        resume = {"skills": ["Python"], "experience": []}
        letter = _build_fallback_cover_letter(jd, resume, {})
        assert "Engineer position" in letter
        assert "Acme" in letter

    def test_ascii_only_output(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), self._resume(), self._strategy()
        )
        assert all(ord(char) < 128 for char in letter)


class _MockClient:
    """Stub ``ModelClient`` returning a canned response or raising an error."""

    def __init__(
        self, response: str | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error

    async def chat(self, **kwargs: Any) -> str:
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("no response configured")
        return self.response


class TestFallbackLogging:
    def _inputs(self, resume: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "parsed_job_description": {"role_title": "", "company_name": ""},
            "parsed_resume": resume or {"skills": []},
            "tailoring_strategy": {},
        }

    async def test_llm_success_logs_word_count(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        letter = " ".join(["word"] * 210)
        client = _MockClient(response=json.dumps({"cover_letter": letter}))
        agent = CoverLetterAgent(client)
        result = await agent.run(self._inputs())
        assert len(result.cover_letter.split()) == 210
        assert "LLM cover letter succeeded" in caplog.text
        assert "words=210" in caplog.text

    async def test_llm_failure_logs_fallback_reason(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        agent = CoverLetterAgent(_MockClient(error=LLMConnectionError("boom")))
        result = await agent.run(self._inputs())
        assert "Sincerely," in result.cover_letter
        assert "Fallback: template cover letter used" in caplog.text
        assert "LLM failed on both attempts" in caplog.text

    async def test_empty_input_logs_fallback_reason(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        agent = CoverLetterAgent(_MockClient())
        await agent.run({})
        assert "Fallback: template cover letter used" in caplog.text
        assert "empty input" in caplog.text
