"""Why an outcome happened, not only that it did.

* :func:`treatment_effect`: an average effect with its interval, paired on common random
  numbers, and the variance reduction they bring, measured (``modelly.explain.effects``);
* :func:`counterfactual`: the effect of a change applied at a recorded step of a run,
  through time travel;
* :func:`attribute`: the agents whose removal moves the outcome most
  (``modelly.explain.attribution``);
* :func:`shapley`: exact Shapley values of an emulator's prediction, per parameter
  (``modelly.explain.shapley``).

Guide: ``docs/explain.md``.
"""

from modelly.explain.attribution import Attribution, attribute, remove
from modelly.explain.effects import Effect, counterfactual, treatment_effect
from modelly.explain.shapley import shapley

__all__ = [
    "Attribution",
    "Effect",
    "attribute",
    "counterfactual",
    "remove",
    "shapley",
    "treatment_effect",
]
