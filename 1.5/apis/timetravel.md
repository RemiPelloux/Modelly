# Time travel

Recording, rewinding, branching and diffing runs. How to use them is in [Time travel and run diff](https://remipelloux.github.io/Modelly/timetravel.html).

Module

Contents

modelly.timetravel.recorder

Recorder

modelly.timetravel.ring

the in-memory and on-disk checkpoint rings

modelly.timetravel.diff

diff

modelly.timetravel.report

RunDiff, Difference

modelly.timetravel.snapshot

agent_state, model_state

Time travel: rewind a run, replay it with changes, branch it, diff two runs.

`Recorder` checkpoints a running model into a ring held in memory or on disk; `Recorder.at(step)` returns a model at any recorded step, bit-identical to a straight run; `Recorder.branch` returns several futures from one state; `diff` finds the first step, agent and attribute where two runs diverge.

`Timeline` is the small interface tools such as a timeline scrubber use: anything with `steps`, `span` and `at`. `Recorder` implements it.

#### `class Timeline(*args, **kwargs)`

A recorded run a tool can list and scrub through.

#### `property steps: list[float]`

The steps that hold a checkpoint, oldest first (instant to fetch).

#### `property span: tuple[float, float]`

The first and last step `at` accepts.

#### `at(step: float) → Model[Any, Any]`

A new, independent model in the state of the run at `step`.

Record a run as a ring of checkpoints and rewind it to any step.

A [`Recorder`](https://remipelloux.github.io/Modelly/apis/timetravel.html#modelly.timetravel.recorder.Recorder) checkpoints the model when recording starts and then every `every` time units, holding the checkpoints in a ring ([`modelly.timetravel.ring`](https://remipelloux.github.io/Modelly/apis/timetravel.html#module-modelly.timetravel.ring)). `at(step)` restores the nearest checkpoint at or before `step` and replays forward to it. Checkpoints and replay are the 1.2 checkpoints (`modelly.Model.save()`), so the model returned is the one a straight run reaches at that step, bit for bit.

#### `thaw(model: Model[Any, Any]) → Model[Any, Any]`

Let `model.scenario` be changed, as on a model returned by `at`.

#### `reseed_model(model: Model[Any, Any], seed: np.random.SeedSequence) → None`

Reseed both generators of `model` in place from `seed`.

`model.rng` gets a bit generator of its own class seeded with `seed` and `model.random` the stdlib seed `Model` derives from a seed sequence, so spaces and columns holding the generators follow.

#### `class Recorder(model: Model[Any, Any], every: float = 10, *, memory_budget: int = 268435456, directory: str | Path | None = None, compress: bool = False)`

Checkpoint a model as it runs, to rewind, replay and branch it.

Use it as a context manager, or call `start()` and `stop()`:

```default
with Recorder(model, every=10) as rec:
    model.run_for(1000)
past = rec.at(312)
```

**Parameters:**

- **model** – The model to record.
- **every** – Time units between checkpoints; one is also taken at start.
- **memory_budget** – Bytes the checkpoints may take in all, in memory or, with `directory`, on disk. The oldest are evicted beyond it, except the first and the newest.
- **directory** – Write the checkpoints to this directory instead of holding them in memory.
- **compress** – Gzip each checkpoint (smaller, slower).

Prepare to record `model`; recording starts with `start()`.

#### `property recording: bool`

Whether the model is being recorded now.

#### `property steps: list[float]`

The steps that hold a checkpoint, oldest first.

#### `property span: tuple[float, float]`

The first and last step `at` can return.

#### `property nbytes: int`

The bytes the checkpoints take, in memory or on disk.

#### `start() → None`

Checkpoint the model now and every `every` time units from here.

#### `stop() → None`

Stop recording; `at` and `branch` keep working.

#### `checkpoint() → None`

Checkpoint the model now, after changing it from outside the run.

Replay reruns the model’s own dynamics only: a change made between two `run_for` calls, such as setting an agent attribute, reaches `at` for the steps after the next checkpoint. Call this right after such a change so that every later step includes it.

#### `at(step: float) → Model[Any, Any]`

A new model in the state of the recorded run at `step`.

The nearest checkpoint at or before `step` is restored and run on to `step`. The model is independent of the recorded one and of the checkpoints, and its scenario can be changed (see the time travel guide for what that means).

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `step` is outside `span`.

#### `branch(step: float, n: int, *, reseed: bool = False) → list[Model[Any, Any]]`

`n` independent models, all in the state of the run at `step`.

Without `reseed` every branch continues the same random streams, so identical runs stay identical until you change one. With `reseed`, branch `i` is reseeded from `scenario.seed_sequence.spawn(n)[i]`: the child seeds `Scenario.spawn_replications(n)` uses.

Checkpoint rings: the recorded checkpoints of a run, within a byte budget.

A ring maps a step (the model’s `time` when the checkpoint was taken) to the bytes of a checkpoint file. When the ring holds more bytes than its budget it drops its oldest checkpoints, except the first one, so a recorded run can always be rewound to where recording started.

[`MemoryRing`](https://remipelloux.github.io/Modelly/apis/timetravel.html#modelly.timetravel.ring.MemoryRing) keeps the bytes in memory. [`DiskRing`](https://remipelloux.github.io/Modelly/apis/timetravel.html#modelly.timetravel.ring.DiskRing) writes each checkpoint to its own file through a temporary file and `os.replace`, which is atomic on Windows, macOS and Linux: a file in the ring is always whole.

#### `class MemoryRing(budget: int)`

Checkpoints held in memory as bytes.

Hold checkpoints up to `budget` bytes of memory.

#### `get(step: float) → bytes`

The checkpoint bytes of `step`.

#### `discard(step: float) → None`

Drop the checkpoint of `step`.

#### `class DiskRing(directory: str | Path, budget: int)`

Checkpoints held as files `step-<time>.ckpt` in one directory.

Each file is an ordinary checkpoint that `Model.load` reads. Files left when the ring is dropped stay on disk; evicted ones are deleted.

Hold checkpoints up to `budget` bytes of disk in `directory`.

#### `path(step: float) → Path`

The file that holds the checkpoint of `step`.

#### `get(step: float) → bytes`

The checkpoint bytes of `step`, read from its file.

#### `discard(step: float) → None`

Drop the checkpoint of `step` and delete its file.

Find where two runs diverge: first in their collected data, then in state.

`diff` takes two runs given as models, recorders, `DataCollector` objects or model-variable DataFrames (`get_model_vars_dataframe()`):

- collected data (both runs have a collector or a DataFrame): the first collection step at which a model reporter differs, or, from collectors, the first agent and reporter whose agent record differs;
- state (both runs are models or recorders): the first model scalar, agent or agent attribute that differs (see [`modelly.timetravel.snapshot`](https://remipelloux.github.io/Modelly/apis/timetravel.html#module-modelly.timetravel.snapshot)). Two recorders are compared at their common checkpoints, then replayed one time unit at a time from the last matching one, so the state difference is at the first step where the runs diverge; two models are compared as they are.

#### `data_difference(a: Run, b: Run) → Difference | None`

The first difference in the data two runs collected.

#### `state_difference(a: Run, b: Run) → Difference | None`

The first difference in the state of two runs.

#### `diff(run_a: Run, run_b: Run) → RunDiff`

Where two runs first diverge.

**Parameters:**

- **run_a** – A model, a `Recorder`, a `DataCollector` or a DataFrame of model variables.
- **run_b** – The run to compare it with, of any of the same kinds.

**Returns:**

`str()` of it is a readable report, and its `data` and `state` fields say step, agent and attribute.

**Return type:**

A `RunDiff`

The result of [`modelly.timetravel.diff()`](https://remipelloux.github.io/Modelly/apis/timetravel.html#module-modelly.timetravel.diff): where two runs diverge.

#### `class Difference(step: float, name: str, a: Any, b: Any, agent: int | None = None, agent_class: str | None = None)`

One value that differs between two runs.

**Variables:**

- **step** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – The model time at which the value differs.
- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The reporter, model attribute or agent attribute that differs.
- **a** (*Any*) – Its value in the first run.
- **b** (*Any*) – Its value in the second run.
- **agent** ([*int*](https://docs.python.org/3/builtins/functions.html#int)* | **None*) – The `unique_id` of the agent, or None for a model value.
- **agent_class** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – The class name of the agent, when known.

#### `class RunDiff(data: Difference | None = None, state: Difference | None = None)`

Where two runs first diverge, in their collected data and their state.

**Variables:**

- **data** ([*modelly.timetravel.report.Difference*](https://remipelloux.github.io/Modelly/apis/timetravel.html#modelly.timetravel.report.Difference)* | **None*) – The first difference in the collected data (model reporters, then agent reporters), or None.
- **state** ([*modelly.timetravel.report.Difference*](https://remipelloux.github.io/Modelly/apis/timetravel.html#modelly.timetravel.report.Difference)* | **None*) – The first difference in model or agent state, or None. For two recorders it is at the first step where the states differ; for two models, at their current time.

#### `property identical: bool`

Whether no difference was found.

#### `property step: float | None`

The first step at which the runs differ, or None.

#### `report() → str`

A readable report of the divergence.

Stable snapshots of model and agent state, and their first difference.

An agent’s snapshot is its `unique_id`, class name and the values that make up its state: its `Column` values, the scalars in its `__dict__` (names starting with `_` excluded) and where it is (`cell` coordinate or `position`). Short numpy vectors and tuples of scalars count as scalars; lists, sets, other agents and objects do not. The model’s snapshot adds its own scalars and a digest of each random generator’s state.

#### `agent_state(agent: Agent[Any]) → dict[str, Any]`

The state of `agent`: columns, `__dict__` scalars and place.

#### `class ModelState(model: dict[str, Any], agents: dict[int, tuple[str, dict[str, Any]]], generators: dict[str, str])`

A model’s snapshot: its scalars, its agents and its generators.

#### `model_state(model: Model[Any, Any]) → ModelState`

The snapshot of `model` and every agent it holds.

#### `same(a: Any, b: Any) → bool`

Whether two snapshot or data values are equal, NaN equal to NaN.

#### `first_value_difference(a: dict[str, Any], b: dict[str, Any], step: float, **who: Any) → Difference | None`

The first name, in `a`’s order then `b`’s, whose values differ.

#### `first_state_difference(a: ModelState, b: ModelState, step: float) → Difference | None`

The first difference: model scalars, then agents, then generators.
