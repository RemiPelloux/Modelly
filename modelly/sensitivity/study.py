"""What a sensitivity analysis evaluates: a model's output, a function, or an emulator.

A :class:`Study` turns points of the unit cube (one coordinate per varying
parameter of a :class:`~modelly.experiments.ScenarioSpace`) into one number
each:

* a Model class (or ``"module:Class"`` reference) is run through the
  experiment executors (:mod:`modelly.calibrate.simulator`); ``output`` names
  what it records every step and ``statistic`` reduces each run's series to
  one value (``"last"``, ``"max"``, ``"min"``, ``"mean"``, ``"sum"`` or a
  function), averaged over the replicates;
* a plain function is called with the parameters as keyword arguments;
* an :class:`~modelly.sensitivity.emulator.Emulator` predicts all points at once.
"""

from __future__ import annotations

import inspect
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from modelly.calibrate.simulator import (
    DEFAULT_EXECUTOR,
    Batch,
    Execution,
    Simulator,
    Stream,
    generator,
)
from modelly.core.model import Model
from modelly.experiments.space import ScenarioSpace
from modelly.experiments.tasks import reference

DEFAULT_STEPS = 100
OUTPUT_COLUMN = "sensitivity_output"
STATISTICS: dict[str, Callable[[np.ndarray], float]] = {
    "last": lambda series: series[-1],
    "max": np.max,
    "min": np.min,
    "mean": np.mean,
    "sum": np.sum,
}


def is_model(model: Any) -> bool:
    """Whether ``model`` is a Model class or a ``module:Class`` reference to one."""
    return isinstance(model, str) or (
        inspect.isclass(model) and issubclass(model, Model)
    )


@dataclass
class Study:
    """The quantity analysed and where it is computed.

    Args:
        model: a Model class or reference, a function of the parameters, or an Emulator.
        space: the parameter space; its ranges and choices are the inputs.
        output: for a model, the attribute, method or function of the model to record.
        seed: the root of the design, the bootstrap and the runs' seeds.
        steps: steps per run (models only).
        replicates: runs per point, averaged (models only).
        statistic: how a run's series becomes one number (models only).
        store: the folder of the runs (a temporary one by default).
        executor: where the runs execute (any experiment executor).
        max_parallel: the most runs at once.
        options: the executor's options.
    """

    model: Any
    space: ScenarioSpace
    output: str | Callable[[Any], Any] | None = None
    seed: int = 0
    steps: int = DEFAULT_STEPS
    replicates: int = 1
    statistic: str | Callable[[np.ndarray], float] = "last"
    store: str | Path | None = None
    executor: Any = DEFAULT_EXECUTOR
    max_parallel: int | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Check the space and, for a model, the output and statistic."""
        if not self.space.dimensions:
            raise ValueError("the space has no range or choice to analyse")
        if is_model(self.model) and self.output is None:
            raise ValueError("a model needs output= (what to record every step)")
        if isinstance(self.statistic, str) and self.statistic not in STATISTICS:
            raise ValueError(
                f"statistic must be a function or one of {sorted(STATISTICS)}"
            )
        space = getattr(self.model, "space", None)
        if space is not None and space != self.space:
            raise ValueError("the emulator was fitted over another space")
        self._temporary: tempfile.TemporaryDirectory | None = None

    @property
    def names(self) -> list[str]:
        """The analysed parameters, in the space's order."""
        return list(self.space.dimensions)

    def rng(self, stream: Stream, key: int) -> np.random.Generator:
        """The generator of one stream of this study's seed."""
        return generator(self.seed, stream, key)

    def evaluate(self, units: np.ndarray, key: int) -> np.ndarray:
        """One output value per row of ``units``; ``key`` names the batch of runs."""
        units = np.atleast_2d(np.asarray(units, float))
        if hasattr(self.model, "predict_unit"):
            return np.asarray(self.model.predict_unit(units), float)
        points = [self.space.point(row) for row in units]
        if not is_model(self.model):
            return np.array([float(self.model(**point)) for point in points])
        return self._simulate(points, key)

    def _simulate(self, points: list[dict[str, Any]], key: int) -> np.ndarray:
        """Run the model at ``points``; the replicate mean of the statistic."""
        if self.store is None and self._temporary is None:
            self._temporary = tempfile.TemporaryDirectory(prefix="modelly-sensitivity-")
        root = Path(self.store).resolve() if self.store else Path(self._temporary.name)
        model = self.model if isinstance(self.model, str) else reference(self.model)
        output = self.output if isinstance(self.output, str) else reference(self.output)
        simulator = Simulator(
            model, {OUTPUT_COLUMN: output}, self.steps, self.replicates, self.seed, root
        )
        execution = Execution(self.executor, self.max_parallel, self.options)
        results = simulator.run(Batch((key,), points), execution)
        reduce = STATISTICS.get(self.statistic, self.statistic)
        return np.array(
            [
                np.mean([reduce(row) for row in result[OUTPUT_COLUMN]])
                for result in results
            ]
        )
