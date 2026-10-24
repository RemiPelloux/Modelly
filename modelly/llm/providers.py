"""Adapters from a :class:`Request` to a provider's HTTP API and back.

An adapter knows one wire format. The API key is read from the argument or, when that
is None, from the environment at call time. It is never pickled, printed or stored in
the cache: a checkpoint of a model holding a provider has no key in it, and a loaded
model reads the key from the environment again.
"""

from __future__ import annotations

import os
from typing import Any

from modelly.llm.errors import ProviderError
from modelly.llm.request import Request, Response
from modelly.llm.transport import DEFAULT_TIMEOUT, post_json

ANTHROPIC_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MODEL = "claude-sonnet-5-5"
OPENAI_URL = "https://api.openai.com/v1"


class Provider:
    """The interface of every adapter: a ``name`` and :meth:`complete`.

    Subclasses set ``name`` (part of every cache key), ``default_model`` and
    ``key_variable``, the environment variable holding the API key.
    """

    name = "provider"
    default_model: str | None = None
    key_variable: str | None = None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Keep the endpoint; the key stays in memory only."""
        self._api_key = api_key
        self.base_url = (base_url or self.default_url()).rstrip("/")
        self.timeout = timeout

    @staticmethod
    def default_url() -> str:
        """The endpoint used when ``base_url`` is None."""
        return ""

    def api_key(self, required: bool = True) -> str | None:
        """The explicit key, else the environment's; raise when one is required."""
        key = self._api_key or (
            os.environ.get(self.key_variable) if self.key_variable else None
        )
        if required and not key:
            raise ProviderError(
                f"{type(self).__name__} needs an API key: set {self.key_variable} "
                "or pass api_key=...",
                retryable=False,
            )
        return key

    def complete(self, request: Request) -> Response:
        """Send ``request`` and return the reply."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """The class and endpoint, never the key."""
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def __getstate__(self) -> dict[str, Any]:
        """Everything but the key."""
        return {k: v for k, v in vars(self).items() if k != "_api_key"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the fields; the key comes from the environment from now on."""
        vars(self).update(state)
        self._api_key = None


class AnthropicProvider(Provider):
    """The Anthropic Messages API (``POST /v1/messages``); key from ``ANTHROPIC_API_KEY``.

    Example:
        >>> AnthropicProvider(api_key="sk-...")
        AnthropicProvider(base_url='https://api.anthropic.com')
    """

    name = "anthropic"
    default_model = ANTHROPIC_MODEL
    key_variable = "ANTHROPIC_API_KEY"

    @staticmethod
    def default_url() -> str:  # noqa: D102
        return ANTHROPIC_URL

    def complete(self, request: Request) -> Response:
        """Call the Messages API and join the text blocks of the reply."""
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            **dict(request.params),
        }
        if request.system:
            payload["system"] = request.system
        headers = {
            "x-api-key": self.api_key() or "",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        reply = post_json(
            f"{self.base_url}/v1/messages", payload, headers, self.timeout
        )
        blocks = reply.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = reply.get("usage") or {}
        return Response(
            text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        )


class OpenAICompatibleProvider(Provider):
    """Any ``POST /chat/completions`` endpoint: OpenAI, or a local Ollama or llama.cpp.

    The key comes from ``OPENAI_API_KEY`` and is optional, since local servers need
    none. ``name`` is part of the cache key: give each endpoint its own when they
    serve different models under one name.

    Example:
        >>> OpenAICompatibleProvider(base_url="http://127.0.0.1:11434/v1", name="ollama")
        OpenAICompatibleProvider(base_url='http://127.0.0.1:11434/v1')
    """

    name = "openai"
    key_variable = "OPENAI_API_KEY"

    def __init__(self, *, name: str | None = None, **options: Any) -> None:
        """Set the endpoint, and a ``name`` for its cache keys."""
        super().__init__(**options)
        if name:
            self.name = name

    @staticmethod
    def default_url() -> str:  # noqa: D102
        return OPENAI_URL

    def complete(self, request: Request) -> Response:
        """Call chat completions; the system prompt is the first message."""
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if request.system:
            messages.insert(0, {"role": "system", "content": request.system})
        payload = {"model": request.model, "messages": messages, **dict(request.params)}
        key = self.api_key(required=False)
        headers = {"authorization": f"Bearer {key}"} if key else {}
        url = f"{self.base_url}/chat/completions"
        reply = post_json(url, payload, headers, self.timeout)
        choices = reply.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = reply.get("usage") or {}
        return Response(
            text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        )
