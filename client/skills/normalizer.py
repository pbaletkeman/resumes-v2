"""Skill normalization and canonical taxonomy.

Provides :class:`SkillNormalizer`, a deterministic mapping from raw skill
names (synonyms, abbreviations, variations) to canonical skill names, backed by
the ``taxonomy.json`` resource. No LLM calls.

Canonical taxonomy -> normalized forms
-------------------------------------
The taxonomy (``client/skills/taxonomy.json``, documented in
``docs/skill-taxonomy.md``) is a ``category -> {canonical name -> [variants]}``
mapping.  ``SkillNormalizer`` reduces each raw skill to three comparable forms
-- lowercase, squashed (non-alphanumeric stripped), and tokenized -- and looks
them up in order, so ``"js"``, ``"JS"``, ``"react.js"``, and ``"react js"`` all
resolve to their canonical names.  Unknown skills fall back to the normalized
lowercase tokenized form so every skill maps to a stable, comparable string.

Choosing an entry point
-----------------------
- Use :meth:`SkillNormalizer.normalize_list` when you need a canonical,
  de-duplicated, order-preserving list of skills (e.g. to compare JD and
  resume skill sets, or to feed canonical forms into an LLM prompt).
- Use :meth:`SkillNormalizer.match_skills` when you need the three-way
  classification of one list against another (``missing`` / ``matched`` /
  ``extra``); it normalizes both inputs with ``normalize_list`` internally.
- Use :meth:`SkillNormalizer.normalize` (or its alias ``canonicalize``) for a
  single-skill lookup, and :meth:`SkillNormalizer.get_variants` to inspect
  the known aliases of a canonical name.
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


def _whole_word_in(text: str, target: str) -> bool:
    """Return True when ``text`` appears in ``target`` as a whole word.

    Uses non-alphanumeric lookarounds (rather than ``\\b``) so multi-token
    and punctuation-bearing forms (e.g. ``"ci/cd"``, ``"c#"``) match on
    their boundaries without tripping on adjacent characters.
    """
    return re.search(rf"(?<![a-z0-9]){re.escape(text)}(?![a-z0-9])", target) is not None


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

        Matching is case-insensitive and punctuation-insensitive: the raw
        skill is reduced to three comparable forms (lowercase, squashed,
        tokenized) which are looked up in that order.  Returns the
        canonical name when a taxonomy match is found; unknown skills fall
        back to the normalized lowercase tokenized form.
        """
        low, squashed, tokenized = _match_keys(skill)

        # 1. exact canonical/variant match (case-insensitive), e.g. "mysql"
        canonical = _CANONICAL_BY_KEY.get(low)
        if canonical is not None:
            return canonical

        # 2. squashed lookup (punctuation stripped), e.g. "react.js"
        canonical = _CANONICAL_BY_KEY.get(squashed)
        if canonical is not None:
            return canonical

        # 3. tokenized lookup, e.g. "react js"
        canonical = _CANONICAL_BY_KEY.get(tokenized)
        if canonical is not None:
            return canonical

        # Unknown skill: fall back to the normalized lowercase tokenized form.
        return tokenized

    def canonicalize(self, skill: str) -> str:
        """Alias for :meth:`normalize` — explicit canonicalization.

        Same behavior: case-insensitive taxonomy lookup with a lowercase
        tokenized fallback for unknown skills.
        """
        return self.normalize(skill)

    def normalize_list(self, skills: list[str]) -> list[str]:
        """Normalize, canonicalize, and de-duplicate a skill list.

        Each skill goes through :meth:`normalize` (canonical form when
        known, lowercase tokenized fallback when unknown; case- and
        punctuation-insensitive).  Empty results are dropped and order is
        preserved with duplicates removed.  Prefer this when you need a
        clean, comparable canonical list (e.g. to compare two lists or
        feed a prompt).
        """
        result: list[str] = []
        for skill in skills:
            norm = self.normalize(skill)
            if norm and norm not in result:
                result.append(norm)
        return result

    def get_variants(self, canonical: str) -> list[str]:
        """Return the known variants for a canonical skill (excluding aliases).

        The lookup is case-insensitive: *canonical* is compared to the
        stored canonical names after lowercasing.  Unknown canonical names
        return an empty list.
        """
        target = canonical.strip().lower()
        for name, variants in _VARIANTS.items():
            if name.strip().lower() == target:
                return list(variants)
        return []

    def known_skills_in_text(
        self, text: str, *, include_soft: bool = False
    ) -> list[str]:
        """Return canonical taxonomy skills that appear in ``text`` as whole words.

        Every canonical name and known variant in the taxonomy is scanned for
        in ``text`` (case-insensitive, whole-word), and the canonical names of
        the hits are returned in taxonomy order.  Soft skills (e.g.
        Communication, Leadership) are excluded unless ``include_soft`` is
        True, so ordinary prose words in a cover letter (such as
        "communication skills") are not misread as technology skill claims.

        Args:
            text: Free text (e.g. a joined list of JD skill phrases).
            include_soft: When False (default), soft-skill categories are
                skipped so only technical skill nouns are reported.

        Returns:
            The canonical names of taxonomy skills found in ``text``.
        """
        text_lower = text.lower()
        found: list[str] = []
        for canonical, variants in _VARIANTS.items():
            if (
                not include_soft
                and _CATEGORY_BY_CANONICAL.get(canonical) == "soft_skills"
            ):
                continue
            forms = [canonical, *variants]
            if any(_whole_word_in(form, text_lower) for form in forms):
                found.append(canonical)
        return found

    def match_skills(
        self, jd_skills: list[str], resume_skills: list[str]
    ) -> dict[str, list[str]]:
        """Classify canonical resume skills against canonical JD skills.

        Both lists are normalized and canonicalized first (see
        :meth:`normalize_list`; case- and punctuation-insensitive, unknown
        skills become their lowercase tokenized form).  The result reports
        the JD skills missing from the resume, the resume skills that match
        the JD, and the resume skills the JD does not request.  Prefer this
        when you need the three-way comparison; use :meth:`normalize_list`
        alone when you only need canonical lists.
        """
        jd_norm = self.normalize_list(jd_skills)
        resume_norm = self.normalize_list(resume_skills)
        return {
            "missing": [skill for skill in jd_norm if skill not in resume_norm],
            "matched": [skill for skill in resume_norm if skill in jd_norm],
            "extra": [skill for skill in resume_norm if skill not in jd_norm],
        }
