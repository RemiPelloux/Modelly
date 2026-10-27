"""Observation operators: what a model would report if it were observed like the world.

An operator names each observed quantity and how to read it from a model::

    observe = ObservationOperator(
        cases=lambda m: m.new_cases,
        hospital=lambda m: m.count("hospitalised"),
    )
    observe(model)                      # {"cases": 41.0, "hospital": 7.0}
    observe.residuals(model, obs)       # observed minus modelled, for the quantities obs has

``log_likelihood`` scores a model against an observation under independent
Gaussian errors; the particle filter weights replicates with it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from modelly.stream.sources import Observation

LOG_2PI = math.log(2 * math.pi)


class ObservationOperator:
    """Maps a model to the quantities an observation reports."""

    def __init__(self, **quantities: Callable[[Any], float]) -> None:
        """One callable per observed quantity, taking the model."""
        if not quantities:
            raise ValueError("an observation operator needs at least one quantity")
        bad = [name for name, read in quantities.items() if not callable(read)]
        if bad:
            raise TypeError(f"quantities must be callables of the model: {bad}")
        self._quantities = dict(quantities)

    @property
    def names(self) -> tuple[str, ...]:
        """The observed quantities, in declaration order."""
        return tuple(self._quantities)

    def __call__(self, model: Any) -> dict[str, float]:
        """Every quantity, read from ``model``."""
        return {name: float(read(model)) for name, read in self._quantities.items()}

    def residuals(self, model: Any, observation: Observation) -> dict[str, float]:
        """Observed minus modelled, for the quantities both the operator and ``observation`` have."""
        shared = [n for n in self._quantities if n in observation.values]
        return {
            n: observation.values[n] - float(self._quantities[n](model)) for n in shared
        }

    def log_likelihood(
        self, model: Any, observation: Observation, sd: float | Mapping[str, float]
    ) -> float:
        """Log density of ``observation`` given ``model`` under independent Gaussian errors.

        ``sd`` is one standard deviation for every quantity, or one per quantity.
        Quantities the observation lacks do not count.
        """
        total = 0.0
        for name, residual in self.residuals(model, observation).items():
            scale = float(sd[name] if isinstance(sd, Mapping) else sd)
            if scale <= 0:
                raise ValueError(
                    f"standard deviation of {name!r} must be positive, got {scale}"
                )
            total -= 0.5 * (LOG_2PI + 2 * math.log(scale) + (residual / scale) ** 2)
        return total
