"""An evaluation harness for language-model agents: behaviour, consistency and cost.

``evaluate(build, clients, seeds=..., steps=..., metrics=...)`` runs the same model with each
client (a provider, a hosted model, a local one) on each seed, and records per run every
behaviour metric (a function of the finished model), the calls sent and served from the
cache, the tokens and the cost. ``Evaluation.report()`` gives per client the mean and spread
of each metric over the seeds, how consistently its agents chose the same thing from one
seed to the next (``choices``), and the totals of calls, tokens and cost: which model
behaves as the study needs, how stably, and at what price.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

USAGE = ("calls", "cache_hits", "input_tokens", "output_tokens", "cost")


def _usage(model: Any) -> dict[str, float]:
    """The model's client usage: calls, hits, tokens and cost."""
    usage = model.llm.usage
    return {name: (getattr(usage, name) if getattr(usage, name) is not None else np.nan)
            for name in USAGE}  # fmt: skip


def agreement(choices: Sequence[Sequence[Any]]) -> float:
    """The share of positions where two seeds' choices agree, over every pair of seeds."""
    pairs = list(combinations(choices, 2))
    if not pairs:
        return float("nan")
    return float(np.mean([np.mean([x == y for x, y in zip(a, b)]) for a, b in pairs]))


@dataclass(frozen=True)
class Evaluation:
    """Every run's metrics and usage, and the choices recorded for consistency.

    Attributes:
        runs: one row per (client, seed).
        choices: per client, one list of choices per seed (empty without ``choices``).
        metrics: the names of the behaviour metrics.
    """

    runs: pd.DataFrame
    choices: Mapping[str, list[list[Any]]]
    metrics: tuple[str, ...]

    def report(self) -> pd.DataFrame:
        """Per client: each metric's mean and sd, the agreement, and the usage totals."""
        rows = []
        for name, runs in self.runs.groupby("client", sort=False):
            row: dict[str, Any] = {"client": name, "seeds": len(runs)}
            for metric in self.metrics:
                row[f"{metric}_mean"] = runs[metric].mean()
                row[f"{metric}_sd"] = runs[metric].std(ddof=1) if len(runs) > 1 else 0.0
            row["agreement"] = agreement(self.choices.get(name, []))
            row |= {key: runs[key].sum(min_count=1) for key in USAGE}
            rows.append(row)
        return pd.DataFrame(rows).set_index("client")


def evaluate(
    build: Callable[[int, Any], Any], clients: Mapping[str, Callable[[], Any]], *,
    seeds: Sequence[int], steps: int, metrics: Mapping[str, Callable[[Any], float]],
    choices: Callable[[Any], Sequence[Any]] | None = None,
) -> Evaluation:  # fmt: skip
    """Run ``build(seed, client)`` for ``steps`` steps with every client on every seed.

    ``clients`` maps a name to a function making a fresh ``Client``, so runs share no cache
    unless the factory gives them one. ``choices(model)`` lists the agents' decisions, in a
    fixed order, for the agreement between seeds.
    """
    rows: list[dict[str, Any]] = []
    chosen: dict[str, list[list[Any]]] = {name: [] for name in clients}
    for name, make in clients.items():
        for seed in seeds:
            model = build(int(seed), make())
            model.run_for(int(steps))
            row = {"client": name, "seed": int(seed)}
            row |= {metric: float(read(model)) for metric, read in metrics.items()}
            rows.append(row | _usage(model))
            if choices is not None:
                chosen[name].append(list(choices(model)))
    return Evaluation(pd.DataFrame(rows), chosen, tuple(metrics))
