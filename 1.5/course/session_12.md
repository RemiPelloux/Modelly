# Session 12: continuous dynamics inside agents, and the final projects

**Zoo model:** [within-host and between-host epidemic](https://remipelloux.github.io/Modelly/zoo/within_host.html)

## Goals

- Give every agent its own ODE with `modelly.couple.AgentODE`: the state variables are columns, and the whole population is integrated as one batch.
- Know what the batch guarantees: each agent takes the steps its own `solve_ivp` call would take, and events (a threshold crossed) are located to the instant, not rounded to the step.
- Present the final project: a validation test, a seeded experiment, a figure, a model card and a comparison with intervals.

**Before the session:** [ODEs in every agent](https://remipelloux.github.io/Modelly/agent_odes.html), up to “Inputs from the rest of the model”, and the [within-host page](https://remipelloux.github.io/Modelly/zoo/within_host.html).

## Walk-through

Every host carries three ODEs, target cells, infected cells and virus. A host is infectious while its virus load is above a threshold; between hosts, a daily phase exposes susceptible hosts with a chance that grows with the share infectious.

```python
import numpy as np

from modelly.zoo.within_host.model import Host, WithinHost, WithinHostScenario

model = WithinHost(WithinHostScenario(rng=1, hosts=2000, days=40))
model.run()
table = model.columns[Host]
print(model.attack_rate())
print(table.onset[:5])  # the index cases became infectious within the first day
frame = model.datacollector.get_model_vars_dataframe()
print(frame["infectious"].idxmax(), frame["infectious"].max())
```

Open `modelly/zoo/within_host/model.py` and follow one day: `step` calls `self.coupling.step(1.0)`, which runs `transmit` (phase 0), then the `AgentODE` (phase 1). The ODE reads `cells`, `infected` and `virus` from the hosts’ columns, integrates every exposed host to the end of the day, and writes them back. The two `ODEEvent`s fire when the virus rises through the threshold and when it falls back; their actions set `infectious`, `onset` and `cleared`. So `onset` holds times like 0.23 days, not whole days: the event is located on the solver’s interpolant.

## Exercises

**12.1** Write a model from scratch: 1,000 cells whose mass decays at its own rate, `dm/dt = -rate m`, with rates drawn uniformly between 0.1 and 2. Integrate it with an `AgentODE` in a `Coupling`, run three steps of length 1, and check it against `exp(-3 rate)`.

Solution

```python
import numpy as np

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple import AgentODE, Coupling

class Cell(Agent):
    mass = Column(float, default=1.0)
    rate = Column(float, default=0.5)

def decay(t, y, params):
    """y has shape (1, cells): one column per agent."""
    return -params["rate"] * y

class Culture(Model):
    def __init__(self, cells=1000, rng=1):
        super().__init__(rng=rng)
        Cell.create_agents(self, cells)
        self.table = self.columns[Cell]
        self.table.rate[:] = self.rng.uniform(0.1, 2.0, cells)
        self.coupling = Coupling()
        self.coupling.add(AgentODE(self, Cell, decay, state=["mass"], params=["rate"]))
        self.coupling.build()

    def step(self):
        self.coupling.step(1.0)

model = Culture()
model.run_for(3)
exact = np.exp(-3 * model.table.rate)
print(np.max(np.abs(model.table.mass - exact) / exact))  # about 2e-8
```

The right-hand side is written for the whole population at once: `y` has one column per agent, and `params["rate"]` is the column of rates. Each agent still reads its own value as `cell.mass`.

**12.2** A host with no target cells cannot make new virus, so its load falls as `V(t) = V0 exp(-c t)` and crosses the threshold at `log(V0 / threshold) / c`. Check the model’s `cleared` times against this for fifty hosts with loads from 0.02 to 5.

Solution

```python
model = WithinHost(WithinHostScenario(rng=1, hosts=50, index_cases=0, contacts=0.0))
s, table = model.scenario, model.columns[Host]
loads = np.geomspace(0.02, 5.0, 50)
table.cells[:], table.virus[:], table.exposed[:] = 0.0, loads, True
model.run(5)
exact = np.log(loads / s.threshold) / s.clearance
print(np.max(np.abs(table.cleared - exact) / exact))  # below 1e-6
```

This is one of the zoo’s validation tests (`tests/zoo/test_within_host.py`). With `contacts=0.0` nobody else is exposed, so the run tests the ODE and its events alone. A model that only updated the virus once a day would get each clearance time wrong by up to a day.

**12.3** Check the batch against scipy: integrate the hosts’ equations for twenty hosts with random infection rates over ten days with `solve_batch`, and with one `solve_ivp` call per host. Compare the final states and the number of steps.

Solution

```python
from functools import partial

from scipy.integrate import solve_ivp

from modelly.couple import solve_batch
from modelly.zoo.within_host.model import within_host

rhs = partial(within_host, death=2.0, production=20.0, clearance=3.0)
beta = np.random.default_rng(1).lognormal(np.log(10.0), 0.5, 20)
y0 = np.tile([[1.0], [0.0], [1e-3]], (1, 20))
batch = solve_batch(rhs, (0.0, 10.0), y0, {"beta": beta}, rtol=1e-6, atol=1e-9)
worst = 0.0
for k in range(20):

    def one_host(t, y, k=k):
        return rhs(t, y[:, None], {"beta": beta[k : k + 1]})[:, 0]

    alone = solve_ivp(one_host, (0.0, 10.0), y0[:, k], rtol=1e-6, atol=1e-9)
    assert len(alone.t) - 1 == batch.nsteps[k]
    worst = max(worst, np.max(np.abs(alone.y[:, -1] - batch.y[:, k])))
print(worst)  # round-off
```

Same number of steps for every host, same final states to round-off. One stacked `solve_ivp` call over all hosts would be a different method: one step size for everybody and an error measured over the whole population, so a host’s numbers would depend on the others.

**12.4** An antiviral clears the virus faster: `clearance` from 3 to 4.5 per day. With the same seed and 2,000 hosts, compare the median infectious period (`cleared - onset`) and the attack rate. Which changes more, and why?

Solution

```python
for clearance in (3.0, 4.5):
    model = WithinHost(
        WithinHostScenario(rng=1, hosts=2000, days=40, clearance=clearance)
    )
    model.run()
    table = model.columns[Host]
    period = np.nanmedian(table.cleared - table.onset)
    print(clearance, model.attack_rate(), round(float(period), 2))
```

The median infectious period falls from about 4.2 to 3.8 days; the attack rate only from 0.95 to 0.94. With 8 contacts a day and a transmissibility of 0.1, transmission is still well above the epidemic threshold, so most hosts are exposed either way. To report the effect with an interval, use `treatment_effect` from session 11, with a few replicates.

## Final project presentations

The second half of the session is the presentations of the projects started in session 8. Each group has ten minutes and shows, from its own folder:

1. **The question** and the zoo model it started from, in two sentences.
1. **The validation test**: `pytest` passing, and what the test compares with (a known result, a limit case, the zoo’s own test kept from session 8).
1. **A seeded experiment**: a sweep or a comparison run from a script, with the seed in the script, which anybody can rerun to get the same table.
1. **One figure** with the spread across seeds shown, not one run.
1. **The model card**: `modelly card check card.toml` passing, and the out-of-scope uses read aloud.
1. **A comparison with intervals**: two scenarios or strategies on common random numbers, with `modelly.decide.compare` or `modelly.explain.treatment_effect`, and the measured `variance_reduction` or the paired interval.

The rubric is in the [instructor notes](https://remipelloux.github.io/Modelly/course/instructors.html#final-project-rubric).
