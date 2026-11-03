"""Comparing strategies: paired replicates, intervals, rankings.

A *strategy* is a named set of parameters (an intervention, a policy) and its cost.
``compare(run, strategies, replicates=..., seed=...)`` runs every strategy ``replicates``
times; replicate ``r`` of every strategy gets the same seed (common random numbers), so the
strategies face the same chance events and their differences are paired: the interval of a
difference is the interval of the per-replicate differences, much narrower than two
independent intervals would give. ``run(params, seed)`` builds and runs the model and
returns its outputs as a mapping of numbers; ``model_runner`` makes one from a model class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

type Outputs = Mapping[str, float]
type Run = Callable[[Mapping[str, Any], int], Outputs]
CONFIDENCE = 0.95
STRATEGY, REPLICATE, SEED, COST = "strategy", "replicate", "seed", "cost"


@dataclass(frozen=True)
class Strategy:
    """A named intervention: the parameters it sets and what it costs.

    Attributes:
        name: how tables and rankings call it.
        params: the model parameters it sets.
        cost: a fixed cost, or ``cost(outputs)`` computed from one run's outputs.
    """

    name: str
    params: Mapping[str, Any] = field(default_factory=dict)
    cost: float | Callable[[Outputs], float] = 0.0

    def cost_of(self, outputs: Outputs) -> float:
        """The cost of one run."""
        return float(self.cost(outputs) if callable(self.cost) else self.cost)


def replicate_seeds(seed: int, replicates: int) -> list[int]:
    """One seed per replicate, the same for every strategy (common random numbers)."""
    children = np.random.SeedSequence(seed).spawn(replicates)
    return [int(child.generate_state(1)[0]) for child in children]


def model_runner(
    model_class: type, outputs: Mapping[str, Callable[[Any], float]], steps: int | None = None,
    base: Mapping[str, Any] | None = None, scenario: type | None = None,
) -> Run:  # fmt: skip
    """A ``run(params, seed)`` that builds ``model_class`` and reads ``outputs`` after it runs.

    With ``scenario``, the parameters (``base`` updated by the strategy's) and the seed go
    to it; otherwise to the model's constructor as keywords and ``rng``. The model runs
    ``steps`` steps, or its own ``run()`` when ``steps`` is None.
    """

    def run(params: Mapping[str, Any], seed: int) -> dict[str, float]:
        values = {**(base or {}), **params}
        if scenario is not None:
            model = model_class(scenario(rng=seed, **values))
        else:
            model = model_class(rng=seed, **values)
        model.run() if steps is None else model.run_for(steps)
        return {name: float(read(model)) for name, read in outputs.items()}

    return run


def interval(
    values: np.ndarray, confidence: float = CONFIDENCE
) -> tuple[float, float, float]:
    """Mean and Student-t interval of the mean of ``values``."""
    from scipy import stats  # noqa: PLC0415 - scipy is heavy

    values = np.asarray(values, dtype=float)
    mean = float(values.mean())
    if values.size < 2:
        return mean, mean, mean
    half = stats.t.ppf((1 + confidence) / 2, values.size - 1) * values.std(ddof=1)
    half /= np.sqrt(values.size)
    return mean, mean - float(half), mean + float(half)


@dataclass(frozen=True)
class Comparison:
    """Every run of every strategy, and summaries of them.

    Attributes:
        runs: one row per (strategy, replicate): its seed, outputs and cost.
        strategies: the strategies, in the order given; the first is the baseline.
        confidence: the level of every interval.
    """

    runs: pd.DataFrame
    strategies: tuple[Strategy, ...]
    confidence: float = CONFIDENCE

    @property
    def names(self) -> list[str]:
        """The strategies' names, baseline first."""
        return [s.name for s in self.strategies]

    def values(self, output: str, name: str) -> np.ndarray:
        """``output`` of strategy ``name``, by replicate."""
        rows = self.runs[self.runs[STRATEGY] == name].sort_values(REPLICATE)
        return rows[output].to_numpy(dtype=float)

    def summary(self, output: str) -> pd.DataFrame:
        """Mean and interval of ``output`` per strategy."""
        rows = [
            (name, *interval(self.values(output, name), self.confidence))
            for name in self.names
        ]
        return pd.DataFrame(rows, columns=[STRATEGY, "mean", "low", "high"]).set_index(
            STRATEGY
        )

    def difference(self, output: str, baseline: str | None = None) -> pd.DataFrame:
        """Each strategy minus ``baseline`` (the first by default), paired by replicate."""
        base = self.values(output, baseline or self.names[0])
        rows = [
            (name, *interval(self.values(output, name) - base, self.confidence))
            for name in self.names
        ]
        return pd.DataFrame(rows, columns=[STRATEGY, "mean", "low", "high"]).set_index(
            STRATEGY
        )

    def rank(self, output: str, lower_is_better: bool = True) -> pd.DataFrame:
        """Strategies by mean ``output``, best first, with how often each was best.

        ``best_share`` is the share of replicates in which the strategy had the best
        value: with common random numbers each replicate is one shared set of chance
        events, so it estimates the probability that the strategy is the best choice.
        """
        table = np.array([self.values(output, n) for n in self.names])
        best = table.argmin(axis=0) if lower_is_better else table.argmax(axis=0)
        frame = self.summary(output)
        frame["best_share"] = [
            float(np.mean(best == i)) for i in range(len(self.names))
        ]
        return frame.sort_values("mean", ascending=lower_is_better, kind="stable")


def compare(
    run: Run, strategies: Sequence[Strategy], *, replicates: int = 20, seed: int = 0,
    confidence: float = CONFIDENCE,
) -> Comparison:  # fmt: skip
    """Run every strategy ``replicates`` times with common random numbers.

    Raises:
        ValueError: without strategies, with two of the same name, or with fewer than two
            replicates (no interval).
    """
    names = [s.name for s in strategies]
    if not names or len(set(names)) != len(names):
        raise ValueError("compare needs strategies with distinct names")
    if replicates < 2:
        raise ValueError("compare needs at least two replicates for an interval")
    rows = []
    for r, child in enumerate(replicate_seeds(seed, replicates)):
        for strategy in strategies:
            outputs = dict(run(strategy.params, child))
            rows.append({STRATEGY: strategy.name, REPLICATE: r, SEED: child, **outputs,
                         COST: strategy.cost_of(outputs)})  # fmt: skip
    return Comparison(pd.DataFrame(rows), tuple(strategies), confidence)
