"""Skill normalization and canonical taxonomy package.

Public surface: :class:`SkillNormalizer` (``client/skills/normalizer.py``),
a deterministic, offline mapper from raw skill names to canonical forms
backed by ``taxonomy.json``.  See ``docs/skill-taxonomy.md``.
"""

from client.skills.normalizer import SkillNormalizer

__all__ = ["SkillNormalizer"]
