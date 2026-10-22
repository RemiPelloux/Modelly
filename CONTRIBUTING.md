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

## Brand assets

The animated SVGs in `docs/images/branding/` are generated, not hand-edited:

```bash
python tools/branding/generate_assets.py
```

Edit `tools/branding/generate_assets.py` and commit both the generator and the regenerated SVGs.

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
