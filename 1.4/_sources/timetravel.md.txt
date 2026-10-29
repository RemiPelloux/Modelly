# Time travel and run diff

`modelly.timetravel` lets you debug a stochastic model without rerunning it from step zero. A
`Recorder` keeps checkpoints of a run as it goes; from them you can get the model back at any
step, change it and replay from there, branch it into several futures, and `diff` two runs to
see the first step, agent and attribute where they diverge.

It is built on [checkpoints](checkpoints.md): a recorder checkpoint is a `Model.save` file,
held in memory or written to disk, so everything said there about what can be saved holds here.

## Recording and rewinding

```python
from modelly.examples import WolfSheep
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario
from modelly.timetravel import Recorder

model = WolfSheep(WolfSheepScenario(rng=42))
with Recorder(model, every=10) as rec:
    model.run_for(1000)

rec.steps  # [0.0, 10.0, 20.0, ..., 1000.0], or fewer if the budget evicted some
past = rec.at(312)  # a new model at step 312
```

The recorder checkpoints the model when recording starts (`with` or `start()`) and then every
`every` time units, at the multiples of `every`. `at(step)` restores the nearest checkpoint at or
before `step` and runs the model on to `step`. The model returned is independent: running it
changes neither the recorded model nor the checkpoints, and `at` can be called again for the
same or another step. `at` accepts any step in `rec.span`, from the first checkpoint to the
last time the recorder saw the model; after `stop()` (or the end of the `with` block) the
checkpoints stay available, and the model can go on running unrecorded.

### Bit-identical replay

The state `at(step)` returns is the state a straight run reaches at `step`, bit for bit: agents
and their attributes, columns, spaces, scheduled events, collected data and the exact state of
`model.random` and `model.rng`. Running it on gives what the straight run gives. Recording does
not change the run either. Both are tested on the bundled Boltzmann, Schelling, Wolf-Sheep
(with its grass regrowth events) and Boids examples, with the compiled core and with the
pure-Python one (`MODELLY_PURE_PYTHON=1`).

Recording stops time at each checkpoint, so a model observed through `observe("time", ...)`
sees one `time` change at each checkpoint time even when no event falls on it. With the default
schedule there is always a step there, and nothing changes.

### Changes from outside the run

Replay reruns the model's own dynamics: its steps and scheduled events. A change made from
outside between two `run_for` calls, such as setting an agent's attribute by hand, is part of
the recorded run only from the next checkpoint on; replay from an earlier checkpoint does not
repeat it. Call `rec.checkpoint()` right after such a change to record it at once.

## Budget and storage

```python
Recorder(model, every=10, memory_budget=512 * 2**20)  # bytes, default 256 MiB
Recorder(model, every=10, compress=True)  # gzip each checkpoint
Recorder(model, every=10, directory="runs/rewind")  # checkpoints on disk
```

`memory_budget` bounds the bytes all checkpoints take, in memory or, with `directory`, on disk.
When a new checkpoint takes the ring over its budget, the oldest are evicted, except the first
one (step 0 when recording starts with the model) and the newest, so the run can always be
rewound to where recording started; `rec.nbytes` says how much is held. Evicting a checkpoint
only makes rewinding to the steps after it slower, since `at` replays from an earlier one.

On disk each checkpoint is a file `step-<time>.ckpt`, for example `step-310.0.ckpt`, that
`Model.load` reads. A file is written under a temporary name and moved into place with
`os.replace`, which is atomic on Windows, macOS and Linux, so a file in the directory is always
whole. Evicted files are deleted; the others are left when the recorder is gone.

## Replay with a changed scenario

```python
past = rec.at(312)
past.scenario.grass_regrowth_time = 10
past.grass = False
past.run_for(100)
```

A `Scenario` is frozen, but the scenario of a model returned by `at` or `branch` is a copy you
may change. Changing a scenario mid-run means:

- the new value is seen by any code that reads `self.scenario.<name>` (or
  `self.model.scenario.<name>`) from the next step or event on;
- values the model copied out of the scenario when it was created keep their old value: in
  Wolf-Sheep, `grass` is copied to `model.grass` and `grass_regrowth_time` to each grass patch,
  so change those attributes too, as above;
- the random generators are not touched, so the replay draws the same numbers as the original
  until the change makes it draw differently;
- the recorded run and its checkpoints keep the original scenario. A model saved after the
  change keeps the new values (frozen again once loaded).

## Branching

```python
futures = rec.branch(312, 4)  # four models at step 312, same random streams
futures = rec.branch(312, 4, reseed=True)  # four models at step 312, four streams
```

`branch(step, n)` returns `n` independent models, all in the state of the run at `step`. Without
`reseed` they continue the same random streams: left unchanged they stay identical, so
differences between them come only from what you change. With `reseed=True`, branch `i` has
both generators reseeded from `scenario.seed_sequence.spawn(n)[i]`, the child seeds
`Scenario.spawn_replications(n)` uses: the futures differ by chance, and the same call gives the
same futures again. `model.rng` keeps its bit generator class and `model.random` gets the stdlib
seed `Model` derives from a seed sequence. The scenario's `seed_sequence` is left as it was.

## Diffing two runs

```python
from modelly.examples import BoltzmannWealth
from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannScenario
from modelly.timetravel import Recorder, diff


def record(nudge):
    model = BoltzmannWealth(BoltzmannScenario(rng=42))
    with Recorder(model, every=10) as rec:
        model.run_for(23)
        if nudge:  # one agent gets one more coin at step 23
            min(model.agents, key=lambda a: a.unique_id).wealth += 1
            rec.checkpoint()
        model.run_for(17)
    return rec


print(diff(record(False), record(True)))
```

```text
The runs diverge at step 23.
Collected data: step 24, model, Gini: 0.6597999999999999 != 0.6620792079207921
State: step 23, agent 1 (MoneyAgent), wealth: 5 != 6
```

`diff` takes two runs, each a model, a `Recorder`, a `DataCollector` or a DataFrame of model
variables (`get_model_vars_dataframe()`), and returns a `RunDiff`:

- `data`: the first difference in the collected data: the first collection at which a model
  reporter differs, or, between two collectors, the first agent and reporter whose agent record
  differs, whichever comes first;
- `state`: the first difference in state: model attributes first, then agents in `unique_id`
  order (an agent present in only one run, a different class, then the first attribute that
  differs), then the generators. Between two recorders the states are compared at the common
  checkpoints and then step by step from the last matching one, so `state.step` is the first
  step where the runs differ. Between two models, they are compared as they are now.

`RunDiff.step` is the earlier of the two, `RunDiff.identical` is true when neither was found,
and each `Difference` has `step`, `name`, `a`, `b`, `agent` and `agent_class`.

An agent's state, as compared, is `agent_state(agent)`: its `Column` values, the scalars in its
`__dict__` (bools, numbers, strings, short numpy vectors and tuples of scalars; names starting
with `_` left out) and its place (`cell` coordinate or `position`). Lists, sets, references to
other agents and other objects are not compared; the generators are compared through a digest
of their state. NaN equals NaN.

## For tools: the timeline interface

A timeline scrubber, such as the one planned for Modelly Studio, needs only three members, which
`modelly.timetravel.Timeline` names and `Recorder` implements:

| Member | Returns |
|---|---|
| `steps` | the steps that hold a checkpoint, oldest first: instant to fetch |
| `span` | `(first, last)`: the steps `at` accepts |
| `at(step)` | a new, independent model at `step`: a checkpoint restored, then replayed from it to `step` |

```{warning}
Checkpoints are pickles. A directory of recorder checkpoints is as trusted as the code that
wrote it: only load files you made yourself or otherwise trust.
```
