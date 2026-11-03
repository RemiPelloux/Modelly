"""Intervention optimisation: search the parameters of a policy for the best outcome (Optuna).

``optimise(run, space, objective, trials=...)`` lets Optuna's TPE sampler propose policy
parameters from ``space`` (``{name: (low, high)}``, or a list of choices), evaluates each
proposal on the same replicate seeds (common random numbers, so two proposals differ only by
the policy), and keeps the best. The sampler is seeded from ``seed``, and trials run one after
another, so the same call gives the same trials and the same answer. Optuna is an optional
dependency: ``pip install "modelly-abm[decide]"``.

Reference:
    Akiba, T., Sano, S., Yanase, T., Ohta, T. and Koyama, M. (2019). Optuna: a
    next-generation hyperparameter optimization framework. KDD 2019, 2623-2631.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly._optional import require
from modelly.decide.compare import Outputs, Run, replicate_seeds

type Space = Mapping[str, tuple[float, float] | Sequence[Any]]


@dataclass(frozen=True)
class Optimum:
    """The best parameters found, their objective, and every trial.

    Attributes:
        params: the best proposal.
        value: its objective, averaged over the replicates.
        trials: one row per trial: its parameters and objective.
    """

    params: dict[str, Any]
    value: float
    trials: pd.DataFrame


def _suggest(trial: Any, space: Space) -> dict[str, Any]:
    """One proposal: a float in each range, a choice from each list."""
    params = {}
    for name, domain in space.items():
        if (
            isinstance(domain, tuple)
            and len(domain) == 2
            and all(isinstance(v, int | float) for v in domain)
        ):
            params[name] = trial.suggest_float(name, float(domain[0]), float(domain[1]))
        else:
            params[name] = trial.suggest_categorical(name, list(domain))
    return params


def optimise(
    run: Run, space: Space, objective: Callable[[Outputs], float], *, trials: int = 50,
    replicates: int = 5, seed: int = 0, minimise: bool = True,
    fixed: Mapping[str, Any] | None = None,
) -> Optimum:  # fmt: skip
    """Search ``space`` for the parameters with the best mean ``objective``."""
    optuna = require("optuna", "decide")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    seeds = replicate_seeds(seed, replicates)

    def evaluate(trial: Any) -> float:
        params = {**(fixed or {}), **_suggest(trial, space)}
        return float(np.mean([objective(run(params, x)) for x in seeds]))

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(
        direction="minimize" if minimise else "maximize", sampler=sampler
    )
    study.optimize(evaluate, n_trials=trials, n_jobs=1)
    frame = pd.DataFrame([{**t.params, "objective": t.value} for t in study.trials])
    return Optimum(dict(study.best_params), float(study.best_value), frame)
