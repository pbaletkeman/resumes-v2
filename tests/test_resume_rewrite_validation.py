"""Tests for ResumeRewriteAgent post-validation helpers (no LLM)."""

import json

from client.agents.resume_rewrite import (
    _company_matches,
    _extract_companies,
    _extract_start_year,
    _normalize_skill,
    _sanitize_skills,
    _skill_matches,
    _validate_chronological,
    _validate_companies,
)
from client.models import ExperienceEntry, RewriteOutput


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
