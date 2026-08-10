"""
tone_polishing.py
Tone Polishing Agent.

LLM-only agent: improves the tone and professionalism of the
ATS-optimized resume without changing facts.  There is no regex fallback
-- tone rewriting requires LLM reasoning.

Output model: ``TonePolishingOutput``.  On total LLM failure (both
attempts fail) the deterministic fallback returns the input resume
unchanged, so the pipeline never loses the ATS-optimized text.

The LLM call, JSON parsing, and Pydantic validation scaffolding is shared
with the other LLM-only agents via ``client.agents._validation``.
The empty-output fill used for ``polished_resume`` is agent-specific and
stays here.
"""

import logging
from typing import Any

from client.agents._validation import chat_and_validate
from client.json_utils import model_to_json_schema
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
            A validated ``TonePolishingOutput``.  On total LLM failure
            the input resume text is returned unchanged.
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

        result = await chat_and_validate(
            self.client,
            purpose=_SYSTEM_PROMPT,
            prompt=prompt,
            rules=rules,
            inputs=[resume_text],
            json_schema=model_to_json_schema(TonePolishingOutput),
            output_model=TonePolishingOutput,
            agent_label="tone polishing",
            strict=strict,
        )
        if result is None:
            return None

        # Post-validation: if polished_resume is empty, use the input
        if not result.polished_resume.strip():
            logger.warning("polished_resume is empty, using input resume text")
            result.polished_resume = resume_text

        return result
