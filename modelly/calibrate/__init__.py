"""Calibration: fit scenario parameters to observed data, with uncertainty.

Give priors over the parameters and targets (observed series or summary
statistics); a method runs the model through the experiment executors and
returns a :class:`Posterior`:

* :class:`ABCRejection`: sample the priors, keep the closest runs;
* :class:`ABCSMC`: sequential Monte Carlo ABC with adaptive tolerances;
* :class:`SimulatedMoments`: the method of simulated moments;
* :class:`BayesOpt`: a basic Gaussian-process Bayesian optimiser;
* :class:`ExternalBayesOpt`: Bayesian optimisation by an outside library (optuna).

Every random draw comes from the calibration's seed, so a posterior is the
same on every executor and after a resume (``save`` / ``load``). The runs are
written as Parquet files: ``pip install "modelly-abm[experiments]"``.
"""

from modelly.calibrate import distance
from modelly.calibrate.base import Calibration, CalibrationError
from modelly.calibrate.bayesopt import BayesOpt
from modelly.calibrate.external import ExternalBayesOpt
from modelly.calibrate.moments import SimulatedMoments
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.priors import Prior
from modelly.calibrate.rejection import ABCRejection
from modelly.calibrate.simulator import SimulationError
from modelly.calibrate.smc import ABCSMC
from modelly.calibrate.targets import Target

__all__ = [
    "ABCSMC",
    "ABCRejection",
    "BayesOpt",
    "Calibration",
    "CalibrationError",
    "ExternalBayesOpt",
    "Posterior",
    "Prior",
    "SimulatedMoments",
    "SimulationError",
    "Target",
    "distance",
]
