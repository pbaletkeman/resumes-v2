"""
gap_analysis.py
Gap Analysis Agent.

Compares parsed JD vs parsed resume, produces a tailoring strategy.
Uses an LLM to compare structured inputs and output a
``GapAnalysisOutput``.  No regex fallback -- gap analysis requires
LLM reasoning.
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.json_utils import model_to_json_schema, parse_json_response
from client.model_client import ModelClient
from client.models import GapAnalysisOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Gap Analysis Agent. "
    "Using the parsed job description and parsed resume, produce a "
    "Tailoring Strategy with the following fields: "
    "missing_skills, weak_skills, strong_matches, "
    "recommended_emphasis, keyword_strategy, "
    "bullet_point_improvement_plan, tone_guidance. "
    "Rules: "
    "Base all analysis strictly on provided data. "
    "Identify the most impactful resume improvements. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "Base all analysis strictly on provided data",
    "No markdown, no explanation -- just the JSON object",
]


class GapAnalysisAgent:
    """Agent that compares parsed JD and resume to produce a tailoring strategy.

    Tries LLM extraction first with one retry on failure.  No regex fallback
    because gap analysis requires LLM reasoning.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> GapAnalysisOutput:
        """Compare parsed JD and resume to produce a tailoring strategy.

        Args:
            inputs: Must contain ``"parsed_job_description"`` (``JDParsingOutput``
                or serializable dict) and ``"parsed_resume"`` (``ResumeParsingOutput``
                or serializable dict).

        Returns:
            A validated ``GapAnalysisOutput``.
        """
        jd = inputs.get("parsed_job_description", {})
        resume = inputs.get("parsed_resume", {})

        if not jd or not resume:
            logger.debug("Gap analysis: empty input, returning defaults")
            return GapAnalysisOutput()

        jd_json = _serialize(jd)
        resume_json = _serialize(resume)

        logger.debug(
            "Gap analysis: jd_len=%d resume_len=%d",
            len(jd_json),
            len(resume_json),
        )

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(jd_json, resume_json, strict=(attempt == 1))
            if result is not None:
                return result

        logger.error("Gap analysis: LLM failed on both attempts")
        return GapAnalysisOutput()

    async def _try_llm(
        self,
        jd_json: str,
        resume_json: str,
        *,
        strict: bool = False,
    ) -> GapAnalysisOutput | None:
        """Attempt LLM extraction and validation.

        Args:
            jd_json: Serialized JD data.
            resume_json: Serialized resume data.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``GapAnalysisOutput``, or ``None`` on failure.
        """
        prompt = (
            "Compare the following parsed job description and parsed resume. "
            "Identify gaps and produce a tailoring strategy.\n\n"
            f"JOB DESCRIPTION:\n{jd_json}\n\n"
            f"RESUME:\n{resume_json}"
        )
        rules = (
            _STRICT_RULES
            if strict
            else [
                "Output only valid JSON",
                "Base all analysis strictly on provided data",
            ]
        )

        logger.debug(
            "LLM gap analysis attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[jd_json, resume_json],
                response_format="json",
                json_schema=model_to_json_schema(GapAnalysisOutput),
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM gap analysis failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug("LLM gap analysis response: %s", raw[:200] if raw else "<empty>")
        data = _parse_json(raw)
        if data is None:
            return None

        try:
            return GapAnalysisOutput(**data)
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
