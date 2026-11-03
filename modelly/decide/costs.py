"""Cost-effectiveness: what each strategy costs for what it achieves, against the others.

``cost_effectiveness(comparison, effect)`` places every strategy by its mean cost and mean
effect (cases averted, years of life gained), removes the *dominated* ones (another costs no
more and achieves at least as much) and the *extendedly dominated* ones (a mix of two others
would do better), and gives the incremental cost-effectiveness ratio (ICER) of each
remaining strategy over the previous one on that frontier: the price of one more unit of
effect. ``net_benefit`` turns a willingness to pay per unit of effect into one number per
strategy and replicate, ``wtp * effect - cost``, ranked with paired intervals.

Reference:
    Drummond, M. F., Sculpher, M. J., Claxton, K., Stoddart, G. L. and Torrance, G. W.
    (2015). Methods for the Economic Evaluation of Health Care Programmes, 4th ed., ch. 4.
    Oxford University Press.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from modelly.decide.compare import COST, Comparison

FRONTIER, DOMINATED, EXTENDED = "frontier", "dominated", "extendedly dominated"


def _dominated(costs: np.ndarray, effects: np.ndarray) -> np.ndarray:
    """Strategies another one beats: no more cost and no less effect, one strictly."""
    out = np.zeros(costs.size, bool)
    for i in range(costs.size):
        better = (costs <= costs[i]) & (effects >= effects[i])
        better &= (costs < costs[i]) | (effects > effects[i])
        out[i] = better.any()
    return out


def _frontier(order: list[int], costs: np.ndarray, effects: np.ndarray) -> list[int]:
    """Remove extended dominance: ICERs must rise along the frontier."""
    kept = list(order)
    changed = True
    while changed and len(kept) > 2:
        changed = False
        icers = [
            (costs[b] - costs[a]) / (effects[b] - effects[a])
            for a, b in itertools.pairwise(kept)
        ]
        for j in range(len(icers) - 1):
            if icers[j] > icers[j + 1]:
                del kept[j + 1]
                changed = True
                break
    return kept


def cost_effectiveness(
    comparison: Comparison, effect: str, cost: str = COST
) -> pd.DataFrame:
    """Mean cost and effect, status and ICER of each strategy, cheapest first."""
    names = comparison.names
    costs = np.array([comparison.values(cost, n).mean() for n in names])
    effects = np.array([comparison.values(effect, n).mean() for n in names])
    dominated = _dominated(costs, effects)
    order = sorted(
        (i for i in range(len(names)) if not dominated[i]), key=lambda i: costs[i]
    )
    frontier = _frontier(order, costs, effects)
    status = [DOMINATED if dominated[i] else EXTENDED for i in range(len(names))]
    icer = [np.nan] * len(names)
    for a, b in itertools.pairwise(frontier):
        icer[b] = (costs[b] - costs[a]) / (effects[b] - effects[a])
    for i in frontier:
        status[i] = FRONTIER
    frame = pd.DataFrame({"strategy": names, "cost": costs, "effect": effects,
                          "status": status, "icer": icer})  # fmt: skip
    return frame.set_index("strategy").sort_values("cost", kind="stable")


def net_benefit(
    comparison: Comparison, effect: str, wtp: float, cost: str = COST
) -> pd.DataFrame:
    """``wtp * effect - cost`` per strategy, with intervals and best shares, best first."""
    runs = comparison.runs.copy()
    runs["net_benefit"] = wtp * runs[effect] - runs[cost]
    return Comparison(runs, comparison.strategies, comparison.confidence).rank(
        "net_benefit", lower_is_better=False
    )
