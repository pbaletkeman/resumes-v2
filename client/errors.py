"""
errors.py
Custom exceptions for LLM client operations.
"""


class LLMError(Exception):
    """Base exception for all LLM-related errors."""


class LLMConnectionError(LLMError):
    """Raised when the LLM server cannot be reached."""


class LLMResponseError(LLMError):
    """Raised when the LLM returns an error response."""


class LLMTimeoutError(LLMError):
    """Raised when the LLM request times out."""
