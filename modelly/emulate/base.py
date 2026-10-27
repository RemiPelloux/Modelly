"""What every emulator shares: named outputs, predictions on the unit cube, accuracy, data.

An emulator is fitted to ``units[point, dimension]`` (points of the unit cube of
a :class:`~modelly.experiments.ScenarioSpace`, as designs draw them) and
``values[point, output]``. ``predict`` returns the mean and standard deviation of
every output; ``select`` keeps one output, and an emulator with one output and
its ``space`` stands in for the model in :mod:`modelly.sensitivity`.
:meth:`Emulator.from_results` trains one on the runs of an
:class:`~modelly.experiments.Experiment`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

from modelly.experiments.space import Choice, Range, ScenarioSpace
from modelly.experiments.store import Results
from modelly.sensitivity.study import STATISTICS

OUTPUT_PREFIX = "y"
HALF = 0.5  # a level is represented by the centre of its share of [0, 1)
POINT = "point"
REPLICATE = "replicate"
STEP = "step"
Statistic = str | Callable[[np.ndarray], float]


def output_names(count: int, names: Sequence[str] | None = None) -> list[str]:
    """``names`` checked against ``count`` outputs, or ``y0, y1, ...``."""
    if names is None:
        return [f"{OUTPUT_PREFIX}{index}" for index in range(count)]
    if len(names) != count:
        raise ValueError(f"{count} outputs but {len(names)} names")
    return list(names)


def as_columns(values: np.ndarray) -> np.ndarray:
    """``values`` as a float array ``[point, output]`` (one column for a 1-d array)."""
    values = np.asarray(values, float)
    return values[:, None] if values.ndim == 1 else values


class Emulator:
    """Base class: a fit of several outputs over the unit cube.

    Subclasses implement ``fit``, ``predict`` and ``_subset``.

    Attributes:
        names: the outputs, in column order.
        space: the space whose unit cube the inputs are (``None`` if not known).
    """

    names: list[str]
    space: ScenarioSpace | None

    @classmethod
    def fit(
        cls,
        units: np.ndarray,
        values: np.ndarray,
        names: Sequence[str] | None = None,
        **options: Any,
    ) -> Emulator:
        """Fit to ``units[point, dimension]`` and ``values[point, output]``."""
        raise NotImplementedError

    def predict(self, units: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The predicted mean and standard deviation, each ``[point, output]``."""
        raise NotImplementedError

    def _subset(self, index: int) -> Emulator:
        """An emulator of the output in column ``index`` only."""
        raise NotImplementedError

    def select(self, name: str) -> Emulator:
        """The emulator of one output (for the sensitivity methods)."""
        if name not in self.names:
            raise KeyError(f"no output {name!r}; the outputs are {self.names}")
        return self._subset(self.names.index(name))

    def predict_unit(self, units: np.ndarray) -> np.ndarray:
        """The predicted mean of the only output (the sensitivity methods call this)."""
        if len(self.names) != 1:
            raise ValueError(f"{len(self.names)} outputs: select(name) one of them")
        return self.predict(np.atleast_2d(units))[0][:, 0]

    def score(self, units: np.ndarray, values: np.ndarray) -> dict[str, float]:
        """The normalised root-mean-square error of every output on test data.

        The error is divided by the test values' standard deviation: 0 is
        perfect, 1 is no better than predicting their mean.
        """
        values = as_columns(values)
        error = self.predict(units)[0] - values
        spread = values.std(axis=0)
        rmse = np.sqrt(np.mean(error**2, axis=0))
        ratio = np.divide(rmse, spread, out=np.zeros_like(rmse), where=spread > 0)
        return {name: float(value) for name, value in zip(self.names, ratio)}

    @classmethod
    def from_results(
        cls,
        results: Results,
        space: ScenarioSpace,
        outputs: Mapping[str, Statistic] | Sequence[str],
        **options: Any,
    ) -> Emulator:
        """Fit to an experiment's runs: one point per design point, replicates averaged.

        ``outputs`` lists recorded outputs (each run's last value) or maps each to
        a statistic of its series (``"last"``, ``"max"``, ``"mean"``... or a
        function); ``options`` go to ``fit``.
        """
        units, values = training_data(results, space, outputs)
        return cls.fit(units, values, list(outputs), space=space, **options)


def unit_of(space: ScenarioSpace, params: Mapping[str, Any]) -> np.ndarray:
    """The unit-cube position of ``params``: the inverse of ``space.point``.

    A level of an integer range or a choice maps to the centre of its share.
    """
    return np.array(
        [_unit(dim, params[name]) for name, dim in space.dimensions.items()]
    )


def _unit(dim: Range | Choice, value: Any) -> float:
    """The position of ``value`` in ``[0, 1)`` along one dimension."""
    if isinstance(dim, Choice):
        return (dim.values.index(value) + HALF) / len(dim.values)
    if dim.integer:
        width = int(dim.high) - int(dim.low) + 1
        return (int(value) - int(dim.low) + HALF) / width
    if dim.log:
        low, high = math.log(dim.low), math.log(dim.high)
        return (math.log(value) - low) / (high - low)
    return (float(value) - dim.low) / (dim.high - dim.low)


def reducer(statistic: Statistic) -> Callable[[np.ndarray], float]:
    """The function a statistic names (``"last"``, ``"max"``...), or the function given."""
    if isinstance(statistic, str):
        if statistic not in STATISTICS:
            raise ValueError(
                f"statistic must be a function or one of {sorted(STATISTICS)}"
            )
        return STATISTICS[statistic]
    return statistic


def training_data(
    results: Results,
    space: ScenarioSpace,
    outputs: Mapping[str, Statistic] | Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """``(units, values)`` of an experiment's runs, one row per design point."""
    statistics = (
        dict(outputs)
        if isinstance(outputs, Mapping)
        else dict.fromkeys(outputs, "last")
    )
    reducers = {name: reducer(s) for name, s in statistics.items()}
    frame = results.df()
    units, values = [], []
    for _, point in frame.groupby(POINT, sort=True):
        first = point.iloc[0]
        units.append(unit_of(space, {name: first[name] for name in space.dimensions}))
        runs = [run.sort_values(STEP) for _, run in point.groupby(REPLICATE)]
        values.append(
            [
                np.mean([f(run[n].to_numpy(float)) for run in runs])
                for n, f in reducers.items()
            ]
        )
    return np.array(units), np.array(values, float)
