"""
This module defines the ModelClient class, which serves as an abstract base class for model clients.
It provides a common interface for interacting with different model clients, such as OllamaClient and OpenAIClient. The ModelClient class includes an abstract method `chat` that must be implemented by subclasses
"""
class ModelClient:
    """Abstract base class for model clients."""

    async def chat(self, purpose: str, prompt: str, output: list[str], rules: list[str], inputs: list[str]) -> str:
        """Abstract method to be implemented by subclasses for handling chat interactions."""
        raise NotImplementedError


    def __init__(self,
        purpose: str = "",
        job_description: str = "",
        resume: str = "",
        parsed_job_description: str = "",
        parsed_resume: str = "",
        tailoring_strategy: str = "",
        rewritten_resume: str = "",
        ats_optimized_resume: str = "") -> None:

        self._purpose = job_description
        self._job_description = purpose
        self._resume = resume
        self._parsed_job_description = parsed_job_description
        self._parsed_resume = parsed_resume
        self._tailoring_strategy = tailoring_strategy
        self._rewritten_resume = rewritten_resume
        self._ats_optimized_resume = ats_optimized_resume


    @property
    def purpose(self) -> str:
        """The getter method."""
        return self._purpose

    @purpose.setter
    def purpose(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("purpose cannot be empty")
        self._purpose = value


    @property
    def job_description(self) -> str:
        """The getter method."""
        return self._job_description

    @job_description.setter
    def job_description(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("Description cannot be empty")
        self._job_description = value

    @property
    def resume(self) -> str:
        """The getter method."""
        return self._resume

    @resume.setter
    def resume(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("Resume cannot be empty")
        self._resume = value

    @property
    def parsed_job_description(self) -> str:
        """The getter method."""
        return self._parsed_job_description

    @parsed_job_description.setter
    def parsed_job_description(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("parsed_job_description cannot be empty")
        self._parsed_job_description = value

    @property
    def parsed_resume(self) -> str:
        """The getter method."""
        return self._parsed_resume

    @parsed_resume.setter
    def parsed_resume(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("parsed_resume cannot be empty")
        self._parsed_resume = value

    @property
    def tailoring_strategy(self) -> str:
        """The getter method."""
        return self._tailoring_strategy

    @tailoring_strategy.setter
    def tailoring_strategy(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("tailoring_strategy cannot be empty")
        self._tailoring_strategy = value

    @property
    def rewritten_resume(self) -> str:
        """The getter method."""
        return self._rewritten_resume

    @rewritten_resume.setter
    def rewritten_resume(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("rewritten_resume cannot be empty")
        self._rewritten_resume = value

    @property
    def ats_optimized_resume(self) -> str:
        """The getter method."""
        return self._ats_optimized_resume

    @ats_optimized_resume.setter
    def ats_optimized_resume(self, value: str) -> None:
        """The setter method for validation or processing."""
        if not value:
            raise ValueError("ats_optimized_resume cannot be empty")
        self._ats_optimized_resume = value
