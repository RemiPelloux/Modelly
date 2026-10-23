# Checking a model

`python -m modelly.lint` reads your model's source and reports two kinds of problems:

- **Errors** (`MDL0xx`): the model runs, but its result is wrong or cannot be reproduced from
  its seed.
- **Warnings** (`MDL1xx`): the model is right, but its cost grows faster than it needs to,
  usually O(N²) per step where O(N) is possible.

Nothing is imported or executed: the files are parsed and walked, so the check takes
milliseconds and is safe to run on any code.

```bash
python -m modelly.lint my_model/            # a folder, recursively
python -m modelly.lint model.py agents.py   # or files
python -m modelly.lint --list-rules
```

```text
model.py:14:12: MDL001 random draw outside the model's generators
    hint: use self.random (stdlib API) or self.rng (numpy Generator) so the seed reproduces the run
model.py:17:19: MDL101 an agent scans the whole population: O(N) per agent, O(N^2) per step
    hint: look at neighbours through self.cell.neighborhood or a space query, or move the phase to the model as columns
2 finding(s): 1 error(s), 1 warning(s)
```

The exit status is 1 when there are findings, 0 when there are none and 2 when a file does not
parse, so the command works as a CI step. `--select MDL0` keeps only the errors, `--ignore
MDL105` drops one rule, `--format json` prints a list for other tools, and `--exit-zero` reports
without failing.

## Errors

### MDL001: random draw outside the model's generators

`random.random()`, `np.random.normal()` and `np.random.default_rng()` without a seed draw from
generators the model does not own, so two runs with the same seed differ.

```python
if random.random() < self.p:                 # MDL001
if self.random.random() < self.p:            # the model's stdlib-style generator
step = self.rng.normal(size=n)               # the model's numpy Generator
```

### MDL002: `__init__` does not call `super().__init__`

An agent whose `__init__` skips `super().__init__(model)` is never registered: it is not in
`model.agents`, is never activated and has no `unique_id`. Nothing raises. A model that skips
it fails later with an `AttributeError` far from the cause.

### MDL003: loop over a set

A set of agents iterates in an order that follows memory addresses, which change from run to
run. Iterate the `AgentSet`, a list, or `sorted(...)`.

### MDL004: mutable class attribute on an agent

```python
class Trader(Agent):
    partners = []  # MDL004: one list, shared by every Trader

    def __init__(self, model):
        super().__init__(model)
        self.partners = []  # one list per agent
```

## Warnings

### MDL101: an agent scans the whole population

A loop, comprehension, `select`, `agg`, `groupby`, `sort` or `map` over `self.model.agents`
inside an agent method visits every agent once per agent: N² visits per step. Look at
neighbours through the space instead (`self.cell.neighborhood`, a continuous-space query), or
write the phase once at the model level over columns; see [vectorised step
phases](vectorised_phases).

### MDL102: nested loops over the population

`for a in self.agents: for b in self.agents:` in the model is N² per step. Pair agents through
the space (cells, `pairs_within`) or group them first with `agents.groupby`.

### MDL103: hand-written activation loop

`for a in self.agents: a.step()` is `self.agents.do("step")`, which says the order is fixed;
most models mean `self.agents.shuffle_do("step")`, a new random order each step.

### MDL104: `deepcopy` inside `step`

Copying a whole object graph every step usually costs more than the step itself. Copy the
fields you need, or keep the previous value in a column.

### MDL105: `step` has more than 12 branches

A long `step` hides its phase order. Split it into named phases (`move`, `interact`, `update`)
and call them in order, which is also the first move towards
[vectorising](vectorised_phases) them.

## Silencing a finding

End the line with `# noqa: MDL101` to skip that rule there, or `# noqa` to skip every rule on
the line. The checks are heuristics on the source: a loop over `self.model.agents` that runs
once at set-up is fine, and the comment is the place to say so.

## In CI

```yaml
- run: pip install git+https://github.com/RemiPelloux/Modelly.git
- run: python -m modelly.lint src/
```
