"""The insect population as cohorts, with the cohort table on a GPU.

Same model as ``modelly_cohorts.py``: one row per (stage, age, sex) class,
survival a binomial thinning, sex at emergence a binomial split, laying a
binomial draw. The table is a ``DeviceCohortTable`` on the backend chosen by
``MODELLY_BACKEND`` (``cupy``, ``jax``, ``numpy``; ``auto`` by default) and the
draws come from a ``PhiloxStream``, so a seed gives the same counts on every
backend. The updates are written functionally (``set_where``, ``put``), which
the host table writes in place.

The table has fewer than two hundred rows whatever the population, so this
variant shows the cohort operations run on a GPU, not that they run faster
there: each step is a few dozen kernel launches on tiny arrays.
"""

from __future__ import annotations

import math
import os

import numpy as np

from modelly import CohortTable, Model
from modelly.gpu import DeviceCohortTable, PhiloxStream, get_backend
from modelly.gpu.backend import AUTO, ENV_VARIABLE

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3
STAGES = 4
STEP_STREAM = 0


class Population(Model):
    """The cohorts (a DeviceCohortTable) and the daily step."""

    def __init__(self, params, rng):
        super().__init__(rng=rng)
        self.transitions = ((EGG, params["egg_days"]), (LARVA, params["larva_days"]))
        self.pupa_days = params["pupa_days"]
        survival = params["survival"]
        self.base_survival = np.array(
            [survival["egg"], survival["larva"], survival["pupa"], survival["adult"]]
        )
        self.capacity, self.maturity = params["capacity"], params["maturity_days"]
        self.lay_prob, self.clutch = params["lay_prob"], params["clutch"]
        self.fertile = 1.0 / (1.0 + params["sterile_ratio"])
        host = CohortTable(self.rng, stage=np.int8, age=np.int16, female=bool)
        adults = params["initial_adults"]
        host.add(
            np.ones(adults, dtype=np.int64),
            stage=ADULT,
            age=self.rng.integers(0, 20, adults),
            female=self.rng.random(adults) < 0.5,
        )
        host.merge()
        backend = get_backend(os.environ.get(ENV_VARIABLE, AUTO))
        self.stream = PhiloxStream(rng, STEP_STREAM, backend)
        self.cohorts = DeviceCohortTable.from_table(host, self.stream)
        self.history = []

    def counts(self):
        table = self.cohorts
        return table.backend.to_numpy(table.totals_by("stage", STAGES)).tolist()

    def emerge(self):
        """Each pupal cohort at the end of the pupal stage splits into females and males."""
        table, backend = self.cohorts, self.cohorts.backend
        done = (table["stage"] == PUPA) & (table["age"] >= self.pupa_days)
        if not bool(done.any()):
            return
        rows = backend.xp.nonzero(done)[0]
        table.split(0.5, where=done, stage=ADULT, age=0, female=True)
        for name, value in (("stage", ADULT), ("age", 0), ("female", False)):
            table[name] = backend.put(table[name], rows, value)  # the males

    def step(self):
        table, backend = self.cohorts, self.cohorts.backend
        survival = self.base_survival.copy()
        survival[LARVA] *= math.exp(
            -table.total(table["stage"] == LARVA) / self.capacity
        )
        table.thin(backend.asarray(survival)[table["stage"].astype(np.int32)])
        table["age"] = table["age"] + 1
        for from_stage, duration in self.transitions:
            done = (table["stage"] == from_stage) & (table["age"] >= duration)
            table.set_where("stage", done, from_stage + 1)
            table.set_where("age", done, 0)
        self.emerge()
        mature = (
            (table["stage"] == ADULT)
            & table["female"]
            & (table["age"] >= self.maturity)
        )
        laying = table.draw(self.lay_prob * self.fertile, where=mature)
        eggs = int(laying.sum()) * self.clutch
        if eggs:
            table.add(eggs, stage=EGG)
        table.compact()
        self.history.append(self.counts())


def build(seed, **params):
    """Build the model."""
    return Population(params, seed)


def simulate(model, steps):
    """Run ``steps`` days and summarise."""
    model.run_for(steps)
    adults = [h[ADULT] for h in model.history]
    final = model.history[-1]
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
