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
from functools import cached_property
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.couple.dense import BatchDense, interpolate
from modelly.couple.inputs import Input, evaluated

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
        values = self.condition(t, y, evaluated(params, t))
        return np.asarray(values, dtype=float).reshape(t.shape)

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
        self.batch, self.rows = batch, rows
        self.t0, self.y0 = batch.t[rows], batch.y[:, rows]
        self.h = t_new - self.t0
        self.t_new = t_new
        self.Q = np.einsum("sd,s...->d...", batch.tab.P, ks)  # (degree, m, systems)

    @cached_property
    def params(self) -> dict[str, Any]:
        """The parameters of the step's systems, cut once when an event needs them."""
        return self.batch.cut(self.rows)

    def at(self, x: np.ndarray, cols) -> tuple[np.ndarray, np.ndarray]:
        """Time and state at the fraction ``x`` of the step, for the columns ``cols``."""
        h = self.h[cols]
        return self.t0[cols] + x * h, interpolate(
            self.Q[..., cols], h, self.y0[:, cols], x
        )

    def root(self, event: ODEEvent, before: np.ndarray, cols: np.ndarray) -> np.ndarray:
        """The fraction of the step where ``event`` crosses, by bisection on the interpolant."""
        sign = np.sign(before[cols])
        lo, hi = np.zeros(cols.size), np.ones(cols.size)
        h, t0, y0 = self.h[cols], self.t0[cols], self.y0[:, cols]
        coefficients = self.Q[..., cols]
        params = _cut(self.params, cols, self.h.size)
        for _ in range(BISECTIONS):
            mid = (lo + hi) / 2
            t, y = t0 + mid * h, interpolate(coefficients, h, y0, mid)
            same = np.sign(event.value(t, y, params)) == sign
            lo, hi = np.where(same, mid, lo), np.where(same, hi, mid)
        return np.where(sign == 0, 0.0, hi)


def _record(
    step: _Step,
    events: Sequence[ODEEvent],
    logs: list[EventLog],
    previous: list[np.ndarray],
    y_new: np.ndarray,
    sol: BatchDense | None,
) -> np.ndarray:
    """Keep an accepted step's interpolant and locate its events; which systems stopped."""
    if sol is not None:
        sol.add(step.rows, step.t0, step.h, step.y0, step.Q)
    if not events:
        return np.zeros(step.rows.size, bool)
    stop = _locate(step, events, logs, previous, y_new)
    if sol is not None and np.any(stop):
        sol.clip(np.flatnonzero(stop), step.batch.t[step.rows[stop]])
    return stop


def _locate(
    step: _Step,
    events: Sequence[ODEEvent],
    logs: list[EventLog],
    previous: list[np.ndarray],
    y_new: np.ndarray,
) -> np.ndarray:
    """Record the crossings in an accepted step; stop systems at a terminal one.

    Returns:
        Which of ``rows`` a terminal event stopped (their time and state are set to the
        crossing).
    """
    batch, rows, t_new = step.batch, step.rows, step.t_new
    afters = [event.value(t_new, y_new, step.params) for event in events]
    fractions = [
        _fractions(step, e, p[rows], after)
        for e, p, after in zip(events, previous, afters)
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
    for p, after in zip(previous, afters):
        p[rows] = after
    return stop


def _fractions(step: _Step, event: ODEEvent, before, after) -> np.ndarray:
    """The fraction of the step where each system crosses, ``inf`` where none does."""
    cols = np.flatnonzero(event.crossed(before, after))
    x = np.full(after.size, np.inf)
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
    return {name: _cut_one(value, rows, k) for name, value in params.items()}


def _cut_one(value: Any, rows: np.ndarray, k: int) -> Any:
    """One parameter of the systems ``rows``: inputs cut themselves, arrays on their last axis."""
    if isinstance(value, Input):
        return value.cut(rows, k)
    if np.ndim(value) and np.shape(value)[-1] == k:
        return value[..., rows]
    return value
