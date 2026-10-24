# Contributing to Modelly

Thanks for taking the time to contribute. This page covers everything you need to get a change
from your machine into a merged pull request.

By taking part in this project you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Ways to help

- **Report a bug** — open an issue with a minimal reproduction: the smallest model that shows the
  problem, plus the exact command you ran and the traceback.
- **Request a feature** — open an issue describing the model or workflow you are trying to build and
  where Modelly gets in the way. "What I tried" beats "what I want".
- **Improve the docs** — tutorials, docstrings and examples are all fair game.
- **Send a model** — if you built something interesting with Modelly, an example under
  `modelly/examples/` is a great first pull request.

Please open an issue before writing a large pull request. It saves you from reworking an
implementation that does not fit the roadmap.

## Development setup

Modelly supports **Python 3.12+**.

```bash
git clone https://github.com/RemiPelloux/Modelly.git
cd Modelly

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # runtime deps + test and lint tooling
playwright install chromium-headless-shell   # required by the visualization tests
bash scripts/build-native.sh       # rebuild modelly/_native in place after editing a .c file
```

`modelly/_native` holds two C modules: `fastrng.c` (`FastRandom`) and `fastloop.c` (agent-set
`do` / `shuffle_do` and the neighbourhood walk). Each has a pure-Python twin with identical
results, used when the module is not built. `pip install -e` compiles them in place when a C
compiler is available; after editing a `.c` file, rebuild with `bash scripts/build-native.sh`
(set `PYTHON=` to pick an interpreter). The built `.so` files are gitignored.
`MODELLY_PURE_PYTHON=1` forces the Python twins at run time, which is how CI tests them.

Extras:

| Extra | Adds |
|---|---|
| `.[viz]` | solara, matplotlib, altair — needed to run the browser UI |
| `.[network]` | networkx |
| `.[examples]` | everything needed to run the bundled example models |
| `.[docs]` | sphinx, myst-nb, pydata theme, seaborn |

## Engineering guidelines

Modelly follows the [Pelloux guidelines](pelloux-guidelines.md): small files (300 lines, hard
error above 400), short functions (25 lines), surgical changes, no debug leftovers, conventional
commits without attribution trailers. Read it once before your first pull request; §11 holds
the Python rules for code under `modelly/` (layout and imports, public API, hot paths,
determinism, native code, measuring performance).

The whole gate runs locally and is what CI runs. It has two front ends with the same stages
(lint, format, test, audit), the same skips when the optional `solara` extra is missing, and the
same coverage badge refresh:

```bash
# Linux and macOS (bash)
bash scripts/ci-local.sh                 # lint, format, tests, size audit
bash scripts/ci-local.sh --list          # stage names
bash scripts/ci-local.sh lint test       # a subset while iterating
bash scripts/audit-pelloux.sh            # size audit alone
```

```powershell
# Any operating system, Windows included: no bash or WSL needed
python -m modelly.dev gate               # lint, format, tests, size audit
python -m modelly.dev gate --list        # stage names
python -m modelly.dev gate lint test     # a subset while iterating
python scripts/pelloux_audit.py audit    # size audit alone
```

`python -m modelly.dev gate` runs every stage with the interpreter that starts it (`python -m
ruff`, `python -m pytest`), so run it from the environment where you installed `.[dev]`.

### No commit makes Modelly slower

A pre-commit hook refuses a commit that makes a core operation slower than the last release.
Turn it on once per clone:

```bash
python -m modelly.dev install-hooks      # git runs .githooks/pre-commit before every commit
python -m modelly.dev perf               # the same check by hand
python -m modelly.dev perf --against 1.2.0
```

When the staged changes touch Modelly's code (`.py`, `.c` or `.h` under `modelly/`), the hook
times 17 core operations (`benchmarks/micro/ops.py`: agent sets, Column reads and writes,
agent removal, cell moves, neighbourhood walks, data collection, events, random draws) in two
interpreters: the last release, built from its tag in this repository with your compiler, and
your working tree. Commits that only touch docs, tests or benchmarks are not timed. The two
run on one core, in alternating bursts; an operation is refused when its median is more than
3% slower and even its fastest quarter is slower, and a first-session suspect is timed again
in fresh processes before anything is refused, so one noisy run cannot block a commit. A run
takes about ten seconds; the first one after a release also builds that release (a few
minutes, cached in `.modelly-bench/`). Smaller differences are caught before each release by
the full benchmark (`docs/performance.md`, "No regression from release to release").

`git commit --no-verify` (or `MODELLY_SKIP_PERF=1`) skips the hook: say why in the commit
message.

Files that were already over the size limit are listed in `pelloux-baseline.json`; they may
shrink but never grow. Only re-seed the baseline (`bash scripts/seed-pelloux-baseline.sh`) when a
split or removal legitimately changes a recorded ceiling, and say so in the pull request.

## Tests

Run the suite from the repository root. Tests mirror the package layout:
`tests/<domain>/test_<module>.py`, with one folder per package (`tests/core`, `tests/space`,
`tests/time`, `tests/data`, `tests/behaviour`, `tests/scenarios`, `tests/batch`, `tests/viz`),
`tests/native` for the compiled loops against their Python twins, and `tests/examples` for the
bundled models.

```bash
pytest tests/                                             # everything
pytest tests/core/test_model.py tests/core/test_agent.py  # one or two modules while iterating
pytest tests/space                                        # one domain
pytest tests/ -Werror                                     # what CI runs (warnings are errors)
MODELLY_PURE_PYTHON=1 pytest tests/                       # the same suite on the pure-Python twins
```

Guidelines:

- Every behaviour change needs a test that fails before your change and passes after it.
- Keep tests deterministic — model seeds are part of the public API, so seed your test models
  explicitly instead of relying on the default.
- Visualization changes need a test that drives the actual component, not just the data path.

## Lint and format

Linting and formatting are pinned in `.pre-commit-config.yaml` (ruff `0.16.10`). The simplest way to
match CI is pre-commit itself:

```bash
pip install pre-commit
pre-commit run --all-files
```

Or run the tools directly, with the pinned version:

```bash
pip install "ruff==0.16.10"
ruff check --fix .
ruff format .
```

A pull request should leave both of these clean:

```bash
ruff check .
ruff format --check .
```

## Documentation

Docs live in `docs/` and are built with Sphinx + MyST. Tutorials are Jupyter notebooks in
`docs/tutorials/` and are executed during the docs build, so they must run top to bottom.

```bash
pip install -e ".[docs]"
cd docs && make html      # output in docs/_build/html
```

If you document a function, document the parameters and the return value, and add a short example
that someone can paste into a notebook.

## Examples and visualization

Each example lives in its own folder with `model.py`, `agents.py` and an `app.py` entry point:

```bash
solara run modelly/examples/basic/boltzmann_wealth_model/app.py
```

Keep new examples small, self-contained and reproducible from a scenario object — they double as
documentation and as the benchmark inputs.

## Repository layout

One package per domain (pelloux-guidelines.md §11.1). Each domain package's `__init__.py`
re-exports its public names in `__all__`; inside `modelly/`, import from the defining module.

```text
modelly/                      # the package
├── __init__.py               # top-level names: Agent, Model, DataCollector, Column, CohortTable, ...
├── py.typed                  # annotations are part of the API
├── core/                     # agents, the model, agent sets, columns, the random source
│   ├── agent.py              #   Agent, create_agents, from_dataframe
│   ├── model.py              #   Model: state, seed, time, events
│   ├── registry.py           #   model.agents and model.agents_by_type
│   ├── columns.py            #   Column: attributes in model-owned numpy arrays
│   ├── column_access.py      #   fast per-agent access to Column attributes
│   ├── rng.py                #   FastRandom
│   ├── exceptions.py         #   the exception hierarchy
│   └── agentset/             #   AgentSet (weak views), the strong registry, select, get/set/agg, groupby
├── space/                    # discrete and continuous space
│   ├── base.py               #   DiscreteSpace
│   ├── cells/                #   Cell, neighbourhoods, CellCollection, cell agents, CellIndex, occupancy
│   ├── grid/                 #   orthogonal and hex grids, the empty-cell index, property layers
│   ├── network.py            #   Network
│   ├── voronoi.py            #   VoronoiGrid (on delaunay.py)
│   └── continuous/           #   ContinuousSpace, its agents and neighbour queries
├── time/                     # Schedule (schedule.py), events/ (Event, EventList, EventGenerator), signals/
├── data/                     # DataCollector (collector.py), reporters, tables, frames, recorders/
├── behaviour/                # actions/, states/ (ContinuousState, Threshold), meta_agents/
├── scenarios/                # Scenario, sampling, run_scenarios, result stores
├── batch/                    # run_batch and run_grid (runs.py), CohortTable (cohorts.py)
├── viz/                      # solara/, render/, mpl/, altair/, console/
├── _native/                  # fastrng.c, fastloop.c and loops.py (the Python twins and dispatch)
├── lint/                     # python -m modelly.lint
├── migrate.py                # python -m modelly.migrate: Mesa to Modelly codemod
├── log.py                    # module loggers and method tracing
└── examples/                 # basic/, advanced/, behaviour/: the bundled models
docs/                         # notebooks, guides, API docs, performance audit
example.py                    # the 30-second model from the README, runnable
CHANGELOG.md                  # release notes
benchmarks/                   # timing harnesses for the example models
scripts/                      # local CI gate, the Pelloux audit, build-native.sh
tests/                        # mirrors modelly/: core, space, time, data, behaviour, scenarios, batch, viz, native, examples
tools/branding/               # generator for the animated SVGs in the README
```

## Brand assets

The animated banner, architecture diagram and loop diagram in `docs/images/branding/` are
hand-rolled SVG (CSS keyframes and SMIL, no JavaScript, no external fonts), so they render inside
GitHub's image sandbox and respect `prefers-reduced-motion`. Each ships in a light and a dark
variant, switched by `prefers-color-scheme`. They are generated, not hand-edited:

```bash
python tools/branding/generate_assets.py
```

Edit `tools/branding/generate_assets.py` and commit both the generator and the regenerated SVGs.
`docs/images/branding/social-preview.png` is the 1280x640 image for GitHub's social preview
(repository Settings, "Social preview"); regenerate it with `python tools/branding/social_preview.py`.

## Pull requests

1. Fork the repository and branch from `main` (`fix/event-priority`, `feat/scenario-inheritance`).
2. Keep the change focused. Unrelated refactoring belongs in its own pull request.
3. Add or update tests and docs in the same pull request as the code.
4. Give the pull request a conventional title, `type(scope): subject`, for example
   `fix(time): event priority inversion in EventList`. Pull requests are squash-merged and the
   title becomes the commit subject on `main`, so it is the line that ends up in the history and
   the changelog. Use the description to explain *why*, not *what* — the diff already shows what.
5. Fill in the [pull request template](.github/pull_request_template.md) and link the issue it
   closes (`Closes #123`).
6. Make sure `bash scripts/ci-local.sh` (or `python -m modelly.dev gate`, on any operating
   system) passes locally before asking for review. It runs the same lint, format, test and
   size-audit stages as CI.

`main` only moves through pull requests: it cannot be force-pushed or deleted, history stays
linear, and the branch is deleted automatically after the merge.

Reviewers may ask for a smaller diff, a test, or a docstring. That is normal — it means the change is
worth getting right.

## Release notes

User-facing changes are described in the pull request body; they are collected into release notes at
release time. Internal refactors without behaviour changes do not need an entry.

## Questions

Open a [discussion](https://github.com/RemiPelloux/Modelly/discussions) or an issue. If you are
unsure whether something is a bug, ask — a question costs far less than a rejected pull request.
