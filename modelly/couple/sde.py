"""Stochastic differential equations for many independent systems at once.

``solve_sde_batch`` integrates ``k`` systems of ``m`` Ito equations with diagonal noise,

    dy = drift(t, y, params) dt + diffusion(t, y, params) dW,

``y`` of shape ``(m, k)``, each component driven by its own Wiener process, on a fixed step
``dt``. Two schemes:

* ``"euler"``: Euler-Maruyama, ``y + a dt + b dW``; strong order one half.
* ``"milstein"``: the derivative-free Milstein scheme of Kloeden and Platen (Sec. 11.1),
  ``y + a dt + b dW + (b(y + b sqrt(dt)) - b(y)) (dW**2 - dt) / (2 sqrt(dt))``; strong
  order one for diagonal noise, with no derivative of ``diffusion`` to write.

The increments are drawn from the generator given (a model's ``rng``, so a run is a function
of its seed and a saved model resumes the same stream), ``dW = sqrt(dt) * N(0, 1)``, one array
of shape ``(m, k)`` per step; or they are passed in (``noise=``), to drive several
schemes or step sizes with one Brownian path, as a convergence study does.

References:
    Kloeden, P. E. and Platen, E. (1992). Numerical Solution of Stochastic Differential
    Equations. Springer.

    Higham, D. J. (2001). An algorithmic introduction to numerical simulation of stochastic
    differential equations. SIAM Review, 43(3), 525-546.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.couple.inputs import evaluated
from modelly.couple.schedule import CouplingError

SCHEMES = ("euler", "milstein")

type Coefficient = Callable[[np.ndarray, np.ndarray, Mapping[str, Any]], Any]


@dataclass
class SDEResult:
    """What ``solve_sde_batch`` returns.

    Attributes:
        t: the times of the steps, shape ``(steps + 1,)``.
        y: the final states, shape ``(m, k)``.
        path: with ``keep_path=True``, the states at every time, ``(steps + 1, m, k)``.
    """

    t: np.ndarray
    y: np.ndarray
    path: np.ndarray | None = None


def steps_of(t0: float, t1: float, dt: float) -> int:
    """The number of steps of size ``dt`` from ``t0`` to ``t1`` (the last may be shorter)."""
    if dt <= 0:
        raise CouplingError(f"the SDE step must be positive, not {dt}")
    return max(1, int(np.ceil((t1 - t0) / dt - 1e-12)))


def increments(
    rng: np.random.Generator, shape: tuple[int, int], times: np.ndarray
) -> np.ndarray:
    """Wiener increments over ``times``, shape ``(steps, m, k)``, from ``rng``."""
    root = np.sqrt(np.diff(times))[:, None, None]
    return rng.standard_normal((times.size - 1, *shape)) * root


def _call(f: Coefficient, t: float, y: np.ndarray, params: Mapping[str, Any]):
    """A coefficient at one time for every system, broadcast to ``y``'s shape."""
    times = np.full(y.shape[1], t)
    return np.broadcast_to(
        np.asarray(f(times, y, evaluated(params, times)), float), y.shape
    )


def _step(scheme, drift, diffusion, t, y, h, dw, params) -> np.ndarray:
    """One step of ``scheme`` from ``(t, y)`` over ``h`` with increments ``dw``."""
    a, b = _call(drift, t, y, params), _call(diffusion, t, y, params)
    new = y + a * h + b * dw
    if scheme == "milstein":
        root = np.sqrt(h)
        support = _call(diffusion, t, y + b * root, params)
        new += (support - b) * (dw * dw - h) / (2.0 * root)
    return new


def solve_sde_batch(
    drift: Coefficient,
    diffusion: Coefficient,
    t_span: tuple[float, float],
    y0: Any,
    params: Mapping[str, Any] | None = None,
    *,
    dt: float,
    rng: np.random.Generator | None = None,
    scheme: str = "euler",
    noise: np.ndarray | None = None,
    keep_path: bool = False,
) -> SDEResult:
    """Integrate ``k`` independent SDE systems on a fixed step.

    Args:
        drift: ``a(t, y, params)``, shape ``(m, k)`` (or broadcastable to it).
        diffusion: ``b(t, y, params)``, the noise of each component (diagonal noise).
        t_span: start and end times, shared by every system.
        y0: the initial states, shape ``(m, k)``.
        params: per-system arrays, scalars or inputs (``modelly.couple.inputs``).
        dt: the step; the last step ends at ``t_span[1]`` exactly.
        rng: the generator the increments are drawn from; needed unless ``noise``.
        scheme: ``"euler"`` (Euler-Maruyama) or ``"milstein"``.
        noise: the Wiener increments, shape ``(steps, m, k)``, instead of drawing them.
        keep_path: keep the state at every step.

    Raises:
        CouplingError: for an unknown scheme, a step that is not positive, increments of
            the wrong shape, or neither a generator nor ``noise``.
    """
    if scheme not in SCHEMES:
        raise CouplingError(f"solve_sde_batch supports {SCHEMES}, not {scheme!r}")
    y = np.array(y0, dtype=float, ndmin=2)
    t0, t1 = float(t_span[0]), float(t_span[1])
    times = np.minimum(t0 + dt * np.arange(steps_of(t0, t1, dt) + 1), t1)
    dws = _increments(noise, rng, y.shape, times)
    path = [y.copy()] if keep_path else None
    params = dict(params or {})
    for i in range(times.size - 1):
        y = _step(
            scheme,
            drift,
            diffusion,
            times[i],
            y,
            times[i + 1] - times[i],
            dws[i],
            params,
        )
        if path is not None:
            path.append(y.copy())
    return SDEResult(times, y, np.array(path) if path is not None else None)


def _increments(given, rng, shape, times) -> np.ndarray:
    """The increments passed in, checked, or drawn from ``rng``."""
    if given is None:
        if rng is None:
            raise CouplingError("solve_sde_batch needs rng= or noise=")
        return increments(rng, shape, times)
    given = np.asarray(given, dtype=float)
    if given.shape != (times.size - 1, *shape):
        raise CouplingError(
            f"increments of shape {given.shape}, expected {(times.size - 1, *shape)}"
        )
    return given


def coarsen(dws: np.ndarray, factor: int) -> np.ndarray:
    """The increments of a path on a step ``factor`` times longer (sums of blocks)."""
    steps = dws.shape[0]
    if steps % factor:
        raise ValueError(f"{steps} steps do not split into blocks of {factor}")
    return dws.reshape(steps // factor, factor, *dws.shape[1:]).sum(axis=1)
