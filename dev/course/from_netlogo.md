# From NetLogo: a track for instructors

This page is for instructors who teach agent-based modelling with NetLogo and want to move a course to Modelly. It maps the NetLogo concepts to Modelly, shows what `modelly netlogo` does with a model and what is left for a person to write, and suggests which sessions of this course replace which usual NetLogo lessons.

The translator and its exact subset are described in [From NetLogo](https://remipelloux.github.io/Modelly/dev/netlogo.html); this page only uses what is listed there.

## The concepts

NetLogo

In a translated model

In a model written for Modelly

turtles, turtles-own

Turtle agents (a CellAgent), one attribute per variable

an Agent or CellAgent subclass; attributes updated in bulk as Columns (session 5)

breeds

a subclass of the turtle class per breed

a class per kind of agent

patches, patches-own

a Patch agent per cell of an OrthogonalMooreGrid

a grid of cells, or a CellIndex with per-cell arrays and rasters (session 3)

links

not translated: each line is reported

a network from modelly.space.networks, influence as a sparse product (session 4)

ask agents [ ... ]

self.ask(agents, function), a new random order each time

model.agents.shuffle_do("step"), or one numpy update of a column for the whole population (session 5)

with [ ... ]

a list comprehension

a list comprehension, or a boolean mask over a column

ticks, tick, reset-ticks

self.ticks, self.tick(), self.reset_ticks()

model.step() advances model.time by one; model.run_for(n)

setup, go

run by __init__ and by step(); stop sets running = False

the model’s __init__ and step

globals

model attributes

model attributes; the inputs among them belong in the Scenario

sliders and switches

fields of the generated Scenario

fields of the Scenario (session 1)

the view

the min_pxcor … max_pycor and wrap fields of the Scenario

the grid’s size, from the Scenario

plots and monitors

a DataCollector of ticks, every global and every breed’s size

a DataCollector with the reporters you choose (session 2)

random, random-float, one-of

draws from the model’s seeded self.random

draws from model.rng or model.random only; modelly lint reports any other (session 2)

BehaviorSpace

not translated

a run function and modelly.batch.run_grid, seeds spawned per run (session 7)

the Info tab

not translated

a model card, card.toml, checked against the tests (session 9)

the models library

two bundled models, fire and wolf_sheep

the [zoo](https://remipelloux.github.io/Modelly/dev/zoo/index.html) and the [hub](https://remipelloux.github.io/Modelly/dev/hub.html)

Two differences matter from the first lesson:

- **Every random draw is seeded.** A NetLogo run is reproducible only with `random-seed`; a Modelly model takes its seed in the `Scenario` (`rng=1`), and the same seed gives the same run, including the order of every `ask`.
- **The interface is a `Scenario`.** The sliders are fields with types and defaults, so a run with other values is `FireScenario(rng=1, density=62)`, from a script or a test. Studio draws the inputs from the same fields (`modelly studio fire.py:FireModel`): a slider for a float between 0 and 1, a number field for other numbers, a checkbox for a switch.

## Translating a model

Start with the bundled fire model:

```text
modelly netlogo --example fire --show       print the NetLogo source
modelly netlogo --example fire -o fire.py   translate it
modelly lint fire.py
```

The commands are the same in bash and PowerShell. The output is one module, `fire.py`, with a `FireScenario` (the `density` slider and the world’s size) and a `FireModel` whose methods are the procedures. The translation passes `modelly lint`. Run it on a smaller world than the 251 x 251 of the interface:

```python
from fire import FireModel, FireScenario

WORLD = {"min_pxcor": -50, "max_pxcor": 50, "min_pycor": -50, "max_pycor": 50}

for density in (50, 59, 70):
    model = FireModel(FireScenario(rng=1, density=density, **WORLD))
    while model.running:
        model.step()
    print(density, round(model.percent_burned(), 1), model.ticks)
```

About 10% of the trees burn at a density of 50, half at 59 and almost all at 70: the site-percolation threshold of session 3. The zoo’s [forest fire](https://remipelloux.github.io/Modelly/dev/zoo/forest_fire.html) is the same question written for Modelly, with a `CellIndex`; comparing the two is a good exercise for the end of session 5.

### What is left for a person

The translator reads a subset of NetLogo. Anything outside it stays in the output as a `# NETLOGO` comment at the place it was, and is listed on stderr with its line number; the exit status is 1. A model of 50 turtles that links each one to a friend, `friends.nlogo`:

```text
turtles-own [ wealth ]

to setup
  clear-all
  create-turtles 50 [ setxy random-xcor random-ycor set wealth 10 ]
  ask turtles [ create-link-with one-of other turtles ]
  reset-ticks
end

to go
  ask turtles [ rt random 360 fd 1 ]
  tick
end
```

```text
$ modelly netlogo friends.nlogo -o friends.py
friends.nlogo:6: not translated: unknown command 'create-link-with': ask turtles [ create-link-with one-of other turtles ]
```

The rest of the model translates and runs; the person writes the missing line in Python, then checks the model with a test. Plan for this work when a course model uses:

- links, `of`, lists, `while`, `foreach`, `map`, anonymous procedures, string primitives or extensions;
- distances and positions inside a patch (`distance`, `in-radius`, `face`, flocking): a turtle stands on a patch, and `fd` moves whole patches along the nearest of eight directions, so such models translate and run but do not behave like the original;
- choosers and input boxes, which are reported as interface widgets;
- BehaviorSpace experiments, which are not read: write them as below.

Display commands (`set-default-shape`, `pen-down`, `print`, …) are dropped and listed.

### BehaviorSpace as a script

A BehaviorSpace experiment is a run function and a grid. Put it in a file so that worker processes can import it on Windows and macOS (session 7):

```python
# experiment.py: density 50 to 70, five runs each
from fire import FireModel, FireScenario

from modelly.batch import run_grid

WORLD = {"min_pxcor": -50, "max_pxcor": 50, "min_pycor": -50, "max_pycor": 50}

def run(task):
    model = FireModel(FireScenario(rng=task["seed"], density=task["density"], **WORLD))
    while model.running:
        model.step()
    return {"percent_burned": model.percent_burned(), "ticks": model.ticks}

if __name__ == "__main__":
    frame = run_grid(run, {"density": [50, 55, 59, 63, 70]}, replicates=5, seed=1)
    print(frame.groupby("density")["percent_burned"].agg(["mean", "std"]))
```

`python experiment.py` prints the mean and spread per density; every run’s seed is in the table, so one run can be repeated alone.

### A test for the translation

Before changing a translated model, write the test that will tell you if a change broke it:

```python
# test_fire.py
from fire import FireModel, FireScenario

WORLD = {"min_pxcor": -50, "max_pxcor": 50, "min_pycor": -50, "max_pycor": 50}

def burned(density, seed):
    model = FireModel(FireScenario(rng=seed, density=density, **WORLD))
    while model.running:
        model.step()
    return model.percent_burned()

def test_same_seed_same_fire():
    assert burned(59, 3) == burned(59, 3)

def test_the_fire_crosses_above_the_threshold_only():
    assert max(burned(50, seed) for seed in range(3)) < 30
    assert min(burned(70, seed) for seed in range(3)) > 90
```

## Writing the model again for Modelly

A translation keeps the NetLogo structure: every patch is an agent and every `ask` visits agents one by one. That is the right first step and a slow last one. For a large world, write the model again, phase by phase, with columns and a `CellIndex` (sessions 3 and 5), and keep the translation and its test as the reference the new version must match.

The NetLogo wealth exchange, “every turtle moves to a neighbouring patch and gives one unit to a turtle on its patch”, reads like this when written for Modelly:

```python
from modelly import Column, Model
from modelly.data.collector import DataCollector
from modelly.scenarios import Scenario
from modelly.space import CellAgent, OrthogonalMooreGrid

class Trader(CellAgent):
    wealth = Column(int, default=1)

    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        others = [a for a in self.cell.agents if a is not self]
        if others and self.wealth > 0:
            self.random.choice(others).wealth += 1
            self.wealth -= 1

class MarketScenario(Scenario):
    n: int = 100
    width: int = 10
    height: int = 10

class Market(Model):
    def __init__(self, scenario: MarketScenario = MarketScenario):
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid((s.width, s.height), random=self.random)
        cells = self.random.choices(self.grid.all_cells.cells, k=s.n)
        Trader.create_agents(self, s.n, cells)
        self.datacollector = DataCollector(
            model_reporters={"broke": lambda m: sum(a.wealth == 0 for a in m.agents)}
        )

    def step(self):
        self.agents.shuffle_do("step")  # ask turtles [ ... ], in a new random order
        self.datacollector.collect(self)

model = Market(MarketScenario(rng=1))
model.run_for(50)
print(model.time, model.datacollector.get_model_vars_dataframe().tail(3))
```

Studio’s **Builder** tab writes models of this shape from a form (walk to a neighbouring cell, give wealth to a cellmate, catch and recover from an infection), and shows the code: a way to show a NetLogo class that the code is short. See [Studio for everyone](https://remipelloux.github.io/Modelly/dev/studio.html#studio-for-everyone).

## Which sessions replace which lessons

A NetLogo course usually runs through the interface, turtles and patches, plots, BehaviorSpace and the models library. The sessions of this course cover the same ground, in Python, and add what NetLogo courses rarely teach: seeds, validation tests, cards and comparisons with intervals.

Usual NetLogo lesson

Session that replaces it

What changes

The interface, turtles, setup and go

[1](https://remipelloux.github.io/Modelly/dev/course/session_1.html), with the translated fire or wolf_sheep as a warm-up

the sliders become a Scenario

Plots and monitors

[2](https://remipelloux.github.io/Modelly/dev/course/session_2.html)

a DataCollector and a DataFrame; seeds and reproducibility

Patches, diffusion, fire

[3](https://remipelloux.github.io/Modelly/dev/course/session_3.html)

per-cell arrays and a CellIndex; the percolation threshold

Links and networks

[4](https://remipelloux.github.io/Modelly/dev/course/session_4.html)

networks written by hand, since links are not translated

Making a model faster

[5](https://remipelloux.github.io/Modelly/dev/course/session_5.html)

columns and cohorts instead of ask one by one

Verification

[6](https://remipelloux.github.io/Modelly/dev/course/session_6.html)

a pytest test against a known result

BehaviorSpace

[7](https://remipelloux.github.io/Modelly/dev/course/session_7.html)

run_grid in a script, with spawned seeds

A student project

[8](https://remipelloux.github.io/Modelly/dev/course/session_8.html)

started from a zoo model with modelly zoo copy

The Info tab, the models library

[9](https://remipelloux.github.io/Modelly/dev/course/session_9.html)

a model card checked against the tests; the hub

(no usual counterpart)

[10](https://remipelloux.github.io/Modelly/dev/course/session_10.html), [11](https://remipelloux.github.io/Modelly/dev/course/session_11.html), [12](https://remipelloux.github.io/Modelly/dev/course/session_12.html)

decisions with costs, causes, ODEs inside agents

A first course can keep NetLogo for the first week, translate the students’ first model with `modelly netlogo` in session 1, and run the rest of the course in Modelly. The [instructor notes](https://remipelloux.github.io/Modelly/dev/course/instructors.html) give the timing and the misconceptions of each session.
