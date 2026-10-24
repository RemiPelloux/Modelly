"""A provider that answers from a Python function: for tests, teaching and dry runs.

It never opens a connection. Its replies depend only on the request, so a run with it
is as reproducible as the function it calls, and it counts what it was asked so a test
can check that a replay made no call at all.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Iterable
from typing import Any

from modelly.llm.budget import CHARS_PER_TOKEN
from modelly.llm.errors import ProviderError
from modelly.llm.providers import Provider
from modelly.llm.request import Request, Response

FAKE_MODEL = "fake"
# Characters of the key the default reply quotes.
ECHO_CHARS = 12


def echo(request: Request) -> str:
    """The default reply: names the call, so two calls never get the same text."""
    return f"fake reply {request.key()[:ECHO_CHARS]}"


class FakeProvider(Provider):
    """Replies come from ``responder(request) -> str``; tokens are counted from length.

    Args:
        responder: A module-level function (so a model holding it can be saved).
        failures: HTTP statuses to raise, one per call, before answering normally:
            ``failures=[429, 503]`` fails twice, then replies.

    Example:
        >>> from modelly.llm import Client
        >>> client = Client(FakeProvider(lambda request: "yes"))
        >>> client.complete("Agree?").text
        'yes'
    """

    name = "fake"
    default_model = FAKE_MODEL

    def __init__(
        self,
        responder: Callable[[Request], str] = echo,
        failures: Iterable[int] = (),
    ) -> None:
        """Keep the responder and the failures to play back."""
        super().__init__(base_url="fake://")
        self.responder = responder
        self.failures = list(failures)
        self.calls = 0
        self.requests: list[Request] = []
        self._lock = threading.Lock()

    def complete(self, request: Request) -> Response:
        """Fail with the next queued status, if any; otherwise call the responder."""
        with self._lock:
            self.calls += 1
            self.requests.append(request)
            status = self.failures.pop(0) if self.failures else None
        if status is not None:
            raise ProviderError(f"fake failure {status}", status=status)
        text = self.responder(request)
        tokens_in = math.ceil(request.prompt_chars() / CHARS_PER_TOKEN)
        tokens_out = math.ceil(len(text) / CHARS_PER_TOKEN)
        return Response(text, tokens_in, tokens_out)

    def __getstate__(self) -> dict[str, Any]:
        """Everything but the lock and the request log."""
        state = super().__getstate__()
        return {k: v for k, v in state.items() if k not in {"_lock", "requests"}}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the fields, an empty log and a fresh lock."""
        super().__setstate__(state)
        self.requests = []
        self._lock = threading.Lock()
