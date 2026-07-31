"""
jd_parsing.py
JD Parsing Agent — extracts structured data from job descriptions.

Uses an LLM to parse the JD into a ``JDParsingOutput`` model.  Falls
back to ``FormatDetector.parse_job_description()`` on LLM failure or
validation errors.
"""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.format_detector import FormatDetector
from client.model_client import ModelClient
from client.models import JDParsingOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Job Description Parsing Agent. "
    "Your task is to extract structured, machine-readable information "
    "from a job description. "
    "Produce a JSON object with the following fields: "
    "role_title, seniority_level, required_skills, preferred_skills, "
    "responsibilities, keywords, industry_terms, company_signals. "
    "Follow these rules: "
    "Do not add information not present in the job description. "
    "Normalize skills (e.g., 'communication skills' -> 'communication'). "
    "Extract all relevant keywords. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "Do not add information not present in the JD",
    "No markdown, no explanation — just the JSON object",
]


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

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(jd_text, strict=(attempt == 1))
            if result is not None:
                return result

        # Fallback to regex
        logger.info("LLM parsing failed, falling back to regex")
        return await self._regex_fallback(jd_text)

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
            return JDParsingOutput(**data)
        except ValidationError:
            logger.warning("LLM output failed Pydantic validation")
            return None

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from an LLM response.

        Handles responses wrapped in markdown fences.
        """
        text = raw.strip()
        logger.debug("JSON parse input: %s", text[:300] if text else "<empty>")
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return None

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

        # Map ParsedJobDescription fields to JDParsingOutput fields
        return JDParsingOutput(
            role_title=parsed.title,
            seniority_level="",
            required_skills=parsed.requirements,
            preferred_skills=parsed.nice_to_have,
            responsibilities=parsed.responsibilities,
            keywords=FormatDetector.extract_keywords(jd_text),
            industry_terms=[],
            company_signals={},
        )
