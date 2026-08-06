"""Tests for CoverLetterAgent post-validation helpers (no LLM)."""

import json
import logging
from typing import Any

from client.agents.cover_letter import (
    CoverLetterAgent,
    _apply_candidate_name,
    _apply_company_name,
    _apply_contact_info,
    _build_fallback_cover_letter,
    _check_company,
    _check_skills,
    _company_from,
    _get_company_name,
    _join_skills,
    _load_str_list,
    _most_recent_achievement,
    _overlapping_skills,
    _skill_in_list,
    _skill_mentioned,
    _validate_length,
    _validate_role,
)
from client.agents.resume_parsing import ResumeParsingAgent
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


class TestApplyCompanyName:
    @staticmethod
    def _resume_with_companies(*companies: str) -> str:
        return json.dumps(
            {
                "skills": [],
                "experience": [{"company": company} for company in companies],
            }
        )

    def test_placeholder_replaced_with_jd_company(self) -> None:
        jd = _jd_json(company_name="3Pillar")
        result = _apply_company_name(
            _letter("I want to join [Company Name] as an engineer."), jd
        )
        assert "3Pillar" in result.cover_letter
        assert "[Company Name]" not in result.cover_letter

    def test_bracket_variant_replaced(self) -> None:
        jd = _jd_json(company_name="Acme")
        result = _apply_company_name(_letter("Join [Company] today!"), jd)
        assert result.cover_letter == "Join Acme today!"

    def test_angle_bracket_variant_replaced(self) -> None:
        jd = _jd_json(company_name="Acme")
        result = _apply_company_name(
            _letter("I admire <Company Name> for its work."), jd
        )
        assert result.cover_letter == "I admire Acme for its work."

    def test_employer_placeholder_replaced(self) -> None:
        jd = _jd_json(company_name="Acme")
        result = _apply_company_name(_letter("I want to work at [Employer Name]."), jd)
        assert result.cover_letter == "I want to work at Acme."

    def test_resume_company_substituted_with_jd_company(self) -> None:
        jd = _jd_json(company_name="3Pillar")
        resume = self._resume_with_companies("Globex")
        result = _apply_company_name(
            _letter("I worked at Globex and would love to dedicate myself."), jd, resume
        )
        assert "3Pillar" in result.cover_letter
        assert "Globex" not in result.cover_letter

    def test_only_first_resume_company_occurrence_substituted(self) -> None:
        jd = _jd_json(company_name="3Pillar")
        resume = self._resume_with_companies("Globex")
        letter_text = "At Globex I grew a lot. Globex taught me resilience."
        result = _apply_company_name(_letter(letter_text), jd, resume)
        assert result.cover_letter.count("3Pillar") == 1
        assert result.cover_letter.count("Globex") == 1

    def test_already_correct_left_unchanged(self) -> None:
        jd = _jd_json(company_name="Acme")
        letter_text = "I want to work at Acme because of its mission."
        result = _apply_company_name(_letter(letter_text), jd)
        assert result.cover_letter == letter_text

    def test_partial_token_mention_left_unchanged(self) -> None:
        jd = _jd_json(company_name="Acme Corporation")
        letter_text = "I admire Acme for its values."
        result = _apply_company_name(_letter(letter_text), jd)
        assert result.cover_letter == letter_text

    def test_no_target_company_unchanged(self) -> None:
        letter_text = "I want to join [Company Name]."
        result = _apply_company_name(_letter(letter_text), _jd_json())
        assert result.cover_letter == letter_text

    def test_no_resume_json_no_substitution(self) -> None:
        jd = _jd_json(company_name="3Pillar")
        letter_text = "I have grown a lot at my current company."
        result = _apply_company_name(_letter(letter_text), jd)
        assert result.cover_letter == letter_text

    def test_ignores_resume_company_that_matches_target(self) -> None:
        jd = _jd_json(company_name="Acme Corp")
        resume = self._resume_with_companies("Acme")
        letter_text = "I worked at Acme and loved it."
        result = _apply_company_name(_letter(letter_text), jd, resume)
        assert result.cover_letter == letter_text


class TestApplyCandidateName:
    @staticmethod
    def _resume(name: str = "") -> str:
        return json.dumps({"name": name, "skills": []})

    def test_your_name_placeholder_replaced(self) -> None:
        letter = _letter("Sincerely,\n[Your Name]")
        result = _apply_candidate_name(letter, self._resume("Peter Letkeman"))
        assert result.cover_letter == "Sincerely,\nPeter Letkeman"

    def test_candidate_name_placeholder_replaced(self) -> None:
        letter = _letter("Sincerely,\n[Candidate Name]")
        result = _apply_candidate_name(letter, self._resume("Jane Doe"))
        assert result.cover_letter == "Sincerely,\nJane Doe"

    def test_angle_bracket_placeholder_replaced(self) -> None:
        letter = _letter("Sincerely,\n<Your Name>")
        result = _apply_candidate_name(letter, self._resume("Jane Doe"))
        assert result.cover_letter == "Sincerely,\nJane Doe"

    def test_empty_name_leaves_letter_unchanged(self) -> None:
        letter = _letter("Sincerely,\n[Your Name]")
        result = _apply_candidate_name(letter, self._resume())
        assert result.cover_letter == "Sincerely,\n[Your Name]"

    def test_no_placeholder_leaves_letter_unchanged(self) -> None:
        letter = _letter("Sincerely,\nJane Doe")
        result = _apply_candidate_name(letter, self._resume("Jane Doe"))
        assert result.cover_letter == "Sincerely,\nJane Doe"

    def test_invalid_resume_json_unchanged(self) -> None:
        letter = _letter("Sincerely,\n[Your Name]")
        result = _apply_candidate_name(letter, "not json")
        assert result.cover_letter == "Sincerely,\n[Your Name]"

    def test_whitespace_name_untouched(self) -> None:
        letter = _letter("Sincerely,\n[Your Name]")
        result = _apply_candidate_name(letter, self._resume("   "))
        assert result.cover_letter == "Sincerely,\n[Your Name]"


class TestResumeParsingName:
    async def test_name_flows_regex_fallback_into_output(self) -> None:
        resume_text = "# Peter Letkeman\n\n## Summary\nData engineer.\n"
        result = await ResumeParsingAgent._regex_fallback(resume_text)
        assert result.name == "Peter Letkeman"

    async def test_unknown_name_becomes_empty(self) -> None:
        result = await ResumeParsingAgent._regex_fallback("\n\n\n")
        assert result.name == ""

    async def test_resume_parsing_output_defaults_empty_name(self) -> None:
        assert ResumeParsingOutput().name == ""


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

    def test_includes_contact_line_from_resume(self) -> None:
        resume_dict = self._resume().model_dump()
        resume_dict.update(
            {
                "phone": "555-1234",
                "email": "peter@example.com",
                "linkedin": "https://linkedin.com/in/peter",
            }
        )
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), resume_dict, self._strategy()
        )
        assert "555-1234 | peter@example.com | https://linkedin.com/in/peter" in letter

    def test_omits_contact_line_when_absent(self) -> None:
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), self._resume(), self._strategy()
        )
        assert " | " not in letter

    def test_signature_contact_line_after_name(self) -> None:
        resume_dict = self._resume().model_dump()
        resume_dict["email"] = "peter@example.com"
        letter = _build_fallback_cover_letter(
            self._jd(role_title="Engineer"), resume_dict, self._strategy()
        )
        assert "Sincerely,\nCandidate\npeter@example.com" in letter


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

    async def test_llm_success_injects_contact_info(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        letter = " ".join(["word"] * 210)
        client = _MockClient(response=json.dumps({"cover_letter": letter}))
        agent = CoverLetterAgent(client)
        resume: dict[str, Any] = {
            "skills": [],
            "phone": "555-1234",
            "email": "peter@example.com",
        }
        result = await agent.run(self._inputs(resume))
        assert "555-1234 | peter@example.com" in result.cover_letter
        assert "Injected contact info" in caplog.text

    async def test_llm_success_without_contact_leaves_unchanged(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        letter = " ".join(["word"] * 210)
        client = _MockClient(response=json.dumps({"cover_letter": letter}))
        agent = CoverLetterAgent(client)
        result = await agent.run(self._inputs())
        assert len(result.cover_letter.split()) == 210
        assert " | " not in result.cover_letter
        assert "Injected contact info" not in caplog.text

    async def test_fallback_includes_contact_line(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        agent = CoverLetterAgent(_MockClient(error=LLMConnectionError("boom")))
        resume: dict[str, Any] = {
            "skills": ["Python"],
            "email": "peter@example.com",
        }
        result = await agent.run(self._inputs(resume))
        assert "peter@example.com" in result.cover_letter
        assert "Sincerely,\nCandidate\npeter@example.com" in result.cover_letter

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


class TestApplyContactInfo:
    def _resume(self, **contacts: str) -> str:
        data: dict[str, Any] = {"skills": []}
        data.update(contacts)
        return json.dumps(data)

    def test_injects_contact_line_when_absent(self) -> None:
        letter = _letter("Dear Hiring Manager,\n\nI am applying.\n\nSincerely,\nJane")
        result = _apply_contact_info(
            letter,
            self._resume(phone="555-1234", email="jane@example.com"),
        )
        assert result.cover_letter.endswith("555-1234 | jane@example.com\n")
        assert "555-1234 | jane@example.com" in result.cover_letter

    def test_leaves_unchanged_when_contact_already_present(self) -> None:
        letter = _letter(
            "Dear Hiring Manager,\n\nYou can reach me at jane@example.com.\n"
        )
        result = _apply_contact_info(
            letter, self._resume(email="jane@example.com")
        )
        assert result.cover_letter == letter.cover_letter

    def test_leaves_unchanged_when_no_contact_fields(self) -> None:
        letter = _letter("Dear Hiring Manager,\n\nI am applying.")
        result = _apply_contact_info(letter, self._resume())
        assert result.cover_letter == letter.cover_letter

    def test_leaves_unchanged_on_invalid_json(self) -> None:
        letter = _letter("Dear Hiring Manager,\n\nI am applying.")
        result = _apply_contact_info(letter, "not json")
        assert result.cover_letter == letter.cover_letter

    def test_missing_contact_fields_do_not_break_output(self) -> None:
        letter = _letter("Dear Hiring Manager,\n\nI am applying.")
        result = _apply_contact_info(letter, self._resume(phone="555-1234"))
        assert "555-1234" in result.cover_letter
        assert " | " not in result.cover_letter.split("555-1234", 1)[0]
