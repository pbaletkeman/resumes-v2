"""
tone_polishing.py
Tone Polishing Agent.

Improves the tone and professionalism of the ATS-optimized resume
without changing facts.  Uses an LLM to produce a ``TonePolishingOutput``.
Falls back to returning the input unchanged on LLM failure.
"""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from client.errors import LLMConnectionError, LLMResponseError, LLMTimeoutError
from client.model_client import ModelClient
from client.models import TonePolishingOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Tone Polishing Agent. "
    "Improve the tone of the resume while preserving meaning. "
    "Apply: "
    "Professional tone, "
    "Confident phrasing, "
    "Clear narrative flow, "
    "Role-appropriate voice (technical, managerial, creative). "
    "Output the polished resume. "
    "Rules: "
    "Do not change factual content. "
    "Do not add new achievements. "
    "Improve readability and cohesion. "
    "Output only valid JSON."
)

_STRICT_RULES = [
    "Output only valid JSON",
    "polished_resume must contain the full polished resume text",
    "No markdown, no explanation -- just the JSON object",
]

_SCHEMA_HINT = (
    "Output a JSON object with a single key: "
    "polished_resume (string with the full polished resume text)."
)


class TonePolishingAgent:
    """Agent that improves resume tone and professionalism.

    Tries LLM extraction first with one retry on failure.  On second
    failure, returns the input resume unchanged.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    async def run(self, inputs: dict[str, Any]) -> TonePolishingOutput:
        """Improve the tone of the ATS-optimized resume.

        Args:
            inputs: Must contain ``"ats_optimized_resume"`` (string
                with the full resume text).

        Returns:
            A validated ``TonePolishingOutput``.
        """
        resume_text = inputs.get("ats_optimized_resume", "")

        if not resume_text:
            logger.debug("Tone polishing: empty input, returning defaults")
            return TonePolishingOutput(polished_resume="")

        logger.debug("Tone polishing: resume_len=%d", len(resume_text))

        # Attempt LLM extraction (with one retry)
        for attempt in range(2):
            result = await self._try_llm(resume_text, strict=(attempt == 1))
            if result is not None:
                return result

        # Fallback: return the input resume unchanged
        logger.warning(
            "LLM tone polishing failed on both attempts, "
            "returning input resume unchanged"
        )
        return TonePolishingOutput(polished_resume=resume_text)

    async def _try_llm(
        self,
        resume_text: str,
        *,
        strict: bool = False,
    ) -> TonePolishingOutput | None:
        """Attempt LLM tone polishing and validation.

        Args:
            resume_text: The full ATS-optimized resume text.
            strict: If True, use stricter rules (retry mode).

        Returns:
            A validated ``TonePolishingOutput``, or ``None`` on failure.
        """
        prompt = (
            "Polish the tone and professionalism of the following resume. "
            "Improve readability, confidence, and clarity without changing "
            "factual content or adding new achievements.\n\n"
            f"RESUME:\n{resume_text}"
        )
        rules = (
            _STRICT_RULES + [_SCHEMA_HINT]
            if strict
            else [
                "Output only valid JSON",
                "polished_resume must contain the full polished resume text",
            ]
        )

        logger.debug(
            "LLM tone attempt=%s prompt_len=%d",
            "strict" if strict else "normal",
            len(prompt),
        )

        try:
            raw = await self.client.chat(
                purpose=_SYSTEM_PROMPT,
                prompt=prompt,
                output=["json"],
                rules=rules,
                inputs=[resume_text],
            )
        except (
            NotImplementedError,
            LLMConnectionError,
            LLMResponseError,
            LLMTimeoutError,
        ):
            logger.exception(
                "LLM tone polishing failed (attempt %s)",
                "strict" if strict else "normal",
            )
            return None

        logger.debug(
            "LLM tone response: %s", raw[:200] if raw else "<empty>"
        )
        data = _parse_json(raw)
        if data is None:
            return None

        try:
            result = TonePolishingOutput(**data)
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

        # If polished_resume is empty, use the input
        if not result.polished_resume.strip():
            logger.warning("polished_resume is empty, using input resume text")
            result.polished_resume = resume_text

        return result


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
