"""
resume_rewrite.py
Resume Rewrite Agent.

Rewrites a resume using a tailoring strategy from the Gap Analysis Agent.
Uses an LLM to produce a ``RewriteOutput``.  Falls back to the original
parsed resume on LLM failure.
"""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import RewriteOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Resume Rewrite Agent. "
    "Rewrite the resume using the Tailoring Strategy. "
    "Output a full resume with: "
    "Updated summary, Updated skills section, "
    "Rewritten bullet points, Quantified achievements, "
    "ATS-aligned keywords, Strong action verbs, "
    "Clear concise phrasing. "
    "Rules: "
    "Maintain factual accuracy. "
    "Do not invent employment history. "
    "You may add reasonable metrics only if implied "
    "(e.g., 'managed a team' -> 'managed a team of 5'). "
    "Produce clean professional formatting. "
    "All experiences MUST be listed in proper chronological order "
    "(most recent first). "
    "No new experiences can be added - use the input resume as the "
    "reference for all experience entries. "
    "All certifications from the input resume MUST be included. "
    "Do not use the extended character set: "
    "use straight quotes not curly quotes, "
    "use -> not a right arrow. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "Maintain factual accuracy",
    "No new experiences can be added",
    "All certifications from the input resume MUST be included",
    "Experiences MUST be in chronological order (most recent first)",
    "No markdown, no explanation -- just the JSON object",
]

_SCHEMA_HINT = (
    "Output a JSON object with these keys: "
    "summary (string), skills (list of strings), "
    "experience (list of objects with title, company, dates, "
    "responsibilities, achievements, metrics), "
    "projects (list of strings), certifications (list of strings), "
    "education (list of strings)."
)


class ResumeRewriteAgent:
    """Agent that rewrites a resume using a tailoring strategy.

    Tries LLM extraction first with one retry on failure.  On second
    failure, returns the original parsed resume unchanged.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> RewriteOutput:
        """Rewrite the resume using the tailoring strategy.

        Args:
            inputs: Must contain ``"parsed_resume"`` (``ResumeParsingOutput``
                or serializable dict) and ``"tailoring_strategy"``
                (``GapAnalysisOutput`` or serializable dict).

        Returns:
            A validated ``RewriteOutput``.
        """
        parsed_resume = inputs.get("parsed_resume", {})
        tailoring = inputs.get("tailoring_strategy", {})
        jd = inputs.get("parsed_job_description", {})

        if not parsed_resume:
            logger.debug("Resume rewrite: empty input, returning defaults")
            return RewriteOutput()

        resume_json = _serialize(parsed_resume)
        strategy_json = _serialize(tailoring)

        logger.debug(
            "Resume rewrite: resume_len=%d strategy_len=%d",
            len(resume_json),
            len(strategy_json),
        )

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(
                resume_json, strategy_json, strict=(attempt == 1)
            )
            if result is not None:
                logger.info(
                    "LLM rewrite succeeded (skills=%d, words=%d)",
                    len(result.skills),
                    _count_words(result),
                )
                return result

        # Fallback: return the parsed resume, tailored deterministically
        logger.warning(
            "LLM rewrite failed on both attempts, returning tailored parsed resume"
        )
        logger.info(
            "Fallback: parsed resume used (reason: %s)", "LLM failed on both attempts"
        )
        return _parsed_to_rewrite(parsed_resume, jd=jd, strategy=tailoring)

    async def _try_llm(
        self,
        resume_json: str,
        strategy_json: str,
        *,
        strict: bool = False,
    ) -> RewriteOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            resume_json: Serialized resume data.
            strategy_json: Serialized tailoring strategy.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``RewriteOutput``, or ``None`` on failure.
        """
        prompt = (
            "Rewrite the following resume using the provided tailoring strategy. "
            "Return a JSON object matching the schema described in the rules.\n\n"
            f"TAILORING STRATEGY:\n{strategy_json}\n\n"
            f"RESUME:\n{resume_json}"
        )
        rules = (
            _STRICT_RULES + [_SCHEMA_HINT]
            if strict
            else [
                "Output only valid JSON",
                "Maintain factual accuracy",
                "No new experiences can be added",
                "All certifications from the input resume MUST be included",
            ]
        )

        logger.debug(
            "LLM rewrite attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[resume_json, strategy_json],
                response_format="json",
                json_schema=model_to_json_schema(RewriteOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM resume rewrite failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM rewrite response: %s", raw[:200] if raw else "<empty>")
        data = _parse_json(raw)
        if data is None:
            return None

        try:
            result = RewriteOutput(**data)
        except ValidationError as exc:
            data_keys = list(data.keys()) if hasattr(data, "keys") else str(type(data))
            data_preview = (
                json.dumps(data, indent=2, default=str)[:500] if data else "<None>"
            )
            logger.warning(
                "LLM output failed Pydantic validation: %s\n"
                "  parsed data keys: %s\n"
                "  parsed data: %s",
                exc,
                data_keys,
                data_preview,
            )
            return None

        # Post-validation checks
        if not _validate_experience_count(result, resume_json):
            logger.warning("Output has more experiences than input -- rejecting")
            return None

        if not _validate_certifications(result, resume_json):
            logger.warning("Output missing certifications from input -- rejecting")
            return None

        if not _validate_companies(result, resume_json):
            logger.warning("Output contains a fabricated company -- rejecting")
            return None

        if not _validate_chronological(result):
            logger.warning("Output experiences not in chronological order -- rejecting")
            return None

        sanitized = _sanitize_skills(result, resume_json)
        if sanitized is None:
            logger.warning("Output skills are mostly fabricated -- rejecting")
            return None
        result = sanitized

        return result


def _serialize(value: Any) -> str:
    """Serialize a Pydantic model or dict to a JSON string."""
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(), indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def _count_words(result: RewriteOutput) -> int:
    """Count words across all text fields of a rewritten resume."""
    fields: list[str] = [result.summary]
    fields.extend(result.skills)
    fields.extend(result.projects)
    fields.extend(result.certifications)
    fields.extend(result.education)
    for entry in result.experience:
        fields.extend([entry.title, entry.company, entry.dates])
        fields.extend(entry.responsibilities)
        fields.extend(entry.achievements)
        fields.extend(entry.metrics)
    return sum(len(text.split()) for text in fields)


def _parse_json(raw: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from an LLM response.

    Thin wrapper over :func:`client.json_utils.parse_json_response`.
    Handles responses wrapped in markdown fences.
    """
    return parse_json_response(raw)


def _parsed_to_rewrite(
    parsed: Any,
    jd: Any | None = None,
    strategy: Any | None = None,
) -> RewriteOutput:
    """Convert a ``ResumeParsingOutput`` (or dict) to ``RewriteOutput``.

    Skills are tailored deterministically toward the JD ``required_skills``
    / ``keywords`` (falling back to the strategy's ``keyword_strategy``) so
    the fallback resume is still ATS-targeted without an LLM.  Experience,
    projects, certifications, and education are passed through unchanged.
    """
    if hasattr(parsed, "model_dump"):
        data: dict[str, Any] = parsed.model_dump()
    elif isinstance(parsed, dict):
        data = dict(parsed)  # type: ignore[reportUnknownArgumentType]
    else:
        return RewriteOutput()
    return RewriteOutput(
        summary=str(data.get("summary", "")),
        skills=_tailor_skills(
            list(data.get("skills", [])),
            jd=jd,
            strategy=strategy,
        ),
        experience=list(data.get("experience", [])),
        projects=list(data.get("projects", [])),
        certifications=list(data.get("certifications", [])),
        education=list(data.get("education", [])),
    )


def _tailor_skills(
    skills: list[str],
    jd: Any | None = None,
    strategy: Any | None = None,
) -> list[str]:
    """Reorder and augment skills for ATS targeting without an LLM.

    Two deterministic transformations:

    1. Skills matching the JD ``required_skills`` (or the strategy's
       ``keyword_strategy``) move to the front, preserving relative order.
    2. Up to 5 JD ``keywords`` (or strategy keywords) not already present
       in the resume skills are prepended.
    """
    jd_data = _as_dict(jd)
    strategy_data = _as_dict(strategy)

    priority = _read_str_list(jd_data, "required_skills") or _read_str_list(
        strategy_data, "keyword_strategy"
    )
    additions_source = _read_str_list(jd_data, "keywords") or _read_str_list(
        strategy_data, "keyword_strategy"
    )

    priority_norm = [_normalize_skill(s) for s in priority]
    matched: list[str] = []
    unmatched: list[str] = []
    for skill in skills:
        if _skill_matches(skill, priority_norm):
            matched.append(skill)
        else:
            unmatched.append(skill)
    reordered = matched + unmatched

    present = [_normalize_skill(s) for s in reordered]
    additions: list[str] = []
    additions_norm: list[str] = []
    for keyword in additions_source:
        if len(additions) >= 5:
            break
        keyword = keyword.strip()
        if not keyword or not _is_ascii(keyword):
            continue
        if _skill_matches(keyword, present) or _skill_matches(keyword, additions_norm):
            continue
        additions.append(keyword)
        additions_norm.append(_normalize_skill(keyword))

    return additions + reordered


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert a Pydantic model or dict to a plain dict."""
    result: dict[str, Any]
    if hasattr(value, "model_dump"):
        result = value.model_dump()
    elif isinstance(value, dict):
        result = dict(value)  # type: ignore[reportUnknownArgumentType]
    else:
        result = {}
    return result


def _read_str_list(data: dict[str, Any], field: str) -> list[str]:
    """Read a list-of-strings field from a dict, ignoring non-strings."""
    value = data.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]  # type: ignore[reportUnknownVariableType]


def _is_ascii(text: str) -> bool:
    """Return True when every character is in the ASCII range."""
    return all(ord(char) < 128 for char in text)


def _validate_experience_count(result: RewriteOutput, resume_json: str) -> bool:
    """Return True if the output does not have more experiences than input."""
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return True  # can't validate, pass
    input_exp: list[Any] = resume_data.get("experience", [])
    if not input_exp:
        return True
    if len(result.experience) > len(input_exp):
        logger.debug(
            "Experience count mismatch: output=%d input=%d",
            len(result.experience),
            len(input_exp),
        )
        return False
    return True


def _validate_certifications(result: RewriteOutput, resume_json: str) -> bool:
    """Return True if all input certifications appear in the output."""
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return True  # can't validate, pass
    input_certs: list[Any] = resume_data.get("certifications", [])
    if not input_certs:
        return True
    output_certs_lower = {c.lower() for c in result.certifications}
    for cert in input_certs:
        if not isinstance(cert, str):
            continue
        if cert.lower() not in output_certs_lower:
            logger.debug("Missing certification: %s", cert)
            return False
    return True


def _validate_companies(result: RewriteOutput, resume_json: str) -> bool:
    """Return True if every output company matches an input employer.

    Companies are matched case-insensitively by substring against the set
    of input company names (the LLM may reorder entries, so match by name
    rather than by position).  Empty output companies are skipped.
    """
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return True  # can't validate, pass
    input_companies = _extract_companies(resume_data.get("experience", []))
    if not input_companies:
        return True
    for entry in result.experience:
        company = entry.company.strip()
        if not company:
            continue
        if not any(_company_matches(company, inp) for inp in input_companies):
            logger.debug("Fabricated company not in input resume: %s", company)
            return False
    return True


def _extract_companies(experiences: list[Any]) -> list[str]:
    """Extract non-empty company names from a list of experience entries."""
    companies: list[str] = []
    for exp in experiences:
        if isinstance(exp, dict):
            company = exp.get("company", "")  # type: ignore[reportUnknownMemberType]
        else:
            company = getattr(exp, "company", "")
        if isinstance(company, str) and company.strip():
            companies.append(company.strip())
    return companies


def _company_matches(output: str, input_: str) -> bool:
    """Case-insensitive substring match between two company names."""
    out = output.lower()
    inp = input_.lower()
    return out in inp or inp in out


def _validate_chronological(result: RewriteOutput) -> bool:
    """Return True if experiences are listed most-recent-first.

    Entries without a parseable start year are skipped.  A result with
    fewer than two parseable years is accepted (cannot be validated).
    """
    years: list[int] = []
    for entry in result.experience:
        year = _extract_start_year(entry.dates)
        if year is not None:
            years.append(year)
    if len(years) < 2:
        return True
    for current, following in zip(years, years[1:], strict=False):
        if current < following:
            logger.debug(
                "Experience out of chronological order: %d before %d",
                current,
                following,
            )
            return False
    return True


def _extract_start_year(dates: str) -> int | None:
    """Return the first 4-digit year in a dates string, or None."""
    match = re.search(r"(\d{4})", dates)
    if match is None:
        return None
    return int(match.group(1))


def _sanitize_skills(result: RewriteOutput, resume_json: str) -> RewriteOutput | None:
    """Filter output skills to those present in the input resume.

    Returns a copy of ``result`` with fabricated skills removed, or
    ``None`` when more than half of the output skills are fabricated
    (the caller should fall back to ``_parsed_to_rewrite``).
    """
    input_skills = _load_str_list(resume_json, "skills")
    if not input_skills or not result.skills:
        return result
    input_normalized = [norm for s in input_skills if (norm := _normalize_skill(s))]
    kept: list[str] = []
    dropped: list[str] = []
    for skill in result.skills:
        if _skill_matches(skill, input_normalized):
            kept.append(skill)
        else:
            dropped.append(skill)
    if not dropped:
        return result
    drop_ratio = len(dropped) / len(result.skills)
    if drop_ratio > 0.5:
        logger.warning(
            "Rejecting rewrite: %d/%d output skills not in input resume",
            len(dropped),
            len(result.skills),
        )
        return None
    logger.warning(
        "Dropped %d skills not present in input resume: %s",
        len(dropped),
        ", ".join(dropped),
    )
    return result.model_copy(update={"skills": kept})


def _skill_matches(skill: str, input_skills: list[str]) -> bool:
    """Fuzzy-match an output skill against normalized input skills.

    Accepts exact, substring (len >= 3), and shared-token matches to
    tolerate LLM renaming (e.g., 'SQL' vs 'PostgreSQL').
    """
    norm = _normalize_skill(skill)
    if not norm:
        return False
    if norm in input_skills:
        return True
    norm_tokens = {t for t in norm.split() if len(t) >= 2}
    for inp in input_skills:
        if not inp:
            continue
        if len(norm) >= 3 and (norm in inp or inp in norm):
            return True
        inp_tokens = {t for t in inp.split() if len(t) >= 2}
        if norm_tokens & inp_tokens:
            return True
    return False


def _normalize_skill(skill: str) -> str:
    """Lowercase a skill and reduce it to whitespace-separated tokens."""
    return " ".join(re.findall(r"[a-z0-9]+", skill.lower()))


def _load_str_list(resume_json: str, field: str) -> list[str]:
    """Load a list-of-strings field from a serialized resume."""
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return []
    value = resume_data.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]  # type: ignore[reportUnknownVariableType]
