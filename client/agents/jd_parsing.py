"""
jd_parsing.py
JD Parsing Agent — extracts structured data from job descriptions.

Uses an LLM to parse the JD into a ``JDParsingOutput`` model.  Falls
back to ``FormatDetector.parse_job_description()`` on LLM failure or
validation errors.  The "try LLM twice, then fall back" loop comes from
``client.agents._retry`` — see :func:`retry_llm_then_fallback`.
"""

import logging
import re
from typing import Any

from pydantic import ValidationError

from client.agents._retry import retry_llm_then_fallback
from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.format_detector import FormatDetector
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import JDParsingOutput
from client.skills import SkillNormalizer

logger = logging.getLogger(__name__)

_NORMALIZER = SkillNormalizer()

_SYSTEM_PROMPT = (
    "You are the Job Description Parsing Agent. "
    "Your task is to extract structured, machine-readable information "
    "from a job description. "
    "Produce a JSON object with the following fields: "
    "role_title, company_name, seniority_level, required_skills, "
    "preferred_skills, responsibilities, keywords, industry_terms, "
    "company_signals. "
    "Follow these rules: "
    "Do not add information not present in the job description. "
    "Extract the company name exactly as it appears in the job "
    "description; output empty string if not present. "
    "Normalize skills (e.g., 'communication skills' -> 'communication'). "
    "Normalize all skills to their canonical form "
    "(e.g., 'JS' -> 'JavaScript', 'React.js' -> 'React', "
    "'AWS' -> 'Amazon Web Services'). "
    "Extract all relevant keywords. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "Do not add information not present in the JD",
    "No markdown, no explanation — just the JSON object",
]

_COMPANY_TOKEN = r"[A-Z0-9][A-Za-z0-9&.'-]+"
_COMPANY_NAME_GROUP = _COMPANY_TOKEN + r"(?:[ \t]+" + _COMPANY_TOKEN + r")"
_COMPANY_LABEL_RE = re.compile(
    r"(?:^|\n)[ \t]*(?i:company|employer|organization|hiring\s+company)"
    r"[ \t]*[:–-][ \t]*(" + _COMPANY_NAME_GROUP + r"{0,2})"
)
_COMPANY_FIRST_SENTENCE_RE = re.compile(
    r"^(" + _COMPANY_NAME_GROUP + r"{0,2})\s+(?:is|are)\b",
    re.MULTILINE,
)
_COMPANY_AT_RE = re.compile(
    r"\b(?:at|for|with)\s+(" + _COMPANY_NAME_GROUP + r"{0,1})\b"
)

_NON_COMPANY_NAMES = frozenset(
    {"we", "you", "they", "our", "this", "there", "it", "that", "your"}
)


def _extract_company_name(jd_text: str) -> str:
    """Best-effort extraction of the employer name from raw JD text.

    Tries explicit labels (``Company:``) first, then the common JD opening
    pattern ``<Name> is/are ...``, then ``at/for/with <Name>`` references.
    Returns an empty string when nothing confident can be derived.
    """
    text = jd_text.lstrip("\ufeff \t\r\n")
    for pattern in (_COMPANY_LABEL_RE, _COMPANY_FIRST_SENTENCE_RE, _COMPANY_AT_RE):
        match = pattern.search(text)
        if match:
            name = _clean_company_name(match.group(1))
            if (
                name
                and any(ch.isalpha() for ch in name)
                and name.lower() not in _NON_COMPANY_NAMES
            ):
                return name
    return ""


def _clean_company_name(name: str) -> str:
    """Strip trailing punctuation and stray whitespace from a company name.

    Args:
        name: Raw candidate name captured by a regex group.

    Returns:
        The trimmed name, or an empty string when nothing is left.
    """
    return name.strip(" \t\r\n,;:!?.").strip()


def _sync_company_name(result: JDParsingOutput) -> JDParsingOutput:
    """Make ``company_name`` and ``company_signals["company_name"]`` agree.

    Prefers the top-level ``company_name`` field, falling back to the
    value embedded in ``company_signals``.  Injects the name into
    ``company_signals`` under the ``"company_name"`` key so downstream
    consumers have a single source of truth.
    """
    signals = dict(result.company_signals)
    name = result.company_name or signals.get("company_name", "")
    if name:
        signals["company_name"] = name
    else:
        signals.pop("company_name", None)
    return result.model_copy(update={"company_name": name, "company_signals": signals})


class JDParsingAgent:
    """Agent that parses job descriptions into structured JSON.

    Tries LLM extraction first.  On failure or validation error, falls
    back to ``FormatDetector`` regex parsing and wraps the result in a
    ``JDParsingOutput``.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> JDParsingOutput:
        """Parse a job description into structured fields.

        Args:
            inputs: Must contain ``"job_description"`` (str).

        Returns:
            A validated ``JDParsingOutput``.
        """
        jd_text = inputs.get("job_description", "")
        if not jd_text:
            logger.debug("JD parsing: empty input, returning defaults")
            return JDParsingOutput()

        logger.debug("JD parsing: input_len=%d", len(jd_text))

        # Attempt LLM extraction (with one retry), then fall back to regex.
        return await retry_llm_then_fallback(
            try_llm=lambda strict: self._try_llm(jd_text, strict=strict),
            fallback=lambda: self._regex_fallback(jd_text),
            agent_name="JD parsing",
        )

    async def _try_llm(
        self, jd_text: str, *, strict: bool = False
    ) -> JDParsingOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            jd_text: Raw job description text.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``JDParsingOutput``, or ``None`` on failure.
        """
        prompt = f"Extract structured data from this job description:\n\n{jd_text}"
        rules = (
            _STRICT_RULES
            if strict
            else [
                "Output only valid JSON",
                "Do not add information not present in the JD",
            ]
        )

        logger.debug(
            "LLM JD attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[jd_text],
                response_format="json",
                json_schema=model_to_json_schema(JDParsingOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM JD parsing failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM JD response: %s", raw[:200] if raw else "<empty>")
        data = self._parse_json(raw)
        if data is None:
            return None

        try:
            result = JDParsingOutput(**data)
        except ValidationError:
            logger.warning("LLM output failed Pydantic validation")
            return None

        # Keep company_name and company_signals in sync so the name
        # flows with the signals regardless of which the LLM populated.
        result = _sync_company_name(result)
        # Canonicalize skill lists per the shared taxonomy.
        return result.model_copy(
            update={
                "required_skills": _NORMALIZER.normalize_list(result.required_skills),
                "preferred_skills": _NORMALIZER.normalize_list(result.preferred_skills),
            }
        )

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from an LLM response.

        Thin wrapper over :func:`client.json_utils.parse_json_response`.
        Handles responses wrapped in markdown fences.
        """
        return parse_json_response(raw)

    @staticmethod
    async def _regex_fallback(jd_text: str) -> JDParsingOutput:
        """Fall back to FormatDetector regex parsing.

        Args:
            jd_text: Raw job description text.

        Returns:
            A ``JDParsingOutput`` built from regex-extracted fields.
        """
        fd = FormatDetector()
        parsed = await fd.parse_job_description(jd_text)

        logger.debug(
            "Regex fallback results: title=%s responsibilities=%d"
            " requirements=%d nice_to_have=%d",
            parsed.title,
            len(parsed.responsibilities),
            len(parsed.requirements),
            len(parsed.nice_to_have),
        )

        company_name = _extract_company_name(jd_text)
        company_signals = {"company_name": company_name} if company_name else {}

        # Map ParsedJobDescription fields to JDParsingOutput fields
        return JDParsingOutput(
            role_title=parsed.title,
            company_name=company_name,
            seniority_level="",
            required_skills=_NORMALIZER.normalize_list(parsed.requirements),
            preferred_skills=_NORMALIZER.normalize_list(parsed.nice_to_have),
            responsibilities=parsed.responsibilities,
            keywords=FormatDetector.extract_keywords(jd_text),
            industry_terms=[],
            company_signals=company_signals,
        )
