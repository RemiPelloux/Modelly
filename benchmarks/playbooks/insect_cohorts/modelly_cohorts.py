"""The insect population as cohorts (super-individuals), written for Modelly.

Same model as ``mesa_model.py`` in distribution, compressed: one agent stands
for every insect that is in the same stage, has the same age and the same sex.
Daily survival thins each cohort with one Binomial draw (``ColumnTable.thin``),
sex at emergence splits a pupal cohort with a Binomial draw, and the number of
laying females in a mature cohort is a Binomial draw too. Each of those is the
law of the corresponding independent per-insect draws, so the stage counts have
the same distribution as the individual-level model (see
docs/vectorised_phases.md, cohort compression). The number of agents is the
number of distinct (stage, age, sex) classes, a few dozen, whatever the
population.
"""

from __future__ import annotations

import math

import numpy as np

from modelly import Agent, Column, Model

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3


class Cohort(Agent):
    """``count`` identical insects: same stage, same age in stage, same sex."""

    count = Column(np.int64, default=0)
    stage = Column(np.int8, default=EGG)
    age = Column(np.int16, default=0)
    female = Column(bool, default=False)

    def __init__(self, model, count=0, stage=EGG, age=0, female=False):
        super().__init__(model)
        self.count, self.stage, self.age, self.female = count, stage, age, female


class Population(Model):
    """The cohorts and the daily step."""

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
        self._seed_adults(initial_adults)
        self.history = []

    def _seed_adults(self, initial_adults):
        """The initial adults, grouped by (age, sex) into cohorts."""
        ages = self.rng.integers(0, 20, initial_adults)
        females = self.rng.random(initial_adults) < 0.5
        for age in range(20):
            for female in (False, True):
                count = int(((ages == age) & (females == female)).sum())
                if count:
                    Cohort.create_agents(
                        self, 1, count=count, stage=ADULT, age=age, female=female
                    )

    def counts(self):
        table = self.columns[Cohort]
        return (
            np.bincount(table.stage, weights=table.count, minlength=4)
            .astype(int)
            .tolist()
        )

    def emerge(self, table):
        """Pupal cohorts at the end of the pupal stage become one female and one male cohort."""
        done = (table.stage == PUPA) & (table.age >= self.pupa_days)
        if not done.any():
            return
        rows = np.flatnonzero(done)
        total = table.count[rows]
        females = self.rng.binomial(total, 0.5)
        table.count[rows] = females
        table.stage[rows] = ADULT
        table.age[rows] = 0
        table.female[rows] = True
        Cohort.create_agents(
            self, rows.shape[0], count=total - females, stage=ADULT, age=0, female=False
        )

    def step(self):
        table = self.columns[Cohort]
        larvae = int(table.count[table.stage == LARVA].sum())
        survival = self.base_survival.copy()
        survival[LARVA] *= math.exp(-larvae / self.capacity)
        table.thin("count", survival[table.stage])
        table.age += 1
        for from_stage, duration in self.transitions:
            done = (table.stage == from_stage) & (table.age >= duration)
            table.stage[done] = from_stage + 1
            table.age[done] = 0
        self.emerge(table)
        mature = (table.stage == ADULT) & table.female & (table.age >= self.maturity)
        laying = self.rng.binomial(table.count[mature], self.lay_prob * self.fertile)
        eggs = int(laying.sum()) * self.clutch
        if eggs:
            Cohort.create_agents(self, 1, count=eggs)
        table.remove_where(table.count == 0)
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
