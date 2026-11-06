"""Attribution: which agents, taken out of a run, change its outcome the most.

``attribute(build, candidates, output, steps=...)`` reruns the model once per candidate
agent with an intervention on that agent at the start (by default it is removed), on the
same seed as the baseline, and measures how far the outcome moves. Over several seeds the
effects are averaged per candidate, keyed by the agents' unique ids, so a candidate is the
same agent in every rerun of a seed. The agents whose removal moves the outcome most are the
ones it depends on: in an outbreak, the index case; in a market, the trader the crash
started from.

Removing an agent can shift the random draws that follow it, so the rerun is paired with
the baseline but not identical to it apart from the agent; averaging over seeds smooths that
out, and an intervention that keeps the agent (``intervene`` setting its state) changes the
draws less.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly.decide._parallel import ordered
from modelly.decide.compare import CONFIDENCE, interval

type Build = Callable[[int], Any]


def remove(model: Any, agent: Any) -> None:
    """The default intervention: the agent leaves the model."""
    agent.remove()


def _agent(model: Any, unique_id: int) -> Any:
    """The agent of ``model`` with ``unique_id``."""
    for agent in model.agents:
        if agent.unique_id == unique_id:
            return agent
    raise KeyError(f"no agent {unique_id} in the rebuilt model")


@dataclass(frozen=True)
class Attribution:
    """The effect of intervening on each candidate, largest first.

    Attributes:
        table: per candidate (its unique id): the mean change of the outcome (baseline
            minus intervened) and its interval over the seeds.
        baseline: the outcome of each seed's unchanged run.
    """

    table: pd.DataFrame
    baseline: tuple[float, ...]

    def top(self, n: int = 5) -> list[int]:
        """The unique ids of the ``n`` candidates with the largest effect."""
        return [int(i) for i in self.table.index[:n]]


def _run(model: Any, steps: int, output: Callable[[Any], float]) -> float:
    """Run ``steps`` steps and read the outcome."""
    model.run_for(steps)
    return float(output(model))


@dataclass(frozen=True)
class _Rerun:
    """One seed's rerun with an intervention on one agent: the outcome (runs in a worker)."""

    build: Build
    intervene: Callable[[Any, Any], None]
    output: Callable[[Any], float]
    steps: int
    seed: int

    def __call__(self, unique_id: int) -> float:
        """Rebuild, intervene on agent ``unique_id``, run, read the outcome."""
        model = self.build(self.seed)
        self.intervene(model, _agent(model, unique_id))
        return _run(model, self.steps, self.output)


def attribute(
    build: Build, candidates: Callable[[Any], Sequence[Any]], output: Callable[[Any], float],
    *, steps: int, seeds: Sequence[int] = (0,),
    intervene: Callable[[Any, Any], None] = remove, confidence: float = CONFIDENCE,
    workers: int | None = 1,
) -> Attribution:  # fmt: skip
    """Intervene on each candidate agent in turn; the outcome's change, per candidate.

    ``build(seed)`` makes a fresh model, ``candidates(model)`` lists the agents to try (in
    the freshly built model), ``output(model)`` reads the outcome after ``steps`` steps.
    ``workers`` reruns a seed's candidates over that many processes
    (``modelly.batch.run_batch``), with the same results; 1, the default, reruns them here.
    """
    effects: dict[int, list[float]] = {}
    baselines = []
    for seed in seeds:
        base = _run(build(seed), steps, output)
        baselines.append(base)
        ids = [agent.unique_id for agent in candidates(build(seed))]
        rerun = _Rerun(build, intervene, output, steps, seed)
        for unique_id, outcome in zip(ids, ordered(rerun, ids, workers)):
            effects.setdefault(unique_id, []).append(base - outcome)
    rows = [(uid, *interval(np.array(v), confidence)) for uid, v in effects.items()]
    table = pd.DataFrame(rows, columns=["agent", "effect", "low", "high"]).set_index(
        "agent"
    )
    return Attribution(table.sort_values("effect", ascending=False, kind="stable"),
                       tuple(baselines))  # fmt: skip
