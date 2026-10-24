"""The insect population as cohorts (super-individuals), written for Modelly.

Same model as ``mesa_model.py`` in distribution, compressed: one row of a
``CohortTable`` stands for every insect that is in the same stage, has the same
age and the same sex; there are no agent objects. Daily survival thins each
cohort with one Binomial draw (``thin``), sex at emergence splits a pupal cohort
with a Binomial draw (``split``), and the number of laying females in a mature
cohort is a Binomial draw too (``draw``). Each of those is the
law of the corresponding independent per-insect draws, so the stage counts have
the same distribution as the individual-level model (see
docs/vectorised_phases.md, cohort compression). The number of rows is the
number of distinct (stage, age, sex) classes, a few dozen, whatever the
population.
"""

from __future__ import annotations

import math

import numpy as np

from modelly import CohortTable, Model

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3


class Population(Model):
    """The cohorts (a CohortTable, no agent objects) and the daily step."""

    def __init__(
        self,
        initial_adults,
        capacity,
        egg_days,
        larva_days,
        pupa_days,
        maturity_days,
        survival,
        lay_prob,
        clutch,
        sterile_ratio,
        rng,
    ):
        super().__init__(rng=rng)
        self.transitions = ((EGG, egg_days), (LARVA, larva_days))
        self.pupa_days = pupa_days
        self.base_survival = np.array(
            [survival["egg"], survival["larva"], survival["pupa"], survival["adult"]]
        )
        self.capacity, self.maturity = capacity, maturity_days
        self.lay_prob, self.clutch = lay_prob, clutch
        self.fertile = 1.0 / (1.0 + sterile_ratio)
        self.cohorts = CohortTable(self.rng, stage=np.int8, age=np.int16, female=bool)
        # the initial adults, one row each, merged into one cohort per (age, sex)
        self.cohorts.add(
            np.ones(initial_adults, dtype=np.int64),
            stage=ADULT,
            age=self.rng.integers(0, 20, initial_adults),
            female=self.rng.random(initial_adults) < 0.5,
        )
        self.cohorts.merge()
        self.history = []

    def counts(self):
        return self.cohorts.totals_by("stage", minlength=4).tolist()

    def emerge(self):
        """Each pupal cohort at the end of the pupal stage splits into females and males."""
        table = self.cohorts
        done = (table["stage"] == PUPA) & (table["age"] >= self.pupa_days)
        if not done.any():
            return
        rows = np.flatnonzero(done)
        table.split(0.5, where=done, stage=ADULT, age=0, female=True)
        table["stage"][rows] = ADULT  # the rest of each cohort: the males
        table["age"][rows] = 0
        table["female"][rows] = False

    def step(self):
        table = self.cohorts
        survival = self.base_survival.copy()
        survival[LARVA] *= math.exp(
            -table.total(table["stage"] == LARVA) / self.capacity
        )
        table.thin(survival[table["stage"]])
        table["age"] += 1
        stage, age = table["stage"], table["age"]
        for from_stage, duration in self.transitions:
            done = (stage == from_stage) & (age >= duration)
            stage[done] = from_stage + 1
            age[done] = 0
        self.emerge()
        mature = (
            (table["stage"] == ADULT)
            & table["female"]
            & (table["age"] >= self.maturity)
        )
        eggs = (
            int(table.draw(self.lay_prob * self.fertile, where=mature).sum())
            * self.clutch
        )
        if eggs:
            table.add(eggs, stage=EGG)
        table.compact()
        self.history.append(self.counts())


def build(
    seed,
    initial_adults,
    capacity,
    egg_days,
    larva_days,
    pupa_days,
    maturity_days,
    survival,
    lay_prob,
    clutch,
    sterile_ratio,
):
    """Build the model."""
    return Population(
        initial_adults,
        capacity,
        egg_days,
        larva_days,
        pupa_days,
        maturity_days,
        survival,
        lay_prob,
        clutch,
        sterile_ratio,
        seed,
    )


def simulate(model, steps):
    """Run ``steps`` days and summarise."""
    model.run_for(steps)
    return summarise(model.history)


def summarise(history):
    """Final stage counts, mean and peak adults."""
    adults = [h[ADULT] for h in history]
    final = history[-1]
    return {
        "population": sum(final),
        "stats": {
            "final_eggs": final[EGG],
            "final_larvae": final[LARVA],
            "final_pupae": final[PUPA],
            "final_adults": final[ADULT],
            "mean_adults": sum(adults) / len(adults),
            "peak_adults": max(adults),
        },
    }
