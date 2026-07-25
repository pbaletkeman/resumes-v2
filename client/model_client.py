"""
model_client.py
Abstract base class defining the interface for LLM model clients.

Provides a unified API for sending structured prompts to different
model providers (Ollama, OpenAI, etc.) and receiving responses.
"""

from typing import Any


class ModelClient:
    """Abstract base class for LLM model clients.

    Subclasses must implement the ``chat`` method to send a structured
    prompt to their specific model provider and return the response.

    Attributes:
        purpose: The system-level role or persona for the model.
        job_description: The raw job description text being processed.
        resume: The raw resume text being processed.
        parsed_job_description: Structured representation of the job description.
        parsed_resume: Structured representation of the resume.
        tailoring_strategy: Strategy for aligning the resume with the job.
        rewritten_resume: The resume after being rewritten by the rewrite agent.
        ats_optimized_resume: The resume after ATS compliance adjustments.
    """

    def __init__(
        self,
        purpose: str = "",
        job_description: str = "",
        resume: str = "",
        parsed_job_description: str = "",
        parsed_resume: str = "",
        tailoring_strategy: str = "",
        rewritten_resume: str = "",
        ats_optimized_resume: str = "",
    ) -> None:
        """Initialize the ModelClient with pipeline state fields.

        Args:
            purpose: System-level role or persona for the model.
            job_description: Raw job description text.
            resume: Raw resume text.
            parsed_job_description: Structured job description data.
            parsed_resume: Structured resume data.
            tailoring_strategy: Resume tailoring strategy.
            rewritten_resume: Rewritten resume text.
            ats_optimized_resume: ATS-optimized resume text.
        """
        self._purpose = purpose
        self._job_description = job_description
        self._resume = resume
        self._parsed_job_description = parsed_job_description
        self._parsed_resume = parsed_resume
        self._tailoring_strategy = tailoring_strategy
        self._rewritten_resume = rewritten_resume
        self._ats_optimized_resume = ats_optimized_resume

    async def chat(
        self,
        purpose: str,
        prompt: str,
        output: list[str],
        rules: list[str],
        inputs: list[str],
    ) -> str:
        """Send a structured prompt to the model and return the response.

        Args:
            purpose: System-level role or persona for this specific call.
            prompt: The user-facing task or question.
            output: Expected output field names or labels.
            rules: Constraints or guidelines the model must follow.
            inputs: Additional context or raw data to include.

        Returns:
            The model's text response.

        Raises:
            NotImplementedError: Always; must be overridden by subclasses.
        """
        raise NotImplementedError

    @property
    def purpose(self) -> str:
        """Get the current purpose."""
        return self._purpose

    @purpose.setter
    def purpose(self, value: str) -> None:
        """Set the purpose.

        Args:
            value: New purpose value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("purpose cannot be empty")
        self._purpose = value

    @property
    def job_description(self) -> str:
        """Get the current job description."""
        return self._job_description

    @job_description.setter
    def job_description(self, value: str) -> None:
        """Set the job description.

        Args:
            value: New job description value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("Description cannot be empty")
        self._job_description = value

    @property
    def resume(self) -> str:
        """Get the current resume."""
        return self._resume

    @resume.setter
    def resume(self, value: str) -> None:
        """Set the resume.

        Args:
            value: New resume value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("Resume cannot be empty")
        self._resume = value

    @property
    def parsed_job_description(self) -> str:
        """Get the parsed job description."""
        return self._parsed_job_description

    @parsed_job_description.setter
    def parsed_job_description(self, value: str) -> None:
        """Set the parsed job description.

        Args:
            value: New parsed job description value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("parsed_job_description cannot be empty")
        self._parsed_job_description = value

    @property
    def parsed_resume(self) -> str:
        """Get the parsed resume."""
        return self._parsed_resume

    @parsed_resume.setter
    def parsed_resume(self, value: str) -> None:
        """Set the parsed resume.

        Args:
            value: New parsed resume value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("parsed_resume cannot be empty")
        self._parsed_resume = value

    @property
    def tailoring_strategy(self) -> str:
        """Get the tailoring strategy."""
        return self._tailoring_strategy

    @tailoring_strategy.setter
    def tailoring_strategy(self, value: str) -> None:
        """Set the tailoring strategy.

        Args:
            value: New tailoring strategy value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("tailoring_strategy cannot be empty")
        self._tailoring_strategy = value

    @property
    def rewritten_resume(self) -> str:
        """Get the rewritten resume."""
        return self._rewritten_resume

    @rewritten_resume.setter
    def rewritten_resume(self, value: str) -> None:
        """Set the rewritten resume.

        Args:
            value: New rewritten resume value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("rewritten_resume cannot be empty")
        self._rewritten_resume = value

    @property
    def ats_optimized_resume(self) -> str:
        """Get the ATS-optimized resume."""
        return self._ats_optimized_resume

    @ats_optimized_resume.setter
    def ats_optimized_resume(self, value: str) -> None:
        """Set the ATS-optimized resume.

        Args:
            value: New ATS-optimized resume value.

        Raises:
            ValueError: If value is empty.
        """
        if not value:
            raise ValueError("ats_optimized_resume cannot be empty")
        self._ats_optimized_resume = value
