"""Tests for ResumeRewriteAgent post-validation helpers (no LLM)."""

import json
import logging
from typing import Any

from client.agents.resume_rewrite import (
    ResumeRewriteAgent,
    _company_matches,
    _count_words,
    _extract_companies,
    _extract_start_year,
    _normalize_skill,
    _parsed_to_rewrite,
    _sanitize_skills,
    _skill_matches,
    _tailor_skills,
    _validate_chronological,
    _validate_companies,
)
from client.errors import LLMConnectionError
from client.models import (
    ExperienceEntry,
    GapAnalysisOutput,
    JDParsingOutput,
    ResumeParsingOutput,
    RewriteOutput,
)


def _resume_json(
    skills: list[str] | None = None,
    experience: list[dict[str, str]] | None = None,
    certifications: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "skills": skills or [],
            "experience": experience or [],
            "certifications": certifications or [],
        }
    )


class TestNormalizeSkill:
    def test_lowercases_and_tokenizes(self) -> None:
        assert _normalize_skill("Python (Django)") == "python django"

    def test_removes_symbols(self) -> None:
        assert _normalize_skill("C++") == "c"

    def test_empty_string(self) -> None:
        assert _normalize_skill("") == ""


class TestSkillMatches:
    def test_exact_lowercase(self) -> None:
        assert _skill_matches("Python", ["python", "sql"])

    def test_case_insensitive(self) -> None:
        assert _skill_matches("PYTHON", ["python"])

    def test_substring_match(self) -> None:
        assert _skill_matches("SQL", ["postgresql"])

    def test_phrase_token_match(self) -> None:
        assert _skill_matches("Machine Learning", ["machine learning"])

    def test_no_match(self) -> None:
        assert not _skill_matches("Kubernetes", ["python", "sql"])

    def test_empty_skill(self) -> None:
        assert not _skill_matches("", ["python"])


class TestSanitizeSkills:
    def test_keeps_only_matching_skills(self) -> None:
        result = RewriteOutput(skills=["Python", "SQL", "Kubernetes"])
        sanitized = _sanitize_skills(result, _resume_json(skills=["Python", "SQL"]))
        assert sanitized is not None
        assert sanitized.skills == ["Python", "SQL"]

    def test_rejects_when_most_skills_fabricated(self) -> None:
        result = RewriteOutput(skills=["Python", "Kubernetes", "Docker", "AWS"])
        sanitized = _sanitize_skills(result, _resume_json(skills=["Python"]))
        assert sanitized is None

    def test_accepts_half_dropped(self) -> None:
        result = RewriteOutput(skills=["Python", "Kubernetes"])
        sanitized = _sanitize_skills(result, _resume_json(skills=["Python"]))
        assert sanitized is not None
        assert sanitized.skills == ["Python"]

    def test_no_input_skills_returns_unchanged(self) -> None:
        result = RewriteOutput(skills=["Python"])
        assert _sanitize_skills(result, _resume_json(skills=[])) is result

    def test_no_output_skills_returns_unchanged(self) -> None:
        result = RewriteOutput(skills=[])
        assert _sanitize_skills(result, _resume_json(skills=["Python"])) is result

    def test_fuzzy_keep(self) -> None:
        result = RewriteOutput(skills=["SQL"])
        sanitized = _sanitize_skills(result, _resume_json(skills=["PostgreSQL"]))
        assert sanitized is not None
        assert sanitized.skills == ["SQL"]


class TestCompanyMatches:
    def test_exact_case_insensitive(self) -> None:
        assert _company_matches("Acme Corp", "ACME")

    def test_output_substring_of_input(self) -> None:
        assert _company_matches("Acme", "Acme Corp")

    def test_input_substring_of_output(self) -> None:
        assert _company_matches("Acme Corp Holdings", "Acme")

    def test_no_match(self) -> None:
        assert not _company_matches("Globex", "Acme")


class TestExtractCompanies:
    def test_extracts_non_empty_companies(self) -> None:
        experiences = [{"company": "Acme"}, {"company": "  "}, {"company": "Globex"}]
        assert _extract_companies(experiences) == ["Acme", "Globex"]

    def test_empty_experiences(self) -> None:
        assert _extract_companies([]) == []

    def test_handles_model_objects(self) -> None:
        experiences = [ExperienceEntry(company="Acme")]
        assert _extract_companies(experiences) == ["Acme"]


class TestValidateCompanies:
    def test_all_companies_match(self) -> None:
        resume = _resume_json(
            experience=[{"company": "Acme Corp"}, {"company": "Globex Inc"}]
        )
        result = RewriteOutput(
            experience=[
                ExperienceEntry(company="Acme"),
                ExperienceEntry(company="Globex"),
            ]
        )
        assert _validate_companies(result, resume)

    def test_rejects_fabricated_company(self) -> None:
        resume = _resume_json(experience=[{"company": "Acme Corp"}])
        result = RewriteOutput(experience=[ExperienceEntry(company="FakeCorp")])
        assert not _validate_companies(result, resume)

    def test_skips_empty_output_company(self) -> None:
        resume = _resume_json(experience=[{"company": "Acme Corp"}])
        result = RewriteOutput(experience=[ExperienceEntry(company="")])
        assert _validate_companies(result, resume)

    def test_passes_when_input_has_no_companies(self) -> None:
        resume = _resume_json(experience=[{"company": ""}])
        result = RewriteOutput(experience=[ExperienceEntry(company="Anything")])
        assert _validate_companies(result, resume)

    def test_invalid_json_passes(self) -> None:
        result = RewriteOutput(experience=[ExperienceEntry(company="Acme")])
        assert _validate_companies(result, "not json")


class TestExtractStartYear:
    def test_range(self) -> None:
        assert _extract_start_year("2020 - Present") == 2020

    def test_month_range(self) -> None:
        assert _extract_start_year("Jan 2019 - Mar 2021") == 2019

    def test_bare_year(self) -> None:
        assert _extract_start_year("2015") == 2015

    def test_no_year(self) -> None:
        assert _extract_start_year("Present") is None


class TestValidateChronological:
    def test_ordered_passes(self) -> None:
        result = RewriteOutput(
            experience=[
                ExperienceEntry(dates="2020 - Present"),
                ExperienceEntry(dates="2018 - 2019"),
                ExperienceEntry(dates="2016 - 2017"),
            ]
        )
        assert _validate_chronological(result)

    def test_reversed_rejects(self) -> None:
        result = RewriteOutput(
            experience=[
                ExperienceEntry(dates="2016 - 2017"),
                ExperienceEntry(dates="2018 - 2019"),
            ]
        )
        assert not _validate_chronological(result)

    def test_single_entry_passes(self) -> None:
        result = RewriteOutput(experience=[ExperienceEntry(dates="2020 - Present")])
        assert _validate_chronological(result)

    def test_no_parseable_years_passes(self) -> None:
        result = RewriteOutput(
            experience=[
                ExperienceEntry(dates="Present"),
                ExperienceEntry(dates="Current"),
            ]
        )
        assert _validate_chronological(result)

    def test_equal_years_passes(self) -> None:
        result = RewriteOutput(
            experience=[
                ExperienceEntry(dates="2020 - Present"),
                ExperienceEntry(dates="2020 - 2020"),
            ]
        )
        assert _validate_chronological(result)

    def test_unparseable_entries_skipped(self) -> None:
        result = RewriteOutput(
            experience=[
                ExperienceEntry(dates="2020 - Present"),
                ExperienceEntry(dates="Current"),
                ExperienceEntry(dates="2016 - 2018"),
            ]
        )
        assert _validate_chronological(result)


class TestTailorSkills:
    def _jd(
        self,
        required: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> JDParsingOutput:
        return JDParsingOutput(
            required_skills=required or [],
            keywords=keywords or [],
        )

    def _strategy(self, keywords: list[str] | None = None) -> GapAnalysisOutput:
        return GapAnalysisOutput(keyword_strategy=keywords or [])

    def test_no_jd_or_strategy_returns_unchanged(self) -> None:
        skills = ["Git", "Python", "SQL"]
        assert _tailor_skills(skills) == skills

    def test_required_skills_move_to_front(self) -> None:
        result = _tailor_skills(
            ["Git", "Docker", "Python", "C#"],
            jd=self._jd(required=["Python", "Git"]),
        )
        assert result[:2] == ["Git", "Python"]

    def test_required_matches_preserve_relative_order(self) -> None:
        result = _tailor_skills(
            ["Python", "Git", "SQL"],
            jd=self._jd(required=["SQL", "Git"]),
        )
        assert result[:2] == ["Git", "SQL"]

    def test_keywords_prepended_when_absent(self) -> None:
        result = _tailor_skills(
            ["Python", "SQL"],
            jd=self._jd(keywords=["REST API", "Docker"]),
        )
        assert result[:2] == ["REST API", "Docker"]

    def test_keyword_already_present_not_duplicated(self) -> None:
        result = _tailor_skills(
            ["Python", "SQL"],
            jd=self._jd(keywords=["Python", "Docker"]),
        )
        assert result == ["Docker", "Python", "SQL"]

    def test_additions_capped_at_five(self) -> None:
        result = _tailor_skills(
            ["Python"],
            jd=self._jd(keywords=["A", "B", "C", "D", "E", "F"]),
        )
        assert len(result) == 6
        assert result[:5] == ["A", "B", "C", "D", "E"]

    def test_strategy_keywords_used_when_no_jd_required(self) -> None:
        result = _tailor_skills(
            ["Git", "Docker", "Python"],
            strategy=self._strategy(keywords=["Python"]),
        )
        assert result[0] == "Python"

    def test_strategy_keywords_prepended_when_no_jd_keywords(self) -> None:
        result = _tailor_skills(
            ["Python", "SQL"],
            strategy=self._strategy(keywords=["Docker"]),
        )
        assert result == ["Docker", "Python", "SQL"]

    def test_accepts_dict_inputs(self) -> None:
        jd = {"required_skills": ["Python"], "keywords": ["Docker"]}
        strategy = {"keyword_strategy": ["Python"]}
        result = _tailor_skills(["SQL", "Python"], jd=jd, strategy=strategy)
        assert result[:2] == ["Docker", "Python"]

    def test_non_ascii_keyword_filtered(self) -> None:
        result = _tailor_skills(
            ["Python"],
            jd=self._jd(keywords=["AWS Glue", "caf\xe9"]),
        )
        assert result == ["AWS Glue", "Python"]

    def test_fuzzy_match_counts_as_present(self) -> None:
        result = _tailor_skills(
            ["PostgreSQL"],
            jd=self._jd(keywords=["SQL"]),
        )
        assert result == ["PostgreSQL"]


class TestParsedToRewrite:
    def _resume(self, skills: list[str] | None = None) -> ResumeParsingOutput:
        return ResumeParsingOutput(
            summary="A summary",
            skills=skills or [],
            experience=[ExperienceEntry(company="Acme", dates="2020 - Present")],
            projects=["Project One"],
            certifications=["Cert A"],
            education=["B.Sc."],
        )

    def test_converts_model_with_tailored_skills(self) -> None:
        jd = JDParsingOutput(
            required_skills=["Python"],
            keywords=["Docker"],
        )
        resume = self._resume(skills=["Git", "Python"])
        result = _parsed_to_rewrite(resume, jd=jd)
        assert result.skills == ["Docker", "Python", "Git"]

    def test_other_sections_passed_through_unchanged(self) -> None:
        resume = self._resume(skills=["Git", "Python"])
        result = _parsed_to_rewrite(resume)
        assert result.summary == "A summary"
        assert result.projects == ["Project One"]
        assert result.certifications == ["Cert A"]
        assert result.education == ["B.Sc."]
        assert result.experience[0].company == "Acme"

    def test_converts_dict(self) -> None:
        resume = {"skills": ["Python"], "experience": [], "summary": ""}
        result = _parsed_to_rewrite(resume)
        assert result.skills == ["Python"]
        assert result.experience == []

    def test_unknown_type_returns_empty(self) -> None:
        result = _parsed_to_rewrite("not a resume")
        assert result.skills == []
        assert result.summary == ""


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


class TestCountWords:
    def test_empty_output_is_zero(self) -> None:
        assert _count_words(RewriteOutput()) == 0

    def test_counts_all_text_fields(self) -> None:
        result = RewriteOutput(
            summary="two words",
            skills=["one", "two words"],
            experience=[
                ExperienceEntry(
                    title="Engineer",
                    company="Acme",
                    dates="2020 - 2024",
                    responsibilities=["Built things"],
                    achievements=["Shipped it"],
                    metrics=["Cut cost"],
                )
            ],
            projects=["Project Alpha"],
            certifications=["Cert X"],
            education=["B.Sc."],
        )
        assert _count_words(result) == 21


class TestFallbackLogging:
    def _inputs(self, resume: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "parsed_resume": resume
            or {
                "summary": "Old summary",
                "skills": ["Python"],
                "experience": [],
                "projects": [],
                "certifications": [],
                "education": [],
            },
            "tailoring_strategy": {},
        }

    async def test_llm_success_logs_metrics(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        client = _MockClient(
            response=json.dumps(
                {
                    "summary": "Improved summary",
                    "skills": ["Python"],
                    "experience": [],
                    "projects": ["Built a project"],
                    "certifications": [],
                    "education": [],
                }
            )
        )
        agent = ResumeRewriteAgent(client)
        result = await agent.run(self._inputs())
        assert result.skills == ["Python"]
        assert "LLM rewrite succeeded" in caplog.text
        assert "skills=1" in caplog.text
        assert "words=6" in caplog.text

    async def test_llm_failure_logs_fallback_reason(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        agent = ResumeRewriteAgent(_MockClient(error=LLMConnectionError("boom")))
        result = await agent.run(self._inputs())
        assert result.skills == ["Python"]
        assert "Fallback: parsed resume used" in caplog.text
        assert "LLM failed on both attempts" in caplog.text
