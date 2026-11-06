"""Dense output of ``solve_batch``: every system's state at any time of its span.

Each accepted step keeps the Runge-Kutta pair's own interpolant (the polynomial
``solve_ivp``'s ``dense_output`` uses), so ``BatchDense(t)`` reads a system inside a step at
the accuracy of the integration, without integrating again. Each system can be read at its
own time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def interpolate(Q, h, y0, x) -> np.ndarray:  # noqa: N803 - scipy's name for it
    """The state at the fraction ``x`` of a step: ``y0 + h * sum_d Q[d] * x**(d+1)``.

    ``Q`` has shape ``(degree, m, systems)``; ``h`` and ``x`` one value per system.
    """
    powers = np.cumprod(np.broadcast_to(x, (Q.shape[0], np.size(x))), axis=0)
    return y0 + h * np.einsum("dmc,dc->mc", Q, powers)


@dataclass
class _Segment:
    """One accepted step of some systems, valid from ``t0`` to ``end``."""

    rows: np.ndarray
    t0: np.ndarray
    h: np.ndarray
    y0: np.ndarray
    Q: np.ndarray
    end: np.ndarray


@dataclass
class BatchDense:
    """The state of every system at any time between its start and its final time.

    Attributes:
        start: each system's start time, shape ``(k,)``.
        y0: each system's initial state, shape ``(m, k)``.
        final: each system's final time (the end of its span, or where a terminal event
            stopped it).
    """

    start: np.ndarray
    y0: np.ndarray
    final: np.ndarray = field(default_factory=lambda: np.zeros(0))
    segments: list[_Segment] = field(default_factory=list, repr=False)

    def add(self, rows, t0, h, y0, Q) -> None:  # noqa: N803
        """Keep one accepted step of the systems ``rows``."""
        self.segments.append(_Segment(rows, t0, h, y0, Q, t0 + h))

    def clip(self, cols: np.ndarray, end: np.ndarray) -> None:
        """End the last step of its systems ``cols`` at ``end`` (a terminal event)."""
        self.segments[-1].end[cols] = end

    def __call__(self, t) -> np.ndarray:
        """The states at ``t``, a scalar or one time per system; shape ``(m, k)``.

        Raises:
            ValueError: for a time outside a system's span.
        """
        t = np.broadcast_to(np.asarray(t, dtype=float), self.start.shape)
        outside = (t < self.start) | (t > self.final)
        if np.any(outside):
            i = int(np.flatnonzero(outside)[0])
            raise ValueError(
                f"time {t[i]} is outside system {i}'s span "
                f"[{self.start[i]}, {self.final[i]}]"
            )
        return self.values(t)

    def values(self, t: np.ndarray) -> np.ndarray:
        """The states at ``t`` (one time per system), unchecked; a NaN time reads ``y0``."""
        out = self.y0.copy()
        for seg in self.segments:
            tq = t[seg.rows]
            cols = np.flatnonzero((tq >= seg.t0) & (tq <= seg.end))
            if cols.size:
                x = (tq[cols] - seg.t0[cols]) / seg.h[cols]
                out[:, seg.rows[cols]] = interpolate(
                    seg.Q[..., cols], seg.h[cols], seg.y0[:, cols], x
                )
        return out

    def column(self, t: np.ndarray, index: int) -> np.ndarray:
        """``values(t)[index]``, the same numbers, interpolating only that variable."""
        out: np.ndarray = self.y0[index].copy()
        for seg in self.segments:
            tq = t[seg.rows]
            cols = np.flatnonzero((tq >= seg.t0) & (tq <= seg.end))
            if cols.size:
                x = (tq[cols] - seg.t0[cols]) / seg.h[cols]
                out[seg.rows[cols]] = _one(seg, cols, x, index)
        return out


def _one(seg: _Segment, cols: np.ndarray, x: np.ndarray, index: int) -> np.ndarray:
    """Variable ``index`` of the segment's interpolant at ``x`` for the systems ``cols``.

    For one system ``einsum`` reduces over the degree in an order that depends on the
    operand's strides, so that case interpolates every variable, as ``values`` does.
    """
    if cols.size == 1:
        every = interpolate(seg.Q[..., cols], seg.h[cols], seg.y0[:, cols], x)
        return np.asarray(every[index])
    one = slice(index, index + 1)
    only = interpolate(seg.Q[:, one, cols], seg.h[cols], seg.y0[one, cols], x)
    return np.asarray(only[0])


@dataclass
class StackedDense:
    """Dense output of ``k`` systems stacked into one ``solve_ivp`` call (``OdeSolution``)."""

    solution: object
    shape: tuple[int, int]
    start: np.ndarray
    final: np.ndarray

    def __call__(self, t) -> np.ndarray:
        """The states at ``t``, a scalar or one time per system; shape ``(m, k)``."""
        m, k = self.shape
        t = np.broadcast_to(np.asarray(t, dtype=float), (k,))
        out = np.empty((m, k))
        values, group = np.unique(t, return_inverse=True)
        order = np.argsort(group, kind="stable")
        bounds = np.searchsorted(group[order], np.arange(values.size + 1))
        for i, value in enumerate(values):
            # a NaN time matches no system (NaN != NaN), as with ``t == value``
            cols = order[bounds[i] : bounds[i + 1]] if value == value else order[:0]
            out[:, cols] = self.solution(value).reshape(m, k)[:, cols]
        return out
