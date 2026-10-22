"""Time the Mesa reference model that ships alongside this file.

The reference workload is a French fruit-fly (medfly) invasion-control ABM:
strawberry and cherry orchards, sterile-insect-technique release budgets,
female remating behaviour. It is written against the **Mesa 2.3** API
(``Agent(unique_id, model)``, ``Model.next_id()``) and lives in a notebook that
is deliberately *not* committed, so this repository never redistributes it.

The notebook is expected next to this script::

    benchmarks/mesa_baseline/Notebook_ABM_TIS_Mis_A_Jour.ipynb

Nothing here imports Modelly. This is the "before" number: what the same
experiment costs on the framework the port is measured against.

Usage
-----
    python benchmarks/mesa_baseline/run_baseline.py                    # both crops
    python benchmarks/mesa_baseline/run_baseline.py --crop cherry -r 3
    python benchmarks/mesa_baseline/run_baseline.py --factorcrop        # full factorial

Requires a *separate* environment from Modelly, because it pins Mesa 2:

    python -m venv .venv-mesa2
    .venv-mesa2/bin/pip install "mesa==2.3.2" numpy pandas
    .venv-mesa2/bin/python benchmarks/mesa_baseline/run_baseline.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_NOTEBOOK = HERE / "Notebook_ABM_TIS_Mis_A_Jour.ipynb"

# Cells 0-5 of the notebook are pure definitions (imports, crop parameters,
# agents, model, TIS release calendars). Cell 6 onwards is where it actually
# runs the experiments, so we stop before that and drive the model ourselves.
SETUP_CELLS = 6

# The factorial design the notebook runs by default, used for extrapolation.
INVASIONS = (("faible", 3), ("moyenne", 10), ("forte", 30))
BUDGETS = (0, 150, 300, 600)
REMATING_MODES = 2
REPLICATES = 3


def load_definitions(notebook: Path, n_cells: int = SETUP_CELLS) -> dict:
    """Execute the notebook's first ``n_cells`` code cells and return their globals."""
    if not notebook.exists():
        raise SystemExit(
            f"reference notebook not found: {notebook}\n"
            "It is intentionally gitignored; drop it back in this directory "
            "or pass --notebook."
        )

    nb = json.loads(notebook.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    namespace: dict = {"__name__": "__baseline__"}
    for cell in code_cells[:n_cells]:
        exec(  # noqa: S102 - trusted local research notebook
            "".join(cell["source"]),
            namespace,
        )
    return namespace


def time_season(
    namespace: dict,
    crop_name: str,
    *,
    invasion: int,
    budget: int,
    replicate: int,
    seed: int,
) -> float:
    """Run one full season and return its wall-clock duration in seconds."""
    crop = namespace["STRAWBERRY" if crop_name == "strawberry" else "CHERRY"]
    schedule: dict = {}
    if budget:
        calendar = namespace["make_strategies"](budget, crop.season_length)
        schedule = calendar["Every 3 days"]

    model = namespace["RematingModel"](
        crop_parameters=crop,
        sterile_release_schedule=schedule,
        num_agents_wild=invasion,
        num_agents_females=invasion,
        seed=seed + replicate,
    )

    start = time.perf_counter()
    for _ in range(crop.season_length):
        model.step()
    return time.perf_counter() - start


def factorial_runs() -> int:
    """Number of seasons in the notebook's default factorial experiment."""
    per_crop = len(INVASIONS) * len(BUDGETS) * REMATING_MODES * REPLICATES
    return 2 * per_crop


def main() -> None:
    """Run the requested seasons and report wall-clock time."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    parser.add_argument(
        "--crop", choices=("strawberry", "cherry", "both"), default="both"
    )
    parser.add_argument(
        "-r", "--replicates", type=int, default=1, help="seasons per configuration"
    )
    parser.add_argument("--invasion", type=int, default=10, help="wild males = females")
    parser.add_argument(
        "--budget", type=int, default=0, help="sterile males per season"
    )
    parser.add_argument(
        "--factorcrop",
        action="store_true",
        help="measure every cell of the factorial for one crop and extrapolate",
    )
    args = parser.parse_args()

    import mesa  # noqa: PLC0415 - deferred so --help works without Mesa 2

    if not mesa.__version__.startswith("2."):
        raise SystemExit(
            f"this baseline needs Mesa 2.x, found {mesa.__version__}.\n"
            "Use a dedicated environment: pip install 'mesa==2.3.2'"
        )
    print(f"Mesa {mesa.__version__} — reference model, {HERE.name}")

    namespace = load_definitions(args.notebook)
    crops = ("strawberry", "cherry") if args.crop == "both" else (args.crop,)

    if args.factorcrop:
        runs = [(b, inv) for b in BUDGETS for _, inv in INVASIONS]
        total = 0.0
        for crop in crops:
            for budget, invasion in runs:
                elapsed = time_season(
                    namespace,
                    crop,
                    invasion=invasion,
                    budget=budget,
                    replicate=0,
                    seed=42,
                )
                total += elapsed * REMATING_MODES * REPLICATES
                print(
                    f"  {crop:10s} budget={budget:3d} invasion={invasion:2d}"
                    f"  {elapsed:7.2f} s/season"
                )
        print(
            f"\nextrapolated factorial ({factorial_runs()} seasons): {total / 60:.0f} min"
        )
        return

    for crop in crops:
        seasons = []
        for replicate in range(args.replicates):
            elapsed = time_season(
                namespace,
                crop,
                invasion=args.invasion,
                budget=args.budget,
                replicate=replicate,
                seed=42,
            )
            seasons.append(elapsed)
            print(f"  {crop:10s} season {replicate + 1}: {elapsed:7.2f} s")
        mean = statistics.fmean(seasons)
        label = (
            "strawberry (100 steps)" if crop == "strawberry" else "cherry (25 steps)"
        )
        print(f"  {label:24s} mean {mean:7.2f} s")


if __name__ == "__main__":
    main()
