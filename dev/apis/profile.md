# Profile

The runtime profiler behind `python -m modelly.profile`. How to read its report is in [Profiling a model](https://remipelloux.github.io/Modelly/dev/profile.html).

Runtime profiling for Modelly models: where each step’s time goes, in Modelly terms.

The runtime companion of `python -m modelly.lint`. `Profiler` times each step, every `AgentSet.do` / `shuffle_do` / `map` call by agent class and method, `DataCollector.collect` and the scheduled-event callbacks, and counts births and deaths per step:

```default
from modelly.profile import Profiler

with Profiler(model) as prof:
    model.run_for(100)
print(prof.report())
```

From a shell: `python -m modelly.profile path/to/model.py:MyModel --steps 100`. `compare_sizes` builds the model at several population sizes and compares the cost per agent (`--sizes 1000,4000` on the command line). Nothing is patched outside the `with` block. The guide is `docs/profile.md`.

#### `class Profiler(model: Model[Any, Any], sample_every: int = 1)`

Record where each step of `model` spends its time.

Use it as a context manager around the run:

```default
with Profiler(model) as prof:
    model.run_for(100)
print(prof.report())
frame = prof.to_dataframe()
```

**Parameters:**

- **model** – the model to profile.
- **sample_every** – profile one step in `sample_every` (steps 1, 1 + N, …); the others run through the wrappers untimed.

Notes

The patched methods are class attributes, so while the block runs every agent set, collector and event in the process is timed, not only those of `model`. Only one profiler can be active at a time. Times of nested loops (an agent’s step calling `do` on another set) are inclusive.

Prepare a profiler; nothing is patched until the `with` block starts.

#### `report(top: int = 15) → str`

A text table of the `top` costliest operations, with hints.

#### `to_dict() → dict[str, Any]`

The summary, the per-step totals and the hints, JSON-ready.

#### `to_dataframe() → pd.DataFrame`

One row per step (kind `step`) and per operation within a step.

#### `class SizeComparison(model: str, runs: list[SizeRun])`

The profiles of one model built at several sizes, compared per agent.

`runs` are ordered by size, smallest first.

#### `growths() → list[Growth]`

The whole step, then each agent loop, costliest at the largest size first.

#### `hints() → list[str]`

A hint per notable operation whose cost per agent grows roughly with N.

#### `report(top: int = 15) → str`

The us-per-agent table, one column per size, then the growth and the hints.

#### `to_dict() → dict[str, Any]`

The sizes, each operation’s us per agent and growth, and the hints.

#### `to_dataframe() → DataFrame`

One row per operation and size: `operation`, `size`, `us_per_agent`.

#### `class StepRecord(step: int, time: float, agents: int, wall: float = 0.0, cpu: float = 0.0, births: int = 0, deaths: int = 0, ops: dict[tuple[str, str, str], list[~typing.Any]] = <factory>)`

What one profiled step cost.

`ops` maps `(kind, owner, name)` to `[calls, agents visited, wall s, CPU s]`. `kind` is an AgentSet method (`do`, `shuffle_do`, `map`), `collect` or `event`; `owner` is the agent class (`A|B` for a mixed set) or the collector class. Births and deaths count from this step’s start to the next one’s, so agents created by events in between are included.

#### `add(key: tuple[str, str, str] | None, agents: int, times: tuple[Any, ...]) → None`

Add one timed call; `key` None is the step itself.

#### `compare_sizes(factory: Callable[[int], Model[Any, Any]], sizes: Sequence[int], steps: int = 100, sample_every: int = 1) → SizeComparison`

Build the model with `factory(size)` at each size, profile `steps` steps of each.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – when there are fewer than two different positive sizes.

The profiler: time a running model’s steps, agent-set loops, data collection and events.

`Profiler` replaces a handful of framework methods while its `with` block runs and puts the originals back on exit, so a model that is not being profiled runs exactly the code it always does. The wrappers never draw a random number nor reorder a loop: a profiled run gives the same results as an unprofiled one.

#### `class StepRecord(step: int, time: float, agents: int, wall: float = 0.0, cpu: float = 0.0, births: int = 0, deaths: int = 0, ops: dict[tuple[str, str, str], list[~typing.Any]] = <factory>)`

What one profiled step cost.

`ops` maps `(kind, owner, name)` to `[calls, agents visited, wall s, CPU s]`. `kind` is an AgentSet method (`do`, `shuffle_do`, `map`), `collect` or `event`; `owner` is the agent class (`A|B` for a mixed set) or the collector class. Births and deaths count from this step’s start to the next one’s, so agents created by events in between are included.

#### `add(key: tuple[str, str, str] | None, agents: int, times: tuple[Any, ...]) → None`

Add one timed call; `key` None is the step itself.

#### `agent_classes(agentset: Any) → str`

The class names of the members of `agentset`, sorted and joined by `|`.

#### `callable_name(fn: Any) → str`

A readable name for a method name, a function or an event callback.

#### `class Profiler(model: Model[Any, Any], sample_every: int = 1)`

Record where each step of `model` spends its time.

Use it as a context manager around the run:

```default
with Profiler(model) as prof:
    model.run_for(100)
print(prof.report())
frame = prof.to_dataframe()
```

**Parameters:**

- **model** – the model to profile.
- **sample_every** – profile one step in `sample_every` (steps 1, 1 + N, …); the others run through the wrappers untimed.

Notes

The patched methods are class attributes, so while the block runs every agent set, collector and event in the process is timed, not only those of `model`. Only one profiler can be active at a time. Times of nested loops (an agent’s step calling `do` on another set) are inclusive.

Prepare a profiler; nothing is patched until the `with` block starts.

#### `report(top: int = 15) → str`

A text table of the `top` costliest operations, with hints.

#### `to_dict() → dict[str, Any]`

The summary, the per-step totals and the hints, JSON-ready.

#### `to_dataframe() → pd.DataFrame`

One row per step (kind `step`) and per operation within a step.
