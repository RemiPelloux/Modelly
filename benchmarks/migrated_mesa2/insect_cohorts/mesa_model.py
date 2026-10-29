"""Stage-structured insect population, migrated from Mesa 2.3 to Modelly (see ../README.md).

Each insect is an egg, larva, pupa or adult. Every day: it survives with its
stage's daily probability (larval survival is scaled by exp(-L / capacity),
L the number of larvae at the start of the day); it ages one day and moves to
the next stage when its stage's duration is reached (sex is drawn at adult
emergence); a mature adult female lays a clutch with probability ``lay_prob``,
and the clutch is fertile with probability 1 / (1 + sterile_ratio). Eggs laid
today start acting tomorrow.
"""

from __future__ import annotations

import math

import modelly

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3


class Insect(modelly.Agent):
    """One insect: stage, days in stage, sex."""

    def __init__(self, model, stage, age, female):
        super().__init__(model)
        self.stage = stage
        self.age = age
        self.female = female

    def step(self):
        model = self.model
        if self.random.random() >= model.survival_today[self.stage]:
            self.remove()
            return
        self.age += 1
        duration = model.durations[self.stage]
        if duration is not None and self.age >= duration:
            self.stage += 1
            self.age = 0
            if self.stage == ADULT:
                self.female = self.random.random() < 0.5
        if (
            self.stage == ADULT
            and self.female
            and self.age >= model.maturity
            and self.random.random() < model.lay_prob
            and self.random.random() < model.fertile
        ):
            for _ in range(model.clutch):
                Insect(model, EGG, 0, False)


class Population(modelly.Model):
    """The insects and the daily step."""

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
        seed,
    ):
        super().__init__(rng=seed)
        self.random = modelly.FastRandom(seed)  # Mesa 2.3: random.Random(seed)
        self.durations = (egg_days, larva_days, pupa_days, None)
        self.base_survival = (
            survival["egg"],
            survival["larva"],
            survival["pupa"],
            survival["adult"],
        )
        self.capacity, self.maturity = capacity, maturity_days
        self.lay_prob, self.clutch = lay_prob, clutch
        self.fertile = 1.0 / (1.0 + sterile_ratio)
        self.survival_today = self.base_survival
        for _ in range(initial_adults):
            Insect(
                self,
                ADULT,
                self.random.randrange(0, 20),
                self.random.random() < 0.5,
            )
        self.history = []

    def counts(self):
        counts = [0, 0, 0, 0]
        for insect in self.agents:
            counts[insect.stage] += 1
        return counts

    def step(self):
        larvae = self.counts()[LARVA]
        egg, larva, pupa, adult = self.base_survival
        self.survival_today = (
            egg,
            larva * math.exp(-larvae / self.capacity),
            pupa,
            adult,
        )
        insects = list(self.agents)
        self.random.shuffle(insects)
        for insect in insects:
            insect.step()
        self.history.append(self.counts())


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
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
        seed=seed,
    )


def simulate(model, steps):
    """Run ``steps`` days and summarise."""
    for _ in range(steps):
        model.step()
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
