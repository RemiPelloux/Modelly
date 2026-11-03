"""The vaccination study of the decisions guide: which age group should get the doses?

The age-structured SEIR zoo model with 10,000 doses to give before an epidemic: to children,
to adults, to seniors, or to nobody. Each strategy is run with common random numbers; the
outputs are the infections and the deaths (an illustrative infection fatality ratio per age
group), the cost is the doses plus the care of each infection. The numbers are illustrative,
not a recommendation: see the age_seir model card.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from modelly.decide.compare import Comparison, Strategy, compare, model_runner
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

DOSES = 10_000
DOSE_COST = 20.0
CARE_COST = 150.0  # per infection
FATALITY = np.array([0.0001, 0.002, 0.03])  # children, adults, seniors (illustrative)


def infections(model: AgeSEIR) -> float:
    """People ever infected, every group."""
    return float(np.sum(model.attack_rate() * model.sizes))


def deaths(model: AgeSEIR) -> float:
    """Expected deaths: each group's infections times its fatality ratio."""
    return float(np.sum(model.attack_rate() * model.sizes * FATALITY))


def doses(group: int | None) -> tuple:
    """``vaccinated`` with every dose given to ``group`` (None: nobody)."""
    given = [0, 0, 0]
    if group is not None:
        given[group] = DOSES
    return tuple(given)


def cost(group: int | None) -> Any:
    """The cost of a strategy's run: its doses plus the care of its infections."""
    vaccine = 0.0 if group is None else DOSES * DOSE_COST

    def of(outputs: dict[str, float]) -> float:
        return vaccine + CARE_COST * outputs["infections"]

    return of


GROUPS = {"nobody": None, "children": 0, "adults": 1, "seniors": 2}
STRATEGIES = tuple(
    Strategy(name, {"vaccinated": doses(group)}, cost(group))
    for name, group in GROUPS.items()
)


def vaccination_study(replicates: int = 20, seed: int = 7) -> Comparison:
    """Run the four strategies; ``rank``, ``difference`` and the cost tables read it."""
    run = model_runner(AgeSEIR, {"infections": infections, "deaths": deaths},
                       scenario=SEIRScenario, base={"steps": 300})  # fmt: skip
    study = compare(run, STRATEGIES, replicates=replicates, seed=seed)
    study.runs["deaths_averted"] = (
        _baseline(study, "deaths") - study.runs["deaths"].to_numpy()
    )
    return study


def _baseline(study: Comparison, output: str) -> np.ndarray:
    """The baseline's ``output`` in the replicate of each row."""
    base = study.values(output, study.names[0])
    return base[study.runs["replicate"].to_numpy()]


__all__ = ["STRATEGIES", "vaccination_study"]
