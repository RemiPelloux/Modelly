"""Replay a recorded response cache for every client built inside a block.

``modelly verify`` reruns a study whose model builds its own :class:`Client`, often
with a real provider and an empty cache. Inside ``with replaying(path):`` every
client created takes the cache exported to ``path`` instead, in read-only mode: a
recorded call is answered from it, an unrecorded one raises ``CacheMiss``, and no
call ever reaches the network.

Example:
    >>> from modelly.llm import Client, FakeProvider, ResponseCache
    >>> recorded = Client(FakeProvider(lambda request: "yes"))
    >>> _ = recorded.complete("Vote?")
    >>> path = recorded.cache.export("replies.jsonl")
    >>> with replaying(path):
    ...     replay = Client(FakeProvider(lambda request: "no"))
    >>> replay.complete("Vote?").text, replay.usage.calls
    ('yes', 0)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from modelly.llm.cache import READ_ONLY, ResponseCache

_ACTIVE: ContextVar[ResponseCache | None] = ContextVar(
    "modelly_llm_replay", default=None
)


def active_replay() -> ResponseCache | None:
    """The cache every new client replays from, or None outside ``replaying``."""
    return _ACTIVE.get()


@contextmanager
def replaying(path: str | Path) -> Iterator[ResponseCache]:
    """Make every client created in the block answer only from the file at ``path``.

    The file (JSON lines or SQLite, as ``ResponseCache.export`` writes it) is read
    into memory and never written.
    """
    cache = ResponseCache.from_file(path, mode=READ_ONLY)
    token = _ACTIVE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE.reset(token)
