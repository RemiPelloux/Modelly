# Starting a project

`modelly new` writes a model project that is seeded, tested and linted from its first commit:
the parameters and their seed in one place, a test that the same seed gives the same data, and
lint settings that catch reproducibility bugs and O(N²) loops as you write them.

```bash
modelly new forest-fire                      # the grid template, in ./forest-fire
modelly new epidemic --template network      # another template
modelly new --list-templates                 # what each template models
python -m modelly new forest-fire            # the same, without the modelly script on PATH
```

The commands are the same on Windows, macOS and Linux. The folder must not exist yet, or be
empty: `modelly new` never overwrites a file, and exits with status 2 without writing anything
when the folder has something in it.

## What you get

```text
forest-fire/
├── pyproject.toml           depends on modelly-abm; [tool.modelly.lint] and pytest settings
├── README.md                how to set up, run, test, lint and profile; an ODD outline
├── .gitignore
├── forest_fire/
│   ├── __init__.py          exports ForestFireModel, ForestFireScenario and SEED
│   ├── scenario.py          the parameters, their defaults, and the default seed
│   ├── agents.py            the agent class
│   └── model.py             the model: builds the world from a scenario, steps it
└── tests/
    └── test_determinism.py  same seed, same data; another seed, another run
```

The project name becomes the package name (`forest-fire` gives `forest_fire`) and the class
names (`ForestFireModel`, `ForestFireScenario`). The project contains no shell scripts: every
command in its README is `python -m ...`, which runs the same everywhere.

| Template | The model | Uses |
|---|---|---|
| `grid` (default) | traders on a torus grid give wealth to cellmates; inequality (Gini) emerges | `OrthogonalMooreGrid`, `CellAgent`, a `Column` |
| `network` | an infection spreads over a random contact network (SIR) | `Network` from `networkx` (the `network` extra), a `Column` per state |
| `continuous` | correlated random walkers in a wrapping space; their alignment is recorded | `ContinuousSpace`, `ContinuousSpaceAgent` |
| `cohort` | colonies whose individuals are counted by age class, not one object each | `CohortTable` with binomial survival and births |
| `geo` | news spreads among residents who walk a town of square districts, in metres | `GeoSpace`, `GeoAgent`, a `Column` (the `geo` extra) |
| `llm` | citizens ask a language model what they now think of a proposal, after talking to a few others | `LLMAgent`, `decide_all`, a `Client` with an offline `FakeProvider` |

The `geo` template builds its districts in code, so it runs offline; `districts()` in
`model.py` is the one function to replace with `geopandas.read_file(...)` for a real town. The
`llm` template asks a local function (`local_responder` in `model.py`) instead of a language
model, so its test runs offline and costs nothing; pass `client=Client(AnthropicProvider(...))`
or another provider to the model to ask a real one (see [Language-model agents](llm_agents.md)
for keys, caching, replay and budgets).

## The seed

`scenario.py` holds every parameter of a run and the default seed:

```python
SEED = 42  # the default seed: pass rng=... for another, reproducible, run


class ForestFireScenario(Scenario):
    n: int = 100
    width: int = 10
    height: int = 10

    def __init__(self, *, rng=None, **kwargs):
        super().__init__(rng=SEED if rng is None else rng, **kwargs)
```

`ForestFireModel()` runs the default scenario with `SEED`, so even the first run reproduces.
`ForestFireModel(ForestFireScenario(rng=7, n=500))` changes the seed and a parameter; every
draw in the model comes from `self.random` and `self.rng`, which the scenario seeds.

## Set up, test, lint, profile

```bash
cd forest-fire
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest                   # the determinism test
python -m modelly lint forest_fire # no findings in a fresh project
python -m modelly profile forest_fire.model:ForestFireModel --steps 50
```

The determinism test runs the model twice from one seed and compares everything its
`DataCollector` recorded; it also checks that another seed gives another run, so a seed that is
accidentally ignored fails the test. Keep it passing as the model grows: it is the cheapest
guard against a draw from the global `random` module or a loop over a set.

`[tool.modelly.lint]` in `pyproject.toml` selects every rule and relaxes the O(N²) warnings in
`tests/`; see [Checking a model](lint.md) for the rules, `--fix` and `# noqa`. The profiler is
described in [Profiling a model](profile.md).

## The README and the ODD protocol

The generated README ends with the outline of the ODD protocol (Overview, Design concepts,
Details), the usual way to describe an agent-based model in a paper: purpose and patterns;
entities, state variables and scales; process overview and scheduling; design concepts;
initialization; input data; submodels. Fill it in as the model takes shape, and it becomes the
model description of the paper.

## Long project names

The templates are formatted for names of ordinary length. With a long project name some lines
of the generated code pass the usual 88 characters; run your formatter once (`ruff format .`)
after creating the project.
