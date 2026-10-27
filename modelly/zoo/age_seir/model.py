"""Age-structured SEIR epidemic with a contact matrix.

A population split into age groups, each person susceptible (S), exposed (E), infectious
(I) or recovered (R). A susceptible of group ``a`` is infected in one step with probability
``1 - exp(-beta * sum_b C[a, b] * I_b / N_b)``, where ``C[a, b]`` is the mean number of
contacts a member of ``a`` has with members of ``b`` per step (a contact matrix, as
measured by social-contact surveys or computed by
``modelly.space.networks.contact_matrix``). Exposed people become infectious with
probability ``incubation`` per step and infectious people recover with probability
``recovery`` per step.

Everybody in the same group and state faces the same probabilities, so the population is
a ``CohortTable`` with one row per (group, state): every transition is one binomial draw
per row, with exactly the law of the per-person draws (see ``docs/vectorised_phases.md``).
A million people cost the same as a hundred.

Validation: the final-size relation. Summing the force of infection over the epidemic,
``log(s_a) = log(s0_a) - (beta / recovery) * sum_b C[a, b] * (1 - s_b)``, where ``s_a`` is
the share of group ``a`` never infected; with one group this is the Kermack-McKendrick
relation ``s = s0 * exp(-R0 * (1 - s))``. ``final_size()`` solves it and the test compares
it with the simulated epidemic. ``r0()`` is ``beta / recovery`` times the spectral radius
of the next-generation matrix.

Starting from a synthetic population: ``scenario_from_population(people, network, levels)``
takes the group sizes from the people's age levels and the contact matrix from their
contact network (``modelly.population``: households, schools and workplaces), so the
model runs on a population built from census tables instead of the illustrative default.

References:
    Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory
    of epidemics. Proceedings of the Royal Society A, 115, 700-721.

    Mossong, J. et al. (2008). Social contacts and mixing patterns relevant to the spread
    of infectious diseases. PLoS Medicine, 5(3), e74.

    Andersson, H. and Britton, T. (2000). Stochastic Epidemic Models and Their Statistical
    Analysis. Lecture Notes in Statistics 151, Springer.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum
from functools import partial
from typing import Any

import numpy as np

from modelly.batch.cohorts import CohortTable
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.networks.contacts import contact_matrix


class State(IntEnum):
    """Infection states."""

    S = 0
    E = 1
    I = 2  # noqa: E741 - the epidemiological name
    R = 3


class SEIRScenario(Scenario):
    """Parameters of the age-structured SEIR model.

    The default contact matrix is illustrative (children, adults, seniors), not survey
    data; it is reciprocal, ``N[a] * C[a, b] == N[b] * C[b, a]``.

    Attributes:
        group_sizes: number of people in each age group.
        contacts: contact matrix ``C[a][b]``, contacts per step of a member of ``a``
            with members of ``b``.
        beta: probability of transmission per contact with an infectious person.
        incubation: probability per step that an exposed person becomes infectious.
        recovery: probability per step that an infectious person recovers.
        initial_infected: infectious people at the start, per group.
        steps: default run length used by ``run``.
    """

    group_sizes: tuple = (20_000, 60_000, 20_000)
    contacts: tuple = ((8.0, 6.0, 1.0), (2.0, 9.0, 1.0), (1.0, 3.0, 2.0))
    beta: float = 0.035
    incubation: float = 0.25
    recovery: float = 0.2
    initial_infected: tuple = (10, 10, 10)
    steps: int = 400


class AgeSEIR(Model):
    """SEIR over age groups, one cohort row per (group, state).

    Example:
        >>> model = AgeSEIR(SEIRScenario(rng=1, steps=50))
        >>> model.run()
        >>> int(model.counts().sum()) == sum(model.scenario.group_sizes)
        True
    """

    def __init__(self, scenario: SEIRScenario = SEIRScenario) -> None:
        """Seed the infectious people; everybody else is susceptible."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.contacts = np.asarray(s.contacts, dtype=float)
        self.sizes = np.asarray(s.group_sizes, dtype=np.int64)
        self.n_groups = self.sizes.shape[0]
        groups = np.arange(self.n_groups)
        seeds = np.asarray(s.initial_infected, dtype=np.int64)
        self.people = CohortTable(self.rng, group=np.int16, state=np.int8)
        self.people.add(self.sizes - seeds, group=groups, state=State.S)
        self.people.add(seeds, group=groups, state=State.I)
        self.datacollector = DataCollector(
            model_reporters={
                state.name: partial(count_in, state=state) for state in State
            }
        )
        self.datacollector.collect(self)

    def counts(self) -> np.ndarray:
        """People per (group, state), shape ``(n_groups, 4)``."""
        p = self.people
        flat = p["group"].astype(np.int64) * len(State) + p["state"]
        totals = np.bincount(
            flat, weights=p["count"], minlength=self.n_groups * len(State)
        )
        return totals.astype(np.int64).reshape(self.n_groups, len(State))

    def force(self) -> np.ndarray:
        """Per-step hazard of infection of a susceptible in each group."""
        infectious = self.counts()[:, State.I] / self.sizes
        return self.scenario.beta * self.contacts @ infectious

    def step(self) -> None:
        """Recover, then progress, then infect, all from the start-of-step state."""
        s = self.scenario
        p = self.people
        hazard = self.force()
        p.split(s.recovery, p["state"] == State.I, state=State.R)
        p.split(s.incubation, p["state"] == State.E, state=State.I)
        susceptible = p["state"] == State.S
        catch = 1.0 - np.exp(-hazard[p["group"][susceptible]])
        p.split(catch, susceptible, state=State.E)
        p.merge()
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def r0(self) -> float:
        """Basic reproduction number: spectral radius of the next-generation matrix."""
        s = self.scenario
        ngm = (s.beta / s.recovery) * self.contacts
        return float(np.max(np.abs(np.linalg.eigvals(ngm))))

    def final_size(self, tolerance: float = 1e-12) -> np.ndarray:
        """Share of each group ever infected, from the final-size relation."""
        s = self.scenario
        s0 = 1.0 - np.asarray(s.initial_infected) / self.sizes
        ngm = (s.beta / s.recovery) * self.contacts
        escape = np.zeros(self.n_groups)
        for _ in range(_MAX_ITERATIONS):
            new = s0 * np.exp(-ngm @ (1.0 - escape))
            if np.max(np.abs(new - escape)) < tolerance:
                break
            escape = new
        return 1.0 - new

    def attack_rate(self) -> np.ndarray:
        """Share of each group ever infected so far."""
        return 1.0 - self.counts()[:, State.S] / self.sizes


# Iterating from "nobody escapes" converges monotonically to the epidemic root.
_MAX_ITERATIONS = 10_000
# The age column of a ``modelly.population`` DataFrame, and the default seeds per group.
AGE = "age"
SEEDS_PER_GROUP = 10


def scenario_from_population(
    people: Any, network: Any, levels: Sequence, **parameters: Any
) -> SEIRScenario:
    """A scenario whose age groups and contacts come from a synthetic population.

    Args:
        people: one row per person with an ``age`` column, as ``modelly.population``
            builds it (``synthesize_population``, then ``assign_households`` and so on).
        network: the people's contact network, node ``i`` the ``i``-th row
            (``modelly.population.contact_network``); its weights are contacts per step.
        levels: the age levels in group order, for example ``("0-17", "18-64", "65+")``.
        **parameters: any other ``SEIRScenario`` field (``rng``, ``beta``, ...);
            ``initial_infected`` defaults to 10 per group, or the whole group if smaller.

    Returns:
        an ``SEIRScenario`` with ``group_sizes`` counted from ``people`` and ``contacts``
        from ``contact_matrix(network, groups)``.

    Raises:
        ValueError: if an age level has nobody in it.
    """
    lookup = {level: group for group, level in enumerate(levels)}
    groups = np.fromiter((lookup[age] for age in people[AGE]), dtype=np.intp)
    sizes = np.bincount(groups, minlength=len(levels))
    if not sizes.all():
        raise ValueError(f"Every age level needs people; counts are {sizes.tolist()}.")
    contacts = contact_matrix(network, groups, n_groups=len(levels))
    parameters.setdefault(
        "initial_infected", tuple(int(n) for n in np.minimum(sizes, SEEDS_PER_GROUP))
    )
    return SEIRScenario(
        group_sizes=tuple(int(n) for n in sizes),
        contacts=tuple(tuple(float(c) for c in row) for row in contacts),
        **parameters,
    )


def count_in(model: AgeSEIR, state: State) -> int:
    """The number of people in ``state``, all groups together (a model reporter)."""
    return int(model.counts()[:, state].sum())
