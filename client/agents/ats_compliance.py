"""
ats_compliance.py
ATS Compliance Agent.

Evaluates a rewritten resume for ATS compatibility and fixes issues.
Uses an LLM to produce an ``ATSComplianceOutput``.  Falls back to a
default low-score result on LLM failure.
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import ATSComplianceOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the ATS Compliance Agent. "
    "Evaluate the rewritten resume for ATS compatibility. "
    "Output a JSON object with: "
    "ats_score (0-100), missing_keywords, formatting_issues, "
    "clarity_issues, recommended_fixes, auto_fixes_applied, "
    "final_resume (the full corrected resume text). "
    "Rules: "
    "Ensure keyword coverage. "
    "Remove ATS-unfriendly elements (tables, images, symbols). "
    "Improve clarity and consistency. "
    "Verify all certifications from the input resume are present "
    "in the output. "
    "Verify experiences are in chronological order (most recent first). "
    "Do not add any new experiences. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "ats_score must be an integer between 0 and 100",
    "final_resume must contain the full resume text",
    "No markdown, no explanation -- just the JSON object",
]

_SCHEMA_HINT = (
    "Output a JSON object with these keys: "
    "ats_score (integer 0-100), "
    "missing_keywords (list of strings), "
    "formatting_issues (list of strings), "
    "clarity_issues (list of strings), "
    "recommended_fixes (list of strings), "
    "auto_fixes_applied (list of strings), "
    "final_resume (string with the full corrected resume)."
)


class ATSComplianceAgent:
    """Agent that evaluates and fixes ATS compatibility issues.

    Tries LLM extraction first with one retry on failure.  On second
    failure, returns a default low-score result with the resume unchanged.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> ATSComplianceOutput:
        """Evaluate the rewritten resume for ATS compatibility.

        Args:
            inputs: Must contain ``"rewritten_resume"`` (``RewriteOutput``
                or serializable dict).

        Returns:
            A validated ``ATSComplianceOutput``.
        """
        rewritten = inputs.get("rewritten_resume", {})

        if not rewritten:
            logger.debug("ATS compliance: empty input, returning defaults")
            return ATSComplianceOutput()

        resume_json = _serialize(rewritten)

        logger.debug("ATS compliance: resume_len=%d", len(resume_json))

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(resume_json, strict=(attempt == 1))
            if result is not None:
                return result

        # Fallback: return default low-score result with resume unchanged
        logger.warning(
            "LLM ATS compliance failed on both attempts, "
            "returning default low-score result"
        )
        return _default_result(rewritten)

    async def _try_llm(
        self,
        resume_json: str,
        *,
        strict: bool = False,
    ) -> ATSComplianceOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            resume_json: Serialized resume data.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``ATSComplianceOutput``, or ``None`` on failure.
        """
        prompt = (
            "Evaluate the following resume for ATS compatibility. "
            "Provide an ATS score, identify issues, and return the "
            "corrected resume text.\n\n"
            f"RESUME:\n{resume_json}"
        )
        rules = (
            _STRICT_RULES + [_SCHEMA_HINT]
            if strict
            else [
                "Output only valid JSON",
                "ats_score must be an integer between 0 and 100",
                "final_resume must contain the full resume text",
            ]
        )

        logger.debug(
            "LLM ATS attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[resume_json],
                response_format="json",
                json_schema=model_to_json_schema(ATSComplianceOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM ATS compliance failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM ATS response: %s", raw[:200] if raw else "<empty>")
        data = _parse_json(raw)
        if data is None:
            return None

        try:
            result = ATSComplianceOutput(**data)
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

        # Post-validation: ensure ats_score is in range
        if not 0 <= result.ats_score <= 100:
            logger.warning("ATS score out of range: %d, clamping", result.ats_score)
            result.ats_score = max(0, min(100, result.ats_score))

        # If final_resume is empty, use the input resume text
        if not result.final_resume.strip():
            logger.warning("final_resume is empty, using input resume text")
            result.final_resume = _extract_resume_text(resume_json)

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
    Handles responses wrapped in markdown fences.
    """
    return parse_json_response(raw)


def _extract_resume_text(resume_json: str) -> str:
    """Extract a plain-text resume from the serialized JSON."""
    try:
        data: dict[str, Any] = json.loads(resume_json)
    except json.JSONDecodeError, TypeError:
        return resume_json

    parts: list[str] = []

    summary = data.get("summary", "")
    if summary:
        parts.append(str(summary))

    skills = data.get("skills", [])
    if skills:
        parts.append("Skills: " + ", ".join(str(s) for s in skills))

    for exp in data.get("experience", []):
        if isinstance(exp, dict):
            title = str(exp.get("title", ""))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            company = str(exp.get("company", ""))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            dates = str(exp.get("dates", ""))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            header = title
            if company:
                header += f" at {company}"
            if dates:
                header += f" ({dates})"
            parts.append(header)
            for resp in exp.get("responsibilities", []):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                parts.append(f"  - {resp}")
        elif isinstance(exp, str):
            parts.append(exp)

    certs = data.get("certifications", [])
    if certs:
        parts.append("Certifications: " + ", ".join(str(c) for c in certs))

    edu = data.get("education", [])
    if edu:
        parts.append("Education: " + ", ".join(str(e) for e in edu))

    return "\n".join(parts)


def _default_result(rewritten: Any) -> ATSComplianceOutput:
    """Return a default low-score result with the resume text unchanged."""
    resume_text = _extract_resume_text(_serialize(rewritten))
    return ATSComplianceOutput(
        ats_score=30,
        missing_keywords=[],
        formatting_issues=["Unable to evaluate -- LLM unavailable"],
        clarity_issues=[],
        recommended_fixes=["Retry with LLM for proper ATS evaluation"],
        auto_fixes_applied=[],
        final_resume=resume_text,
    )
