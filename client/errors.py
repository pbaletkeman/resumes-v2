"""
errors.py
Custom exceptions for LLM client operations.

These are the only error types that ``ModelClient`` implementations are
allowed to raise.  Agent code (``client/agents/*.py`` and
``client/format_detector.py``) catches ``LLMConnectionError``,
``LLMResponseError`` and ``LLMTimeoutError`` inside ``_try_llm()`` and
falls back to a deterministic result when any of them is raised, so the
pipeline keeps working even when the LLM provider is down, misbehaving
or slow.

Providers map their SDK exceptions onto these types:

- ``ollama.RequestError``      -> ``LLMConnectionError``
- ``ollama.ResponseError``     -> ``LLMResponseError``
- ``asyncio.TimeoutError``     -> ``LLMTimeoutError``
- ``openai.APIConnectionError`` -> ``LLMConnectionError``
- ``openai.AuthenticationError`` / ``RateLimitError`` / ``APIError``
                               -> ``LLMResponseError``
"""


class LLMError(Exception):
    """Base exception for every LLM client failure.

    Never raised directly; use one of the concrete subclasses so callers
    can distinguish connection, response and timeout failures.
    """


class LLMConnectionError(LLMError):
    """Raised when the LLM server cannot be reached.

    Examples: Ollama is not running on ``localhost:11434``, or the
    OpenAI API is unreachable.  The original SDK exception is chained
    via ``raise ... from e`` so the root cause stays debuggable.
    """


class LLMResponseError(LLMError):
    """Raised when the LLM returns an error or unusable response.

    Covers provider-reported errors (bad API key, rate limit, server
    error) and empty model output (``response.message.content is None``).
    """


class LLMTimeoutError(LLMError):
    """Raised when the LLM request does not finish within the timeout.

    The timeout is provider-specific: Ollama uses ``OllamaClient.timeout``
    (default 300 s) and OpenAI uses a fixed 90 s timeout.
    """
