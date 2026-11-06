"""The client every language-model call of a model goes through.

It builds requests, serves them from the cache when it can, holds each new call
against the budget, sends the rest concurrently with retries, and returns the replies
in the order they were asked for, whatever order the threads finish in.
"""

from __future__ import annotations

import sys
import weakref
from collections.abc import Iterable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import replace
from typing import Any

from modelly.llm.budget import Budget, Usage
from modelly.llm.cache import READ_ONLY, ResponseCache
from modelly.llm.errors import BudgetExceeded, CacheMiss, ProviderError
from modelly.llm.providers import Provider
from modelly.llm.replay import active_replay
from modelly.llm.request import USER, Message, Request, Response, freeze_params
from modelly.llm.retry import RetryPolicy

DEFAULT_CONCURRENCY = 4
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.0
MODEL_SCOPE = "model"
# Pyodide (sys.platform "emscripten") cannot start threads: calls go one at a time.
THREADS = sys.platform != "emscripten"
# The attribute holding the thread pool and its size (left out of pickles).
POOL_SLOT = "_pool"

Prompt = str | Sequence[Message]


class Client:
    """Language-model calls with a cache, a budget, retries and a concurrency limit.

    Args:
        provider: The adapter: ``AnthropicProvider``, ``OpenAICompatibleProvider`` or
            ``FakeProvider``.
        model: The model name; the provider's default when None.
        cache: Where replies are kept; a fresh in-memory cache when None. Inside
            ``modelly.llm.replay.replaying``, the replayed cache instead.
        budget: Token and cost limits; no limit when None.
        retry: How failed calls are retried.
        max_concurrency: The most calls in flight at once.
        system: The system prompt used when a call sets none.
        seed: Part of every cache key; agents pass their model's seed instead.
        **params: Default call parameters (``temperature``, ``max_tokens``, ...).

    Example:
        >>> from modelly.llm import FakeProvider
        >>> client = Client(FakeProvider())
        >>> client.complete("Hello").cached
        False
        >>> client.usage.calls
        1
    """

    def __init__(
        self,
        provider: Provider,
        *,
        model: str | None = None,
        cache: ResponseCache | None = None,
        budget: Budget | None = None,
        retry: RetryPolicy | None = None,
        max_concurrency: int = DEFAULT_CONCURRENCY,
        system: str = "",
        seed: int | None = None,
        **params: Any,
    ) -> None:
        """Set the provider and the defaults of every call."""
        self.model: str = model or provider.default_model or ""
        if not self.model:
            raise ValueError(f"{type(provider).__name__} needs model=...")
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >= 1, got {max_concurrency}")
        self.provider = provider
        replay = active_replay()  # inside replaying(): the recorded replies, read-only
        if replay is not None:
            cache = replay
        self.cache = ResponseCache() if cache is None else cache
        self.budget = Budget() if budget is None else budget
        self.retry = RetryPolicy() if retry is None else retry
        self.max_concurrency = max_concurrency
        self.system = system
        self.seed = seed
        defaults = {
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
        }
        self.params = {**defaults, **params}
        self.counters: dict[str, int] = {}

    @property
    def usage(self) -> Usage:
        """Calls, cache hits, retries, tokens and cost so far."""
        return self.budget.usage

    def next_index(self, scope: str) -> int:
        """The next call counter of ``scope``, for calls not made by an ``LLMAgent``."""
        index = self.counters.get(scope, 0)
        self.counters[scope] = index + 1
        return index

    def request(
        self,
        prompt: Prompt,
        *,
        scope: str = MODEL_SCOPE,
        call_index: int | None = None,
        system: str | None = None,
        seed: int | None = None,
        schema: dict[str, Any] | None = None,
        **params: Any,
    ) -> Request:
        """Build a :class:`Request`; ``prompt`` is a user message or a list of messages."""
        messages = (
            (Message(USER, prompt),) if isinstance(prompt, str) else tuple(prompt)
        )
        index = self.next_index(scope) if call_index is None else call_index
        return Request(
            provider=self.provider.name,
            model=self.model,
            messages=messages,
            system=self.system if system is None else system,
            params=freeze_params({**self.params, **params}),
            scope=scope,
            call_index=index,
            seed=self.seed if seed is None else seed,
            schema=schema,
        )

    def complete(self, prompt: Prompt, **options: Any) -> Response:
        """One call: options are those of :meth:`request`."""
        return self.complete_many([self.request(prompt, **options)])[0]

    def complete_many(self, requests: Iterable[Request]) -> list[Response]:
        """Replies to ``requests``, in their order.

        Cached replies come first and cost nothing. The calls left are held
        against the budget in order; up to the first that could pass it, they
        are sent concurrently, counted and cached, then :class:`BudgetExceeded`
        is raised for the rest.

        Raises:
            CacheMiss: In replay mode, for the first call the cache does not hold.
            BudgetExceeded: Before the first call that could pass the budget.
            ProviderError: The first call (in order) that failed after its retries.
        """
        batch = list(requests)
        replies: list[Response | None] = self.lookup_many(batch)
        pending = [i for i, reply in enumerate(replies) if reply is None]
        allowed, refusal = self.reserve(batch, pending)
        self.dispatch(batch, replies, allowed)
        if refusal is not None:
            raise refusal
        return replies  # type: ignore[return-value]

    def lookup(self, request: Request) -> Response | None:
        """The cached reply of ``request``; a miss in replay mode raises."""
        return self.lookup_many([request])[0]

    def lookup_many(self, batch: Sequence[Request]) -> list[Response | None]:
        """The cached reply of each request (one query); a miss in replay mode raises.

        Hits are counted in order up to the first miss in replay mode, as one
        :meth:`lookup` per request would.
        """
        if not self.cache.reads:
            return [None] * len(batch)
        found = self.cache.get_many([request.key() for request in batch])
        replies: list[Response | None] = []
        for request in batch:
            hit = found.get(request.key())
            if hit is not None:
                self.budget.record_hit()
            elif self.cache.mode == READ_ONLY:
                key = request.key()
                raise CacheMiss(
                    request.scope, request.call_index, key, request.excerpt()
                )
            replies.append(hit)
        return replies

    def reserve(
        self, batch: list[Request], pending: list[int]
    ) -> tuple[list[int], BudgetExceeded | None]:
        """The pending calls the budget allows, and the refusal that stopped the rest."""
        allowed: list[int] = []
        for index in pending:
            try:
                self.budget.reserve(batch[index])
            except BudgetExceeded as refusal:
                return allowed, refusal
            allowed.append(index)
        return allowed, None

    def dispatch(
        self, batch: list[Request], replies: list[Response | None], allowed: list[int]
    ) -> None:
        """Send the ``allowed`` calls, then count and cache their replies in order."""
        if not allowed:
            return
        workers = min(self.max_concurrency, len(allowed)) if THREADS else 1
        if workers == 1:
            futures = [self.send_here(batch[i]) for i in allowed]
        else:
            pool = self.executor()
            futures = [
                pool.submit(self.retry.run, self.provider.complete, batch[i])
                for i in allowed
            ]
            wait(futures)
        failures = self.collect_all(batch, replies, allowed, futures)
        if failures:
            raise failures[0]

    def collect_all(
        self,
        batch: list[Request],
        replies: list[Response | None],
        allowed: list[int],
        futures: list[Future[Any]],
    ) -> list[ProviderError]:
        """Count every finished call in order; cache the replies in one transaction."""
        stored: list[tuple[Request, Response]] = []
        try:
            return [
                failure
                for index, future in zip(allowed, futures)
                if (
                    failure := self.collect(
                        batch[index], future, replies, index, stored
                    )
                )
            ]
        finally:  # the replies counted so far are cached, even when one raised
            if self.cache.writes and stored:
                self.cache.put_many(stored)

    def executor(self) -> ThreadPoolExecutor:
        """The client's thread pool, made on first use and kept for later batches.

        Its threads stop when the client is collected; a pickle leaves it out.
        """
        pool, size = self.__dict__.get(POOL_SLOT) or (None, 0)
        if pool is None or size != self.max_concurrency:
            if pool is not None:
                pool.shutdown(wait=False)
            pool = ThreadPoolExecutor(max_workers=self.max_concurrency)
            self.__dict__[POOL_SLOT] = (pool, self.max_concurrency)
            weakref.finalize(self, pool.shutdown, wait=False)
        return pool

    def __getstate__(self) -> dict[str, Any]:
        """Every attribute but the thread pool."""
        return {k: v for k, v in self.__dict__.items() if k != POOL_SLOT}

    def send_here(self, request: Request) -> Future[Any]:
        """Send ``request`` in this thread; its outcome as a finished future."""
        future: Future[Any] = Future()
        try:
            future.set_result(self.retry.run(self.provider.complete, request))
        except ProviderError as error:
            future.set_exception(error)
        return future

    def collect(
        self,
        request: Request,
        future: Future[Any],
        replies: list[Response | None],
        index: int,
        stored: list[tuple[Request, Response]],
    ) -> ProviderError | None:
        """Count one finished call and queue it in ``stored`` to cache, or return its error."""
        self.budget.release(request)
        try:
            response, retries = future.result()
        except ProviderError as error:
            return error
        response = replace(response, key=request.key(), cached=False)
        self.budget.record(request, response, retries)
        stored.append((request, response))
        replies[index] = response
        return None
