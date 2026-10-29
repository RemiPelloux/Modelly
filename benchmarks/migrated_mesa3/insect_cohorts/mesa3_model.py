"""Stage-structured insect population under sterile releases, migrated from Mesa 3.5 to Modelly by the codemod alone (see ../README.md).

Same model as ``mesa_model.py``, one ``modelly.Agent`` per insect. Each insect is
an egg, larva, pupa or adult. Every day: it survives with its stage's daily
probability (larval survival is scaled by exp(-L / capacity), L the number of
larvae at the start of the day); it ages one day and moves to the next stage
when its stage's duration is reached (sex is drawn at adult emergence); a
mature adult female lays a clutch with probability ``lay_prob``, and the
clutch is fertile with probability 1 / (1 + sterile_ratio). Eggs laid today
start acting tomorrow: ``shuffle_do`` steps the agents present when it starts.
"""

from __future__ import annotations

import math

from modelly import Agent, Model

EGG, LARVA, PUPA, ADULT = 0, 1, 2, 3
STAGES = ("egg", "larva", "pupa", "adult")
FEMALE_FRACTION = 0.5
INITIAL_AGE_LIMIT = 20


class Insect(Agent):
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
                self.female = self.random.random() < FEMALE_FRACTION
        if (
            self.stage == ADULT
            and self.female
            and self.age >= model.maturity
            and self.random.random() < model.lay_prob
            and self.random.random() < model.fertile
        ):
            Insect.create_agents(model, model.clutch, EGG, 0, False)


class Population(Model):
    """The insects and the daily step."""

    def __init__(self, initial_adults, capacity, durations, survival, rng, **laying):
        super().__init__(rng=rng)
        self.durations = (*durations, None)
        self.base_survival = tuple(survival[stage] for stage in STAGES)
        self.survival_today = self.base_survival
        self.capacity = capacity
        self.maturity = laying["maturity_days"]
        self.lay_prob, self.clutch = laying["lay_prob"], laying["clutch"]
        self.fertile = 1.0 / (1.0 + laying["sterile_ratio"])
        for _ in range(initial_adults):
            age = self.random.randrange(0, INITIAL_AGE_LIMIT)
            Insect(self, ADULT, age, self.random.random() < FEMALE_FRACTION)
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
        self.agents.shuffle_do("step")
        self.history.append(self.counts())


def build(seed, initial_adults, capacity, egg_days, larva_days, pupa_days, **rest):
    """Build the model."""
    durations = (egg_days, larva_days, pupa_days)
    survival = rest.pop("survival")
    return Population(initial_adults, capacity, durations, survival, rng=seed, **rest)


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
