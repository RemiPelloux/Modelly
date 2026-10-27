"""One call to a language model and its reply, and the cache key that names the call."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

USER = "user"
ASSISTANT = "assistant"
ROLES = frozenset({USER, ASSISTANT})
# Version of the key recipe: bump it and every old cache entry stops matching.
KEY_VERSION = 1
# How much of a prompt an error message quotes.
EXCERPT = 60


@dataclass(frozen=True)
class Message:
    """One turn of a conversation: who spoke (``"user"`` or ``"assistant"``) and what."""

    role: str
    content: str

    def __post_init__(self) -> None:
        """Refuse a role the providers do not share; the system prompt is separate."""
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {sorted(ROLES)}, got {self.role!r}")


@dataclass(frozen=True)
class Request:
    """Everything that decides a reply, and who asked.

    ``scope`` and ``call_index`` say which caller made the call and how many it
    made before: an agent's id and its own call counter. They are part of the
    cache key, so two agents asking the same question get their own replies, and
    the key of a call does not depend on which thread sent it.

    Example:
        >>> r = Request("fake", "m", (Message("user", "Hi"),), scope="a1", call_index=0)
        >>> len(r.key())
        64
    """

    provider: str
    model: str
    messages: tuple[Message, ...]
    system: str = ""
    params: tuple[tuple[str, Any], ...] = ()
    scope: str = "model"
    call_index: int = 0
    seed: int | None = None
    schema: dict[str, Any] | None = field(default=None, compare=False, hash=False)

    @property
    def max_tokens(self) -> int | None:
        """The ``max_tokens`` parameter, the most the reply may use."""
        return dict(self.params).get("max_tokens")

    def identity(self) -> dict[str, Any]:
        """The fields the cache key hashes, as plain JSON values."""
        return {
            "v": KEY_VERSION,
            "provider": self.provider,
            "model": self.model,
            "system": self.system,
            "messages": [[m.role, m.content] for m in self.messages],
            "params": sorted([k, v] for k, v in self.params),
            "scope": self.scope,
            "call": self.call_index,
            "seed": self.seed,
        }

    def key(self) -> str:
        """SHA-256 of the canonical JSON of :meth:`identity`: the cache key."""
        text = json.dumps(self.identity(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def prompt_chars(self) -> int:
        """Characters in the system prompt and every message."""
        return len(self.system) + sum(len(m.content) for m in self.messages)

    def excerpt(self) -> str:
        """The start of the last message, for error messages."""
        text = self.messages[-1].content if self.messages else ""
        return text[:EXCERPT]

    def follow_up(self, reply: str, prompt: str, call_index: int) -> Request:
        """This conversation, the model's ``reply``, then a new user ``prompt``."""
        messages = (*self.messages, Message(ASSISTANT, reply), Message(USER, prompt))
        return Request(
            self.provider,
            self.model,
            messages,
            self.system,
            self.params,
            self.scope,
            call_index,
            self.seed,
            self.schema,
        )


@dataclass(frozen=True)
class Response:
    """A reply: its text, the tokens it used, and whether it came from the cache."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    key: str = ""

    @property
    def tokens(self) -> int:
        """Input plus output tokens."""
        return self.input_tokens + self.output_tokens


def freeze_params(params: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Sorted ``(name, value)`` pairs, dropping None values, so requests hash and compare."""
    return tuple(sorted((k, v) for k, v in params.items() if v is not None))
