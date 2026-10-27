"""What an emulator learns: the outputs of a model (or a function) at points of a space.

A :class:`Simulation` turns rows of the unit cube of a
:class:`~modelly.experiments.ScenarioSpace` into ``values[point, output]``:

* a Model class (or ``"module:Class"`` reference) is run through the experiment
  executors (:mod:`modelly.calibrate.simulator`), each batch of runs written to
  a Parquet store; every output is something the model records each step,
  reduced to one number per run by a statistic and averaged over replicates::

      Simulation(Epidemic, space, {"peak": ("infected", "max"), "size": "recovered"})

* a plain function is called with the parameters as keyword arguments and
  returns one number, a sequence, or a mapping ``{output: value}``.

Run seeds follow the experiment discipline: a batch's seeds depend only on the
simulation's ``seed`` and the batch key, never on the executor. With
``common=True`` every point runs with the same replicate seeds (common random
numbers), which makes a stochastic model's output a smoother function of its
parameters.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from modelly.calibrate.simulator import DEFAULT_EXECUTOR, Batch, Execution, Simulator
from modelly.emulate.base import Statistic, reducer
from modelly.experiments.scratch import scratch_folder
from modelly.experiments.space import ScenarioSpace
from modelly.experiments.tasks import reference
from modelly.sensitivity.study import is_model

DEFAULT_STEPS = 100
DEFAULT_OUTPUT = "output"
PAIR = 2  # an (output, statistic) pair
Outputs = Mapping[str, Any] | Sequence[str]


def _output_specs(outputs: Outputs) -> dict[str, tuple[Any, Statistic]]:
    """Every output as ``name -> (what the model records, statistic)``."""
    if not isinstance(outputs, Mapping):
        return {name: (name, "last") for name in outputs}
    specs = {}
    for name, spec in outputs.items():
        pair = isinstance(spec, tuple) and len(spec) == PAIR
        specs[name] = spec if pair else (spec, "last")
    return specs


@dataclass
class Simulation:
    """A model or function and the outputs an emulator learns.

    Args:
        model: a Model class or reference, or a function of the parameters.
        space: the parameter space; its ranges and choices are the inputs.
        outputs: for a model, a list of recorded outputs (each run's last
            value) or ``{name: output}`` / ``{name: (output, statistic)}``,
            the statistic one of ``"last"``, ``"max"``, ``"min"``, ``"mean"``,
            ``"sum"`` or a function of the series; for a function, its outputs'
            names (one output named ``"output"`` by default).
        seed: the root of every run's seed.
        steps: steps per run (models only).
        replicates: runs per point, averaged (models only).
        common: run every point with the same replicate seeds (models only).
        store: the folder of the runs (a temporary one by default).
        executor: where the runs execute (any experiment executor).
        max_parallel: the most runs at once.
        options: the executor's options.
    """

    model: Any
    space: ScenarioSpace
    outputs: Outputs | None = None
    seed: int = 0
    steps: int = DEFAULT_STEPS
    replicates: int = 1
    common: bool = False
    store: str | Path | None = None
    executor: Any = DEFAULT_EXECUTOR
    max_parallel: int | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Check the space and the outputs; resolve the statistics."""
        if not self.space.dimensions:
            raise ValueError("the space has no range or choice to emulate over")
        if self.outputs is None and is_model(self.model):
            raise ValueError("a model needs outputs= (what to record every step)")
        specs = _output_specs(
            (DEFAULT_OUTPUT,) if self.outputs is None else self.outputs
        )
        if not specs:
            raise ValueError("a simulation needs at least one output")
        self._reducers: dict[str, Callable[[np.ndarray], float]] = {
            name: reducer(statistic) for name, (_, statistic) in specs.items()
        }
        self._records = {
            name: spec if isinstance(spec, str) else reference(spec)
            for name, (spec, _) in specs.items()
        }
        self._temporary: Path | None = None

    @property
    def names(self) -> list[str]:
        """The outputs, in column order."""
        return list(self._reducers)

    def evaluate(self, units: np.ndarray, key: Sequence[int]) -> np.ndarray:
        """``values[point, output]`` at the rows of ``units``; ``key`` names the batch."""
        units = np.atleast_2d(np.asarray(units, float))
        points = [self.space.point(row) for row in units]
        if not is_model(self.model):
            return np.array([self._call(point) for point in points], float)
        return self._simulate(points, tuple(int(part) for part in key))

    def _call(self, point: Mapping[str, Any]) -> list[float]:
        """A function's outputs at ``point``, in column order."""
        value = self.model(**point)
        if isinstance(value, Mapping):
            return [float(value[name]) for name in self.names]
        values = np.atleast_1d(np.asarray(value, float))
        if len(values) != len(self.names):
            raise ValueError(f"the function returned {len(values)} outputs")
        return list(values)

    def _simulate(
        self, points: list[dict[str, Any]], key: tuple[int, ...]
    ) -> np.ndarray:
        """Run the model at ``points``; the replicate mean of each output's statistic."""
        if self.store is None and self._temporary is None:
            self._temporary = scratch_folder(self, "modelly-emulate-")
        root = Path(self.store).resolve() if self.store else self._temporary
        model = self.model if isinstance(self.model, str) else reference(self.model)
        simulator = Simulator(
            model, self._records, self.steps, self.replicates, self.seed, root
        )
        execution = Execution(self.executor, self.max_parallel, self.options)
        if self.common:
            batches = [
                Batch((*key, i), [point], common=True) for i, point in enumerate(points)
            ]
            results = [found[0] for found in simulator.run_many(batches, execution)]
        else:
            results = simulator.run(Batch(key, points), execution)
        return np.array(
            [
                [np.mean([self._reducers[n](row) for row in r[n]]) for n in self.names]
                for r in results
            ]
        )
