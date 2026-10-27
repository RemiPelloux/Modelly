"""Retries with exponential backoff for rate limits, server errors and lost connections.

The wait is deterministic (no jitter) and goes through an injectable ``sleeper``, so a
test can check the delays without sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from modelly.llm.errors import ProviderError
from modelly.llm.request import Request, Response

DEFAULT_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
BACKOFF_FACTOR = 2


@dataclass
class RetryPolicy:
    """How many times to retry a failed call and how long to wait in between.

    Args:
        max_retries: Extra tries after the first; 0 never retries.
        base_delay: Seconds before the first retry; doubled each time after.
        max_delay: The longest wait, also capping a server's ``Retry-After``.
        sleeper: Called with the seconds to wait; ``time.sleep`` by default.

    Example:
        >>> RetryPolicy(base_delay=1.0).delay(2, None)
        4.0
    """

    max_retries: int = DEFAULT_RETRIES
    base_delay: float = DEFAULT_BASE_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    sleeper: Callable[[float], None] = field(default=time.sleep, repr=False)

    def delay(self, attempt: int, retry_after: float | None) -> float:
        """Seconds to wait before retry number ``attempt`` (counting from 0)."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)
        delay: float = min(self.base_delay * BACKOFF_FACTOR**attempt, self.max_delay)
        return delay

    def run(
        self, send: Callable[[Request], Response], request: Request
    ) -> tuple[Response, int]:
        """``send(request)``, retried on a retryable error; return the reply and the retries."""
        attempt = 0
        while True:
            try:
                return send(request), attempt
            except ProviderError as error:
                if not error.retryable or attempt >= self.max_retries:
                    raise
                self.sleeper(self.delay(attempt, error.retry_after))
                attempt += 1

    def __getstate__(self) -> dict[str, Any]:
        """The numbers; a custom sleeper is replaced by ``time.sleep`` on load."""
        return {k: v for k, v in vars(self).items() if k != "sleeper"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the numbers with ``time.sleep``."""
        vars(self).update(state)
        self.sleeper = time.sleep
