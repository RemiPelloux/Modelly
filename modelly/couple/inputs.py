"""Inputs that change inside a step: ``Forcing`` (a function of time) and ``Series`` (a table).

A parameter of ``solve_batch`` or ``AgentODE`` given as an ``Input`` is evaluated at every
stage's time instead of being held over the step, so a temperature that varies through the
day, a dosing schedule or a measured series drives each system at the times its own steps
land on. ``rhs`` and the events' conditions receive the evaluated value, never the ``Input``.

    from modelly.couple import Forcing, Series, solve_batch

    daylight = Forcing(lambda t: np.maximum(np.sin(2 * np.pi * t), 0.0))
    rainfall = Series([0.0, 1.0, 2.0], [0.0, 4.0, 1.0])  # linear between the points
    solve_batch(rhs, (0.0, 2.0), y0, {"light": daylight, "rain": rainfall})

A ``Series`` with two-dimensional values gives every system its own series (one column per
system), and is cut with the systems like any per-system parameter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

KINDS = ("linear", "previous")


class Input:
    """A parameter that is a function of time; subclasses define ``__call__`` and ``cut``."""

    def __call__(self, t: np.ndarray) -> Any:
        """The value at the times ``t`` (one per system)."""
        raise NotImplementedError

    def cut(self, rows: np.ndarray, k: int) -> Input:
        """The input for the systems ``rows`` among ``k``; itself when it is shared."""
        return self


@dataclass(frozen=True)
class Forcing(Input):
    """``function(t)``, called with each system's time, shape ``(systems,)``.

    The result is a scalar or one value per system. The function must be a module-level
    function for a model holding it to be saved.

    Example:
        >>> Forcing(lambda t: 2 * t)(np.array([0.5, 1.0])).tolist()
        [1.0, 2.0]
    """

    function: Callable[[np.ndarray], Any]

    def __call__(self, t: np.ndarray) -> Any:
        """The function at ``t``."""
        return self.function(t)


@dataclass(frozen=True)
class Series(Input):
    """Values at given times, read between them linearly or as the last value.

    Attributes:
        times: increasing times, shape ``(n,)``.
        values: shape ``(n,)`` for one series shared by every system, or ``(n, systems)``
            for one series per system.
        kind: ``"linear"`` interpolation, or ``"previous"`` to hold each value until the next
            time. Before the first time and after the last the end values hold.

    Example:
        >>> Series([0.0, 2.0], [0.0, 10.0])(np.array([0.5, 3.0])).tolist()
        [2.5, 10.0]
    """

    times: Any
    values: Any
    kind: str = "linear"

    def __post_init__(self) -> None:
        """Check the table; store float arrays."""
        times = np.asarray(self.times, dtype=float)
        values = np.asarray(self.values, dtype=float)
        if times.ndim != 1 or times.size < 1 or np.any(np.diff(times) <= 0):
            raise ValueError("Series times must be a non-empty increasing 1-D sequence")
        if values.ndim not in (1, 2) or values.shape[0] != times.size:
            raise ValueError(
                f"Series values need {times.size} rows (one per time), not {values.shape}"
            )
        if self.kind not in KINDS:
            raise ValueError(f"Series kind is one of {KINDS}, not {self.kind!r}")
        object.__setattr__(self, "times", times)
        object.__setattr__(self, "values", values)

    def __call__(self, t: np.ndarray) -> np.ndarray:
        """The series at ``t``: one value per system."""
        t = np.asarray(t, dtype=float)
        values = self._columns(t)
        n = self.times.size
        if self.kind == "previous" or n == 1:
            i = np.clip(np.searchsorted(self.times, t, side="right") - 1, 0, n - 1)
            return values[i, np.arange(t.size)] if values.ndim == 2 else values[i]
        i = np.clip(np.searchsorted(self.times, t, side="right") - 1, 0, n - 2)
        lo, hi = self.times[i], self.times[i + 1]
        w = np.clip((t - lo) / (hi - lo), 0.0, 1.0)
        if values.ndim == 2:
            cols = np.arange(t.size)
            return values[i, cols] * (1 - w) + values[i + 1, cols] * w
        return values[i] * (1 - w) + values[i + 1] * w

    def _columns(self, t: np.ndarray) -> np.ndarray:
        """The values, checked to have one column per time given."""
        if self.values.ndim == 2 and self.values.shape[1] != t.size:
            raise ValueError(
                f"a Series with {self.values.shape[1]} columns read for {t.size} systems"
            )
        return self.values

    def cut(self, rows: np.ndarray, k: int) -> Series:
        """The series of the systems ``rows``: its columns when there is one per system."""
        if self.values.ndim == 2 and self.values.shape[1] == k:
            return Series(self.times, self.values[:, rows], self.kind)
        return self


def has_inputs(params: Mapping[str, Any]) -> bool:
    """Whether any parameter is an ``Input``."""
    return any(isinstance(value, Input) for value in params.values())


def evaluated(params: Mapping[str, Any], t: np.ndarray) -> Mapping[str, Any]:
    """``params`` with every ``Input`` replaced by its value at ``t``."""
    if not has_inputs(params):
        return params
    return {
        name: value(t) if isinstance(value, Input) else value
        for name, value in params.items()
    }
