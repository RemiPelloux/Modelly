"""Targets: what a calibration compares between the model and the data.

A :class:`Target` names an output the model records every step (an attribute,
a method or a module-level function of the model, the same things an
``Experiment`` output or a ``DataCollector`` model reporter reads) and the
observed values it should match::

    Target("infected", observed=cases)                         # the whole series
    Target("infected", observed=[412.0], summary=peak)         # one statistic
    Target("prey", observed=counts, distance=distance.mae, weight=0.5)

Without ``summary`` the observed series is matched to the end of the simulated
one: ``observed[-1]`` against the value after the last step. With ``summary``,
``summary(series)`` of every replicate is compared to ``observed``. Replicates
are averaged before the distance is taken.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.calibrate.distance import DISTANCES, Distance, rmse
from modelly.experiments.tasks import reference

Summary = Callable[[np.ndarray], Any]


@dataclass(frozen=True, eq=False)
class Target:
    """One observed quantity and how to measure the model's distance to it.

    Args:
        name: the column name; also the output read unless ``output`` is given.
        observed: the observed series, or the observed summary statistics.
        distance: a function ``(simulated, observed) -> float`` or the name of
            a built-in (``"rmse"``, ``"mae"``, ``"euclidean"``, ``"wasserstein"``).
        weight: the factor of this target's distance in the total.
        summary: a function of one simulated series (a 1-d array, step 0 first)
            returning the statistics compared to ``observed``.
        output: what to record, when it is not ``name``: an attribute path or a
            module-level function of the model.
    """

    name: str
    observed: Any
    distance: Distance | str = rmse
    weight: float = 1.0
    summary: Summary | None = None
    output: str | Callable[[Any], Any] | None = None

    def __post_init__(self) -> None:
        """Store ``observed`` as a float array and resolve a distance name."""
        observed = np.atleast_1d(np.asarray(self.observed, dtype=float))
        object.__setattr__(self, "observed", observed)
        if isinstance(self.distance, str):
            if self.distance not in DISTANCES:
                raise ValueError(
                    f"distance must be a function or one of {sorted(DISTANCES)}"
                )
            object.__setattr__(self, "distance", DISTANCES[self.distance])
        if self.weight < 0:
            raise ValueError(f"target {self.name!r} needs weight >= 0")

    @property
    def spec(self) -> str:
        """The output as an experiment reads it: an attribute path or a reference."""
        if self.output is None:
            return self.name
        return self.output if isinstance(self.output, str) else reference(self.output)

    def check_length(self, steps: int) -> None:
        """Refuse an observed series longer than a run (``steps + 1`` values)."""
        if self.summary is None and len(self.observed) > steps + 1:
            raise ValueError(
                f"target {self.name!r} has {len(self.observed)} observed values; "
                f"a run of {steps} steps records {steps + 1}"
            )

    def replicate_values(self, series: np.ndarray) -> np.ndarray:
        """What is compared, per replicate: ``array[replicate, value]``."""
        if self.summary is None:
            return series[:, series.shape[1] - len(self.observed) :]
        rows = [np.atleast_1d(np.asarray(self.summary(row), float)) for row in series]
        return np.vstack(rows)

    def simulated(self, series: np.ndarray) -> np.ndarray:
        """The replicate mean of what is compared, from ``series[replicate, step]``."""
        return self.replicate_values(series).mean(axis=0)

    def score(self, simulated: np.ndarray) -> float:
        """This target's weighted distance for one simulated summary."""
        return self.weight * float(self.distance(simulated, self.observed))


def total_distance(
    targets: Sequence[Target], simulated: dict[str, np.ndarray]
) -> float:
    """The sum of the targets' weighted distances."""
    return sum(target.score(simulated[target.name]) for target in targets)
