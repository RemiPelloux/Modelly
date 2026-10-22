<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/branding/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/images/branding/banner-light.svg">
    <img src="docs/images/branding/banner-light.svg" alt="Modelly — agent-based modeling in Python" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/RemiPelloux/Modelly/actions/workflows/build_lint.yml"><img src="https://github.com/RemiPelloux/Modelly/actions/workflows/build_lint.yml/badge.svg" alt="build"></a>
  <a href="https://codecov.io/gh/RemiPelloux/Modelly"><img src="https://codecov.io/gh/RemiPelloux/Modelly/branch/main/graph/badge.svg" alt="coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-3B82F6" alt="python 3.12+">
  <img src="https://img.shields.io/badge/ruff-linted-261230" alt="ruff">
  <a href="https://github.com/RemiPelloux/Modelly/discussions"><img src="https://img.shields.io/badge/discussions-open-7C5CFF" alt="discussions"></a>
</p>

<p align="center"><b>Modelly</b> is a Python framework for <b>agent-based modeling</b>: declare a scenario,
give your agents behaviour, and run the world forward in time — then watch, measure and replay it.</p>

---

## Why Modelly

Agent-based models are easy to describe and hard to keep tidy. Modelly gives you the boring,
load-bearing parts as small composable objects, so your model file reads like the description of
the system instead of the plumbing around it:

| | |
|---|---|
| **Scenario** | Parameters as a typed class: one run, one seed, one config object |
| **Agents** | Typed agent classes with `step()` behaviour, grouped in fast `AgentSet`s |
| **Space** | Orthogonal / hexagonal grids, cells, networks, continuous space |
| **Time** | Discrete ticks, events, generators and priorities in one scheduler |
| **Data** | Reporters and datasets that land in pandas, ready to plot |
| **Front end** | Browser visualization (Solara), static charts, notebooks |

No global state, no hidden step order, no bespoke loops — reproducibility is the default.

<p align="center">
  <img src="docs/images/branding/simulation-loop.svg" alt="The Modelly loop: scenario, step, record, visualize" width="720">
</p>

## Install

Modelly requires **Python 3.12+**.

```bash
git clone https://github.com/RemiPelloux/Modelly.git
cd Modelly

python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"          # core + network + visualization + examples + docs
```

Pick only what you need if `all` is too much:

```bash
pip install -e .                 # core: numpy, pandas, scipy, tqdm
pip install -e ".[viz]"          # + solara, matplotlib, altair
pip install -e ".[network]"      # + networkx
```

## A model in 30 seconds

> Verified end to end against this repository: `python example.py` prints the Gini coefficient rising.

```python
from modelly import Model
from modelly.discrete_space import CellAgent, OrthogonalMooreGrid
from modelly.experimental.scenarios import Scenario


class WealthScenario(Scenario):
    """Everything that can vary between runs lives here."""

    n: int = 120
    width: int = 12
    height: int = 12


class MoneyAgent(CellAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell
        self.wealth = 1

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        cellmates = [a for a in self.cell.agents if a is not self]
        if self.wealth > 0 and cellmates:
            self.random.choice(cellmates).wealth += 1
            self.wealth -= 1


class WealthModel(Model):
    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), random=self.random
        )
        MoneyAgent.create_agents(
            self,
            scenario.n,
            self.random.choices(self.grid.all_cells.cells, k=scenario.n),
        )

    def step(self):
        self.agents.shuffle_do("step")   # every agent, in random order

    @property
    def gini(self):
        x, n = sorted(a.wealth for a in self.agents), len(self.agents)
        return 1 + 1 / n - 2 * sum(xi * (n - i) for i, xi in enumerate(x)) / (n * sum(x))


model = WealthModel()
for _ in range(100):
    model.step()

print(model.gini)   # 0.0 at t=0 ... ~0.62 after 100 ticks
```

Three pieces, and nothing else: a **scenario** of inputs, **agents** that know one thing each,
and a **model** that owns the world and advances it.

## Record it, then look at it

```python
from modelly.datacollection import DataCollector

class WealthModel(Model):
    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        # ... grid and agents as above ...
        self.datacollector = DataCollector(
            model_reporters={"Gini": "gini"},      # anything reachable from the model
            agent_reporters={"Wealth": "wealth"},  # anything on each agent
        )

    def step(self):
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)           # one row per tick
```

```python
model_vars = model.datacollector.get_model_vars_dataframe()   # Gini per tick
agent_vars = model.datacollector.get_agent_vars_dataframe()   # wealth per agent per tick
agent_vars.groupby("Step")["Wealth"].mean().plot()
```

Both frames are plain pandas, so everything you already know how to do keeps working.

## Architecture

<p align="center">
  <img src="docs/images/branding/architecture.svg" alt="Modelly architecture" width="860">
</p>

- **Scenario → Model.** Inputs enter through one typed object; the model owns state, seed, RNG and time.
- **Model → AgentSet / Space / Time.** Agents live in sets, act inside some space, and are driven by the scheduler.
- **Model → Dataset.** Reporters sample the model and its agents on intervals you choose.
- **Dataset → Visualize / Analyze / Reproduce.** Same data, three exits: a browser app, a dataframe, or a seeded re-run.

## Built-in examples

Real, runnable models that ship with the package — good reading material for the patterns above.

| Model | Shows | Path |
|---|---|---|
| Boltzmann Wealth | Money exchange on a grid, emerging inequality | `modelly/examples/basic/boltzmann_wealth_model` |
| Schelling | Segregation from local tolerance thresholds | `modelly/examples/basic/schelling` |
| Conway's Game of Life | Cellular automaton, cell-state transitions | `modelly/examples/basic/conways_game_of_life` |
| Virus on Network | SIR epidemic on a contact network | `modelly/examples/basic/virus_on_network` |
| Boid Flockers | Continuous space, alignment and cohesion | `modelly/examples/basic/boid_flockers` |
| Wolf Sheep | Predator–prey ecology on a grid | `modelly/examples/advanced/wolf_sheep` |
| Sugarscape G1MT | Resource harvesting, trade and growth | `modelly/examples/advanced/sugarscape_g1mt` |
| Epstein Civil Violence | Regime shifts from agent state | `modelly/examples/advanced/epstein_civil_violence` |
| Prisoner's Dilemma | Pairwise strategic interaction | `modelly/examples/advanced/pd_grid` |
| Alliance Formation | Network structure and group formation | `modelly/examples/advanced/alliance_formation` |

Run one:

```bash
solara run modelly/examples/basic/boltzmann_wealth_model/app.py   # browser UI
```

## Documentation

| | |
|---|---|
| **Tutorials** | `docs/tutorials/` — 12 notebooks, from *your first model* to *hybrid ABM/DES* |
| **Overview** | `docs/overview.md` — the object model, end to end |
| **Best practices** | `docs/best-practices.md` |
| **Migration guide** | `docs/migration_guide.md` |
| **API reference** | `docs/apis/` — agents, model, space, time, data |

The tutorials are executable: open them locally, in Colab, or through Binder (links at the top of
each notebook).

## Repository layout

```text
modelly/                  # the package
├── agent.py              # Agent, create_agents
├── agentset.py           # AgentSet: bulk operations, groupby, shuffle_do
├── model.py              # Model: state, seed, time, step
├── datacollection.py     # DataCollector: reporters -> pandas
├── discrete_space/       # grids, cells, neighbourhoods, CellAgent
├── time/                 # events, generators, schedules
├── experimental/         # scenarios, signals, data records, dev-facing APIs
├── examples/             # the models in the table above
└── visualization/        # Solara components, matplotlib, altair
docs/                     # notebooks, guides, API docs, brand assets
benchmarks/               # timing harnesses for the example models
tests/                    # the test suite
tools/branding/           # generator for the animated SVGs on this page
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest -q
```

CI runs the same commands (`.github/workflows/build_lint.yml`), plus benchmarks, docs and a prose
linter.

## Brand assets

The animated banner, architecture diagram and loop diagram are hand-rolled SVG (CSS keyframes and
SMIL — no JavaScript, no external fonts), so they render inside GitHub's image sandbox and respect
`prefers-reduced-motion`. Regenerate them after editing the generator:

```bash
python tools/branding/generate_assets.py
```

## Contributing

Issues, ideas and pull requests are welcome on the
[issue tracker](https://github.com/RemiPelloux/Modelly/issues). If you are adding a feature, opening
a ticket first is the fastest route — it keeps the patch small and reviewable.

<p align="center"><sub>Modelly — build the system, run the world, watch what emerges.</sub></p>
