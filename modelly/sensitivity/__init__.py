"""Sensitivity analysis: which parameters drive which outputs.

Every method takes a model (run through the experiment executors), a plain
function of the parameters, or an :class:`Emulator`, and a
:class:`~modelly.experiments.ScenarioSpace`:

* :func:`oat`: one parameter at a time around the midpoint;
* :func:`morris`: elementary effects, ``mu*`` and ``sigma``;
* :func:`sobol`: first-order and total Sobol indices with bootstrap intervals;
* :func:`pawn`: moment-independent indices from output distributions;
* :func:`emulate`: a Gaussian-process stand-in for an expensive model.

Designs and bootstraps are drawn from the ``seed``: the same seed gives the
same indices on every executor.
"""

from modelly.sensitivity.emulator import Emulator, emulate
from modelly.sensitivity.pawn import pawn
from modelly.sensitivity.results import (
    MorrisResult,
    OATResult,
    SensitivityResult,
    SobolResult,
)
from modelly.sensitivity.screening import morris, oat
from modelly.sensitivity.study import Study
from modelly.sensitivity.variance import sobol

__all__ = [
    "Emulator",
    "MorrisResult",
    "OATResult",
    "SensitivityResult",
    "SobolResult",
    "Study",
    "emulate",
    "morris",
    "oat",
    "pawn",
    "sobol",
]
