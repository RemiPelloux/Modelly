"""Decisions people can defend: compare strategies, cost them, and test them against futures.

* :func:`compare` and :class:`Strategy`: every strategy run on the same replicate seeds
  (common random numbers), with intervals, paired differences and rankings
  (``modelly.decide.compare``);
* :func:`cost_effectiveness` and :func:`net_benefit`: the efficient frontier, ICERs and net
  monetary benefit (``modelly.decide.costs``);
* :func:`robust` and :func:`sample_futures`: strategies across many futures, ranked by their
  largest regret (``modelly.decide.robust``);
* :func:`optimise`: a policy's parameters searched with Optuna, seeded
  (``modelly.decide.optimise``, the ``decide`` extra).

``modelly.decide.vaccination`` is the worked example of ``docs/decide.md``.
"""

from modelly.decide.compare import Comparison, Strategy, compare, interval, model_runner
from modelly.decide.costs import cost_effectiveness, net_benefit
from modelly.decide.optimise import Optimum, optimise
from modelly.decide.robust import Robustness, robust, sample_futures

__all__ = [
    "Comparison",
    "Optimum",
    "Robustness",
    "Strategy",
    "compare",
    "cost_effectiveness",
    "interval",
    "model_runner",
    "net_benefit",
    "optimise",
    "robust",
    "sample_futures",
]
