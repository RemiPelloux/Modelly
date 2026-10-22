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
```

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
commits without attribution trailers. Read it once before your first pull request.

The whole gate runs locally and is what CI runs:

```bash
bash scripts/ci-local.sh                 # lint, format, tests, size audit
bash scripts/ci-local.sh --list          # stage names
bash scripts/ci-local.sh lint test       # a subset while iterating
bash scripts/audit-pelloux.sh            # size audit alone
```

Files that were already over the size limit are listed in `pelloux-baseline.json`; they may
shrink but never grow. Only re-seed the baseline (`bash scripts/seed-pelloux-baseline.sh`) when a
split or removal legitimately changes a recorded ceiling, and say so in the pull request.

## Tests

Run the suite from the repository root:

```bash
pytest tests/                                    # everything
pytest tests/test_model.py tests/test_agent.py   # one or two modules while iterating
pytest tests/ -Werror                            # what CI runs (warnings are errors)
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

```text
modelly/                      # the package
├── agent.py                  # Agent, create_agents, from_dataframe
├── columns.py                # Column: agent attributes stored in model-owned numpy arrays
├── migrate.py                # python -m modelly.migrate: Mesa to Modelly codemod
├── py.typed                  # annotations are part of the API
├── agentset/                 # ordered agent sets
│   ├── abstract.py           #   the shared interface and algorithms
│   ├── selection.py          #   select, select_random
│   ├── weak.py               #   AgentSet: weak-reference views
│   ├── strong.py             #   the model's strong-reference registry
│   └── groupby.py            #   GroupBy
├── model.py                  # Model: state, seed, time, events
├── datacollection.py         # DataCollector: reporters -> pandas
├── reporters.py              # reporter normalisation and fast row collection
├── log.py                    # module loggers and method tracing
├── discrete_space/           # cells, grids, networks, Voronoi
│   ├── cell.py               #   Cell with a per-cell neighbourhood cache
│   ├── base_grid.py          #   Grid: cell creation, empty-cell index, pickling
│   ├── grid.py               #   Moore, Von Neumann and hex grids
│   └── property_layer.py     #   numpy layers exposed on cells
├── time/                     # events, generators, schedules
├── experimental/             # scenarios, continuous space, signals, data records, actions, states
├── examples/                 # the models in the table above
└── visualization/            # Solara components, matplotlib, altair
docs/                         # notebooks, guides, API docs, performance audit
example.py                    # the 30-second model above, runnable
CHANGELOG.md                  # release notes
benchmarks/                   # timing harnesses for the example models
scripts/                      # local CI gate and the Pelloux audit
tests/                        # the test suite
tools/branding/               # generator for the animated SVGs on this page
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
4. Write commit messages in the imperative mood: `Fix event priority inversion in EventList`. Use
   the body to explain *why*, not *what* — the diff already shows what.
5. Fill in the [pull request template](.github/pull_request_template.md) and link the issue it
   closes (`Closes #123`).
6. Make sure `pytest tests/`, `ruff check .` and `ruff format --check .` pass locally before asking
   for review.

Reviewers may ask for a smaller diff, a test, or a docstring. That is normal — it means the change is
worth getting right.

## Release notes

User-facing changes are described in the pull request body; they are collected into release notes at
release time. Internal refactors without behaviour changes do not need an entry.

## Questions

Open a [discussion](https://github.com/RemiPelloux/Modelly/discussions) or an issue. If you are
unsure whether something is a bug, ask — a question costs far less than a rejected pull request.
