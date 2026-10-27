"""Active learning: choose the next runs where the emulator is least certain.

An :class:`ActiveLearning` design starts from a small Latin hypercube, fits an
emulator, and then, batch after batch, runs the candidate points the emulator
would learn most from, refitting after every batch:

* ``criterion="ivr"`` (the default): the largest integrated variance
  reduction, the drop in predictive variance averaged over the whole space
  that running the point would bring (Cohn 1996's ALC; Sacks, Welch, Mitchell
  and Wynn 1989), the error measure an emulator is judged by;
* ``criterion="variance"``: the largest predictive variance (MacKay 1992's
  ALM): cheaper, but it favours the edges of the space, more so in more
  dimensions.

A batch of several runs is chosen greedily: after each pick the emulator is
conditioned on it (its variance becomes what it would be after the run, the
"kriging believer"), so the batch spreads out instead of piling up where the
variance was largest. The batch then runs at once on the simulation's executor.
With several outputs, the criteria add the outputs' variances, each relative to
its spread in the runs so far.

Every random draw (the first design, the candidates, the reference points)
comes from the simulation's seed: the same seed chooses the same runs.

Example:
    >>> import math
    >>> from modelly.experiments import ScenarioSpace
    >>> space = ScenarioSpace(x=(0.0, 1.0), y=(0.0, 1.0))
    >>> simulation = Simulation(lambda x, y: math.sin(6 * x) + y, space, seed=1)
    >>> design = ActiveLearning(simulation, ActiveSettings(batch=2)).run(runs=14)
    >>> len(design.units)
    14
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import Stream, generator
from modelly.emulate.base import Emulator
from modelly.emulate.gaussian import GaussianEmulator
from modelly.emulate.simulation import Simulation
from modelly.experiments.designs import Custom, custom

ACTIVE_KEY = 16  # first element of the batch keys and streams of active learning
VARIANCE = "variance"
IVR = "ivr"
CRITERIA = (IVR, VARIANCE)
REFERENCE_STREAM = 1  # the design stream's sub-key of the IVR reference points
INITIAL_PER_DIMENSION = 2  # a first design of 2 d + 2 runs
DEFAULT_CANDIDATES = 1000
DEFAULT_REFERENCES = 300
ITERATION = "iteration"


@dataclass(frozen=True)
class ActiveSettings:
    """How an active-learning design chooses its runs.

    Args:
        initial: runs of the first Latin hypercube (``2 * dimensions + 2`` by default).
        batch: runs chosen and run together at each iteration.
        criterion: ``"ivr"`` (integrated variance reduction) or ``"variance"``.
        candidates: random points scored at each iteration.
        references: points the integrated variance is averaged over (``"ivr"``).
        emulator: the emulator class (a batch needs ``condition``, as
            :class:`~modelly.emulate.gaussian.GaussianEmulator` has).
        options: keyword arguments of the emulator's ``fit``.
    """

    initial: int | None = None
    batch: int = 1
    criterion: str = IVR
    candidates: int = DEFAULT_CANDIDATES
    references: int = DEFAULT_REFERENCES
    emulator: type[Emulator] = GaussianEmulator
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject an unknown criterion and empty batches or candidate sets."""
        if self.criterion not in CRITERIA:
            raise ValueError(f"criterion must be one of {CRITERIA}")
        if min(self.batch, self.candidates, self.references) < 1:
            raise ValueError("batch, candidates and references must be at least 1")
        if self.initial is not None and self.initial < 1:
            raise ValueError("initial must be at least 1")


@dataclass
class ActiveDesign:
    """The runs an active-learning design chose, and the emulator fitted to them.

    Attributes:
        simulation: what was run.
        units: the runs' points of the unit cube, in the order they ran.
        values: their outputs ``[run, output]``.
        iterations: the iteration of each run (0 for the first design).
        emulator: the emulator fitted to every run.
    """

    simulation: Simulation
    units: np.ndarray
    values: np.ndarray
    iterations: np.ndarray
    emulator: Emulator

    def points(self) -> list[dict[str, Any]]:
        """The parameters of every run, in the order they ran."""
        return [self.simulation.space.point(row) for row in self.units]

    def design(self) -> Custom:
        """The runs as a custom design, to rerun them in an ``Experiment``."""
        return custom(self.points())

    def frame(self) -> pd.DataFrame:
        """One row per run: the iteration, the parameters and the outputs."""
        outputs = pd.DataFrame(self.values, columns=self.simulation.names)
        params = pd.DataFrame(self.points())
        return pd.concat(
            [pd.Series(self.iterations, name=ITERATION), params, outputs], axis=1
        )


class ActiveLearning:
    """An active-learning design over a simulation (see the module docstring).

    ``run(runs)`` can be called again with a larger ``runs`` to go on.
    """

    def __init__(
        self, simulation: Simulation, settings: ActiveSettings | None = None
    ) -> None:
        """Nothing runs before ``run``."""
        self.simulation = simulation
        self.settings = settings or ActiveSettings()
        self.dimensions = len(simulation.space.dimensions)
        self.units = np.empty((0, self.dimensions))
        self.values = np.empty((0, len(simulation.names)))
        self.iterations = np.empty(0, int)
        self._references = self._stream(REFERENCE_STREAM).random(
            (self.settings.references, self.dimensions)
        )

    def _stream(self, *key: int) -> np.random.Generator:
        """A generator of the design stream of active learning."""
        return generator(self.simulation.seed, Stream.DESIGN, ACTIVE_KEY, *key)

    def run(self, runs: int) -> ActiveDesign:
        """Run until ``runs`` runs are done; the design and its emulator."""
        from scipy.stats import qmc  # noqa: PLC0415 - lazy import

        initial = self.settings.initial or INITIAL_PER_DIMENSION * (self.dimensions + 1)
        if runs < initial:
            raise ValueError(f"runs must be at least the {initial} initial runs")
        if not len(self.units):
            start = qmc.LatinHypercube(self.dimensions, rng=self._stream()).random(
                initial
            )
            self._add(start, 0)
        while len(self.units) < runs:
            emulator = self.fit()
            count = min(self.settings.batch, runs - len(self.units))
            self._add(self._choose(emulator, count), int(self.iterations[-1]) + 1)
        return ActiveDesign(
            self.simulation, self.units, self.values, self.iterations, self.fit()
        )

    def fit(self) -> Emulator:
        """The emulator fitted to every run so far."""
        return self.settings.emulator.fit(
            self.units,
            self.values,
            self.simulation.names,
            space=self.simulation.space,
            **dict(self.settings.options),
        )

    def _add(self, units: np.ndarray, iteration: int) -> None:
        """Run ``units`` as one batch and keep the results."""
        values = self.simulation.evaluate(units, (ACTIVE_KEY, iteration))
        self.units = np.vstack([self.units, units])
        self.values = np.vstack([self.values, values])
        self.iterations = np.append(self.iterations, np.full(len(units), iteration))

    def _choose(self, emulator: Emulator, count: int) -> np.ndarray:
        """``count`` candidates picked one by one, conditioning on each pick."""
        if count > 1 and not hasattr(emulator, "condition"):
            raise TypeError(
                f"a batch needs an emulator with condition(), not {type(emulator).__name__}"
            )
        iteration = int(self.iterations[-1]) + 1
        candidates = self._stream(iteration).random(
            (self.settings.candidates, self.dimensions)
        )
        chosen = []
        for pick in range(count):
            best = int(np.argmax(self._scores(emulator, candidates)))
            chosen.append(candidates[best])
            if pick < count - 1:
                emulator = emulator.condition(candidates[best][None, :])
            candidates = np.delete(candidates, best, axis=0)
        return np.array(chosen)

    def _scores(self, emulator: Emulator, candidates: np.ndarray) -> np.ndarray:
        """The criterion at every candidate, outputs relative to their spread."""
        spread = self.values.std(axis=0)
        scale = np.where(spread > 0, spread, 1.0) ** 2
        variance = emulator.predict(candidates)[1] ** 2
        if self.settings.criterion == VARIANCE:
            return np.sum(variance / scale, axis=1)
        if not hasattr(emulator, "covariance"):
            raise TypeError(
                f"ivr needs an emulator with covariance(), not {type(emulator).__name__}"
            )
        covariance = emulator.covariance(self._references, candidates)
        noise = getattr(emulator, "noise_variance", np.zeros(len(scale)))
        reduction = np.sum(covariance**2, axis=1) / (variance.T + noise[:, None])
        return np.sum(reduction / scale[:, None], axis=0) / len(self._references)
