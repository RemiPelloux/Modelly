"""Token and cost budgets for a run, and the counters the client keeps.

No price is built in: prices change, and a wrong one is worse than none. Pass a
price table to know the cost; without one, the cost stays unknown (None) and only a
token budget can be enforced.

Before a call is sent, its worst case is reserved: the prompt's estimated tokens plus
its ``max_tokens``. When that could take the run past a limit, :class:`BudgetExceeded`
is raised and the call is never made. Replies from the cache cost nothing and are
counted apart (``cache_hits``).

Example:
    >>> budget = Budget(max_tokens=10_000, prices={"m": Price(3.0, 15.0)}, max_cost=0.5)
    >>> budget.usage.cost
    0.0
"""

from __future__ import annotations

import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from modelly.llm.errors import BudgetExceeded
from modelly.llm.request import Request, Response

# A rough count for English text, used only to reserve tokens before a call.
CHARS_PER_TOKEN = 4
# Prices are per million tokens, as providers publish them.
PER_PRICE_UNIT = 1_000_000
# Output tokens reserved when a request sets no max_tokens.
DEFAULT_RESERVED_OUTPUT = 1024


@dataclass(frozen=True)
class Price:
    """Price per million input tokens and per million output tokens, in any currency."""

    input_per_million: float
    output_per_million: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """The price of one call."""
        return (
            input_tokens * self.input_per_million
            + output_tokens * self.output_per_million
        ) / PER_PRICE_UNIT


@dataclass
class Usage:
    """What a run used so far.

    Attributes:
        calls: Calls sent to the provider (retries not included).
        cache_hits: Replies served from the cache.
        retries: Extra tries after a 429, a 5xx or a lost connection.
        input_tokens: Prompt tokens of the calls sent.
        output_tokens: Reply tokens of the calls sent.
        cost: The cost of the calls sent, or None when a model has no price.
    """

    calls: int = 0
    cache_hits: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = 0.0

    @property
    def tokens(self) -> int:
        """Input plus output tokens."""
        return self.input_tokens + self.output_tokens


@dataclass
class Budget:
    """Limits for one run and the usage counted against them.

    Args:
        max_tokens: The most input plus output tokens the run may send for. None: no limit.
        max_cost: The most the run may cost. Needs a price for every model it calls.
        prices: Model name to :class:`Price`.
    """

    max_tokens: int | None = None
    max_cost: float | None = None
    prices: Mapping[str, Price] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    _reserved_tokens: int = field(default=0, init=False, repr=False)
    _reserved_cost: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Copy the price table and create the lock."""
        self.prices = dict(self.prices)
        self._lock = threading.Lock()

    def estimate(self, request: Request) -> tuple[int, int]:
        """Worst-case (input, output) tokens of ``request``."""
        prompt = math.ceil(request.prompt_chars() / CHARS_PER_TOKEN)
        return prompt, request.max_tokens or DEFAULT_RESERVED_OUTPUT

    def price_of(self, model: str) -> Price | None:
        """The price of ``model``; required when a cost budget is set."""
        price = self.prices.get(model)
        if price is None and self.max_cost is not None:
            raise BudgetExceeded(
                f"a cost budget is set but model {model!r} has no price: pass "
                f"prices={{{model!r}: Price(input, output)}} or drop max_cost"
            )
        return price

    def reserve(self, request: Request) -> None:
        """Hold the worst case of ``request``, or raise :class:`BudgetExceeded`."""
        tokens_in, tokens_out = self.estimate(request)
        price = self.price_of(request.model)
        cost = price.cost(tokens_in, tokens_out) if price else 0.0
        with self._lock:
            tokens = self.usage.tokens + self._reserved_tokens + tokens_in + tokens_out
            spent = (self.usage.cost or 0.0) + self._reserved_cost + cost
            self.refuse_over(tokens, spent, request)
            self._reserved_tokens += tokens_in + tokens_out
            self._reserved_cost += cost

    def refuse_over(self, tokens: int, cost: float, request: Request) -> None:
        """Raise when ``tokens`` or ``cost`` passes its limit."""
        call = f"call {request.call_index} of {request.scope!r}"
        if self.max_tokens is not None and tokens > self.max_tokens:
            raise BudgetExceeded(
                f"{call} could bring the run to {tokens} tokens, over the budget of "
                f"{self.max_tokens}; {self.usage.tokens} used so far"
            )
        if self.max_cost is not None and cost > self.max_cost:
            raise BudgetExceeded(
                f"{call} could bring the run's cost to {cost:.6f}, over the budget of "
                f"{self.max_cost}; {self.usage.cost:.6f} spent so far"
            )

    def release(self, request: Request) -> None:
        """Give back the reservation of ``request`` once its reply is counted."""
        tokens_in, tokens_out = self.estimate(request)
        price = self.prices.get(request.model)
        with self._lock:
            self._reserved_tokens -= tokens_in + tokens_out
            if price:
                self._reserved_cost -= price.cost(tokens_in, tokens_out)

    def record(self, request: Request, response: Response, retries: int) -> None:
        """Count a reply from the provider."""
        price = self.prices.get(request.model)
        with self._lock:
            usage = self.usage
            usage.calls += 1
            usage.retries += retries
            usage.input_tokens += response.input_tokens
            usage.output_tokens += response.output_tokens
            if price is None or usage.cost is None:
                usage.cost = None
            else:
                usage.cost += price.cost(response.input_tokens, response.output_tokens)

    def record_hit(self) -> None:
        """Count a reply served from the cache."""
        with self._lock:
            self.usage.cache_hits += 1

    def __getstate__(self) -> dict[str, Any]:
        """Everything but the lock."""
        return {k: v for k, v in vars(self).items() if k != "_lock"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the fields and a fresh lock."""
        vars(self).update(state)
        self._lock = threading.Lock()
