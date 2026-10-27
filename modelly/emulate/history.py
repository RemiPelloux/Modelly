"""History matching: rule out, wave by wave, the parameters that cannot match the data.

For an observed value ``z`` of an output, the implausibility of a point ``x``
of the parameter space is::

    I(x) = |z - E[f(x)]| / sqrt(Var[f(x)] + Var_obs + Var_discrepancy)

where ``E[f(x)]`` and ``Var[f(x)]`` are an emulator's prediction of the model's
output, ``Var_obs`` the observation error and ``Var_discrepancy`` the model
discrepancy (what even the best parameters miss, the run-to-run scatter of a
stochastic model included). With several outputs a point's implausibility is
the largest of theirs (or, with ``rank=2``, the second largest). A point with
``I(x) > cutoff`` (3, by Pukelsheim's three-sigma rule) is implausible.

A :class:`HistoryMatch` runs waves (Vernon, Goldstein and Bower 2010;
Andrianakis et al. 2015). Wave 1 spreads ``runs`` runs over the whole space,
fits an emulator and rules out the implausible part. Each later wave spreads
its runs over the space not yet ruled out, refits the emulators on the runs
inside it (more accurate there, as the region is smaller) and rules out more.
The space not ruled out yet, NROY, is tracked on a fixed random sample of
``candidates`` points of the space, so its volume is the share of the sample
left.

Example:
    >>> from modelly.experiments import ScenarioSpace
    >>> space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
    >>> simulation = Simulation(lambda a, b: [a + b, a - b], space, ["sum", "diff"])
    >>> observed = [Observation("sum", 1.0, 1e-4), Observation("diff", 0.2, 1e-4)]
    >>> result = HistoryMatch(simulation, observed).run(waves=2, runs=12)
    >>> bool(result.volumes[-1] < 0.1 and result.contains({"a": 0.6, "b": 0.4}))
    True
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import Stream, generator
from modelly.emulate.base import Emulator, unit_of
from modelly.emulate.gaussian import GaussianEmulator
from modelly.emulate.simulation import Simulation

MATCH_KEY = 17  # first element of the batch keys and streams of history matching
CUTOFF = 3.0  # Pukelsheim's three-sigma rule
DEFAULT_CANDIDATES = 20_000
DEFAULT_RUNS = 40


@dataclass(frozen=True)
class Observation:
    """One observed output and its uncertainty.

    Args:
        name: the simulation output it observes.
        value: the observed value ``z``.
        variance: the observation error variance.
        discrepancy: the model discrepancy variance.
    """

    name: str
    value: float
    variance: float
    discrepancy: float = 0.0

    def __post_init__(self) -> None:
        """Reject negative variances."""
        if self.variance < 0 or self.discrepancy < 0:
            raise ValueError(f"observation {self.name!r} needs variances >= 0")


def implausibility(
    mean: np.ndarray, sd: np.ndarray, observations: Sequence[Observation]
) -> np.ndarray:
    """``I[point, output]`` from an emulator's ``mean`` and ``sd`` (columns as observations)."""
    value = np.array([o.value for o in observations])
    extra = np.array([o.variance + o.discrepancy for o in observations])
    return np.abs(value - mean) / np.sqrt(sd**2 + extra)


@dataclass(frozen=True)
class MatchSettings:
    """How the waves rule out space.

    Args:
        cutoff: the implausibility above which a point is ruled out.
        rank: combine the outputs by their largest implausibility (1) or the
            ``rank``-th largest (2 tolerates one badly matched output).
        candidates: the random points of the space NROY is tracked on.
        emulator: the emulator class refitted at every wave.
        options: keyword arguments of the emulator's ``fit``.
    """

    cutoff: float = CUTOFF
    rank: int = 1
    candidates: int = DEFAULT_CANDIDATES
    emulator: type[Emulator] = GaussianEmulator
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(eq=False)
class Wave:
    """One wave: its runs, the emulator fitted to the runs inside its region, and NROY.

    Attributes:
        number: 1 for the first wave.
        units: the wave's runs, as points of the unit cube.
        values: their outputs ``[run, output]``.
        training: how many runs (this wave's and earlier ones in its region) fitted the emulator.
        emulator: the wave's emulator of the observed outputs.
        volume: the share of the space not ruled out after this wave.
    """

    number: int
    units: np.ndarray
    values: np.ndarray
    training: int
    emulator: Emulator
    volume: float


@dataclass(eq=False)
class MatchResult:
    """The waves of a history match and the space they did not rule out.

    Attributes:
        simulation: what was run.
        observations: what was matched.
        settings: how.
        waves: every wave, the first first.
        candidates: the sample of the space NROY is tracked on.
        alive: which candidates are not ruled out.
    """

    simulation: Simulation
    observations: list[Observation]
    settings: MatchSettings
    waves: list[Wave]
    candidates: np.ndarray
    alive: np.ndarray

    @property
    def volumes(self) -> list[float]:
        """The share of the space not ruled out after each wave."""
        return [wave.volume for wave in self.waves]

    def implausibility(self, units: np.ndarray) -> np.ndarray:
        """The combined implausibility ``[wave, point]`` of each wave's emulator."""
        return np.array([self.wave_implausibility(wave, units) for wave in self.waves])

    def wave_implausibility(self, wave: Wave, units: np.ndarray) -> np.ndarray:
        """One wave's combined implausibility at ``units``: the ``rank``-th largest output's."""
        mean, sd = wave.emulator.predict(np.atleast_2d(units))
        each = implausibility(mean, sd, self.observations)
        return np.sort(each, axis=1)[:, -self.settings.rank]

    def nonimplausible(self, units: np.ndarray) -> np.ndarray:
        """Whether each point is below the cutoff under every wave."""
        return np.all(self.implausibility(units) <= self.settings.cutoff, axis=0)

    def contains(self, params: Mapping[str, Any]) -> bool:
        """Whether the parameters ``params`` are not ruled out."""
        unit = unit_of(self.simulation.space, params)
        return bool(self.nonimplausible(unit[None, :])[0])

    def samples(self) -> pd.DataFrame:
        """The candidates not ruled out, as parameters: a sample of NROY."""
        space = self.simulation.space
        return pd.DataFrame([space.point(row) for row in self.candidates[self.alive]])

    def table(self) -> pd.DataFrame:
        """One row per wave: its runs, its training runs and the volume left."""
        rows = [
            {
                "wave": w.number,
                "runs": len(w.units),
                "training": w.training,
                "volume": w.volume,
            }
            for w in self.waves
        ]
        return pd.DataFrame(rows).set_index("wave")


def maximin(region: np.ndarray, count: int, rng: np.random.Generator) -> np.ndarray:
    """``count`` points of ``region`` chosen greedily far from each other (all if fewer)."""
    if count >= len(region):
        return region.copy()
    chosen = [int(rng.integers(len(region)))]
    distance = np.sum((region - region[chosen[0]]) ** 2, axis=1)
    while len(chosen) < count:
        chosen.append(int(np.argmax(distance)))
        distance = np.minimum(
            distance, np.sum((region - region[chosen[-1]]) ** 2, axis=1)
        )
    return region[chosen]


class HistoryMatch:
    """History matching of a simulation to observations (see the module docstring).

    ``run(waves)`` can be called again with more waves to go on.
    """

    def __init__(
        self,
        simulation: Simulation,
        observations: Sequence[Observation],
        settings: MatchSettings | None = None,
    ) -> None:
        """Check the observations name outputs; nothing runs before ``run``."""
        self.observations = list(observations)
        unknown = {o.name for o in self.observations} - set(simulation.names)
        if not self.observations or unknown:
            raise ValueError(f"observations must name outputs of {simulation.names}")
        self.settings = settings or MatchSettings()
        if not 1 <= self.settings.rank <= len(self.observations):
            raise ValueError("rank must be between 1 and the number of observations")
        self.simulation = simulation
        dimensions = len(simulation.space.dimensions)
        pool = self._stream().random((self.settings.candidates, dimensions))
        self.result = MatchResult(
            simulation,
            self.observations,
            self.settings,
            [],
            pool,
            np.ones(len(pool), bool),
        )
        self._columns = [simulation.names.index(o.name) for o in self.observations]
        self._units = np.empty((0, dimensions))
        self._values = np.empty((0, len(self._columns)))

    def _stream(self, *key: int) -> np.random.Generator:
        """A generator of the design stream of history matching."""
        return generator(self.simulation.seed, Stream.DESIGN, MATCH_KEY, *key)

    def run(self, waves: int, runs: int = DEFAULT_RUNS) -> MatchResult:
        """Run ``waves`` more waves of ``runs`` runs each; stop early if NROY is empty."""
        if runs < 1:
            raise ValueError("a wave needs at least one run")
        for _ in range(waves):
            if not self.result.alive.any():
                break
            self._wave(runs)
        return self.result

    def _wave(self, runs: int) -> None:
        """Run one wave in the current NROY, refit, and rule out what it can."""
        result, number = self.result, len(self.result.waves) + 1
        region = result.candidates[result.alive]
        design = maximin(region, runs, self._stream(number))
        values = self.simulation.evaluate(design, (MATCH_KEY, number))[:, self._columns]
        self._units = np.vstack([self._units, design])
        self._values = np.vstack([self._values, values])
        inside = (
            result.nonimplausible(self._units)
            if result.waves
            else np.ones(len(self._units), bool)
        )
        emulator = self.settings.emulator.fit(
            self._units[inside],
            self._values[inside],
            [o.name for o in self.observations],
            space=self.simulation.space,
            **dict(self.settings.options),
        )
        wave = Wave(number, design, values, int(inside.sum()), emulator, 0.0)
        kept = result.wave_implausibility(wave, region) <= self.settings.cutoff
        result.alive[np.flatnonzero(result.alive)[~kept]] = False
        wave.volume = float(result.alive.mean())
        result.waves.append(wave)
