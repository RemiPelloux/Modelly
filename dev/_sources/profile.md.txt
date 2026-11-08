# Profiling a model

`modelly.profile` runs a model and reports where each step's time goes, in Modelly terms: which
`AgentSet` loop, on which agent class and method, at what cost per agent; how long
`DataCollector.collect` and the scheduled events take; how many agents are born and die. It is
the runtime companion of [`python -m modelly.lint`](lint.md): the linter reads the source and
says what could scale badly, the profiler runs it and says what does.

## From the command line

```bash
python -m modelly.profile path/to/model.py:MyModel --steps 100
python -m modelly.profile path/to/model.py:MyModel --param n=5000 --param width=100 --seed 42
python -m modelly.profile modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth \
    --steps 100 --seed 1 --param n=1000 --param width=30 --param height=30
```

```text
BoltzmannWealth: 100 step(s) profiled, one in 1, model time 1 to 100
step wall 0.102 s, CPU 0.101 s; mean 1.02 ms, median 0.74 ms, slowest 23.39 ms (step 45)
agents 1000 at the first step, 1000 at the last; 0 births, 0 deaths

  share    total ms    calls  agents/call   us/agent  operation
  61.0%       61.92      100       1000.0       0.62  MoneyAgent.step (shuffle_do)
  36.3%       36.88      100            -          -  DataCollector.collect

hints:
  - DataCollector.collect takes 36% of the profiled time: collect less often, record fewer
    agent attributes, or store them as Column if they are plain attributes
    (docs/performance.md, 'Columnar agent state')
```

The target is a file and a class (`path/to/model.py:MyModel`, the file's folder goes on
`sys.path` so its sibling imports work) or a dotted module (`package.module:MyModel`). Each
`--param key=value` is read as a Python literal (`n=500`, `torus=True`, `rate=0.2`) and is
otherwise a string. Parameters the model's constructor takes by name go to it; the others go to
its scenario, the `Scenario` class its `scenario` argument defaults to. `--seed` seeds that
scenario, or the model's `rng` when it has none.

| Option | Meaning |
|---|---|
| `--steps N` | steps to run (default 100) |
| `--param KEY=VALUE` | a model or scenario parameter; repeatable |
| `--seed S` | seed for the model's generators |
| `--format text\|json\|csv` | the table and hints; the same as a JSON document; one CSV row per step and per operation |
| `--top N` | rows in the text table (default 15) |
| `--sample-every N` | profile one step in N |
| `--sizes N1,N2,...` | build and profile the model at each population size and compare (see below) |
| `--size-param NAME` | the parameter `--sizes` sets (default: the first of `n`, `N`, `num_agents`, `population` the model or its scenario takes) |

The exit status is 0 when the model ran, 1 when it raised while being built or run (the
traceback goes to stderr) and 2 on a bad command line or a target that cannot be loaded.
`python -m modelly.profile --help` lists all of this with examples.

## From Python

```python
from modelly.profile import Profiler

model = MyModel(rng=42)
with Profiler(model) as prof:
    model.run_for(100)

print(prof.report(top=10))  # the text table above
frame = prof.to_dataframe()  # pandas, one row per step and per operation
data = prof.to_dict()  # totals per operation, per-step totals, hints
```

`Profiler(model, sample_every=10)` times steps 1, 11, 21, ... and lets the others run untimed,
for long runs. `prof.records` holds one `StepRecord` per profiled step.

## In a notebook

Load the extension once, then profile a model class defined in the notebook by its name, or
any target the command line takes; every option of the command line works:

```text
%load_ext modelly.ipython
%modelly profile MyModel --steps 50 --param n=1000
%modelly profile path/to/model.py:MyModel --sizes 500,1000,2000
```

The same extension has `%modelly lint path/to/model.py` (see [Checking a model](lint.md)).
A model shown as the last expression of a cell displays its class, scenario (parameters and
seed), time and the number of agents of each class.

## Comparing population sizes

A scan of the population only shows in one run when the population changes during it. For a
model whose population is fixed, `--sizes` builds it once per size, profiles each run for
`--steps` steps and puts the microseconds per agent side by side:

```bash
python -m modelly.profile crowd.py:Crowd --sizes 100,400 --steps 5
```

```text
Crowd profiled at N = 100, 400; 5 step(s) each

N=100 us/agent  N=400 us/agent    growth  operation
          5.07           17.85     3.52x  whole step
          4.84           17.76     3.67x  Scanner.step (shuffle_do)

hints:
  - Scanner.step (shuffle_do): us per agent grows 3.7x from N=100 to N=400 (about N^0.9):
    each agent probably scans the population. Run `python -m modelly.lint` and look for
    MDL101 / MDL102
```

`whole step` is the model's step time divided by its agents, so it also covers loops written by
hand; the other rows are the `AgentSet` loops that visit agents. `growth` is the cost per agent
at the largest size over the smallest. When it grows roughly linearly with N (the slope of log
cost per agent against log N is above 0.5) for a loop that takes at least a tenth of the time,
the MDL101 / MDL102 hint is printed; an O(1)-per-agent step stays near 1x.

The size goes to the parameter `--size-param` names, or to the first of `n`, `N`, `num_agents`
and `population` among the constructor's parameters and its scenario's fields; when there is
none the command stops with exit status 2 and lists the parameters the model takes
(`--size-param initial_sheep` for the wolf-sheep example). The other options apply to every
size: `--param`, `--seed`, `--sample-every`, `--top`. With `--format json` the report holds
the sizes, each operation's us per agent, growth and slope, and the hints; with `--format csv`,
one row per operation and size.

From Python, `compare_sizes` takes a function that builds the model at a size:

```python
from modelly.profile import compare_sizes

comparison = compare_sizes(lambda n: MyModel(n=n, rng=42), [1000, 4000], steps=20)
print(comparison.report())
comparison.hints()  # the MDL101 / MDL102 hints, if any
frame = comparison.to_dataframe()  # operation, size, us_per_agent
```

## What is measured

| Row | What it times |
|---|---|
| the step | the model's `step`, as run by its default schedule: wall time (`perf_counter`) and CPU time (`thread_time`) |
| `Cls.method (shuffle_do)` | each `AgentSet.do`, `shuffle_do` and `map` call, grouped by the class of the agents in the set (`A\|B` for a mixed set, `(empty)` for an empty one) and by the method name or function |
| `DataCollector.collect` | every `collect` call |
| `event Model.fn` | every other scheduled event, one-off or recurring, by its callback |

`agents/call` is the size of the set, `us/agent` the loop's wall time divided by the agents it
visited. Births and deaths count from the start of one step to the start of the next, so agents
created by events in between are included.

In the DataFrame, `kind` is `step`, `do`, `shuffle_do`, `map`, `collect` or `event`; `owner` is
the agent class, the collector class or the model; `births` and `deaths` are set on the `step`
rows only.

## Hints

The report ends with hints when a pattern is evident:

- **MDL101 / MDL102**: one loop takes more than half the time and its cost per agent grows with
  the population (the slope of log cost per agent against log population, over steps where the
  population varied by at least 1.5x, is above 0.5). An agent that scans every other agent is
  O(N) per agent and O(N²) per step. When the population does not change during a run, compare
  two sizes with `--sizes` (see [Comparing population sizes](#comparing-population-sizes)).
- **MDL103**: less than a tenth of the step runs inside `AgentSet` loops while the model has
  agents, which is what a hand-written `for agent in ...` activation loop looks like.
- **Data collection**: `collect` takes more than 30% of the time.

Run `python -m modelly.lint` on the model to find the lines behind an MDL hint.

## Cost and guarantees

Nothing in Modelly checks for a profiler: inside the `with` block the profiler replaces
`AgentSet.do`, `shuffle_do` and `map` (on both agent-set classes), `DataCollector.collect` and
`Event.execute` with timing wrappers, and on exit it puts the original functions back, also when
the run raises. Outside the block the model runs exactly the code it runs without the profiler.

The wrappers call the originals with the same arguments and draw no random numbers, so a
profiled run gives the same results as an unprofiled one, with the compiled loops or with
`MODELLY_PURE_PYTHON=1`. While the block runs, the timings add a few microseconds per loop call
and naming a set's agent class walks the set once.

Limits:

- The replaced functions are class attributes, so every model in the process is timed while the
  block runs, and only one profiler can be active at a time.
- Times are inclusive: a loop that calls another loop (an agent's `step` calling `do` on its
  neighbours) counts the inner loop in both rows.
- Code outside `AgentSet` loops (a hand-written `for` over agents, `ColumnTable.do_where`,
  numpy phases) is part of the step time but has no row of its own.
