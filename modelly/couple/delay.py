"""Delay differential equations in agents: a state variable read ``tau`` time units ago.

``Delay(variable, tau, before)`` declared in ``AgentODE(delays={name: Delay(...)})`` passes
``rhs`` the value of each agent's ``variable`` at ``t - tau`` as ``params[name]``. The method
of steps makes it exact: each step is integrated in chunks no longer than the shortest
delay, so every delayed time falls in a part already integrated, whose dense output (the
Runge-Kutta interpolant of every step) is kept in a ``History``. Times before an agent's
first integration read ``before``, a constant or a function of time.

The history is keyed by the agents' unique ids, so agents added or removed between steps keep
their own past; it keeps only what the longest delay can still reach, and it is saved with
the model, so a resumed run reads the same past.

Reference:
    Bellen, A. and Zennaro, M. (2003). Numerical Methods for Delay Differential Equations.
    Oxford University Press.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from modelly.couple.dense import BatchDense
from modelly.couple.inputs import Input


@dataclass(frozen=True)
class Delay:
    """A delayed state variable.

    Attributes:
        variable: the state variable (a column of ``AgentODE``'s ``state``).
        tau: the delay, positive.
        before: the value before the agent's first integration: a number or
            ``before(t)``, ``t`` one time per agent.
    """

    variable: str
    tau: float
    before: float | Callable[[np.ndarray], Any] = 0.0

    def __post_init__(self) -> None:
        """Refuse a delay that is not positive."""
        if not self.tau > 0:
            raise ValueError(f"a delay must be positive, not {self.tau}")

    def initial(self, t: np.ndarray) -> np.ndarray:
        """The history before the first integration, at ``t``."""
        value = self.before(t) if callable(self.before) else self.before
        return np.broadcast_to(np.asarray(value, dtype=float), t.shape).copy()


@dataclass
class _Pass:
    """One integration pass: the agents' ids and their dense output."""

    ids: np.ndarray
    order: np.ndarray
    sol: BatchDense


@dataclass
class History:
    """Every agent's past states, as the dense output of the passes that integrated them."""

    reach: float
    passes: list[_Pass] = field(default_factory=list)

    def add(self, ids: np.ndarray, sol: BatchDense) -> None:
        """Keep a pass of the agents ``ids``."""
        ids = np.asarray(ids)
        self.passes.append(_Pass(ids, np.argsort(ids, kind="stable"), sol))

    def prune(self, now: float) -> None:
        """Forget the passes that end before ``now - reach``: no delay reaches them."""
        self.passes = [p for p in self.passes if p.sol.final.max() >= now - self.reach]

    def read(
        self,
        index: int,
        ids: np.ndarray,
        t: np.ndarray,
        delay: Delay,
        cache: dict[int, tuple[Any, ...]] | None = None,
    ) -> np.ndarray:
        """State variable ``index`` of the agents ``ids`` at times ``t`` (one each).

        ``cache`` keeps each pass's lookup of ``ids`` for the next read of the same ids.
        """
        out = delay.initial(t)
        cache = {} if cache is None else cache
        for (
            p
        ) in self.passes:  # later passes win where spans meet (after an event's action)
            hit = cache.get(id(p))
            if hit is None or hit[0] is not p:
                hit = cache[id(p)] = (p, *_lookup(p, ids))
            _, slot, found, start, final = hit
            inside = found & (t >= start) & (t <= final)
            if inside.any():
                times = np.full(p.ids.size, np.nan)
                rows = slot[inside]
                times[rows] = t[inside]
                out[inside] = p.sol.column(times, index)[rows]
        return out


def _lookup(p: _Pass, ids: np.ndarray) -> tuple[np.ndarray, ...]:
    """Where each of ``ids`` sits in the pass, whether it is there, and its span there."""
    slot = np.searchsorted(p.ids, ids, sorter=p.order)
    slot = p.order[np.minimum(slot, p.ids.size - 1)]
    return slot, p.ids[slot] == ids, p.sol.start[slot], p.sol.final[slot]


@dataclass(frozen=True)
class Delayed(Input):
    """The input ``rhs`` reads for one ``Delay``: the variable at ``t - tau`` per agent."""

    history: History
    index: int
    delay: Delay
    ids: np.ndarray
    lookups: dict[int, tuple[Any, ...]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def __call__(self, t: np.ndarray) -> np.ndarray:
        """Each agent's variable at ``t - tau``."""
        t = np.broadcast_to(np.asarray(t, dtype=float), self.ids.shape)
        return self.history.read(
            self.index, self.ids, t - self.delay.tau, self.delay, self.lookups
        )

    def cut(self, rows: np.ndarray, k: int) -> Delayed:
        """The input of the agents ``rows``."""
        return Delayed(self.history, self.index, self.delay, self.ids[rows])


def chunks(start: float, end: float, longest: float) -> list[tuple[float, float]]:
    """``[start, end]`` cut into consecutive pieces no longer than ``longest``."""
    count = max(1, int(np.ceil((end - start) / longest - 1e-12)))
    edges = np.linspace(start, end, count + 1)
    return list(zip(edges[:-1].tolist(), edges[1:].tolist()))
