"""Robust decision making: strategies that do well across many possible futures.

When the parameters of the world are uncertain (how transmissible the next variant is, how
many people comply), a strategy chosen for one best guess can fail badly elsewhere.
``robust(run, strategies, futures, output)`` runs every strategy in every future, with
common random numbers within a future, and reports per strategy: the mean outcome over the
futures, the worst one, the *regret* (how much worse than the best strategy of that future)
at its largest and on average, and the share of futures in which it meets a ``threshold``.
Strategies are ranked by their largest regret (minimax regret), the usual criterion when
the futures cannot be given probabilities. ``sample_futures`` draws futures from ranges by
Latin hypercube sampling, from a seed.

Reference:
    Lempert, R. J., Popper, S. W. and Bankes, S. C. (2003). Shaping the Next One Hundred
    Years: New Methods for Quantitative, Long-Term Policy Analysis. RAND, MR-1626.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly.decide.compare import Run, Strategy

FUTURE = "future"


def sample_futures(
    ranges: Mapping[str, tuple[float, float]], n: int, seed: int = 0
) -> list[dict[str, float]]:
    """``n`` futures, a Latin hypercube over ``ranges`` (``{name: (low, high)}``)."""
    from scipy.stats import qmc  # noqa: PLC0415 - scipy is heavy

    names = list(ranges)
    unit = qmc.LatinHypercube(d=len(names), rng=np.random.default_rng(seed)).random(n)
    low = np.array([ranges[k][0] for k in names])
    high = np.array([ranges[k][1] for k in names])
    return [dict(zip(names, map(float, low + row * (high - low)))) for row in unit]


@dataclass(frozen=True)
class Robustness:
    """The outcome of every strategy in every future, and the summary that ranks them.

    Attributes:
        outcomes: mean ``output`` per (strategy, future), strategies as rows.
        futures: the futures, in column order.
        lower_is_better: the direction of ``output``.
        threshold: the satisficing level, or None.
    """

    outcomes: pd.DataFrame
    futures: tuple[Mapping[str, Any], ...]
    lower_is_better: bool
    threshold: float | None

    def regret(self) -> pd.DataFrame:
        """How much worse each strategy is than the best one of each future."""
        table = self.outcomes
        if self.lower_is_better:
            return table - table.min(axis=0)
        return table.max(axis=0) - table

    def summary(self) -> pd.DataFrame:
        """Mean, worst, largest and mean regret, satisficing share; minimax regret first."""
        table, regret = self.outcomes, self.regret()
        worst = table.max(axis=1) if self.lower_is_better else table.min(axis=1)
        frame = pd.DataFrame({"mean": table.mean(axis=1), "worst": worst,
                              "max_regret": regret.max(axis=1), "mean_regret": regret.mean(axis=1)})  # fmt: skip
        if self.threshold is not None:
            met = (
                table <= self.threshold
                if self.lower_is_better
                else table >= self.threshold
            )
            frame["satisficing"] = met.mean(axis=1)
        return frame.sort_values(["max_regret", "mean_regret"], kind="stable")


def robust(
    run: Run, strategies: Sequence[Strategy], futures: Sequence[Mapping[str, Any]], output: str,
    *, lower_is_better: bool = True, replicates: int = 5, seed: int = 0,
    threshold: float | None = None,
) -> Robustness:  # fmt: skip
    """Run every strategy in every future; the outcomes and their robustness summary.

    A strategy's parameters override the future's where both set one.
    """
    columns = {}
    for f, future in enumerate(futures):
        children = np.random.SeedSequence(seed, spawn_key=(f,)).spawn(replicates)
        seeds = [int(c.generate_state(1)[0]) for c in children]
        columns[f] = [
            float(np.mean([run({**future, **s.params}, x)[output] for x in seeds]))
            for s in strategies
        ]
    outcomes = pd.DataFrame(
        columns, index=pd.Index([s.name for s in strategies], name="strategy")
    )
    outcomes.columns.name = FUTURE
    return Robustness(outcomes, tuple(futures), lower_is_better, threshold)
