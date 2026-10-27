"""Emulators, active learning and history matching: fewer runs of an expensive model.

An emulator is a fast statistical stand-in for a model, fitted to its runs:

* :class:`GaussianEmulator`: one Gaussian process per output
  (:mod:`modelly.calibrate.gp`), with predictive variances and covariances;
* :class:`NeuralEmulator`: an ensemble of small numpy networks, for more runs.

Both are fitted to points of a :class:`~modelly.experiments.ScenarioSpace`'s
unit cube, or to an experiment's runs with ``from_results``. A
:class:`Simulation` runs a model (through the experiment executors) or a
function at chosen points, and two methods choose them:

* :class:`ActiveLearning`: run next where the emulator is least certain
  (largest variance, or largest integrated variance reduction, in batches);
* :class:`HistoryMatch`: waves that rule out the parameters whose
  implausibility against :class:`Observation` s exceeds a cutoff.

Every random draw comes from the simulation's seed: the same seed gives the
same runs, emulators and waves on every executor.
"""

from modelly.emulate.active import ActiveDesign, ActiveLearning, ActiveSettings
from modelly.emulate.base import Emulator, training_data
from modelly.emulate.gaussian import GaussianEmulator
from modelly.emulate.history import (
    HistoryMatch,
    MatchResult,
    MatchSettings,
    Observation,
    Wave,
    implausibility,
)
from modelly.emulate.neural import NeuralEmulator, NeuralSettings
from modelly.emulate.simulation import Simulation

__all__ = [
    "ActiveDesign",
    "ActiveLearning",
    "ActiveSettings",
    "Emulator",
    "GaussianEmulator",
    "HistoryMatch",
    "MatchResult",
    "MatchSettings",
    "NeuralEmulator",
    "NeuralSettings",
    "Observation",
    "Simulation",
    "Wave",
    "implausibility",
    "training_data",
]
