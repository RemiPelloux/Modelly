"""The Runge-Kutta pairs of ``solve_batch``: scipy's tableaux and the stage arithmetic."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from modelly.couple.schedule import CouplingError

METHODS = ("RK45", "RK23")


@dataclass(frozen=True)
class Tableau:
    """A Runge-Kutta pair as scipy defines it."""

    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    E: np.ndarray
    P: np.ndarray
    order: int
    exponent: float

    @classmethod
    def of(cls, method: str) -> Tableau:
        """The tableau of scipy's ``RK45`` or ``RK23``."""
        from scipy import integrate  # noqa: PLC0415 - scipy is heavy

        if method not in METHODS:
            raise CouplingError(f"solve_batch supports {METHODS}, not {method!r}")
        rk = getattr(integrate, method)
        order = rk.error_estimator_order
        return cls(rk.A, rk.B, rk.C, rk.E, rk.P, order, -1 / (order + 1))


def advanced(y: np.ndarray, h: np.ndarray, coefficients: np.ndarray, ks: np.ndarray):
    """``y + h * sum_j coefficients[j] * ks[j]``, in place on one new array.

    The operations and their order are scipy's (the sum, times ``h``, plus ``y``), so the
    result is the same; in place, the expression makes one array instead of three.
    """
    out = combine(coefficients, ks)
    out *= h
    out += y
    return out


def combine(coefficients: np.ndarray, ks: np.ndarray) -> np.ndarray:
    """``sum_j coefficients[j] * ks[j]`` in one pass.

    ``einsum`` rather than ``tensordot``: no BLAS call, so no thread pool to oversubscribe on
    a busy machine, and the same summation order on every platform.
    """
    return np.einsum("s,s...->...", coefficients, ks)
