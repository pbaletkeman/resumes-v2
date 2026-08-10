"""
ats_compliance.py
ATS Compliance Agent.

LLM-only agent: evaluates a rewritten resume for ATS compatibility and
fixes issues.  There is no regex fallback -- ATS evaluation requires LLM
reasoning.

Output model: ``ATSComplianceOutput``.  On total LLM failure (both
attempts fail) the deterministic fallback is a default low-score result
(``ats_score=30``) with the input resume text unchanged, so the pipeline
still yields a usable resume.

The LLM call, JSON parsing, and Pydantic validation scaffolding is shared
with the other LLM-only agents via ``client.agents._validation``.
"""

import logging
from typing import Any

from client.agents._validation import chat_and_validate, serialize
from client.json_utils import load_json_safe, model_to_json_schema
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

        resume_json = serialize(rewritten)

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

        result = await chat_and_validate(
            self.client,
            purpose=_SYSTEM_PROMPT,
            prompt=prompt,
            rules=rules,
            inputs=[resume_json],
            json_schema=model_to_json_schema(ATSComplianceOutput),
            output_model=ATSComplianceOutput,
            agent_label="ATS compliance",
            strict=strict,
        )
        if result is None:
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


def _extract_resume_text(resume_json: str) -> str:
    """Extract a plain-text resume from the serialized JSON.

    Rebuilds a readable resume from the parsed ``RewriteOutput`` fields:
    summary, skills, experience (title/company/dates/responsibilities),
    certifications, and education.  Returns the raw ``resume_json``
    unchanged when the JSON cannot be parsed.

    Args:
        resume_json: Serialized resume data (from ``serialize``).

    Returns:
        The plain-text resume, or ``resume_json`` when parsing fails.
    """
    data = load_json_safe(resume_json)
    if data is None:
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
    """Return a default low-score result with the resume text unchanged.

    Deterministic fallback used when both LLM attempts fail: scores 30,
    reports that evaluation was impossible, and keeps the input resume as
    ``final_resume`` so the downstream pipeline still has a usable resume.

    Args:
        rewritten: The rewritten resume (``RewriteOutput`` or dict).

    Returns:
        An ``ATSComplianceOutput`` with ``ats_score=30``.
    """
    resume_text = _extract_resume_text(serialize(rewritten))
    return ATSComplianceOutput(
        ats_score=30,
        missing_keywords=[],
        formatting_issues=["Unable to evaluate -- LLM unavailable"],
        clarity_issues=[],
        recommended_fixes=["Retry with LLM for proper ATS evaluation"],
        auto_fixes_applied=[],
        final_resume=resume_text,
    )
