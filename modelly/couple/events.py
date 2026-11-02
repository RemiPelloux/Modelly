"""Events for ``solve_batch``: where a function of the state crosses zero, per system.

An ``ODEEvent`` wraps ``condition(t, y, params)``, which returns one value per system, as an
event function of ``solve_ivp`` does for one. After every accepted step a system whose value
changed sign (in the event's ``direction``) has the crossing located on the step's dense
output (the Runge-Kutta pair's own interpolant, as ``solve_ivp`` uses), by bisection to the
last bit of the step. A terminal event stops that system at its crossing; the others go on.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from modelly.couple.batch import _Batch

# Bisection halvings: the bracket shrinks to 2**-BISECTIONS of the step, below one ulp.
BISECTIONS = 60


@dataclass(frozen=True)
class ODEEvent:
    """A zero crossing to locate in every system.

    Attributes:
        condition: ``condition(t, y, params)``, one value per system, shape ``(k,)``.
        terminal: stop a system at its first crossing.
        direction: ``1`` for upward crossings only, ``-1`` for downward only, ``0`` for both.
        action: for ``AgentODE``, ``action(table, rows, times)``, called after the
            integration with the agents' column table, the rows that crossed and when.
            ``solve_batch`` ignores it.
    """

    condition: Callable[[np.ndarray, np.ndarray, Mapping[str, Any]], Any]
    terminal: bool = False
    direction: float = 0.0
    action: Callable[[Any, np.ndarray, np.ndarray], Any] | None = None

    def value(
        self, t: np.ndarray, y: np.ndarray, params: Mapping[str, Any]
    ) -> np.ndarray:
        """The condition's value for each system."""
        return np.asarray(self.condition(t, y, params), dtype=float).reshape(t.shape)

    def crossed(self, before: np.ndarray, after: np.ndarray) -> np.ndarray:
        """Which systems crossed zero in this event's direction (``solve_ivp``'s rule)."""
        up = (before <= 0) & (after >= 0)
        down = (before >= 0) & (after <= 0)
        if self.direction > 0:
            return up
        if self.direction < 0:
            return down
        return up | down


@dataclass
class EventLog:
    """The crossings of one event: which system, when, and its state there.

    Attributes:
        rows: the system (column) of each crossing.
        t: the time of each crossing.
        y: the state at each crossing, shape ``(m, crossings)``.
    """

    rows: Any = field(default_factory=list)
    t: Any = field(default_factory=list)
    y: Any = field(default_factory=list)

    def add(self, rows: np.ndarray, t: np.ndarray, y: np.ndarray) -> None:
        """Record crossings."""
        self.rows.append(rows)
        self.t.append(t)
        self.y.append(y)

    def close(self) -> EventLog:
        """Join the recorded pieces into arrays, ordered by system then time."""
        if not self.rows:
            return EventLog(np.zeros(0, int), np.zeros(0), np.zeros((0, 0)))
        rows, t = np.concatenate(self.rows), np.concatenate(self.t)
        order = np.lexsort((t, rows))
        return EventLog(rows[order], t[order], np.concatenate(self.y, axis=1)[:, order])


class _Step:
    """One accepted step of some systems, with its dense output."""

    def __init__(self, batch: _Batch, rows: np.ndarray, t_new: np.ndarray, ks) -> None:
        """Keep the start, the step and the interpolant's coefficients."""
        self.t0, self.y0 = batch.t[rows], batch.y[:, rows]
        self.h = t_new - self.t0
        self.t_new = t_new
        self.Q = np.tensordot(batch.tab.P.T, ks, axes=1)  # (degree, m, systems)
        self.params = batch.cut(rows)

    def at(self, x: np.ndarray, cols) -> tuple[np.ndarray, np.ndarray]:
        """Time and state at the fraction ``x`` of the step, for the columns ``cols``."""
        powers = np.cumprod(np.broadcast_to(x, (self.Q.shape[0], x.size)), axis=0)
        h = self.h[cols]
        dy = np.einsum("dmc,dc->mc", self.Q[..., cols], powers)
        return self.t0[cols] + x * h, self.y0[:, cols] + h * dy

    def root(self, event: ODEEvent, before: np.ndarray, cols: np.ndarray) -> np.ndarray:
        """The fraction of the step where ``event`` crosses, by bisection on the interpolant."""
        sign = np.sign(before[cols])
        lo, hi = np.zeros(cols.size), np.ones(cols.size)
        for _ in range(BISECTIONS):
            mid = (lo + hi) / 2
            t, y = self.at(mid, cols)
            same = (
                np.sign(event.value(t, y, _cut(self.params, cols, self.h.size))) == sign
            )
            lo, hi = np.where(same, mid, lo), np.where(same, hi, mid)
        return np.where(sign == 0, 0.0, hi)


def _locate(
    batch: _Batch,
    events: Sequence[ODEEvent],
    logs: list[EventLog],
    previous: list[np.ndarray],
    rows: np.ndarray,
    t_new: np.ndarray,
    y_new: np.ndarray,
    ks: np.ndarray,
) -> np.ndarray:
    """Record the crossings in an accepted step; stop systems at a terminal one.

    Returns:
        Which of ``rows`` a terminal event stopped (their time and state are set to the
        crossing).
    """
    step = _Step(batch, rows, t_new, ks)
    fractions = [
        _fractions(step, e, p[rows], t_new, y_new) for e, p in zip(events, previous)
    ]
    stop_at = np.full(rows.size, np.inf)
    for event, x in zip(events, fractions):
        if event.terminal:
            stop_at = np.minimum(stop_at, x)
    for log, x in zip(logs, fractions):
        hit = np.flatnonzero(np.isfinite(x) & (x <= stop_at))
        if hit.size:
            log.add(rows[hit], *step.at(x[hit], hit))
    stop = np.isfinite(stop_at)
    if np.any(stop):
        cols = np.flatnonzero(stop)
        batch.t[rows[cols]], batch.y[:, rows[cols]] = step.at(stop_at[cols], cols)
    for event, p in zip(events, previous):
        p[rows] = event.value(t_new, y_new, step.params)
    return stop


def _fractions(step: _Step, event: ODEEvent, before, t_new, y_new) -> np.ndarray:
    """The fraction of the step where each system crosses, ``inf`` where none does."""
    after = event.value(t_new, y_new, step.params)
    cols = np.flatnonzero(event.crossed(before, after))
    x = np.full(t_new.size, np.inf)
    if cols.size:
        x[cols] = step.root(event, before, cols)
    return x


def _cut(params: Mapping[str, Any], rows, k: int) -> dict[str, Any]:
    """The parameters of the systems ``rows``.

    Arrays whose last axis has length ``k`` are cut; everything else, and every parameter
    when ``rows`` is a slice, is passed whole.
    """
    if isinstance(rows, slice):
        return dict(params)
    return {
        name: value[..., rows] if np.ndim(value) and np.shape(value)[-1] == k else value
        for name, value in params.items()
    }
