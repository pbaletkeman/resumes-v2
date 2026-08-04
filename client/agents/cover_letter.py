"""
cover_letter.py
Cover Letter Agent.

Generates a tailored cover letter using the parsed job description,
parsed resume, and tailoring strategy.  Uses an LLM to produce a
``CoverLetterOutput``.  Falls back to a minimal generic cover letter
on LLM failure.
"""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import CoverLetterOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Cover Letter Tailoring Agent. "
    "Using the job description, parsed resume, and tailoring strategy, "
    "write a compelling, personalized cover letter. "
    "Output a JSON object with a single key: "
    "cover_letter (the full cover letter text).\n\n"
    "CRITICAL: You MUST tailor the letter to the SPECIFIC company and role. "
    "Use the company name, role title, required skills, and company values "
    "from the job description. Do NOT write a generic letter.\n\n"
    "Structure the cover letter in three parts:\n\n"
    "First paragraph: State the exact position title you are applying for. "
    "Mention the company name by name. Reference something specific about "
    "the company (its mission, values, or what吸引 you to them).\n\n"
    "Middle paragraphs (1-2): Map your top skills DIRECTLY to the required "
    "skills listed in the job description. Pick 2-3 required skills and "
    "explain how your experience demonstrates them. Include a specific "
    "work achievement with quantified results (numbers, percentages, "
    "dollar amounts). Use keywords from the job description naturally.\n\n"
    "Final paragraph: Thank the reader. Express strong interest in an "
    "interview. Provide a professional closing with your name.\n\n"
    "Rules: "
    "Always use the company name from the job description. "
    "Always use the exact role title from the job description. "
    "Match your skills to the required_skills from the job description. "
    "Do not use skills not found in the resume. "
    "Do not use words like current, now, presently, or currently. "
    "Only include dates or timeframes if they are explicitly present in the resume. "
    "Maintain professional tone. "
    "Do not fabricate achievements. "
    "Keep length between 450-600 words. "
    "No more than 4 paragraphs. "
    "Output only valid JSON with the key cover_letter."
    "Do not use any Unicode characters outside the standard ASCII range. "
)

_STRICT_RULES = [
    "Output only valid JSON",
    "cover_letter must contain the full cover letter text",
    "Do not use words like current, now, presently, or currently",
    "Only include dates or timeframes if they are explicitly present in the resume",
    "No markdown, no explanation -- just the JSON object",
]

_SCHEMA_HINT = (
    "Output a JSON object with a single key: "
    "cover_letter (string with the full cover letter text, 450-600 words)."
)

_MINIMAL_COVER_LETTER = (
    "Dear Hiring Manager,\n\n"
    "I am writing to express my interest in the advertised position "
    "at your company. I am excited about the opportunity to contribute "
    "to your team and believe my background aligns well with your "
    "needs.\n\n"
    "With my experience and skills, I have developed strong capabilities "
    "in my field. I am confident that my qualifications make me a "
    "suitable candidate for this role and that I can deliver meaningful "
    "results.\n\n"
    "Thank you for considering my application. I would welcome the "
    "opportunity to discuss how my skills and experience align with "
    "your needs. I look forward to hearing from you.\n\n"
    "Sincerely,\n[Your Name]"
)


class CoverLetterAgent:
    """Agent that generates a tailored cover letter.

    Tries LLM extraction first with one retry on failure.  On second
    failure, returns a minimal generic cover letter.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> CoverLetterOutput:
        """Generate a tailored cover letter.

        Args:
            inputs: Must contain ``"parsed_job_description"``
                (``JDParsingOutput`` or serializable dict),
                ``"parsed_resume"`` (``ResumeParsingOutput``
                or serializable dict), and ``"tailoring_strategy"``
                (``GapAnalysisOutput`` or serializable dict).

        Returns:
            A validated ``CoverLetterOutput``.
        """
        jd = inputs.get("parsed_job_description", {})
        resume = inputs.get("parsed_resume", {})
        strategy = inputs.get("tailoring_strategy", {})

        if not jd or not resume:
            logger.debug("Cover letter: empty input, returning minimal cover letter")
            return CoverLetterOutput(cover_letter=_MINIMAL_COVER_LETTER)

        jd_json = _serialize(jd)
        resume_json = _serialize(resume)
        strategy_json = _serialize(strategy)

        logger.debug(
            "Cover letter: jd_len=%d resume_len=%d strategy_len=%d",
            len(jd_json),
            len(resume_json),
            len(strategy_json),
        )

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(
                jd_json, resume_json, strategy_json, strict=(attempt == 1)
            )
            if result is not None:
                return result

        # Fallback: return minimal generic cover letter
        logger.warning(
            "LLM cover letter failed on both attempts, "
            "returning minimal generic cover letter"
        )
        return CoverLetterOutput(cover_letter=_MINIMAL_COVER_LETTER)

    async def _try_llm(
        self,
        jd_json: str,
        resume_json: str,
        strategy_json: str,
        *,
        strict: bool = False,
    ) -> CoverLetterOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            jd_json: Serialized JD data.
            resume_json: Serialized resume data.
            strategy_json: Serialized tailoring strategy.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``CoverLetterOutput``, or ``None`` on failure.
        """
        prompt = (
            "Write a cover letter for this SPECIFIC job application. "
            "You MUST use the company name and role title from the job description. "
            "You MUST match the candidate's skills to the required skills.\n\n"
            "CRITICAL RULES:\n"
            "- ONLY mention skills that appear in the CANDIDATE RESUME below. "
            "- Use the company name from the job description.\n"
            "- Do NOT invent or add skills not present in the resume.\n"
            "- Do not use any Unicode characters outside the standard ASCII range.\n"
            "- Do not fabricate the candidate's achievements. Only use achievements "
            "explicitly present in the resume.\n"
            "- Do not fabricate the company name, only use the exact company name from "
            "the job description.\n"
            "- Use the exact role title from the job description.\n\n"
            "STRUCTURE:\n"
            "1. First paragraph: Mention [ROLE TITLE] at [COMPANY NAME]. "
            "Reference something specific about the company.\n"
            "2. Middle paragraphs: Map these required skills to the candidate's "
            "experience: [list the required_skills from the JD]. "
            "Include quantified achievements.\n"
            "3. Final paragraph: Thank them and request an interview.\n\n"
            f"JOB DESCRIPTION (use the company name and role title from here):\n"
            f"{jd_json}\n\n"
            f"CANDIDATE RESUME (use ONLY skills and achievements from here):\n"
            f"{resume_json}\n\n"
            f"TAILORING STRATEGY (use recommended emphasis and keywords):\n"
            f"{strategy_json}\n\n"
            'Return ONLY: {"cover_letter": "your tailored letter here"}'
        )
        rules = (
            _STRICT_RULES + [_SCHEMA_HINT]
            if strict
            else [
                "Output only valid JSON",
                "cover_letter must contain the full cover letter text",
                "Only mention skills that appear in the resume",
            ]
        )

        logger.debug(
            "LLM cover letter attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[jd_json, resume_json, strategy_json],
                response_format="json",
                json_schema=model_to_json_schema(CoverLetterOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM cover letter failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM cover letter response: %s", raw[:200] if raw else "<empty>")
        data = _parse_json(raw)
        if data is None:
            return None

        try:
            result = CoverLetterOutput(**data)
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

        # If cover_letter is empty, use minimal fallback
        if not result.cover_letter.strip():
            logger.warning("cover_letter is empty, using minimal fallback")
            result.cover_letter = _MINIMAL_COVER_LETTER
            return result

        # Post-validation checks
        if not _validate_role(result, jd_json):
            logger.warning("Cover letter does not name the JD role title -- rejecting")
            return None

        _check_company(result, jd_json)

        _check_skills(result, resume_json, jd_json)

        if not _validate_length(result):
            logger.warning("Cover letter length outside extreme bounds -- rejecting")
            return None

        return result


def _serialize(value: Any) -> str:
    """Serialize a Pydantic model or dict to a JSON string."""
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(), indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def _parse_json(raw: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from an LLM response.

    Thin wrapper over :func:`client.json_utils.parse_json_response`.
    Handles responses wrapped in markdown fences, and plain text
    responses that are not wrapped in JSON.
    """
    return parse_json_response(raw, plain_text_fallback="cover_letter")


_ROLE_FILLER_WORDS = {
    "senior",
    "junior",
    "mid",
    "lead",
    "principal",
    "staff",
    "entry",
    "the",
    "a",
    "an",
    "of",
    "for",
}


def _validate_role(result: CoverLetterOutput, jd_json: str) -> bool:
    """Return True if the JD role title appears in the cover letter.

    The check is skipped when ``role_title`` is empty (its default).  The
    full title is matched case-insensitively first; if that fails, the
    non-filler tokens must each appear as whole words (so "Senior Data
    Scientist" still passes a letter that only says "Data Scientist").
    """
    try:
        jd_data: dict[str, Any] = json.loads(jd_json)
    except json.JSONDecodeError, TypeError:
        return True  # can't validate, pass
    role_title = jd_data.get("role_title", "")
    if not isinstance(role_title, str) or not role_title.strip():
        return True
    letter_lower = result.cover_letter.lower()
    title_lower = role_title.strip().lower()
    if title_lower in letter_lower:
        return True
    tokens = [
        t
        for t in re.findall(r"[a-z0-9]+", title_lower)
        if t not in _ROLE_FILLER_WORDS and len(t) >= 3
    ]
    if not tokens:
        return True  # nothing meaningful left to require
    return all(
        re.search(rf"\b{re.escape(t)}\b", letter_lower) is not None for t in tokens
    )


def _check_company(result: CoverLetterOutput, jd_json: str) -> None:
    """Warn if the cover letter omits the JD company name (never rejects).

    Uses ``JDParsingOutput.company_name``, falling back to
    ``company_signals["company_name"]`` (see Phase 4.3.F).  A missing name
    or a letter that omits it only logs a warning -- paraphrased or
    abbreviated company names make a hard reject a false-positive risk.
    """
    company = _get_company_name(jd_json)
    if not company:
        logger.debug("Cover letter: no company name to check against")
        return
    letter_lower = result.cover_letter.lower()
    if company.lower() in letter_lower:
        return
    # Allow partial mention: at least one significant token of the company
    # name appears as a whole word (e.g. "Acme Corporation" vs a letter
    # that only says "Acme").
    tokens = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) >= 3]
    if tokens and any(
        re.search(rf"\b{re.escape(t)}\b", letter_lower) is not None for t in tokens
    ):
        return
    logger.warning(
        "Cover letter does not mention target company %r (accepting anyway)",
        company,
    )


def _get_company_name(jd_json: str) -> str:
    """Return the JD company name, or an empty string when unavailable."""
    try:
        jd_data: dict[str, Any] = json.loads(jd_json)
    except json.JSONDecodeError, TypeError:
        return ""
    company = jd_data.get("company_name", "")
    if isinstance(company, str) and company.strip():
        return company.strip()
    signals = jd_data.get("company_signals", {})
    if isinstance(signals, dict):
        signals_str: dict[str, str] = signals  # type: ignore[reportUnknownVariableType]
        name = signals_str.get("company_name", "")
        if name.strip():
            return name.strip()
    return ""


def _check_skills(result: CoverLetterOutput, resume_json: str, jd_json: str) -> None:
    """Warn if the letter mentions skills absent from the resume (advisory).

    Candidate skill nouns come from the JD's required/preferred skills and
    the resume's skill list.  A skill mentioned in the letter but missing
    from the resume is flagged with a warning; nothing is rejected because
    cover letter prose paraphrases freely.  Word boundaries keep short
    tokens like "ai" from matching inside words like "aimed".
    """
    resume_skills = _load_str_list(resume_json, "skills")
    jd_skills = _load_str_list(jd_json, "required_skills") + _load_str_list(
        jd_json, "preferred_skills"
    )
    candidates = list(dict.fromkeys(jd_skills + resume_skills))
    if not candidates:
        return
    letter_lower = result.cover_letter.lower()
    foreign: list[str] = []
    for skill in candidates:
        if not _skill_mentioned(letter_lower, skill):
            continue
        if not _skill_in_list(skill, resume_skills):
            foreign.append(skill)
    if foreign:
        logger.warning(
            "Cover letter mentions skills not in resume: %s",
            ", ".join(foreign),
        )


def _skill_mentioned(letter_lower: str, skill: str) -> bool:
    """Return True if ``skill`` appears in the letter as whole words."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", skill.lower()) if len(t) >= 2]
    if not tokens:
        return False
    return all(
        re.search(rf"\b{re.escape(t)}\b", letter_lower) is not None for t in tokens
    )


def _skill_in_list(skill: str, skills: list[str]) -> bool:
    """Fuzzy-match ``skill`` against a list of skills (case-insensitive)."""
    norm = _normalize_skill(skill)
    if not norm:
        return True
    for candidate in skills:
        candidate_norm = _normalize_skill(candidate)
        if not candidate_norm:
            continue
        if norm == candidate_norm:
            return True
        if len(norm) >= 3 and (norm in candidate_norm or candidate_norm in norm):
            return True
        if set(norm.split()) & set(candidate_norm.split()):
            return True
    return False


def _normalize_skill(skill: str) -> str:
    """Lowercase a skill and reduce it to whitespace-separated tokens."""
    return " ".join(re.findall(r"[a-z0-9]+", skill.lower()))


def _load_str_list(json_text: str, field: str) -> list[str]:
    """Load a list-of-strings field from a serialized object."""
    try:
        data: dict[str, Any] = json.loads(json_text)
    except json.JSONDecodeError, TypeError:
        return []
    value = data.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]  # type: ignore[reportUnknownVariableType]


def _validate_length(result: CoverLetterOutput) -> bool:
    """Return True unless the letter is an extreme length outlier.

    The spec is 450-600 words.  Mid-range deviations (200-450 and 600-800)
    are accepted with a warning; only <200 or >800 words trigger rejection
    so the caller falls back to the template letter.
    """
    word_count = len(result.cover_letter.split())
    if word_count < 200:
        logger.warning("Cover letter too short (%d words) -- rejecting", word_count)
        return False
    if word_count > 800:
        logger.warning("Cover letter too long (%d words) -- rejecting", word_count)
        return False
    if word_count < 450 or word_count > 600:
        logger.warning(
            "Cover letter length %d words outside 450-600 spec (accepting)",
            word_count,
        )
    return True
