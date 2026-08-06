"""Skill normalization and canonical taxonomy.

Provides :class:`SkillNormalizer`, a deterministic mapping from raw skill
names (synonyms, abbreviations, variations) to canonical skill names, backed by
the ``taxonomy.json`` resource. No LLM calls.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

__all__ = ["SkillNormalizer"]

_TAXONOMY_TEXT = (
    resources.files("client.skills")
    .joinpath("taxonomy.json")
    .read_text(encoding="utf-8")
)


def _match_keys(value: str) -> tuple[str, str, str]:
    """Reduce ``value`` to its comparable lower / squashed / tokenized forms."""
    low = value.strip().lower()
    squashed = re.sub(r"[^a-z0-9]+", "", low)
    tokenized = " ".join(re.findall(r"[a-z0-9]+", low))
    return low, squashed, tokenized


_CANONICAL_BY_KEY: dict[str, str] = {}
_VARIANTS: dict[str, list[str]] = {}
_CATEGORIES: list[str] = []
_CATEGORY_BY_CANONICAL: dict[str, str] = {}


def _register_skill(value: str, canonical: str, category: str) -> None:
    for key in _match_keys(value):
        _CANONICAL_BY_KEY.setdefault(key, canonical)
    if canonical not in _VARIANTS:
        _VARIANTS[canonical] = []
    if value != canonical and value not in _VARIANTS[canonical]:
        _VARIANTS[canonical].append(value)
    _CATEGORY_BY_CANONICAL.setdefault(canonical, category)
    if canonical not in _CATEGORY_BY_CANONICAL and category not in _CATEGORIES:
        _CATEGORIES.append(category)


def _build_index() -> None:
    data: dict[str, Any] = json.loads(_TAXONOMY_TEXT)
    for category, skills in data.items():
        if category not in _CATEGORIES:
            _CATEGORIES.append(category)
        for canonical, variants in skills.items():
            _register_skill(canonical, canonical, category)
            for variant in variants:
                _register_skill(variant, canonical, category)


_build_index()


class SkillNormalizer:
    """Normalize skill names against the bundled canonical taxonomy."""

    def normalize(self, skill: str) -> str:
        """Map *skill* to its canonical form.

        Returns the canonical name when a taxonomy match is found, otherwise
        the normalized lowercase tokenized form.
        """
        for key in _match_keys(skill):
            canonical = _CANONICAL_BY_KEY.get(key)
            if canonical is not None:
                return canonical
        return _match_keys(skill)[2]

    def canonicalize(self, skill: str) -> str:
        """Alias for :meth:`normalize` — explicit canonicalization."""
        return self.normalize(skill)

    def normalize_list(self, skills: list[str]) -> list[str]:
        """Normalize, canonicalize, and de-duplicate a skill list."""
        result: list[str] = []
        for skill in skills:
            norm = self.normalize(skill)
            if norm and norm not in result:
                result.append(norm)
        return result

    def get_variants(self, canonical: str) -> list[str]:
        """Return the known variants for a canonical skill (excluding aliases)."""
        target = canonical.strip().lower()
        for name, variants in _VARIANTS.items():
            if name.strip().lower() == target:
                return list(variants)
        return []

    def match_skills(
        self, jd_skills: list[str], resume_skills: list[str]
    ) -> dict[str, list[str]]:
        """Classify canonical resume skills against canonical JD skills."""
        jd_norm = self.normalize_list(jd_skills)
        resume_norm = self.normalize_list(resume_skills)
        return {
            "missing": [s for s in jd_norm if s not in resume_norm],
            "matched": [s for s in resume_norm if s in jd_norm],
            "extra": [s for s in resume_norm if s not in jd_norm],
        }
