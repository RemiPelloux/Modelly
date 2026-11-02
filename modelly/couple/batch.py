"""Many independent ODE systems integrated at once, each with its own adaptive step.

``solve_batch`` integrates ``k`` systems of ``m`` equations, ``dy/dt = rhs(t, y, params)``,
with ``y`` of shape ``(m, k)``: one column per system (one per agent). It runs the same
explicit Runge-Kutta pairs as ``scipy.integrate.solve_ivp`` (``"RK45"``, Dormand-Prince, and
``"RK23"``, Bogacki-Shampine; their tableaux are read from scipy), with the same initial step
selection, error norm and step-size controller, applied to every column separately. Each
system therefore takes the steps it would take in its own ``solve_ivp`` call and is held to
the same tolerance, while the right-hand side is evaluated once per stage for all of them,
as numpy array operations.

Calling ``solve_ivp`` once per system gives the same answer, one Python solver per system.
Stacking every system into one ``solve_ivp`` call is fast but different: it takes the
smallest step any system needs, for all of them, and measures the error as the RMS over all
``m * k`` components, so one system's error can grow to about ``sqrt(k)`` times the tolerance.

``rhs`` receives ``t`` as an array of shape ``(k,)`` (each system is at its own time), ``y``
of shape ``(m, k)`` and ``params``, a mapping whose arrays of length ``k`` are cut to the
systems being advanced; scalars pass through. It returns an array of shape ``(m, k)``.

References:
    Hairer, E., Norsett, S. P. and Wanner, G. (1993). Solving Ordinary Differential
    Equations I: Nonstiff Problems, 2nd ed., Sec. II.4. Springer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from modelly.couple.events import Event, EventLog, _cut, _locate
from modelly.couple.schedule import CouplingError

# scipy.integrate._ivp.rk: the step-size controller's constants.
SAFETY, MIN_FACTOR, MAX_FACTOR = 0.9, 0.2, 10.0
EPS = np.finfo(float).eps
METHODS = ("RK45", "RK23")
# select_initial_step's thresholds (Hairer, Norsett and Wanner, II.4).
TINY_NORM, FIRST_GUESS, FLAT_NORM, SLACK = 1e-5, 1e-6, 1e-15, 0.01

type Rhs = Callable[[np.ndarray, np.ndarray, Mapping[str, Any]], np.ndarray]


@dataclass
class BatchResult:
    """What ``solve_batch`` returns.

    Attributes:
        t: each system's final time, shape ``(k,)``: the end of the span, or the time of
            the terminal event that stopped it.
        y: each system's final state, shape ``(m, k)``.
        stopped: which systems a terminal event stopped, shape ``(k,)``.
        events: the crossings of every event, as an ``EventLog`` per event.
        nfev: calls of ``rhs``, each on every system still advancing.
        nsteps: accepted steps per system, shape ``(k,)``.
        nrejected: rejected steps per system, shape ``(k,)``.
    """

    t: np.ndarray
    y: np.ndarray
    stopped: np.ndarray
    events: list[EventLog] = field(default_factory=list)
    nfev: int = 0
    nsteps: np.ndarray = field(default_factory=lambda: np.zeros(0, int))
    nrejected: np.ndarray = field(default_factory=lambda: np.zeros(0, int))


@dataclass(frozen=True)
class _Tableau:
    """A Runge-Kutta pair as scipy defines it."""

    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    E: np.ndarray
    P: np.ndarray
    order: int
    exponent: float

    @classmethod
    def of(cls, method: str) -> _Tableau:
        """The tableau of scipy's ``RK45`` or ``RK23``."""
        from scipy import integrate  # noqa: PLC0415 - scipy is heavy

        if method not in METHODS:
            raise CouplingError(f"solve_batch supports {METHODS}, not {method!r}")
        rk = getattr(integrate, method)
        order = rk.error_estimator_order
        return cls(rk.A, rk.B, rk.C, rk.E, rk.P, order, -1 / (order + 1))


class _Batch:
    """The integrator's state: one column per system, cut to the active ones per stage."""

    def __init__(self, rhs: Rhs, t0, t1, y0, params, rtol, atol, method) -> None:
        """Set every system at ``t0`` with its derivative and first step."""
        self.rhs, self.tab = rhs, _Tableau.of(method)
        self.y = np.array(y0, dtype=float, ndmin=2)
        k = self.y.shape[1]
        self.t = np.broadcast_to(np.asarray(t0, dtype=float), (k,)).copy()
        self.t1 = np.broadcast_to(np.asarray(t1, dtype=float), (k,)).copy()
        self.params = dict(params or {})
        self.rtol, self.atol = max(float(rtol), 100 * EPS), float(atol)
        self.nfev, self.k = 0, k
        self.nsteps, self.nrejected = np.zeros(k, int), np.zeros(k, int)
        self.retry = np.zeros(k, bool)
        self.f = self.call(self.t, self.y, self.params)
        self.h = self.first_step()

    def cut(self, rows) -> dict[str, Any]:
        """The parameters of the systems ``rows`` (a slice keeps them all)."""
        return (
            self.params if isinstance(rows, slice) else _cut(self.params, rows, self.k)
        )

    def call(
        self, t: np.ndarray, y: np.ndarray, params: Mapping[str, Any]
    ) -> np.ndarray:
        """``rhs`` on some systems, given their parameters."""
        self.nfev += 1
        return np.asarray(self.rhs(t, y, params), dtype=float).reshape(y.shape)

    def norm(self, x: np.ndarray) -> np.ndarray:
        """The RMS norm of each column, as scipy's ``norm`` of one system."""
        return np.sqrt(np.einsum("ij,ij->j", x, x) / x.shape[0])

    def first_step(self) -> np.ndarray:
        """The first step of each system, by scipy's ``select_initial_step``."""
        span = self.t1 - self.t
        scale = self.atol + np.abs(self.y) * self.rtol
        d0, d1 = self.norm(self.y / scale), self.norm(self.f / scale)
        with np.errstate(
            divide="ignore", invalid="ignore"
        ):  # np.where computes both sides
            h0 = np.where(
                (d0 < TINY_NORM) | (d1 < TINY_NORM), FIRST_GUESS, SLACK * d0 / d1
            )
        h0 = np.minimum(h0, span)
        f1 = self.call(self.t + h0, self.y + h0 * self.f, self.params)
        with np.errstate(divide="ignore", invalid="ignore"):
            d2 = self.norm((f1 - self.f) / scale) / h0
            h1 = (SLACK / np.maximum(d1, d2)) ** (1 / (self.tab.order + 1))
        flat = (d1 <= FLAT_NORM) & (d2 <= FLAT_NORM)
        h1 = np.where(flat, np.maximum(FIRST_GUESS, h0 * 1e-3), h1)
        return np.minimum.reduce([100 * h0, h1, span])

    def stages(self, params, t, y, f, h) -> tuple[np.ndarray, np.ndarray]:
        """One Runge-Kutta step of some systems: the new state and all stages."""
        tab = self.tab
        ks = np.empty((len(tab.B) + 1, *y.shape))
        ks[0] = f
        for s in range(1, len(tab.B)):
            ks[s] = self.call(
                t + tab.C[s] * h, _advanced(y, h, tab.A[s, :s], ks[:s]), params
            )
        y_new = _advanced(y, h, tab.B, ks[:-1])
        ks[-1] = self.call(t + h, y_new, params)
        return y_new, ks

    def attempt(self, rows) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Try a step on ``rows``: accepted mask, new time, new state and stages."""
        t, y, f = self.t[rows], self.y[:, rows], self.f[:, rows]
        h_abs = self.h[rows]
        fresh = ~self.retry[rows]
        min_step = 10 * np.abs(np.nextafter(t, np.inf) - t)
        h_abs = np.where(fresh, np.maximum(h_abs, min_step), h_abs)
        if np.any(h_abs < min_step):
            raise CouplingError("solve_batch: the required step fell below the minimum")
        t_new = np.minimum(t + h_abs, self.t1[rows])
        h = t_new - t
        y_new, ks = self.stages(self.cut(rows), t, y, f, h)
        scale = np.abs(y)
        np.maximum(scale, np.abs(y_new), out=scale)
        scale *= self.rtol
        scale += self.atol
        error = _combine(self.tab.E, ks)
        error *= h
        error /= scale
        error = self.norm(error)
        self.control(rows, error, np.abs(h))
        return error < 1, t_new, y_new, ks

    def control(self, rows, error: np.ndarray, h_abs: np.ndarray) -> None:
        """Update each step size as scipy does, after an accepted or a rejected step."""
        with np.errstate(divide="ignore"):
            grow = SAFETY * error**self.tab.exponent
        ok = error < 1
        factor = np.where(error == 0, MAX_FACTOR, np.minimum(MAX_FACTOR, grow))
        factor = np.where(self.retry[rows], np.minimum(1.0, factor), factor)
        shrink = np.maximum(MIN_FACTOR, grow)
        self.h[rows] = h_abs * np.where(ok, factor, shrink)
        self.retry[rows] = ~ok
        self.nsteps[rows] += ok
        self.nrejected[rows] += ~ok


def solve_batch(
    rhs: Rhs,
    t_span: tuple[Any, Any],
    y0: Any,
    params: Mapping[str, Any] | None = None,
    *,
    method: str = "RK45",
    rtol: float = 1e-3,
    atol: float = 1e-6,
    events: Sequence[Event] = (),
) -> BatchResult:
    """Integrate ``k`` independent systems from ``t_span[0]`` to ``t_span[1]``.

    Args:
        rhs: ``rhs(t, y, params)`` for ``t`` of shape ``(k,)`` and ``y`` of shape ``(m, k)``.
        t_span: start and end, scalars or arrays of shape ``(k,)``; the end must not be
            before the start.
        y0: the initial states, shape ``(m, k)``.
        params: per-system arrays of length ``k``, or scalars, passed to ``rhs``.
        method: ``"RK45"`` (the default, as in ``solve_ivp``) or ``"RK23"``.
        rtol: the relative tolerance, as in ``solve_ivp``.
        atol: the absolute tolerance, as in ``solve_ivp``.
        events: ``Event`` objects located on every accepted step.

    Returns:
        The final times and states, the event crossings and the work counts.

    Raises:
        CouplingError: for an unknown method or a step that falls below the minimum.
    """
    batch = _Batch(rhs, t_span[0], t_span[1], y0, params, rtol, atol, method)
    stopped = np.zeros(batch.k, bool)
    logs = [EventLog() for _ in events]
    previous = [event.value(batch.t, batch.y, batch.params) for event in events]
    while True:
        rows = np.flatnonzero((batch.t < batch.t1) & ~stopped)
        if rows.size == 0:
            break
        whole = slice(None) if rows.size == batch.k else rows
        accepted, t_new, y_new, ks = batch.attempt(whole)
        if events:
            rows, t_new, y_new, ks = _keep(accepted, rows, t_new, y_new, ks)
            stop = _locate(batch, events, logs, previous, rows, t_new, y_new, ks)
            stopped[rows[stop]] = True
            accepted = ~stop
        rows, t_new, y_new, f_new = _keep(accepted, rows, t_new, y_new, ks[-1])
        cols = slice(None) if rows.size == batch.k else rows
        batch.t[cols], batch.y[:, cols], batch.f[:, cols] = t_new, y_new, f_new
    return BatchResult(batch.t, batch.y, stopped, [log.close() for log in logs], batch.nfev,
                       batch.nsteps, batch.nrejected)  # fmt: skip


def _advanced(y: np.ndarray, h: np.ndarray, coefficients: np.ndarray, ks: np.ndarray):
    """``y + h * sum_j coefficients[j] * ks[j]``, in place on one new array.

    The operations and their order are scipy's (the sum, times ``h``, plus ``y``), so the
    result is the same; in place, the expression makes one array instead of three.
    """
    out = _combine(coefficients, ks)
    out *= h
    out += y
    return out


def _combine(coefficients: np.ndarray, ks: np.ndarray) -> np.ndarray:
    """``sum_j coefficients[j] * ks[j]`` in one pass.

    ``einsum`` rather than ``tensordot``: no BLAS call, so no thread pool to oversubscribe on
    a busy machine, and the same summation order on every platform.
    """
    return np.einsum("s,s...->...", coefficients, ks)


def _keep(
    mask: np.ndarray, rows: np.ndarray, t: np.ndarray, y: np.ndarray, extra: np.ndarray
):
    """The systems where ``mask`` holds, ``extra`` on its last axis; no copy if all do."""
    if mask.all():
        return rows, t, y, extra
    return rows[mask], t[mask], y[:, mask], extra[..., mask]
