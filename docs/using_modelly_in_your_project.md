# Using Modelly in your project

This guide takes you from an empty folder to a reproducible, measured agent-based model that
lives in its own repository, uses Modelly as a dependency, and runs as a script, in a notebook,
or as a batch of replications. Every snippet is complete; copy them in order.

## 1. Install Modelly as a dependency

Modelly needs Python 3.12 or newer. From an empty project folder:

```bash
mkdir epidemic && cd epidemic
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install "modelly @ git+https://github.com/RemiPelloux/Modelly.git@v1.0.0"
```

Pin the tag you tested against. To declare it in your own `pyproject.toml` instead:

```toml
[project]
name = "epidemic"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "modelly @ git+https://github.com/RemiPelloux/Modelly.git@v1.0.0",
  "pandas",
]

[project.optional-dependencies]
viz = ["modelly[viz] @ git+https://github.com/RemiPelloux/Modelly.git@v1.0.0"]
```

Then `pip install -e .` (or `pip install -e ".[viz]"` for the browser UI).

## 2. Lay out the project

One model per package, with the three Modelly pieces in three files:

```text
epidemic/
├── pyproject.toml
├── epidemic/
│   ├── __init__.py
│   ├── scenario.py      # the inputs: parameters and the seed
│   ├── agents.py        # what one agent does
│   └── model.py         # the world: space, population, step, reporters
├── scripts/
│   └── run.py           # one run, prints a result
├── notebooks/
└── tests/
    └── test_model.py
```

The separation is not cosmetic. The scenario is what you vary between runs, the agents are what
you reason about, and the model is what you measure. Keeping them apart keeps each file short.

## 3. Write the scenario

`epidemic/scenario.py`. Every parameter has a type and a default, and the seed is part of it:

```python
from modelly.experimental.scenarios import Scenario


class EpidemicScenario(Scenario):
    """Everything that can vary between runs."""

    n: int = 500
    width: int = 30
    height: int = 30
    infection_chance: float = 0.3
    recovery_time: int = 10
    initially_infected: int = 5
```

A scenario instance is one run: `EpidemicScenario(n=2000, rng=42)`. The `rng` argument seeds
both random number generators the model exposes (`model.random`, a stdlib `Random`, and
`model.rng`, a numpy `Generator`), so the same scenario always gives the same run.

## 4. Write the agents

`epidemic/agents.py`. Agents move on a grid and infect their cellmates. The two attributes the
model will aggregate every step are declared as `Column`s, so the model can read them for the
whole population as numpy arrays; the agent still uses them as plain attributes.

```python
from modelly import Column
from modelly.discrete_space import CellAgent

SUSCEPTIBLE, INFECTED, RECOVERED = 0, 1, 2


class Person(CellAgent):
    """Moves to a neighbouring cell, infects cellmates, recovers after a while."""

    state = Column(int, default=SUSCEPTIBLE)
    days_infected = Column(int, default=0)

    def __init__(self, model, cell, infected=False):
        super().__init__(model)
        self.cell = cell
        if infected:
            self.state = INFECTED

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        if self.state != INFECTED:
            return
        for other in self.cell.agents:
            if other.state == SUSCEPTIBLE and (
                self.random.random() < self.scenario.infection_chance
            ):
                other.state = INFECTED
        self.days_infected += 1
        if self.days_infected >= self.scenario.recovery_time:
            self.state = RECOVERED
```

Rules of thumb:

- `self.random` and `self.rng` are the model's seeded generators. Never import `random` or call
  `np.random` directly, or your runs stop being reproducible.
- `self.scenario` is the model's scenario; read parameters from it instead of copying them.
- Use a `Column` for an attribute the *model* aggregates, filters or records every step. Keep a
  scratch value that only the agent reads as a plain attribute: a column read costs about 100 ns
  more per access, which is nothing for a few reads but adds up in a tight loop.

## 5. Write the model

`epidemic/model.py`. The model owns the space, creates the population, defines the step order,
and exposes the quantities you want to measure.

```python
import numpy as np

from modelly import Model
from modelly.datacollection import DataCollector
from modelly.discrete_space import OrthogonalMooreGrid

from epidemic.agents import INFECTED, RECOVERED, SUSCEPTIBLE, Person
from epidemic.scenario import EpidemicScenario


class Epidemic(Model):
    def __init__(self, scenario: EpidemicScenario = EpidemicScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), torus=True, random=self.random
        )
        cells = self.random.choices(self.grid.all_cells.cells, k=scenario.n)
        infected = [i < scenario.initially_infected for i in range(scenario.n)]
        Person.create_agents(self, scenario.n, cells, infected=infected)

        self.datacollector = DataCollector(
            model_reporters={
                "susceptible": lambda m: m.count(SUSCEPTIBLE),
                "infected": lambda m: m.count(INFECTED),
                "recovered": lambda m: m.count(RECOVERED),
            },
            agent_reporters={"state": "state"},
        )
        self.datacollector.collect(self)

    def count(self, state: int) -> int:
        """How many people are in ``state``: one numpy comparison, no loop."""
        return int((self.columns[Person].state == state).sum())

    def step(self):
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)
        self.running = self.count(INFECTED) > 0
```

What each line buys you:

- `create_agents(model, n, cells, infected=infected)`: a sequence of length `n` is spread one
  value per agent, anything else is broadcast. One call creates the whole population.
- `self.columns[Person].state` is a numpy view of every person's state; `count` is a vectorised
  reporter. With 10,000 agents it costs microseconds instead of a millisecond.
- `agent_reporters={"state": "state"}` records a column straight from the array.
- `self.running` is the stop condition that `run_model()` honours.

## 6. Run it

`scripts/run.py`:

```python
from epidemic.model import Epidemic
from epidemic.scenario import EpidemicScenario

model = Epidemic(EpidemicScenario(n=1000, rng=7))
model.run_for(60)  # 60 ticks; or model.run_model() until running is False

frame = model.datacollector.get_model_vars_dataframe()
print(frame.tail())
frame.plot(title="SIR").get_figure().savefig("sir.png")
```

`run_for(duration)` advances model time by `duration`; `run_until(t)` runs to an absolute time;
`step()` is one tick. All three go through the same event scheduler, so a model that also
schedules events (`self.schedule_event(fn, after=3.5)`) mixes ticks and events correctly.

## 7. Look at the data

```python
model_vars = model.datacollector.get_model_vars_dataframe()  # one row per tick
agent_vars = (
    model.datacollector.get_agent_vars_dataframe()
)  # one row per agent per tick
share_infected = agent_vars["state"].eq(1).groupby("Step").mean()
```

For a snapshot of the whole population right now, without going through the collector:

```python
table = model.columns[Person]
table.to_dataframe()  # indexed by unique_id, one column per Column
table.where(table.state == 1)  # the infected, as an AgentSet
table.days_infected[table.state == 1].mean()
```

## 8. Replicate and sweep

A scenario can spawn independent, seeded replications:

```python
import pandas as pd

from epidemic.model import Epidemic
from epidemic.scenario import EpidemicScenario

runs = []
for chance in (0.1, 0.2, 0.3):
    base = EpidemicScenario(infection_chance=chance, rng=1)
    for scenario in base.spawn_replications(20):
        model = Epidemic(scenario)
        model.run_model()
        runs.append(
            {
                "chance": chance,
                "peak": model.datacollector.get_model_vars_dataframe()[
                    "infected"
                ].max(),
            }
        )

print(pd.DataFrame(runs).groupby("chance")["peak"].describe())
```

Each replication has its own seed derived from the base scenario, so the sweep is reproducible
end to end. Runs are independent, so they parallelise without any change to the model:

```python
from modelly.experimental.scenarios import RunConfiguration, run_scenarios

scenarios = [
    s
    for chance in (0.1, 0.2, 0.3)
    for s in EpidemicScenario(infection_chance=chance, rng=1).spawn_replications(20)
]
store = run_scenarios(scenarios, RunConfiguration(Epidemic, until=120), workers=8)
```

## 9. Test it

`tests/test_model.py`. Seeds are part of the API, so tests can assert exact numbers:

```python
from epidemic.model import Epidemic
from epidemic.scenario import EpidemicScenario


def test_same_seed_same_run():
    a = Epidemic(EpidemicScenario(n=200, rng=3))
    b = Epidemic(EpidemicScenario(n=200, rng=3))
    a.run_for(20)
    b.run_for(20)
    assert a.count(1) == b.count(1)


def test_epidemic_ends():
    model = Epidemic(EpidemicScenario(n=200, recovery_time=3, rng=3))
    model.run_model()
    assert model.count(1) == 0
    assert model.time > 0
```

## 10. Make it fast

- Put the population-wide work on columns and numpy (`count` above); keep interactions in `step`.
- Move whole-population phases out of the per-agent loop with the column helpers:
  `table.days_infected[table.state == 1] += 1`, `table.remove_where(mask)`,
  `table.do_where(table.draw(p), "method")`. `draw` uses the model's seeded generator.
- Use `model.agents.shuffle_do("step")` rather than your own loop: it shuffles once and skips
  agents removed earlier in the same tick.
- `cell.neighborhood` is cached per cell; call it freely.
- Record with attribute names (`"state"`) rather than lambdas when you can; they are gathered in C.
- Profile before optimising: `python -m cProfile -s tottime scripts/run.py | head -30`. In a healthy
  model, the top entries are your agents' own methods.

The numbers behind these recommendations are in [performance.md](performance.md).

## 11. Visualise it (optional)

With `modelly[viz]` installed:

```python
from modelly.visualization import SolaraViz, make_space_component, make_plot_component

from epidemic.model import Epidemic

page = SolaraViz(
    Epidemic(),
    components=[
        make_space_component(
            lambda a: {"color": ["tab:blue", "tab:red", "tab:green"][a.state]}
        ),
        make_plot_component(["susceptible", "infected", "recovered"]),
    ],
    name="Epidemic",
)
```

```bash
solara run app.py
```
