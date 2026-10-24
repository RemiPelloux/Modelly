"""The exceptions of ``modelly.llm``: every one is an :class:`LLMError`."""

from __future__ import annotations

# HTTP statuses worth another try: rate limited, or the server failed.
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
# How much of a key or a reply an error message shows.
KEY_EXCERPT = 16
REPLY_EXCERPT = 200


class LLMError(Exception):
    """Base class of every error raised by ``modelly.llm``."""


class ProviderError(LLMError):
    """A provider refused or failed a call.

    Attributes:
        status: The HTTP status, or None when no response came back.
        retryable: Whether the same call may succeed later (429, 5xx, a lost connection).
        retry_after: Seconds the server asked to wait, when it said so.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        retryable: bool | None = None,
    ) -> None:
        """Record the status and whether another try may succeed (from it, by default)."""
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        if retryable is None:
            retryable = status is None or is_retryable(status)
        self.retryable = retryable


def is_retryable(status: int) -> bool:
    """Whether an HTTP ``status`` says to try again: 429 or any 5xx."""
    return status == TOO_MANY_REQUESTS or status >= SERVER_ERROR


class CacheMiss(LLMError):  # noqa: N818 - names what happened
    """A replay (``mode="read-only"``) asked for a response the cache does not hold.

    Attributes:
        scope: Who made the call (an agent's id, or the scope passed to the client).
        call_index: The caller's call counter for this call.
        key: The cache key that was looked up.
    """

    def __init__(self, scope: str, call_index: int, key: str, excerpt: str) -> None:
        """Name the call, so the user can see which prompt was never recorded."""
        super().__init__(
            f"Replay cache has no response for call {call_index} of {scope!r} "
            f"(key {key[:KEY_EXCERPT]}..., prompt {excerpt!r}). The run being replayed made "
            "different calls: check the seed, the prompts and the parameters, or "
            'record the cache again with mode="read-write".'
        )
        self.scope = scope
        self.call_index = call_index
        self.key = key


class BudgetExceeded(LLMError):  # noqa: N818 - names what happened
    """The next call could take the run past its token or cost budget.

    Raised before that call is sent, so the money is never spent. Responses
    already received in the same batch are cached and counted first.
    """


class SchemaError(ValueError):
    """A value does not match a schema; ``path`` points at the first mismatch."""

    def __init__(self, path: str, problem: str) -> None:
        """Say where the value breaks the schema and how."""
        super().__init__(f"{path}: {problem}")
        self.path = path
        self.problem = problem


class DecisionError(LLMError):
    """A model reply stayed invalid after every repair attempt.

    Attributes:
        scope: Who asked.
        reply: The last reply received.
    """

    def __init__(self, scope: str, reply: str, reason: str) -> None:
        """Keep the reply so the prompt or the schema can be fixed."""
        super().__init__(
            f"{scope!r} got no valid decision: {reason}. Last reply: {reply[:REPLY_EXCERPT]!r}"
        )
        self.scope = scope
        self.reply = reply
