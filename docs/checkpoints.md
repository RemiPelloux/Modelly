# Checkpoints

`model.save(path)` writes the whole model to one file, and `Model.load(path)` reads it back. The
file holds both random generators (`model.random` and `model.rng`) at their exact state, so a
loaded model goes on drawing the same numbers as the model that was saved. Running 100 steps,
or running 50, saving, loading in a new Python process and running 50 more, gives the same
`DataCollector` output and leaves the generators in the same state.

```python
from modelly.examples import WolfSheep
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario

model = WolfSheep(WolfSheepScenario(rng=42))
model.run_for(50)
model.save("wolf-sheep.ckpt")

# later, possibly in another process
model = WolfSheep.load("wolf-sheep.ckpt")
model.run_for(50)
model.datacollector.get_model_vars_dataframe()  # identical to a 100-step run
```

`Model.load` is a class method and returns an instance of the class that was saved. Called on
a subclass (`WolfSheep.load`) it also checks that the file holds that class, and raises
`CheckpointError` when it does not; `Model.load` accepts any model.

```{warning}
A checkpoint is a [pickle](https://docs.python.org/3/library/pickle.html). Loading one runs
code chosen by whoever wrote the file. Only load checkpoints you made yourself or otherwise
trust, and never load one downloaded from an unknown source.
```

## Saving periodically

```python
writer = model.checkpoint_every(100, "runs/wolf-sheep-{time:05.0f}.ckpt")
model.run_for(1000)  # writes runs/wolf-sheep-00100.ckpt ... -01000.ckpt
writer.stop()  # no more checkpoints
```

The path pattern is formatted with the model's `time`. Each save is a low-priority scheduled
event, so it runs after the step at the same time, and it schedules the next save before
writing: a run resumed from any of these files keeps checkpointing on the same schedule. Pass
`compress=True` to `save` or `checkpoint_every` to gzip the file.

## What is saved

Everything the model refers to, through the ordinary pickle machinery, including:

- agents and their attributes, the registries (`agents`, `agents_by_type`) in their order;
- columns: the numpy tables are saved and per-agent column properties work after a load;
- cell spaces: cells, the agents in them and the agent-to-cell links, property layers, the
  index of empty cells (its order decides which empty cell a draw returns), `CellIndex`;
- continuous space: the position array, with `agent_positions` restored as a view of it;
- scheduled events, one-off and recurring, the default step schedule, and the counter that
  orders events scheduled at the same time with the same priority;
- signal subscriptions, `DataCollector` history and `DataRecorder` datasets, `CohortTable`s,
  the scenario.

Caches are not saved but rebuilt when next used: cell neighbourhoods and the continuous space's
neighbour lists. Weak references (agent sets, subscribers, event callbacks) are saved as weak
references to the restored objects.

## What cannot be saved

Pickle saves a function by its module and name, so only importable functions can be saved.
Lambdas and functions defined inside other functions cannot, and `save` raises
`CheckpointError` naming them: for a scheduled event it names the event, its time and its
callback. Use a module-level function, a method of the model or of an agent, or a
`functools.partial` of one, for event callbacks and `DataCollector` reporters alike:

```python
# cannot be checkpointed
DataCollector({"Wolves": lambda m: len(m.agents_by_type[Wolf])})


# can
def count_wolves(m):
    return len(m.agents_by_type[Wolf])


DataCollector({"Wolves": count_wolves})
```

The same holds for anything else the model holds that pickle cannot save: open files,
generators and iterators (for example an agent that keeps the iterator returned by
`cell.neighborhood.agents`), and classes created at run time. In this release that excludes
models that use `modelly.behaviour` continuous states and thresholds, whose bindings are
closures, and meta agents, whose classes are created at run time.

Class-level state is not part of a model and is not saved: subscriptions made with
`observe_class`, and attributes set on agent or model classes while the model runs.

## Compatibility

The file starts with a short text header, read before anything is unpickled:

```text
MODELLY-CHECKPOINT
{"format": 1, "modelly": "1.2.0", "python": "3.13", "compression": null}
```

`load` refuses, with a `CheckpointError` that says which field differs, a file written in
another checkpoint format, by another Modelly major.minor release or by another Python
major.minor version, and any file that does not start with this header. Patch releases of
Modelly read each other's checkpoints.

Both implementations of `FastRandom`, the compiled core and the pure-Python one used under
`MODELLY_PURE_PYTHON=1`, keep the same Mersenne Twister state and pickle to it. A checkpoint
saved with either loads into the other and continues the same stream.
