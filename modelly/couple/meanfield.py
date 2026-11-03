"""The mean-field companion: an agent model's ODE limit, run next to it, and the gap.

Many agent models have a deterministic limit as the population grows: the SIR equations for
a well-mixed epidemic, Lotka-Volterra for predators and prey, the Bass equation for adoption.
``Companion(model, MeanField(rhs, observe, names))`` integrates that limit with ``solve_ivp``
from the model's own starting state and, after each of the model's steps, records the
model's aggregate state (``observe``) next to the ODE's. ``gap`` is the largest difference,
which shrinks like ``1 / sqrt(N)`` while sampling noise dominates; ``gap_by_size`` measures it
over population sizes and fits that exponent, to show where the agent model departs from its
limit (small populations, extinctions, network structure) and where it does not::

    from modelly.couple.meanfield import Companion, MeanField, bass

    rates = {"innovation": 0.03, "imitation": 0.38}
    companion = Companion(model, MeanField(bass, lambda m: [m.adoption], ("adopted",), rates))
    for _ in range(100):
        model.step()
        companion.advance(model.scenario.dt)
    companion.gap()
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

type Rhs = Callable[[float, np.ndarray, Mapping[str, Any]], Any]


def sir(t: float, y: np.ndarray, p: Mapping[str, Any]) -> np.ndarray:
    """Shares ``(S, I, R)``: ``S' = -beta S I``, ``I' = beta S I - gamma I``, ``R' = gamma I``."""
    s, i, _ = y
    infection, recovery = p["beta"] * s * i, p["gamma"] * i
    return np.array([-infection, infection - recovery, recovery])


def lotka_volterra(t: float, y: np.ndarray, p: Mapping[str, Any]) -> np.ndarray:
    """Densities ``(prey, predators)``: ``x' = a x - b x y``, ``y' = d b x y - c y``."""
    x, z = y
    eaten = p["b"] * x * z
    return np.array([p["a"] * x - eaten, p["d"] * eaten - p["c"] * z])


def bass(t: float, y: np.ndarray, p: Mapping[str, Any]) -> np.ndarray:
    """Share adopted ``F``: ``F' = (innovation + imitation F) (1 - F)``."""
    return (p["innovation"] + p["imitation"] * y) * (1 - y)


@dataclass(frozen=True)
class MeanField:
    """The ODE limit of a model.

    Attributes:
        rhs: ``rhs(t, y, params)`` for the aggregate state ``y``, as for ``solve_ivp``.
        observe: ``observe(model)``, the model's aggregate state, the same variables.
        names: the variables' names.
        params: passed to ``rhs``.
        rtol, atol: the tolerances of the integration.
    """

    rhs: Rhs
    observe: Callable[[Any], Sequence[float]]
    names: tuple[str, ...]
    params: Mapping[str, Any] = field(default_factory=dict)
    rtol: float = 1e-8
    atol: float = 1e-10


class Companion:
    """A model and its mean-field limit, side by side, from the same starting state."""

    def __init__(self, model: Any, limit: MeanField) -> None:
        """Start the ODE from the model's current aggregate state."""
        self.model, self.limit = model, limit
        start = np.asarray(limit.observe(model), dtype=float)
        self.time = 0.0
        self.times, self.agents, self.ode = [0.0], [start], [start.copy()]

    def advance(self, duration: float) -> None:
        """Integrate the limit over ``duration``; record it next to the model's state.

        Call it after each model step, with the time that step covers.
        """
        from scipy.integrate import solve_ivp  # noqa: PLC0415 - scipy is heavy

        lim = self.limit
        end = self.time + duration
        result = solve_ivp(lim.rhs, (self.time, end), self.ode[-1], args=(lim.params,),
                           rtol=lim.rtol, atol=lim.atol)  # fmt: skip
        self.time = end
        self.times.append(end)
        self.ode.append(result.y[:, -1])
        self.agents.append(np.asarray(lim.observe(self.model), dtype=float))

    def gap(self) -> float:
        """The largest difference between the model and its limit, over times and variables."""
        return float(np.max(np.abs(np.array(self.agents) - np.array(self.ode))))

    def frame(self) -> Any:
        """A DataFrame with each variable twice: ``<name>`` (the model) and ``<name>_limit``."""
        import pandas as pd  # noqa: PLC0415

        agents, ode = np.array(self.agents), np.array(self.ode)
        columns = {name: agents[:, i] for i, name in enumerate(self.limit.names)}
        columns |= {
            f"{name}_limit": ode[:, i] for i, name in enumerate(self.limit.names)
        }
        return pd.DataFrame(columns, index=pd.Index(self.times, name="time"))


@dataclass(frozen=True)
class GapBySize:
    """The mean gap at each population size, and its fitted power of the size."""

    sizes: tuple[int, ...]
    gaps: tuple[float, ...]
    exponent: float


def gap_by_size(
    run: Callable[[int, int], Companion], sizes: Sequence[int], seeds: Sequence[int]
) -> GapBySize:
    """``run(size, seed)`` returns a finished companion; the gaps and their exponent.

    The exponent is the slope of ``log gap`` against ``log size``: about ``-0.5`` while the
    gap is sampling noise, flatter where the model departs from its limit.
    """
    gaps = [float(np.mean([run(n, seed).gap() for seed in seeds])) for n in sizes]
    exponent = float(np.polyfit(np.log(sizes), np.log(gaps), 1)[0])
    return GapBySize(tuple(sizes), tuple(gaps), exponent)
