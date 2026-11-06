"""Decisions and causes, as the paper quotes them: data/decisions.json.

    python paper/scripts/decisions.py

Three measurements, each the one a test in ``tests/decide`` or ``tests/explain`` asserts on:
the vaccination study of ``modelly.decide`` (four strategies on common random numbers, ranked
by deaths, with intervals and the share of replicates each wins, run twice to check that the
ranking repeats); ``treatment_effect`` on the Bass zoo model for two changes of imitation and
on the age-structured SEIR model for vaccinating seniors (the variance reduction that common
random numbers bring, measured against independent seeds); and ``attribute`` on a sixty-person
outbreak (the index case's effect against the next agent's, on five seeds).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from environment import environment

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER.parent))

from modelly.decide import model_runner  # noqa: E402
from modelly.decide.vaccination import infections, vaccination_study  # noqa: E402
from modelly.examples.basic.virus_on_network.agents import State  # noqa: E402
from modelly.explain import attribute, treatment_effect  # noqa: E402
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario  # noqa: E402
from tests.explain.test_explain import (  # noqa: E402
    BASS,
    ever_infected,
    immunise,
    outbreak,
)

REPLICATES = 30
SEEDS = range(10)  # the variance reduction is itself an estimate: its spread over seeds
SENIORS = (0, 0, 10_000)  # the vaccination study's doses, all to the oldest group


def vaccination() -> dict:
    """The ranking by deaths, twice, and whether the two are identical."""
    first, again = vaccination_study(), vaccination_study()
    ranking = first.rank("deaths")
    same = ranking.equals(again.rank("deaths"))
    return {
        "replicates": 20,
        "seed": 7,
        "repeats_identically": bool(same),
        "rank_by_deaths": json.loads(ranking.reset_index().to_json(orient="records")),
    }


def effect_row(name: str, seed: int, effect) -> dict:
    """One effect as a record."""
    return {
        "case": name,
        "seed": seed,
        "mean": effect.mean,
        "low": effect.low,
        "high": effect.high,
        "variance_reduction": effect.variance_reduction,
        "replicates": REPLICATES,
    }


def effects() -> list[dict]:
    """Common random numbers on Bass (two changes) and age_seir (seniors), on ten seeds."""
    age = model_runner(
        AgeSEIR, {"infections": infections}, scenario=SEIRScenario, base={"steps": 300}
    )
    cases = [
        ("bass imitation 0.38 to 0.40", BASS, {"imitation": 0.40}, "adoption"),
        ("bass imitation 0.38 to 0.45", BASS, {"imitation": 0.45}, "adoption"),
        ("age_seir seniors vaccinated", age, {"vaccinated": SENIORS}, "infections"),
    ]
    return [
        effect_row(
            name,
            seed,
            treatment_effect(
                run, {}, treated, output, replicates=REPLICATES, seed=seed
            ),
        )
        for name, run, treated, output in cases
        for seed in SEEDS
    ]


def attribution() -> list[dict]:
    """Per seed: the index case, the top agent, and the two largest effects."""
    rows = []
    for seed in range(1, 6):
        found = attribute(
            outbreak,
            lambda m: list(m.agents),
            ever_infected,
            steps=40,
            seeds=[seed],
            intervene=immunise,
        )
        index = [
            a.unique_id for a in outbreak(seed).agents if a.state == State.INFECTED
        ]
        top = found.table["effect"].to_numpy()
        rows.append(
            {
                "seed": seed,
                "index_case_first": found.top(1) == index,
                "first_effect": float(top[0]),
                "second_effect": float(top[1]),
            }
        )
    return rows


def main() -> None:
    """Run the three measurements and write data/decisions.json."""
    out = {
        "environment": environment(),
        "vaccination": vaccination(),
        "effects": effects(),
        "attribution": attribution(),
    }
    (PAPER / "data" / "decisions.json").write_text(
        json.dumps(out, indent=1, default=float) + "\n"
    )
    pd.set_option("display.width", 120)
    print(
        json.dumps(
            {k: v for k, v in out.items() if k != "environment"},
            indent=1,
            default=float,
        )
    )


if __name__ == "__main__":
    main()
