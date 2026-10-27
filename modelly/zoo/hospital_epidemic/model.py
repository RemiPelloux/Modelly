"""An epidemic among agents coupled to a hospital-capacity model.

People are agents, each susceptible (S), infectious (I) or recovered (R), mixing
homogeneously. A susceptible is infected in a step with probability
``1 - exp(-beta_eff * I / N)``, an infectious person recovers with probability
``recovery`` per step, and a share ``severe`` of the new infections need a hospital bed.

The hospital is a stock-flow model (``modelly.couple.StockFlow``) integrated with
``solve_ivp``: the ``occupied`` beds fill with the admissions of the agents' step and
empty at rate ``occupied / stay``; the ``beds`` open and close towards
``base_beds + surge * occupied`` with time constant ``ramp``, as a hospital adds surge
capacity. People respond to the hospital's pressure: contacts fall with the share of beds
occupied, ``beta_eff = beta / (1 + response * occupied / beds)``. The agents' phase reads
``occupied`` and ``beds`` and writes ``admissions``; the hospital, one phase later, reads
the admissions and writes the beds, so the feedback acts with a lag of one step.

Validation: three known answers. Without the response (``response = 0``) the epidemic is
the stochastic general epidemic, whose attack rate solves the final-size relation
``s = s0 exp(-R0 (1 - s))`` with ``R0 = beta / recovery``, within the central-limit bound
(Andersson and Britton, 2000). The hospital equations are linear, so for the admissions of
each step, held over the step, the exact solution is a matrix exponential; the integrated
occupancy and beds match it to the solver's tolerance. And the stock-flow keeps its mass
balance: the admissions the agents wrote equal the patients in hospital plus those
discharged, to round-off.

References:
    Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory
    of epidemics. Proceedings of the Royal Society A, 115, 700-721.

    Andersson, H. and Britton, T. (2000). Stochastic Epidemic Models and Their Statistical
    Analysis. Lecture Notes in Statistics 151, Springer.

    Sterman, J. D. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex
    World. Irwin/McGraw-Hill.
"""

from __future__ import annotations

from enum import IntEnum
from functools import partial

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.couple.ode import Flow, StockFlow
from modelly.couple.schedule import Coupling, Phase
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

OCCUPIED, BEDS, ADMISSIONS = "occupied", "beds", "admissions"
AGENT_PHASE, HOSPITAL_PHASE = 0, 1
# Iterating from "nobody escapes" converges monotonically to the epidemic root.
_MAX_ITERATIONS = 10_000


class State(IntEnum):
    """Infection states."""

    S = 0
    I = 1  # noqa: E741 - the epidemiological name
    R = 2


class Person(Agent):
    """A person: their infection state."""

    state = Column(np.int8)

    def __init__(self, model: HospitalEpidemic, state: int) -> None:
        """Start in ``state``."""
        super().__init__(model)
        self.state = state


class HospitalScenario(Scenario):
    """Parameters of the epidemic and of the hospital.

    Attributes:
        population: number of people.
        initial_infected: infectious people at the start.
        beta: transmission rate per step (``R0 = beta / recovery``).
        recovery: probability per step that an infectious person recovers.
        severe: share of new infections admitted to hospital.
        stay: mean length of a hospital stay, in steps.
        base_beds: beds open when the hospital is empty.
        surge: beds opened per occupied bed.
        ramp: time constant of opening and closing beds, in steps.
        response: how strongly contacts fall with the share of beds occupied.
        steps: default run length used by ``run``.
    """

    population: int = 20_000
    initial_infected: int = 20
    beta: float = 0.3
    recovery: float = 0.1
    severe: float = 0.02
    stay: float = 8.0
    base_beds: float = 40.0
    surge: float = 0.5
    ramp: float = 7.0
    response: float = 1.0
    steps: int = 300


class HospitalEpidemic(Model):
    """SIR agents whose admissions drive a hospital stock-flow model, and back.

    Attributes:
        hospital: the hospital ``StockFlow`` (stocks ``occupied`` and ``beds``).
        coupling: the schedule: the agents in phase 0, the hospital in phase 1.
        admitted: admissions written by the agents so far.

    Example:
        >>> model = HospitalEpidemic(HospitalScenario(rng=1, steps=30))
        >>> model.run()
        >>> model.hospital.state["beds"] > 0
        True
    """

    def __init__(self, scenario: HospitalScenario = HospitalScenario) -> None:
        """Make the people, the hospital and the coupling between them."""
        super().__init__(scenario=scenario)
        s = self.scenario
        states = np.full(s.population, State.S, dtype=np.int8)
        states[: s.initial_infected] = State.I
        Person.create_agents(self, s.population, states.tolist())
        self.admitted = 0
        self.coupling = Coupling()
        phase = Phase(self.transmit, reads=[OCCUPIED, BEDS], writes=[ADMISSIONS])
        self.coupling.add(phase, AGENT_PHASE)
        self.hospital = self.coupling.add(hospital(s), HOSPITAL_PHASE)
        self.coupling.build()
        self.datacollector = DataCollector(
            model_reporters={
                **{state.name: partial(count_in, state=state) for state in State},
                ADMISSIONS: partial(quantity, name=ADMISSIONS, default=0),
                OCCUPIED: partial(quantity, name=OCCUPIED),
                BEDS: partial(quantity, name=BEDS),
            }
        )
        self.datacollector.collect(self)

    def transmit(self) -> None:
        """Recover, then infect from the start-of-step state; write the admissions."""
        s = self.scenario
        table = self.columns[Person]
        pressure = self.coupling[OCCUPIED] / self.coupling[BEDS]
        beta = s.beta / (1.0 + s.response * pressure)
        infectious = table.state == State.I
        catch = 1.0 - np.exp(-beta * np.count_nonzero(infectious) / s.population)
        susceptible = table.state == State.S
        # One uniform per person: the recovery draw of the infectious, the infection
        # draw of the susceptible; the two groups are disjoint, so the draws are independent.
        draws = self.rng.random(len(table))
        table.state[infectious & (draws < s.recovery)] = State.R
        new = susceptible & (draws < catch)
        table.state[new] = State.I
        admissions = int(self.rng.binomial(np.count_nonzero(new), s.severe))
        self.admitted += admissions
        self.coupling[ADMISSIONS] = admissions

    def step(self) -> None:
        """One step of the agents, then one step of the hospital."""
        self.coupling.step()
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def counts(self) -> np.ndarray:
        """People in each state, ``[S, I, R]``."""
        return np.bincount(self.columns[Person].state, minlength=len(State))

    def r0(self) -> float:
        """The basic reproduction number ``beta / recovery``."""
        return self.scenario.beta / self.scenario.recovery

    def final_size(self, tolerance: float = 1e-12) -> float:
        """Share ever infected without the response, from the final-size relation."""
        s = self.scenario
        s0 = 1.0 - s.initial_infected / s.population
        escape = 0.0
        for _ in range(_MAX_ITERATIONS):
            new = s0 * np.exp(-self.r0() * (1.0 - escape))
            if abs(new - escape) < tolerance:
                break
            escape = new
        return 1.0 - new

    def attack_rate(self) -> float:
        """Share of the population ever infected so far."""
        return 1.0 - self.counts()[State.S] / self.scenario.population


def hospital(s: HospitalScenario) -> StockFlow:
    """The hospital: admissions fill ``occupied``, beds follow the occupancy."""
    flows = [
        Flow("admit", admission_rate, target=OCCUPIED),
        Flow("discharge", partial(discharge_rate, scenario=s), source=OCCUPIED),
        Flow("open", partial(opening_rate, scenario=s), target=BEDS),
    ]
    return StockFlow({OCCUPIED: 0.0, BEDS: s.base_beds}, flows, reads=[ADMISSIONS])


def admission_rate(stocks: dict[str, float], inputs: dict[str, float]) -> float:
    """The admissions of the agents' step, spread over the step (one unit of time)."""
    return inputs[ADMISSIONS]


def discharge_rate(
    stocks: dict[str, float], inputs: dict[str, float], scenario: HospitalScenario
) -> float:
    """Patients leave at rate ``occupied / stay``."""
    return stocks[OCCUPIED] / scenario.stay


def opening_rate(
    stocks: dict[str, float], inputs: dict[str, float], scenario: HospitalScenario
) -> float:
    """Beds open (or close, when negative) towards ``base_beds + surge * occupied``."""
    s = scenario
    return (s.base_beds + s.surge * stocks[OCCUPIED] - stocks[BEDS]) / s.ramp


def count_in(model: HospitalEpidemic, state: State) -> int:
    """The number of people in ``state`` (a model reporter)."""
    return int(model.counts()[state])


def quantity(model: HospitalEpidemic, name: str, default: float | None = None) -> float:
    """A coupling quantity (a model reporter); ``default`` before it is first written."""
    return model.coupling.values.get(name, default)
