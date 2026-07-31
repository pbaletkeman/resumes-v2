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
                return result

        # Fallback: return the parsed resume unchanged
        logger.warning(
            "LLM rewrite failed on both attempts, returning parsed resume unchanged"
        )
        return _parsed_to_rewrite(parsed_resume)

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


def _parsed_to_rewrite(parsed: Any) -> RewriteOutput:
    """Convert a ``ResumeParsingOutput`` (or dict) to ``RewriteOutput``."""
    if hasattr(parsed, "model_dump"):
        data: dict[str, Any] = parsed.model_dump()
    elif isinstance(parsed, dict):
        data = dict(parsed)  # type: ignore[reportUnknownArgumentType]
    else:
        return RewriteOutput()
    return RewriteOutput(
        summary=str(data.get("summary", "")),
        skills=list(data.get("skills", [])),
        experience=list(data.get("experience", [])),
        projects=list(data.get("projects", [])),
        certifications=list(data.get("certifications", [])),
        education=list(data.get("education", [])),
    )


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
