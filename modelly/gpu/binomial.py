"""Binomial variates from a Philox draw, the same on every backend for the same draw.

Two exact samplers, chosen per element by the mean ``m = count * min(p, 1 - p)``:

* ``m < 10``: inversion. One uniform ``u``; walk the cumulative probabilities
  from ``P(0) = (1 - p) ** count`` (by repeated squaring, multiplications only)
  with the ratio ``P(k) / P(k - 1)`` until they pass ``u``. The walk stops at
  ``m + 10 * sqrt(m (1 - p) + 1)``, beyond which the remaining mass is below
  1e-20 (the bound numpy uses before it restarts).
* ``m >= 10``: BTRS, the transformed rejection with squeeze of Hörmann (1993,
  "The generation of binomial random variates", J. Stat. Comput. Simul. 46),
  the algorithm of ``jax.random.binomial`` and TensorFlow. Rounds draw two
  uniforms for every element still pending; about nine in ten accept at each.

``p > 1/2`` draws ``count - Binomial(count, 1 - p)``. Element ``i`` uses the
uniforms at position ``start + i`` of sub-streams ``0`` (inversion) and
``2r + 1``, ``2r + 2`` (round ``r`` of BTRS), so a batch, a subset or another
device gets the same variates. Only IEEE-exact operations (``+ - * /``,
``sqrt``, comparisons) decide the inversion; BTRS takes logarithms, whose last
bit may differ between numpy, CUDA and XLA. A different last bit changes an
outcome only when a uniform falls within one rounding error of the acceptance
bound, so the results are the same in practice and the same law always.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modelly.gpu.streams import PhiloxDraw

HALF = 0.5
BTRS_MIN_MEAN = 10.0
INVERSION_SPREAD = 10.0
MAX_ROUNDS = 200  # BTRS rounds; reaching it means the uniforms are broken
# BTRS constants, Hörmann (1993), table 1 and algorithm BTRS.
B_INTERCEPT, B_SLOPE = 1.15, 2.53
A_INTERCEPT, A_SLOPE, A_P = -0.0873, 0.0248, 0.01
VR_INTERCEPT, VR_SLOPE = 0.92, 4.2
ALPHA_INTERCEPT, ALPHA_SLOPE = 2.83, 5.1
SQUEEZE_US = 0.07
US_FLOOR = 2.0**-53
MIN_BUCKET = 64  # shortest padded length on backends that compile per shape
DUMMY_COUNT = 2 * BTRS_MIN_MEAN  # with p = 1/2: a fast-accepting stand-in
# Stirling-series correction log(k!) - [(k + 1/2) log(k + 1) - (k + 1) + log(2 pi) / 2]
TAIL_TABLE_SIZE = 10
_HALF_LOG_TWO_PI = HALF * math.log(2 * math.pi)
TAIL_TABLE = tuple(
    math.lgamma(k + 1) - ((k + HALF) * math.log(k + 1) - (k + 1) + _HALF_LOG_TWO_PI)
    for k in range(TAIL_TABLE_SIZE)
)
TAIL_C0, TAIL_C1, TAIL_C2 = 1.0 / 12, 1.0 / 360, 1.0 / 1260


def binomial(draw: PhiloxDraw, count: Any, p: Any, start: int = 0) -> Any:
    """One Binomial(count[i], p[i]) variate per element; ``p`` may be a scalar."""
    backend = draw.backend
    xp = backend.xp
    count = xp.asarray(count).astype(backend.int_dtype)
    p = xp.broadcast_to(xp.asarray(p, dtype=backend.float_dtype), count.shape)
    if not backend.compacts:
        return _padded(draw, count, p, start)
    flip = p > HALF
    q = xp.where(flip, 1 - p, p)
    mean = count * q
    positions = xp.arange(count.shape[0], dtype=xp.uint32) + xp.uint32(start)
    drawn = (count > 0) & (q > 0)
    small, large = drawn & (mean < BTRS_MIN_MEAN), drawn & (mean >= BTRS_MIN_MEAN)
    result = xp.zeros(count.shape, dtype=backend.int_dtype)
    for chosen, sampler in ((small, _inversion), (large, _btrs)):
        rows = xp.nonzero(chosen)[0]
        if rows.shape[0]:
            values = sampler(draw, count[rows], q[rows], positions[rows])
            result = backend.put(result, rows, values)
    return xp.where(flip, count - result, result)


def _padded(draw: PhiloxDraw, count: Any, p: Any, start: int) -> Any:
    """The variates of ``count`` padded with zero counts to a power-of-two length.

    A backend that compiles per shape (JAX) then compiles the samplers once per
    length bucket instead of once per length; the padding rows draw nothing
    and every real row keeps its position.
    """
    xp = draw.backend.xp
    n = int(count.shape[0])
    size = max(MIN_BUCKET, 1 << max(n - 1, 0).bit_length())
    count = xp.concatenate([count, xp.zeros(size - n, dtype=count.dtype)])
    p = xp.concatenate([p, xp.zeros(size - n, dtype=p.dtype)])
    flip = p > HALF
    q = xp.where(flip, 1 - p, p)
    mean = count * q
    positions = xp.arange(size, dtype=xp.uint32) + xp.uint32(start)
    drawn = (count > 0) & (q > 0)
    masks = (drawn & (mean < BTRS_MIN_MEAN), drawn & (mean >= BTRS_MIN_MEAN))
    result = _masked(draw, count, q, positions, masks)
    return xp.where(flip, count - result, result)[:n]


def _masked(draw: PhiloxDraw, count: Any, q: Any, positions: Any, masks: tuple) -> Any:
    """Both samplers over every element, the others given harmless parameters.

    Fixed shapes for backends that compile per shape (JAX); each element still
    draws its own uniforms, so the variates are those of the compacting path.
    """
    xp = draw.backend.xp
    small, large = masks
    few = _inversion(draw, xp.where(small, count, 0), q, positions)
    dummy_n, dummy_q = xp.where(large, count, DUMMY_COUNT), xp.where(large, q, HALF)
    many = _btrs(draw, dummy_n, dummy_q, positions)
    return xp.where(small, few, xp.where(large, many, 0))


def _power(base: Any, exponent: Any, xp: Any) -> Any:
    """``base ** exponent`` for integer exponents, by squaring (multiplications only)."""
    result = xp.ones_like(base)
    while bool((exponent > 0).any()):
        result = xp.where((exponent & 1) == 1, result * base, result)
        base = base * base
        exponent = exponent >> 1
    return result


def _inversion(draw: PhiloxDraw, n: Any, q: Any, positions: Any) -> Any:
    """Sequential search of the cumulative probabilities from one uniform each."""
    xp = draw.backend.xp
    u = draw.random_at(positions, sub=0)
    pmf = _power(1 - q, n, xp)
    cdf, ratio = pmf, q / (1 - q)
    bound = xp.minimum(
        n, xp.floor(n * q + INVERSION_SPREAD * xp.sqrt(n * q * (1 - q) + 1))
    )
    k = xp.zeros(n.shape, dtype=n.dtype)
    active = u >= cdf
    while bool(active.any()):
        k = k + active.astype(n.dtype)
        step = (n - k + 1) / xp.maximum(k, 1)
        pmf = xp.where(active, pmf * step * ratio, pmf)
        cdf = xp.where(active, cdf + pmf, cdf)
        active = active & (u >= cdf) & (k < bound)
    return k


def _tail(k: Any, xp: Any) -> Any:
    """The Stirling correction of ``log(k!)``: tabulated below 10, a series above."""
    table = xp.asarray(TAIL_TABLE, dtype=k.dtype)
    small = table[xp.clip(k, 0, TAIL_TABLE_SIZE - 1).astype(xp.int32)]
    square = (k + 1) * (k + 1)
    series = (TAIL_C0 - (TAIL_C1 - TAIL_C2 / square) / square) / (k + 1)
    return xp.where(k < TAIL_TABLE_SIZE, small, series)


def _constants(n: Any, q: Any, xp: Any) -> dict[str, Any]:
    """The per-element constants of BTRS."""
    spread = xp.sqrt(n * q * (1 - q))
    b = B_INTERCEPT + B_SLOPE * spread
    r = q / (1 - q)
    m = xp.floor((n + 1) * q)
    log_mode = (m + HALF) * xp.log((m + 1) / (r * (n - m + 1)))
    return {
        "b": b,
        "a": A_INTERCEPT + A_SLOPE * b + A_P * q,
        "c": n * q + HALF,
        "vr": VR_INTERCEPT - VR_SLOPE / b,
        "alpha": (ALPHA_INTERCEPT + ALPHA_SLOPE / b) * spread,
        "r": r,
        "m": m,
        "mode": log_mode + _tail(m, xp) + _tail(n - m, xp),
    }


def _btrs_round(u: Any, v: Any, n: Any, c: dict[str, Any], xp: Any) -> tuple[Any, Any]:
    """One BTRS proposal per element: the candidate and whether it is accepted."""
    us = xp.maximum(HALF - xp.abs(u), US_FLOOR)
    k = xp.floor((2 * c["a"] / us + c["b"]) * u + c["c"])
    inside = (k >= 0) & (k <= n)
    squeeze = (us >= SQUEEZE_US) & (v <= c["vr"])
    k = xp.clip(k, 0, n)
    log_v = xp.log(v * c["alpha"] / (c["a"] / (us * us) + c["b"]))
    bound = (
        c["mode"]
        + (n + 1) * xp.log((n - c["m"] + 1) / (n - k + 1))
        + (k + HALF) * xp.log(c["r"] * (n - k + 1) / (k + 1))
        - _tail(k, xp)
        - _tail(n - k, xp)
    )
    return k, inside & (squeeze | (log_v <= bound))


def _btrs(draw: PhiloxDraw, n: Any, q: Any, positions: Any) -> Any:
    """Rejection rounds over the pending elements until every one has accepted."""
    backend = draw.backend
    xp = backend.xp
    n = n.astype(backend.float_dtype)
    constants = _constants(n, q, xp)
    result = xp.zeros(n.shape, dtype=backend.int_dtype)
    pending = (
        xp.arange(n.shape[0]) if backend.compacts else xp.ones(n.shape, dtype=bool)
    )
    for round_ in range(MAX_ROUNDS):
        result, pending = _btrs_step(
            draw, (n, positions, constants), round_, result, pending
        )
        if _done(pending, backend.compacts):
            return result
    raise RuntimeError(
        "binomial rejection did not converge: the uniforms are not uniform"
    )


def _done(pending: Any, compacts: bool) -> bool:
    """Whether no element is pending (an empty index array, or an all-False mask)."""
    return pending.shape[0] == 0 if compacts else not bool(pending.any())


def _btrs_step(draw: PhiloxDraw, data: tuple, round_: int, result: Any, pending: Any):
    """Round ``round_`` for the pending elements (an index array, or a mask)."""
    backend = draw.backend
    xp = backend.xp
    n, positions, constants = data
    rows = pending if backend.compacts else slice(None)
    sub = 2 * round_ + 1
    u = draw.random_at(positions[rows], sub=sub) - HALF
    v = 1 - draw.random_at(positions[rows], sub=sub + 1)
    own = {name: value[rows] for name, value in constants.items()}
    k, accept = _btrs_round(u, v, n[rows], own, xp)
    k = k.astype(result.dtype)
    if backend.compacts:
        return backend.put(result, pending[accept], k[accept]), pending[~accept]
    newly = pending & accept
    return xp.where(newly, k, result), pending & ~accept
