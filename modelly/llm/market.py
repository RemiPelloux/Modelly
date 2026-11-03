"""A conversational market: traders who talk, ask a price, and buy or walk away.

Half the traders sell one crate a round at a cost of their own; the other half buy one if
the price is below their value. Each round the model pairs every seller with a buyer, the
pair talks for two turns (``converse_many``), the seller states an asking price and the
buyer accepts or refuses (``decide_all``), and both remember the round (``MemoryAgent``).
Every call goes through ``model.llm``.

``local_trader`` is an offline stand-in for a language model: it reads the trader's value
from its persona and answers in character (a seller asks a fifth above its cost, a buyer
accepts a price at or below its value), so the market runs, caches and replays with no
network and no key. Swap it for a real provider to study what a language model does.
"""

from __future__ import annotations

import json
import re
from typing import Any

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.llm.agent import decide_all
from modelly.llm.client import Client
from modelly.llm.conversation import converse_many
from modelly.llm.fake import FakeProvider
from modelly.llm.memory import MemoryAgent
from modelly.llm.request import Request

TOPIC = "the price of one crate of apples"
ASK = {"type": "object", "required": ["price"], "properties": {"price": {"type": "number", "minimum": 0}}}  # fmt: skip
ACCEPT = {
    "type": "object",
    "required": ["buy"],
    "properties": {"buy": {"type": "boolean"}},
}
MARKUP = 1.2
VALUE = re.compile(r"(?:value|cost) of ([0-9.]+)")
ASKED = re.compile(r"asks ([0-9.]+)")


def _number(pattern: re.Pattern[str], text: str) -> str:
    """The number ``pattern`` finds in ``text``.

    Raises:
        ValueError: when there is none (a prompt the stand-in does not know).
    """
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"local_trader found no {pattern.pattern!r} in {text[:60]!r}")
    return match.group(1)


def local_trader(request: Request) -> str:
    """An offline trader: in character, from the value in its persona."""
    value = float(_number(VALUE, request.system))
    schema = request.schema or {}
    if "price" in schema.get("properties", {}):
        return json.dumps({"price": round(value * MARKUP, 2)})
    if "buy" in schema.get("properties", {}):
        asked = float(_number(ASKED, request.messages[-1].content))
        return json.dumps({"buy": asked <= value})
    return f"For me a crate is worth about {value:.0f}."


class Trader(MemoryAgent, Agent["Market"]):
    """A buyer or a seller of crates, with a value and a memory of its rounds."""

    value = Column(float, default=0.0)
    seller = Column(bool, default=False)
    traded = Column(int, default=0)

    def __init__(self, model: Market, value: float, seller: bool) -> None:
        """A trader of value ``value`` (a seller's cost, a buyer's willingness to pay)."""
        super().__init__(model)
        self.value, self.seller = value, seller
        role = (
            "sell crates of apples at a cost"
            if seller
            else "buy crates of apples, at a value"
        )
        self.persona = f"You {role} of {value:.2f} each. You speak briefly."


class Market(Model[Trader, Any]):
    """Sellers and buyers who talk, then trade; every call goes through ``self.llm``.

    Attributes:
        prices: the price of every trade, in order.
    """

    def __init__(
        self, traders: int = 500, rng: int = 0, client: Client | None = None
    ) -> None:
        """``traders`` traders, half of each side, values drawn from ``rng``."""
        super().__init__(rng=rng)
        self.llm = client if client is not None else Client(FakeProvider(local_trader))
        half = traders // 2
        for cost in self.rng.uniform(20, 60, half):
            Trader(self, round(float(cost), 2), True)
        for value in self.rng.uniform(40, 100, traders - half):
            Trader(self, round(float(value), 2), False)
        self.prices: list[float] = []

    def pairs(self) -> list[tuple[Trader, Trader]]:
        """Every seller with a buyer, both sides shuffled by the model's generator."""
        sellers = [a for a in self.agents if a.seller]
        buyers = [a for a in self.agents if not a.seller]
        mixed_sellers = [sellers[i] for i in self.rng.permutation(len(sellers))]
        mixed_buyers = [buyers[i] for i in self.rng.permutation(len(buyers))]
        return list(zip(mixed_sellers, mixed_buyers))

    def step(self) -> None:
        """Talk, ask, decide, remember."""
        pairs = self.pairs()
        converse_many(pairs, TOPIC, turns=2)
        asks = decide_all(
            [s for s, _ in pairs], "State your asking price for one crate.", ASK
        )
        prices = {b.unique_id: float(a["price"]) for (_, b), a in zip(pairs, asks)}

        def offer(buyer: Any) -> str:
            return f"The seller asks {prices[buyer.unique_id]:.2f} for a crate. Do you buy?"

        answers = decide_all([b for _, b in pairs], offer, ACCEPT)
        for (seller, buyer), answer in zip(pairs, answers):
            self._settle(seller, buyer, prices[buyer.unique_id], bool(answer["buy"]))

    def _settle(self, seller: Trader, buyer: Trader, price: float, deal: bool) -> None:
        """Record a trade, and what each side remembers of the round."""
        if deal:
            seller.traded += 1
            buyer.traded += 1
            self.prices.append(price)
        outcome = f"sold at {price:.2f}" if deal else f"no deal at {price:.2f}"
        seller.remember(f"Asked {price:.2f} of agent {buyer.unique_id}: {outcome}.")
        buyer.remember(f"Agent {seller.unique_id} asked {price:.2f}: {outcome}.")

    def mean_price(self) -> float:
        """The mean price of the trades so far (NaN before any)."""
        return float(np.mean(self.prices)) if self.prices else float("nan")
