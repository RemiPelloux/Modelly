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
python -m modelly.lint --list-rules         # one line per rule
python -m modelly.lint --explain MDL101     # one rule in detail: why, bad and good example
python -m modelly lint my_model/            # the same, through the umbrella command
```

```text
model.py:14:12: MDL001 random draw outside the model's generators
    hint: use self.random (stdlib API) or self.rng (numpy Generator) so the seed reproduces the run
model.py:17:19: MDL101 an agent scans the whole population: O(N) per agent, O(N^2) per step
    hint: look at neighbours through self.cell.neighborhood or a space query, or move the phase to the model as columns
2 finding(s): 1 error(s), 1 warning(s)
```

Each finding is `path:line:col: CODE message`, the form editors and CI logs link to, followed by
a hint.

## Options

| Option | Effect |
|---|---|
| `--select CODES` | keep only these comma-separated codes or prefixes (`MDL0` is every error) |
| `--ignore CODES` | drop these codes or prefixes |
| `--format text` | the default: findings, hints and a summary line |
| `--format json` | a JSON list of findings, for other tools |
| `--format github` | `::error file=...,line=...,col=...,title=MDL001::...` annotations for GitHub Actions |
| `--statistics` | one line per rule with its count, most frequent first |
| `-q`, `--quiet` | only the `path:line:col: CODE message` lines: no hints, no summary |
| `--exit-zero` | report, but exit 0 |
| `--explain CODE` | print why a rule matters, a bad and a good example, and exit |
| `--list-rules` | print every rule and exit |

Exit status: **0** no findings (or `--exit-zero`), **1** at least one finding, **2** a usage error
(a path that cannot be read, a file that does not parse, a bad configuration or an unknown rule
for `--explain`).

## Errors

(mdl001)=
### MDL001: random draw outside the model's generators

The seed fixes a run only when every draw comes from the model. The global `random` and
`np.random` streams, an unseeded `random.Random()`, `np.random.default_rng()` or
`default_rng(None)`, a bit generator built without a seed (`PCG64()`) and `SystemRandom` are
not owned by the model, so two runs with the same seed differ. Calls are read through the
module's imports, so `import numpy.random as npr` and `from random import choice` are caught;
`random.Random(42)`, `default_rng(seed=7)` and `Generator(PCG64(7))` are not reported.

```python
if random.random() < self.p:                 # MDL001
noise = np.random.normal(size=n)             # MDL001
if self.random.random() < self.p:            # the model's stdlib-style generator
noise = self.rng.normal(size=n)              # the model's numpy Generator
```

(mdl002)=
### MDL002: `__init__` does not call `super().__init__`

An agent whose `__init__` skips `super().__init__(model)` is never registered: it is not in
`model.agents`, is never activated and has no `unique_id`. A model that skips it has no
generators or registry. Nothing raises at once; the failure comes later, far from the cause.

```python
class Sheep(Agent):
    def __init__(self, model):
        self.energy = 5              # MDL002

class Sheep(Agent):
    def __init__(self, model):
        super().__init__(model)      # registered, with a unique_id
        self.energy = 5
```

(mdl003)=
### MDL003: loop over a set

A set of agents iterates in an order that follows memory addresses, which change from run to
run, so every draw or update that depends on the order changes too.

```python
for a in set(neighbours):                             # MDL003
for a in neighbours:                                  # an AgentSet or a list keeps its order
for a in sorted(set(neighbours), key=lambda a: a.unique_id):
```

(mdl004)=
### MDL004: mutable class attribute on an agent

A list, dict or set in the class body is created once, with the class, and shared by every
agent: one agent's append shows up in all of them.

```python
class Trader(Agent):
    partners = []  # MDL004: one list, shared by every Trader

    def __init__(self, model):
        super().__init__(model)
        self.partners = []  # one list per agent
```

(mdl005)=
### MDL005: wall clock or OS entropy in model code

`time.time()`, `time.time_ns()`, `datetime.now()`, `datetime.utcnow()`, `date.today()`,
`uuid.uuid1()`, `uuid.uuid4()`, `os.urandom()` and anything from `secrets` return a new value on
every run. Inside a model or agent class they make the outcome depend on the machine and the
moment instead of the seed. Timing code outside the classes, and `time.perf_counter()` for
profiling, are not reported.

```python
class Sheep(Agent):
    def step(self):
        self.born = datetime.now()        # MDL005
        self.tag = uuid.uuid4()           # MDL005
        self.born = self.model.time       # the model's clock
        self.tag = self.unique_id         # already unique and reproducible
```

(mdl006)=
### MDL006: `hash()` or `id()` decides an outcome

`id()` is a memory address, and `hash()` of a `str` or `bytes` is salted per process
(`PYTHONHASHSEED`). Ordering by them (`key=id`, `key=lambda a: id(a)`) anywhere, or calling
`hash()` in a model or agent method other than `__hash__`, gives a different result each run.

```python
queue = sorted(self.agents, key=id)                     # MDL006
group = hash(self.name) % 4                             # MDL006
queue = sorted(self.agents, key=lambda a: a.unique_id)
group = self.unique_id % 4
```

(mdl007)=
### MDL007: a loop over the population removes agents

Iterating an `AgentSet` walks a snapshot taken when the loop starts. An agent removed by an
earlier iteration (`other.remove()`) is therefore still visited and acts after its death.
`agents.do(...)` and `agents.shuffle_do(...)` check membership and skip it. Removing the loop's
own agent (`for a in ...: a.remove()`) is fine and not reported.

```python
for wolf in self.agents_by_type[Wolf]:
    wolf.prey.remove()                                   # MDL007: that prey may come up later
self.agents_by_type[Wolf].shuffle_do("hunt")             # hunt() calls self.prey.remove()
```

(mdl008)=
### MDL008: `global` statement in a model or agent method

A module-level variable outlives the model. Two models in one process (a batch run, a test
suite, a notebook re-run) share it and keep mutating it, so a run depends on what ran before.

```python
BORN = 0

class Sheep(Agent):
    def step(self):
        global BORN                   # MDL008
        BORN += 1
        self.model.born += 1          # state on the model: each run starts fresh
```

(mdl009)=
### MDL009: the model's agent set is changed directly

`model.agents` and `model.agents_by_type[...]` are the registry itself. `add`, `discard`,
`remove` or `clear` on them skips the per-type sets, the column tables and the data
collectors, which then disagree with each other. Creating an agent registers it; `agent.remove()`
deregisters it everywhere.

```python
self.model.agents.discard(self)          # MDL009
self.remove()
```

## Warnings

(mdl101)=
### MDL101: an agent scans the whole population

A loop, comprehension, `select`, `agg`, `groupby`, `sort` or `map` over `self.model.agents`
(or `agents_by_type[...]`) inside an agent method visits every agent once per agent: N² visits
per step. Look at neighbours through the space instead (`self.cell.neighborhood`, a
continuous-space query), or write the phase once at the model level over columns; see
[vectorised step phases](vectorised_phases).

```python
near = [a for a in self.model.agents if a.cell in self.cell.neighborhood]   # MDL101
near = self.cell.neighborhood.agents
```

(mdl102)=
### MDL102: nested loops over the population

Two nested loops over the population compare every pair of agents, N² per step, even when only
neighbours can interact. Pair agents through the space (cells, `pairs_within`) or group them
first with `agents.groupby`.

```python
for a in self.agents:
    for b in self.agents:                    # MDL102
        a.meet(b)
for a in self.agents:
    for b in a.cell.neighborhood.agents:
        a.meet(b)
```

(mdl103)=
### MDL103: hand-written activation loop

`for a in self.agents: a.step()` is `self.agents.do("step")`, a fixed order, and unlike `do`
it still visits agents removed earlier in the loop. Most models mean
`self.agents.shuffle_do("step")`, a new random order each step.

```python
for agent in self.agents:                    # MDL103
    agent.step()
self.agents.shuffle_do("step")
```

(mdl104)=
### MDL104: `deepcopy` inside `step`

`deepcopy` walks the whole object graph, which for an agent includes the model, the space and
every other agent. Done every step, it costs more than the step itself. Copy the fields you
need, or keep the previous value in a column.

```python
self.previous = copy.deepcopy(self)          # MDL104
self.previous_energy = self.energy
```

(mdl105)=
### MDL105: `step` has more than 12 branches

A long `step` hides its phase order. Split it into named phases (`move`, `interact`, `update`)
and call them in order, which is also the first move towards [vectorising](vectorised_phases)
them.

```python
def step(self):
    self.move()
    self.eat()
    self.reproduce()
```

(mdl106)=
### MDL106: pandas DataFrame built inside `step`

`pd.DataFrame(...)` and `pd.concat(...)` copy every row each time, so growing a table step by
step is quadratic in the number of steps. Record with a `DataCollector`, or append rows to a
list and build the frame once after the run.

```python
def step(self):
    self.log = pd.concat([self.log, pd.DataFrame([row])])   # MDL106
    self.rows.append(row)                                    # pd.DataFrame(self.rows) at the end
```

(mdl107)=
### MDL107: per-agent loop that only writes `Column` attributes

In a model method, a loop over the population whose body only assigns attributes declared as
`Column` in the same module (plain `=`/`+=`, or an `if` made of those, with no calls) is a
whole-column update written one agent at a time. The column's numpy array does it in C. Loops
that call anything (a draw, a method) are not reported: vectorising them changes the order of
draws or needs a decision.

```python
class Sheep(Agent):
    energy = Column(float, default=5.0)

class Pasture(Model):
    def step(self):
        for sheep in self.agents_by_type[Sheep]:       # MDL107
            sheep.energy -= 1
        table = self.columns[Sheep]
        table.energy -= 1                              # one numpy operation
```

## Silencing a finding

End the line the finding points at with `# noqa: MDL101` to skip that rule there, `# noqa:
MDL101, MDL104` for several, or a bare `# noqa` to skip every rule on the line. Text after the
codes is free, so the comment can say why. For a loop or a multi-line call, the line is the
first one (`for ...:` or the line the call starts on).

```python
for a in self.model.agents:  # noqa: MDL101 runs once, at set-up
    ...
```

The checks are heuristics on the source: a loop over `self.model.agents` that runs once at
set-up is fine, and the comment is the place to say so.

## Configuration

`[tool.modelly.lint]` in the nearest `pyproject.toml`, searched from the working directory
upwards, sets the defaults:

```toml
[tool.modelly.lint]
select = ["MDL0", "MDL101"]      # only these codes or prefixes (default: every rule)
ignore = ["MDL105"]              # drop these codes or prefixes
per-file-ignores = { "tests/*" = ["MDL001"], "scripts/*.py" = ["MDL1"] }
```

Per-file patterns are globs on the path relative to the `pyproject.toml` folder, or on the bare
file name. `--select` and `--ignore` on the command line replace the file's `select` and
`ignore`; `per-file-ignores` always applies. An unknown key is an error (exit 2), so a typo does
not silently disable the configuration.

## In CI

```yaml
- run: pip install modelly-abm
- run: python -m modelly.lint --format github src/
```

With `--format github`, each finding shows as an annotation on the changed line of the pull
request.
