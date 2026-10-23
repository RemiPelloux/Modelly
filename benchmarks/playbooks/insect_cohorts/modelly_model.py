"""Stage-structured insect population under sterile releases, written for Modelly.

Same model as ``mesa_model.py``, one agent per insect. Survival, ageing, stage
transitions and the laying decision are column operations; the clutches of the
day are created in one ``create_agents`` call.
"""

from __future__ import annotations

import math

import numpy as np

from modelly import Agent, Column, Model

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3


class Insect(Agent):
    """One insect; stage, age and sex live in the column table."""

    stage = Column(np.int8, default=EGG)
    age = Column(np.int16, default=0)
    female = Column(bool, default=False)

    def __init__(self, model, stage=EGG, age=0, female=False):
        super().__init__(model)
        if stage != EGG:
            self.stage, self.age, self.female = stage, age, female


class Population(Model):
    """The insects and the vectorised daily step."""

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
        self.transitions = ((EGG, egg_days), (LARVA, larva_days), (PUPA, pupa_days))
        self.base_survival = np.array(
            [survival["egg"], survival["larva"], survival["pupa"], survival["adult"]]
        )
        self.capacity, self.maturity = capacity, maturity_days
        self.lay_prob, self.clutch = lay_prob, clutch
        self.fertile = 1.0 / (1.0 + sterile_ratio)
        Insect.create_agents(
            self,
            initial_adults,
            stage=ADULT,
            age=self.rng.integers(0, 20, initial_adults),
            female=self.rng.random(initial_adults) < 0.5,
        )
        self.history = []

    def counts(self):
        return np.bincount(self.columns[Insect].stage, minlength=4).tolist()

    def step(self):
        table = self.columns[Insect]
        larvae = int((table.stage == LARVA).sum())
        survival = self.base_survival.copy()
        survival[LARVA] *= math.exp(-larvae / self.capacity)
        table.remove_where(~table.draw(survival[table.stage]))
        stage, age, female = table.stage, table.age, table.female
        age += 1
        for from_stage, duration in self.transitions:
            done = (stage == from_stage) & (age >= duration)
            stage[done] = from_stage + 1
            age[done] = 0
            if from_stage == PUPA:
                female[done] = self.rng.random(int(done.sum())) < 0.5
        mature = (stage == ADULT) & female & (age >= self.maturity)
        laying = mature & table.draw(self.lay_prob * self.fertile)
        eggs = int(laying.sum()) * self.clutch
        if eggs:
            Insect.create_agents(self, eggs)
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
