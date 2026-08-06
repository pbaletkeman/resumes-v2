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
    "the company (its mission, values, or what attracts you to them).\n\n"
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

_PLACEHOLDER_TOKENS = (
    "[Company Name]",
    "[Company]",
    "<Company Name>",
    "[Employer Name]",
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
            logger.debug("Cover letter: empty input, returning fallback cover letter")
            logger.info(
                "Fallback: template cover letter used (reason: %s)", "empty input"
            )
            return CoverLetterOutput(
                cover_letter=_build_fallback_cover_letter(jd, resume, strategy)
            )

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
                logger.info(
                    "LLM cover letter succeeded (words=%d)",
                    len(result.cover_letter.split()),
                )
                return result

        # Fallback: return data-driven fallback cover letter
        logger.warning(
            "LLM cover letter failed on both attempts, returning fallback cover letter"
        )
        logger.info(
            "Fallback: template cover letter used (reason: %s)",
            "LLM failed on both attempts",
        )
        return CoverLetterOutput(
            cover_letter=_build_fallback_cover_letter(jd, resume, strategy)
        )

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
            "- ONLY mention skills whose credentials are in the CANDIDATE resume. "
            "- Use the company name from the job description.\n"
            "- Do NOT invent or add skills not present in the resume.\n"
            "- Do not use any Unicode characters outside the standard ASCII range.\n"
            "- Do not fabricate the candidate's achievements. Only use achievements "
            "explicitly present in the resume.\n"
            "- Do not fabricate the company name, only use the exact company name from "
            "the job description.\n"
            "- Never use a company from the candidate's resume (e.g. a past employer) "
            "as the target company.\n"
            "- Use the exact role title from the job description.\n"
            "- The candidate's contact details (if provided below) are the ONLY "
            "phone number and email address you may mention; never invent contact "
            "information.\n\n"
            f"{_company_directive(jd_json)}"
            "STRUCTURE:\n"
            "1. First paragraph: Mention [ROLE TITLE] at [COMPANY NAME]. "
            "Reference something specific about the company.\n"
            "2. Middle paragraphs: Map these required skills to the candidate's "
            "experience: [list the required_skills from the JD]. "
            "Include quantified achievements.\n"
            "3. Final paragraph: Thank them and request an interview.\n"
            "If any contact details were provided, you may close with a line giving "
            "the candidate's phone number or email address for follow-up.\n\n"
            f"JOB DESCRIPTION (use the company name and role title from here):\n"
            f"{jd_json}\n\n"
            f"CANDIDATE RESUME (use ONLY skills and achievements from here):\n"
            f"{resume_json}\n\n"
            f"CANDIDATE CONTACT INFORMATION (only these, if any are present):\n"
            f"{_contact_from_resume(resume_json)}\n\n"
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

        # If cover_letter is empty, reject so run() falls back to the
        # data-driven fallback letter
        if not result.cover_letter.strip():
            logger.warning("cover_letter is empty, rejecting so run() falls back")
            return None

        # Post-validation checks
        if not _validate_role(result, jd_json):
            logger.warning("Cover letter does not name the JD role title -- rejecting")
            return None

        _check_company(result, jd_json)

        result = _apply_company_name(result, jd_json, resume_json)

        _check_skills(result, resume_json, jd_json)

        if not _validate_length(result):
            logger.warning("Cover letter length outside extreme bounds -- rejecting")
            return None

        return _apply_contact_info(result, resume_json)


def _serialize(value: Any) -> str:
    """Serialize a Pydantic model or dict to a JSON string."""
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(), indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def _contact_from_resume(resume_json: str) -> str:
    """Build a contact-info block string from a serialized resume.

    Reads ``phone``, ``email``, ``linkedin``, and ``github`` from the
    resume JSON and returns them as labeled lines.  Returns the string
    ``"(none)"`` when every field is empty or absent so the LLM knows
    no contact details are available.
    """
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return "(none available)"
    labels = (
        ("Phone", "phone"),
        ("Email", "email"),
        ("LinkedIn", "linkedin"),
        ("GitHub", "github"),
    )
    lines: list[str] = []
    for label, field in labels:
        value = resume_data.get(field, "")
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}: {value.strip()}")
    if not lines:
        return "(none available)"
    return "\n".join(lines)


def _apply_contact_info(
    result: CoverLetterOutput, resume_json: str
) -> CoverLetterOutput:
    """Ensure the letter carries the candidate's contact details.

    Reads ``phone``, ``email``, ``linkedin``, and ``github`` from the
    resume JSON.  When at least one contact value is present AND none of
    the present values already appears in the letter, a contact line is
    appended after the signature so the letter is self-contained even if
    the renderer template omits the contact header.  When the values are
    already present or no contact info exists, the letter is returned
    unchanged.  Pure string post-processing -- no LLM call.
    """
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return result
    contact_values = [
        v.strip()
        for v in (
            resume_data.get("phone", ""),
            resume_data.get("email", ""),
            resume_data.get("linkedin", ""),
            resume_data.get("github", ""),
        )
        if isinstance(v, str) and v.strip()
    ]
    if not contact_values:
        return result

    letter_lower = result.cover_letter.lower()
    present = [v for v in contact_values if v.lower() in letter_lower]
    missing = [v for v in contact_values if v not in present]
    if not missing:
        return result

    contact_line = " | ".join(contact_values)
    letter = result.cover_letter.rstrip() + "\n\n" + contact_line + "\n"
    logger.info(
        "Injected contact info into cover letter (added %d of %d values)",
        len(missing),
        len(contact_values),
    )
    return CoverLetterOutput(cover_letter=letter)


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
    return _company_from(jd_data)


def _company_from(jd_data: dict[str, Any]) -> str:
    """Extract the company name from a JD dict.

    Prefers the top-level ``company_name`` field (Phase 4.3.F source of
    truth), then ``company_signals["company_name"]``.
    """
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


def _company_directive(jd_json: str) -> str:
    """Return a prompt directive pinning the exact target company name.

    An empty string is returned when the JD has no resolvable company so the
    prompt stays neutral.  The directive tells the LLM to name the target
    company (never a past employer from the resume).
    """
    target = _get_company_name(jd_json)
    if not target:
        return ""
    return (
        f'The exact target company name is "{target}". '
        "Your letter MUST name this exact company. "
        "NEVER use a company from the candidate's resume (e.g. a past employer) "
        "as the target company.\n"
    )


def _company_mentioned(letter_lower: str, company: str) -> bool:
    """Return True if ``company`` appears in the letter.

    Mirrors ``_check_company``: an exact case-insensitive match passes, or
    at least one significant token of the company appears as a whole word.
    """
    if company.lower() in letter_lower:
        return True
    tokens = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) >= 3]
    return bool(tokens) and any(
        re.search(rf"\b{re.escape(t)}\b", letter_lower) is not None for t in tokens
    )


def _replace_placeholders(text: str, target: str) -> str:
    """Replace literal company placeholder tokens with the target name."""
    for token in _PLACEHOLDER_TOKENS:
        if token in text:
            text = text.replace(token, target)
    return text


def _resume_companies(resume_data: dict[str, Any]) -> list[str]:
    """Extract non-empty company names from the resume's experience entries."""
    experiences: Any = resume_data.get("experience", [])
    if not isinstance(experiences, list):
        return []
    typed_experiences: list[Any] = experiences  # type: ignore[reportUnknownVariableType]
    companies: list[str] = []
    for exp in typed_experiences:
        if isinstance(exp, dict):
            company = exp.get("company", "")  # type: ignore[reportUnknownMemberType]
        else:
            company = getattr(exp, "company", "")
        if isinstance(company, str) and company.strip():
            companies.append(company.strip())
    return companies


def _resume_company_in_letter(letter_lower: str, resume_json: str, target: str) -> str:
    """Return a resume company mentioned in the letter, or an empty string.

    Only a company that differs from the target JD company is considered a
    wrong mention.  Calls by the target (e.g. the same company under a
    different name) are ignored.
    """
    if not resume_json:
        return ""
    try:
        resume_data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return ""
    target_lower = target.lower()
    for company in _resume_companies(resume_data):
        company_lower = company.lower()
        if (
            company_lower
            and company_lower not in target_lower
            and target_lower not in company_lower
            and _company_mentioned(letter_lower, company)
        ):
            return company
    return ""


def _replace_first_casefold(text: str, old: str, new: str) -> str:
    """Replace the first (case-insensitive) occurrence of ``old`` in ``text``."""
    idx = text.lower().find(old.lower())
    if idx == -1:
        return text
    return text[:idx] + new + text[idx + len(old) :]


def _apply_company_name(
    result: CoverLetterOutput,
    jd_json: str,
    resume_json: str = "",
) -> CoverLetterOutput:
    """Deterministically fix the target company name in the letter.

    Pure string post-processing (no LLM call).  Resolves the JD company via
    ``_company_from``, replaces literal placeholder tokens (``[Company Name]``
    and friends), and — when the letter instead names a company from the
    candidate's resume — substitutes the first wrong mention with the JD
    company.  A letter that is already correct (or has no target) is returned
    unchanged.
    """
    target = _get_company_name(jd_json)
    if not target:
        return result
    letter = result.cover_letter

    letter = _replace_placeholders(letter, target)

    letter_lower = letter.lower()
    if not _company_mentioned(letter_lower, target):
        wrong = _resume_company_in_letter(letter_lower, resume_json, target)
        if wrong:
            letter = _replace_first_casefold(letter, wrong, target)
            logger.info(
                "Substituted resume company %r with target company %r",
                wrong,
                target,
            )

    if letter == result.cover_letter:
        return result
    return CoverLetterOutput(cover_letter=letter)


def _build_fallback_cover_letter(jd: Any, resume: Any, strategy: Any) -> str:
    """Build a data-driven fallback cover letter without an LLM.

    Uses the JD's role title and company name, the candidate's name, 2-3
    JD required skills the candidate already has, and one achievement from
    the most recent experience entry.  Missing data is omitted rather than
    replaced with placeholder text.
    """
    jd_data = _as_dict(jd)
    resume_data = _as_dict(resume)
    strategy_data = _as_dict(strategy)

    role_title = _read_str(jd_data, "role_title").strip()
    company = _company_from(jd_data)
    name = _read_str(resume_data, "name").strip() or "Candidate"

    resume_skills = _read_str_list(resume_data, "skills")
    required_skills = _read_str_list(jd_data, "required_skills")
    overlap = _overlapping_skills(required_skills, resume_skills)[:3]
    if not overlap:
        strategy_keywords = _read_str_list(strategy_data, "keyword_strategy")
        overlap = _overlapping_skills(strategy_keywords, resume_skills)[:3]

    achievement = _most_recent_achievement(resume_data)

    signature = f"Sincerely,\n{name}"
    contact_line = _contact_signature_line(resume_data)
    if contact_line:
        signature += f"\n{contact_line}"

    return (
        "Dear Hiring Manager,\n\n"
        f"{_opening_paragraph(role_title, company)}\n\n"
        f"{_middle_paragraph(overlap, achievement)}\n\n"
        f"{_closing_paragraph(company)}\n\n"
        f"{signature}"
    )


def _contact_signature_line(resume_data: dict[str, Any]) -> str:
    """Join the resume's contact fields into a single signature line.

    Reads ``phone``, ``email``, ``linkedin``, and ``github`` and returns
    them joined on `` | ``.  Returns an empty string when none are present
    so the signature renders unchanged.
    """
    values = [
        v.strip()
        for v in (
            resume_data.get("phone", ""),
            resume_data.get("email", ""),
            resume_data.get("linkedin", ""),
            resume_data.get("github", ""),
        )
        if isinstance(v, str) and v.strip()
    ]
    return " | ".join(values)


def _opening_paragraph(role_title: str, company: str) -> str:
    """Build the opening paragraph naming the role and company."""
    text = "I am writing to express my strong interest in"
    if role_title:
        text += f" the {role_title} position"
    else:
        text += " the advertised position"
    if company:
        text += f" at {company}"
    text += "."
    if company:
        text += (
            " I am excited about the opportunity to work at "
            f"{company} and contribute to its success."
        )
    else:
        text += (
            " I am excited about the opportunity to contribute to a "
            "forward-thinking team."
        )
    return text


def _middle_paragraph(overlap: list[str], achievement: str) -> str:
    """Build the middle paragraph mapping skills and an achievement."""
    parts: list[str] = []
    if overlap:
        skills_text = _join_skills(overlap)
        parts.append(
            "Throughout my career, I have developed strong capabilities in "
            f"{skills_text}, which map directly to the core requirements of "
            "this role."
        )
    if achievement:
        achievement_sentence = achievement.strip().rstrip(".") + "."
        sentence = (
            "In my most recent role, I "
            + achievement_sentence[0].lower()
            + achievement_sentence[1:]
        )
        parts.append(sentence)
    if parts:
        return " ".join(parts)
    return (
        "Throughout my career, I have built a strong track record of "
        "delivering high-quality work, and I am confident my skills and "
        "experience would let me contribute meaningfully from day one."
    )


def _closing_paragraph(company: str) -> str:
    """Build the closing paragraph thanking the reader."""
    if company:
        contribution = f"contribute to {company}'s success"
    else:
        contribution = "contribute to your organization"
    return (
        "Thank you for considering my application. I would welcome the "
        f"opportunity to discuss how I can {contribution}. I look forward "
        "to hearing from you."
    )


def _join_skills(skills: list[str]) -> str:
    """Join 1-3 skills into a natural phrase (e.g. 'a, b, and c')."""
    if not skills:
        return ""
    if len(skills) == 1:
        return skills[0]
    if len(skills) == 2:
        return f"{skills[0]} and {skills[1]}"
    return ", ".join(skills[:-1]) + ", and " + skills[-1]


def _overlapping_skills(candidates: list[str], known: list[str]) -> list[str]:
    """Return candidates the resume already covers (fuzzy match)."""
    return [skill for skill in candidates if _skill_in_list(skill, known)]


def _most_recent_achievement(resume_data: dict[str, Any]) -> str:
    """Return one achievement (or responsibility) from the first entry.

    Resume experience is listed most-recent-first, so the first entry is
    the most recent role.  A responsibility is used only when the entry
    has no achievements.
    """
    experiences: Any = resume_data.get("experience", [])
    if not isinstance(experiences, list) or not experiences:
        return ""
    typed_experiences: list[Any] = experiences  # type: ignore[reportUnknownVariableType]
    first: Any = typed_experiences[0]
    achievements: Any = []
    responsibilities: Any = []
    if isinstance(first, dict):
        achievements = first.get("achievements", [])  # type: ignore[reportUnknownMemberType]
        responsibilities = first.get("responsibilities", [])  # type: ignore[reportUnknownMemberType]
    else:
        achievements = getattr(first, "achievements", [])
        responsibilities = getattr(first, "responsibilities", [])
    if isinstance(achievements, list):
        for item in achievements:  # type: ignore[reportUnknownVariableType]
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(responsibilities, list):
        for item in responsibilities:  # type: ignore[reportUnknownVariableType]
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


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


def _read_str(data: dict[str, Any], field: str) -> str:
    """Read a string field from a dict, returning empty when absent."""
    value = data.get(field, "")
    if isinstance(value, str):
        return value
    return ""


def _read_str_list(data: dict[str, Any], field: str) -> list[str]:
    """Read a list-of-strings field from a dict, ignoring non-strings."""
    value = data.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]  # type: ignore[reportUnknownVariableType]


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
