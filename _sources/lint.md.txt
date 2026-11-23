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
| `--fix` | apply the [safe fixes](#fixing-findings), then report what is left |
| `--diff` | print the safe fixes as a unified diff; nothing is written |
| `--exit-zero` | report, but exit 0 |
| `--explain CODE` | print why a rule matters, a bad and a good example, and exit |
| `--list-rules` | print every rule and exit |
| `--lsp` | run as a language server for editors ([In an editor](#in-an-editor)) |

Exit status: **0** no findings (or `--exit-zero`), **1** at least one finding (with `--diff`:
at least one fix to apply), **2** a usage error
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
        self.energy = 5  # MDL002


class Sheep(Agent):
    def __init__(self, model):
        super().__init__(model)  # registered, with a unique_id
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
agent: one agent's append shows up in all of them. `__slots__` and attributes annotated
`ClassVar[...]` are shared on purpose and not reported.

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
        self.born = datetime.now()  # MDL005
        self.tag = uuid.uuid4()  # MDL005
        self.born = self.model.time  # the model's clock
        self.tag = self.unique_id  # already unique and reproducible
```

(mdl006)=
### MDL006: `hash()` or `id()` decides an outcome

`id()` is a memory address, and `hash()` of a `str` or `bytes` is salted per process
(`PYTHONHASHSEED`). Ordering by them (`key=id`, `key=lambda a: id(a)`) anywhere, or calling
`hash()` in a model or agent method other than `__hash__`, gives a different result each run.

```python
queue = sorted(self.agents, key=id)  # MDL006
group = hash(self.name) % 4  # MDL006
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
    wolf.prey.remove()  # MDL007: that prey may come up later
self.agents_by_type[Wolf].shuffle_do("hunt")  # hunt() calls self.prey.remove()
```

(mdl008)=
### MDL008: `global` statement in a model or agent method

A module-level variable outlives the model. Two models in one process (a batch run, a test
suite, a notebook re-run) share it and keep mutating it, so a run depends on what ran before.

```python
BORN = 0


class Sheep(Agent):
    def step(self):
        global BORN  # MDL008
        BORN += 1
        self.model.born += 1  # state on the model: each run starts fresh
```

(mdl009)=
### MDL009: the model's agent set is changed directly

`model.agents` and `model.agents_by_type[...]` are the registry itself. `add`, `discard`,
`remove` or `clear` on them skips the per-type sets, the column tables and the data
collectors, which then disagree with each other. Creating an agent registers it; `agent.remove()`
deregisters it everywhere.

```python
self.model.agents.discard(self)  # MDL009
self.remove()
```

(mdl010)=
### MDL010: a lambda or nested function is sent to worker processes

Windows and macOS start process-pool workers with `spawn`: each worker is a fresh interpreter
that imports the function or class it runs by its module and qualified name. A lambda, or a
function or class defined inside another function (a closure), has no such name. Linux forks
its workers, so the same batch works there and fails on the other two.

The rule looks at every argument of `run_batch`, `run_grid`, `run_scenarios`,
`RunConfiguration` and `Experiment`, and at keyword arguments of any call named `run`,
`model_class`, `model_cls` or ending in `factory` (`model_factory=`). Lists, tuples, dict
values and `functools.partial(f, ...)` are looked into. A call with `workers=1` runs every
task in this process and is not reported.

```python
def main():
    def run(task):  # nested: a spawned worker cannot import it
        return Sheep(task).run()

    run_batch(run, tasks)  # MDL010
    run_batch(lambda t: t, tasks)  # MDL010


def run(task):  # module level: importable by every worker
    return Sheep(task).run()
```

(mdl011)=
### MDL011: sampler without a seed

An experiment's design is part of its result: the same seed must give the same points. A
`scipy.stats.qmc` engine (`LatinHypercube`, `Sobol`, `Halton`, `PoissonDisk`,
`MultivariateNormalQMC`, `MultinomialQMC`) without `rng=` (or the older `seed=`), a scipy
distribution's `.rvs()` without `random_state=`, and a SALib sampler
(`SALib.sample.<method>.sample`) without `seed=` all scramble from global or fresh OS state,
so the sample, and every result computed from it, changes from one run of the study to the
next. Passing `None` counts as no seed. Modelly's own designs (`modelly.experiments.designs`,
`modelly.sensitivity`) are seeded from the experiment's seed already.

```python
units = qmc.LatinHypercube(d=3).random(64)  # MDL011
noise = norm(0, 1).rvs(10)  # MDL011

rng = np.random.default_rng(seed)
units = qmc.LatinHypercube(d=3, rng=rng).random(64)
noise = norm(0, 1).rvs(10, random_state=rng)
```

Inside a model or agent method, `--fix` passes the model's generator: `rng=self.rng` to a qmc
engine, `random_state=self.rng` to `.rvs()`. Elsewhere there is no generator to pass, and SALib
takes an integer seed whose value is the study's choice, so those findings are left to you.

(mdl012)=
### MDL012: network or language-model call outside `modelly.llm`

A reply from a web service or a language model differs from one call to the next, and the
service may change or disappear. Inside a model or an agent, a call through `requests`, `httpx`,
`urllib.request.urlopen`, or the `openai` and `anthropic` SDKs (including a client kept in an
attribute: `....chat.completions.create`, `....messages.create`) is recorded nowhere, so the run
cannot be replayed, audited or held to a budget. Call through [`modelly.llm`](llm_agents): it
caches every reply under a key of the call, replays offline and stops before a budget is passed.

```python
class Voter(Agent):
    def step(self):
        reply = client.messages.create(model=MODEL, messages=[...])  # MDL012
        self.vote = reply.content[0].text


class Voter(LLMAgent, Agent):
    def step(self):
        self.vote = self.decide(prompt, {"enum": ["yes", "no"]})
```

(mdl013)=
### MDL013: mutable default in a `Scenario`

A `Scenario` subclass's annotated class attributes are its fields' defaults, and every
instance gets the default object itself, not a copy. A list, dict, set, deque or numpy array
default is therefore one object shared by every scenario of the class: the scenario is frozen
against assignment, but `scenario.weights.append(...)` or `scenario.grid[0] = 1` changes the
default for every later run in the process, so a batch's results depend on its order.
`ClassVar` fields and names starting with `_` are not scenario fields and are not reported.

```python
class Params(Scenario):
    weights: list = [0.2, 0.8]  # MDL013
    grid: np.ndarray = np.zeros(10)  # MDL013


class Params(Scenario):
    weights: tuple = (0.2, 0.8)
    grid_size: int = 10  # build np.zeros(scenario.grid_size) in the model
```

There is no automatic fix: a tuple is not a list, and whether the code relies on the
difference needs a reader.

(mdl014)=
### MDL014: wall clock or OS entropy in a calibration target

A calibration compares the model's outputs to data through each `Target`'s `output` and
`summary`. When one of them reads the clock (`time.time()`, `datetime.now()`), a timer
(`time.perf_counter()`, `time.monotonic()`, `time.process_time()`) or OS entropy
(`uuid.uuid4()`, `os.urandom()`, `secrets`), the distance, and so the posterior, depends on the
machine and the moment instead of the seed, and the calibration does not reproduce. The rule
looks at every argument of `modelly.calibrate.Target(...)`, lambdas included, and into the
module-level functions passed to it by name.

```python
def runtime(model):
    return time.perf_counter()  # MDL014: the target measures the machine


Target("speed", observed=[1.0], output=runtime)
Target("infected", observed=cases, output=lambda m: m.infected)
```

There is no automatic fix: what the target should measure instead is the modeller's call.

## Warnings

(mdl101)=
### MDL101: an agent scans the whole population

A loop, comprehension, `select`, `agg`, `groupby`, `sort` or `map` over `self.model.agents`
(or `agents_by_type[...]`) inside an agent method visits every agent once per agent: N² visits
per step. Look at neighbours through the space instead (`self.cell.neighborhood`, a
continuous-space query), or write the phase once at the model level over columns; see
[vectorised step phases](vectorised_phases).

```python
near = [a for a in self.model.agents if a.cell in self.cell.neighborhood]  # MDL101
near = self.cell.neighborhood.agents
```

(mdl102)=
### MDL102: nested loops over the population

Two nested loops over the population compare every pair of agents, N² per step, even when only
neighbours can interact. Pair agents through the space (cells, `pairs_within`) or group them
first with `agents.groupby`.

```python
for a in self.agents:
    for b in self.agents:  # MDL102
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
for agent in self.agents:  # MDL103
    agent.step()
self.agents.shuffle_do("step")
```

(mdl104)=
### MDL104: `deepcopy` inside `step`

`deepcopy` walks the whole object graph, which for an agent includes the model, the space and
every other agent. Done every step, it costs more than the step itself. Copy the fields you
need, or keep the previous value in a column.

```python
self.previous = copy.deepcopy(self)  # MDL104
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
    self.log = pd.concat([self.log, pd.DataFrame([row])])  # MDL106
    self.rows.append(row)  # pd.DataFrame(self.rows) at the end
```

(mdl107)=
### MDL107: per-agent loop that only writes `Column` attributes

In a model method, a loop over the population whose body only assigns attributes declared as
`Column` (plain `=`/`+=`, or an `if` made of those, with no calls) is a whole-column update
written one agent at a time. The columns are those declared in the same module and those of the
agent classes it imports from another file of the linted tree (`from .agents import Sheep`, or
`from pkg.agents import Sheep` under a path given to the linter); that file is parsed once per
run, never imported. The column's numpy array does it in C. Loops
that call anything (a draw, a method) are not reported: vectorising them changes the order of
draws or needs a decision.

```python
class Sheep(Agent):
    energy = Column(float, default=5.0)


class Pasture(Model):
    def step(self):
        for sheep in self.agents_by_type[Sheep]:  # MDL107
            sheep.energy -= 1
        table = self.columns[Sheep]
        table.energy -= 1  # one numpy operation
```

(fixing-findings)=
## Fixing findings

Five rules have a fix that is safe to apply without reading the code around it.
`--diff` shows what it would change; `--fix` writes it and then reports the findings that
are left for you.

```bash
python -m modelly.lint --diff my_model/   # review
python -m modelly.lint --fix my_model/    # apply
```

| Rule | Before | After |
|---|---|---|
| MDL001 | `random.choice(xs)` in an agent or model method | `self.random.choice(xs)` |
| MDL001 | `np.random.normal(0, 1)` in an agent or model method | `self.rng.normal(0, 1)` |
| MDL002 | an agent `__init__(self, model, ...)` without the call | `super().__init__(model)` inserted first |
| MDL002 | a model `__init__(self, scenario=...)` without the call | `super().__init__(scenario=scenario)` inserted first |
| MDL003 | `for x in set(names):` | `for x in sorted(set(names)):` |
| MDL003 | `for a in set(self.cell.agents):` | `sorted(..., key=lambda a: a.unique_id)`: agents do not compare |
| MDL009 | `self.model.agents.discard(self)` | `self.remove()` |
| MDL009 | `self.agents_by_type[Sheep].clear()` | `self.agents_by_type[Sheep].do("remove")` |
| MDL011 | `qmc.Sobol(2)` in an agent or model method | `qmc.Sobol(2, rng=self.rng)` |
| MDL011 | `dist.rvs(5)` in an agent or model method | `dist.rvs(5, random_state=self.rng)` |

Only the expression the finding points at is rewritten: formatting, comments and line endings
around it are kept. A finding is left alone when the right rewrite is a guess: a draw outside a
method (there is no `self`), a numpy function whose `Generator` method takes other arguments
(`randint`, `rand`), a base class whose `__init__` signature is unknown, a model `__init__`
that takes both `rng` and `scenario`, `agents.add(...)` (an agent registers itself when it is
created), or a sampler outside a method or from SALib. Every fix removes its own finding, so a
second `--fix` changes nothing. A finding silenced by `# noqa`, or dropped by `select`,
`ignore` or `per-file-ignores`, is not fixed.

An imported name keeps its import (`from random import choice` stays when `choice(xs)` becomes
`self.random.choice(xs)`); remove it with your formatter or `ruff check --fix`.

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

## Before each commit

Modelly ships two [pre-commit](https://pre-commit.com) hooks. Add one to your project's
`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/RemiPelloux/Modelly
    rev: v1.4.2
    hooks:
      - id: modelly-lint          # fail the commit when a staged file has a finding
      # - id: modelly-lint-fix    # or apply the safe fixes first, then report the rest
```

Both run `modelly lint` once with every staged Python file and read `[tool.modelly.lint]`
from your `pyproject.toml`, so a commit is checked by the same rules as the command line.
`pre-commit run --all-files` checks the whole project.

## In an editor

`modelly lint --lsp` (or `python -m modelly.lint --lsp`) runs the linter as a language
server on stdin and stdout. The editor sends each Python file as you open, edit and save it;
the server answers with the findings as diagnostics (errors and warnings, each linking to its
section of this page), and offers two quick fixes on a finding: the safe fix of `--fix` when
the rule has one, and a `# noqa: CODE` comment for the line. `[tool.modelly.lint]` of the
file's nearest `pyproject.toml` applies; a file that does not parse has no diagnostics until it
does. Nothing beyond the standard library is needed.

Neovim (0.11 or later), in `init.lua`:

```lua
vim.lsp.config("modelly", {
  cmd = { "modelly", "lint", "--lsp" },
  filetypes = { "python" },
  root_markers = { "pyproject.toml", ".git" },
})
vim.lsp.enable("modelly")
```

Helix, in `languages.toml`:

```toml
[language-server.modelly]
command = "modelly"
args = ["lint", "--lsp"]

[[language]]
name = "python"
language-servers = ["pyright", "modelly"]  # keep your usual server first
```

VS Code has no built-in client for an arbitrary server: install a generic LSP client
extension and set its command to `modelly lint --lsp` for Python files. PyCharm does the same
through the LSP4IJ plugin (Settings, Languages & Frameworks, Language Servers, a new server with
the command `modelly lint --lsp` and the `python` language). Use the `modelly` of the
environment your model runs in, so the server lints with the same Modelly version.

The server is tested by driving it over pipes (`tests/test_lint_lsp.py`) and was checked by
hand in Neovim 0.12; the VS Code, Helix and PyCharm settings above are not tested automatically.

## In a notebook

```text
%load_ext modelly.ipython
%modelly lint model.py agents.py
%modelly lint --diff model.py
```

`%modelly lint` takes the options of the command line and prints the same report. A project
made with [`modelly new`](new_project.md) has its `[tool.modelly.lint]` settings and passes every
rule from the start.
