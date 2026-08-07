# Skill Taxonomy (`client/skills/taxonomy.json`)

## What it is

`client/skills/taxonomy.json` is the **canonical skill taxonomy** for the pipeline: a
curated, hand-maintained mapping from the many ways a skill can be written
(synonyms, abbreviations, vendor spellings, casing, version suffixes) down to one
**canonical skill name**.

It is the single source of truth that lets every part of the pipeline agree on what a
skill "really is", so skills parsed from a resume and alternate spellings in a job
description can be compared and matched accurately.

## File structure

The file is a single top-level JSON object keyed by **category**, each mapping a
**canonical skill name** to a list of its **variants** (every common way it is written):

```json
{
  "programming_languages": {
    "JavaScript": ["js", "javascript", "ecmascript", "es6", "es2015"],
    "Python": ["python", "py", "python3"]
  },
  "frameworks": {
    "React": ["react.js", "reactjs", "react", "react js"],
    "Node.js": ["node", "nodejs"]
  }
}
```

The six categories are: `programming_languages`, `frameworks`, `databases`, `cloud`,
`tools`, and `soft_skills`. Each canonical name is unique across all categories; a
variant is a non-canonical spelling that maps back to that canonical name. A canonical
name may also be listed among its own variants (e.g. `"javascript"` → `JavaScript`) for
defensive matching.

## How it is loaded and used

- **Loaded once at import time.** `client/skills/normalizer.py` reads the file via
  `importlib.resources` (`client/skills/taxonomy.json`) and builds in-memory lookup
  indexes (`_CANONICAL_BY_KEY`, `_VARIANTS`, `_CATEGORY_BY_CANONICAL`). No LLM call is
  involved — matching is fully deterministic and offline.
- **Accessed through `SkillNormalizer`** (`client/skills/normalizer.py`), the only thing
  that reads the JSON directly. Matching reduces each raw skill to three comparable
  forms — lowercased, squashed (non-alphanumeric stripped), and tokenized — and maps it
  to a canonical name.

### Key API

| Method | Purpose |
| --- | --- |
| `normalize(skill) -> str` | Map a raw skill to its canonical name (fallback: lowercase tokenized form) |
| `canonicalize(skill) -> str` | Alias for `normalize()` |
| `normalize_list(skills) -> list[str]` | Normalize, canonicalize, de-duplicate a list (order-preserving) |
| `get_variants(canonical) -> list[str]` | Known variants for a canonical skill (empty if unknown) |
| `match_skills(jd, resume) -> dict` | Classify skills into `missing` / `matched` / `extra` using canonical forms |

## What it is used for

Skill normalization supports **JD ↔ resume skill matching**, **gap analysis**, and
**keyword optimization** across the pipeline. Every agent that touches skills converts
raw names to canonical forms using a shared singleton (`_NORMALIZER = SkillNormalizer()`),
so all agents reason about the same canonical skill vocabulary.

Normalization is wired into **5 agents** (`client/agents/`):

1. **`jd_parsing.py`** — canonicalizes JD skills on both the LLM and regex paths; the LLM
   prompt instructs it to emit canonical forms (e.g. `JS` → `JavaScript`).
2. **`resume_parsing.py`** — canonicalizes resume skills on both the LLM and regex paths.
3. **`gap_analysis.py`** — feeds canonical JD/resume lists into the LLM prompt
   (`_canonical_skills_context`) and cross-checks the LLM's `missing_skills` against the
   deterministic `match_skills()` result, logging a warning when they differ.
4. **`resume_rewrite.py`** — canonical-aware skill matching and keyword de-duplication in
   tailoring/sanitizing (`_tailor_skills`).
5. **`cover_letter.py`** — canonical skill matching and standardized keyword highlighting
   in the fallback letter builder.

## How to add or change a skill

1. Edit **`client/skills/taxonomy.json`** — add the canonical name (key) and its variants
   under the appropriate category.
2. No code change is required: `normalizer.py` rebuilds its index at import time.
3. Add/update tests in **`tests/test_skill_normalizer.py`** (currently 15 tests covering
   normalization, canonicalization, de-duplication, variant lookup, and matching).
4. Re-run `uv run pytest` and `uv run ruff check .` / `uv run pyright`.

## Tips

- **Always add the canonical name to its own variants** you intend to match (e.g.
  `"AWS"` should appear both as a canonical key and a variant) for reliable matching.
- Keep variant lists case-insensitive and punctuation-free — matching normalizes both
  sides, so `"React.js"`, `"reactjs"`, and `"REACT.JS"` all resolve to `"React"`.
- `get_variants()` returns only non-canonical variants; the canonical name itself is
  excluded.