"""Shared retry scaffolding for the parsing agents.

Parsing agents (JD Parsing, Resume Parsing) follow the same strategy:
attempt LLM extraction once, retry once with stricter rules if the first
attempt failed, and only then fall back to the deterministic regex path.

This module holds only the loop.  Each agent keeps its own
``_try_llm`` / ``_regex_fallback`` implementations; the helper just
orchestrates the order and the retry so every parsing agent reads the
same way.
"""

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def retry_llm_then_fallback[T](
    try_llm: Callable[[bool], Awaitable[T | None]],
    fallback: Callable[[], Awaitable[T]],
    *,
    agent_name: str,
) -> T:
    """Attempt LLM extraction twice (normal, then strict) before a fallback.

    ``try_llm`` is invoked with ``True`` (strict mode) on the retry and
    returns ``None`` to signal a failed attempt.  ``fallback`` runs only
    after both attempts fail.

    Args:
        try_llm: Async callable taking ``strict: bool`` and returning the
            parsed result or ``None`` when the LLM attempt failed.
        fallback: Async callable producing the deterministic fallback
            result.
        agent_name: Agent name used in log messages.

    Returns:
        The first successful LLM result, or the fallback result.
    """
    for attempt in range(2):
        result = await try_llm(attempt == 1)
        if result is not None:
            return result
    logger.info("%s: LLM parsing failed, falling back to regex", agent_name)
    return await fallback()
