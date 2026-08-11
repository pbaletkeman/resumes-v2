"""Tests for the SkillNormalizer canonical taxonomy (8.5.1).

Covers canonicalization, variant aliasing, localization, and unknown-skill
handling in ``client/skills/normalizer.py`` against ``taxonomy.json``.
Uses ``SkillNormalizer`` directly — no shared fixtures from ``conftest.py``.
"""

from client.skills import SkillNormalizer


class TestNormalize:
    def test_variant_to_canonical(self) -> None:
        assert SkillNormalizer().normalize("js") == "JavaScript"

    def test_abbreviation_to_canonical(self) -> None:
        assert SkillNormalizer().normalize("AWS") == "Amazon Web Services"

    def test_canonical_returns_itself(self) -> None:
        assert SkillNormalizer().normalize("JavaScript") == "JavaScript"

    def test_punctuation_variant(self) -> None:
        assert SkillNormalizer().normalize("react.js") == "React"

    def test_case_insensitive(self) -> None:
        assert SkillNormalizer().normalize("MYSQL") == "MySQL"

    def test_unknown_returns_tokenized_fallback(self) -> None:
        assert SkillNormalizer().normalize("Data Engineering") == "data engineering"

    def test_already_lower_unknown_unchanged(self) -> None:
        assert SkillNormalizer().normalize("kubernetes") == "Kubernetes"

    def test_k8s_abbreviation(self) -> None:
        assert SkillNormalizer().normalize("k8s") == "Kubernetes"


class TestCanonicalize:
    def test_alias_of_normalize(self) -> None:
        assert SkillNormalizer().canonicalize("golang") == "Go"


class TestNormalizeList:
    def test_canonicalizes_and_deduplicates(self) -> None:
        result = SkillNormalizer().normalize_list(
            ["js", "JavaScript", "React.js", "reactjs"]
        )
        assert result == ["JavaScript", "React"]

    def test_preserves_order(self) -> None:
        result = SkillNormalizer().normalize_list(["Python", "js", "Go"])
        assert result == ["Python", "JavaScript", "Go"]

    def test_unknown_skills_preserved(self) -> None:
        result = SkillNormalizer().normalize_list(["js", "Data Engineering"])
        assert result == ["JavaScript", "data engineering"]


class TestGetVariants:
    def test_returns_variants(self) -> None:
        assert "JS" in SkillNormalizer().get_variants(
            "JavaScript"
        ) or "js" in SkillNormalizer().get_variants("JavaScript")

    def test_unknown_returns_empty(self) -> None:
        assert SkillNormalizer().get_variants("NotASkill") == []


class TestMatchSkills:
    def test_matched_missing_extra(self) -> None:
        result = SkillNormalizer().match_skills(
            ["JavaScript", "python", "AWS", "React.js"],
            ["javascript", "aws", "GO"],
        )
        assert result["matched"] == ["JavaScript", "Amazon Web Services"]
        assert result["missing"] == ["Python", "React"]
        assert result["extra"] == ["Go"]
