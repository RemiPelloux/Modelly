"""Speed-ups at three population sizes: does the ratio hold away from the timed size?

    python paper/scripts/sizes.py run --rounds 5 --core 2    # data/sizes.json
    python paper/scripts/sizes.py analyse                    # tables/sizes.tex

Three workloads whose populations scale with one parameter (the grid epidemic,
Schelling's model, Boltzmann wealth) at the playbooks' small size, their timed (large)
size and ten times that (huge), each implementation in a fresh interpreter pinned to one
core, the order of the implementations rotating from round to round, as the playbook
runner times them. The speed-up is the ratio of median step times, as in the paper.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER.parent / "benchmarks" / "playbooks"))

import compare  # noqa: E402
from environment import environment  # noqa: E402
from registry import PLAYBOOKS  # noqa: E402

WORKLOADS = ("grid_epidemic", "schelling", "boltzmann_wealth")
SIZES = ("small", "large", "huge")
VARIANTS = ("mesa", "mesa3", "mesa3np", "frames", "modelly")
DATA = PAPER / "data" / "sizes.json"
LABELS = {
    "grid_epidemic": "Grid epidemic",
    "schelling": "Schelling",
    "boltzmann_wealth": "Boltzmann wealth",
}


def variants(name: str) -> list[str]:
    """The implementations of ``name`` that the sweep times."""
    return [v for v in VARIANTS if v in PLAYBOOKS[name]["variants"]]


def time_size(name: str, size: str, rounds: int, core: int | None) -> dict:
    """Step and build seconds of every implementation over ``rounds`` rotated rounds."""
    order = variants(name)
    steps: dict[str, list[float]] = {v: [] for v in order}
    builds: dict[str, list[float]] = {v: [] for v in order}
    population: dict[str, int] = {}
    for r in range(rounds):
        for variant in order[r % len(order) :] + order[: r % len(order)]:
            row = compare.run_once(name, variant, r + 1, size, core)
            steps[variant].append(row["run_seconds"])
            builds[variant].append(row["build_seconds"])
            population[variant] = row["population"]
        print(f"{name} {size} round {r + 1}", flush=True)
    return {"run_seconds": steps, "build_seconds": builds, "population": population}


def run(rounds: int, core: int | None) -> None:
    """Every workload at every size, written to data/sizes.json."""
    start = environment(PAPER.parent, compare.PYTHONS, core)  # the load before timing
    timing = {
        name: {size: time_size(name, size, rounds, core) for size in SIZES}
        for name in WORKLOADS
    }
    payload = {
        "environment": start,
        "load_at_end": os.getloadavg(),
        "rounds": rounds,
        "sizes": {n: {s: PLAYBOOKS[n]["sizes"][s] for s in SIZES} for n in WORKLOADS},
        "timing": timing,
    }
    DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"written to {DATA}")


def ratio(runs: dict, slow: str, fast: str) -> float | None:
    """Median step time of ``slow`` over that of ``fast``, when both ran."""
    if slow not in runs or fast not in runs:
        return None
    return statistics.median(runs[slow]) / statistics.median(runs[fast])


def cell(value: float | None) -> str:
    """A ratio for the table, or a dash."""
    if value is None:
        return "--"
    return f"{value:.0f}" if value >= 100 else f"{value:.1f}"


def table(timing: dict) -> str:
    """One row per workload and size: agents, Mesa steps, and the columns' speed-ups."""
    lines = [
        "\\begin{tabular}{llrrrrrr}",
        "\\toprule",
        (
            " & & & & \\multicolumn{3}{c}{columns faster than} & numpy faster \\\\ "
            "\\cmidrule(lr){5-7} "
            "Workload & Size & Agents & Mesa 2.3, s & Mesa 2.3 & Mesa 3.5 "
            "& mesa-frames & than columns \\\\"
        ),
        "\\midrule",
    ]
    for name in WORKLOADS:
        for size in SIZES:
            t = timing[name][size]
            runs, agents = t["run_seconds"], t["population"]["modelly"]
            lines.append(
                f"{LABELS[name] if size == 'small' else ''} & {size} & {agents:,} & "
                f"{statistics.median(runs['mesa']):.2f} & "
                f"{cell(ratio(runs, 'mesa', 'modelly'))} & "
                f"{cell(ratio(runs, 'mesa3', 'modelly'))} & "
                f"{cell(ratio(runs, 'frames', 'modelly'))} & "
                f"{cell(ratio(runs, 'modelly', 'mesa3np'))} \\\\".replace(",", "{,}")
            )
        lines.append("\\addlinespace")
    return "\n".join([*lines[:-1], "\\bottomrule", "\\end{tabular}", ""])


def analyse() -> None:
    """The table, and every ratio on stdout."""
    timing = json.loads(DATA.read_text(encoding="utf-8"))["timing"]
    (PAPER / "tables" / "sizes.tex").write_text(table(timing), encoding="utf-8")
    for name in WORKLOADS:
        for size in SIZES:
            runs = timing[name][size]["run_seconds"]
            found = {
                f"{slow}/{fast}": round(r, 2)
                for slow, fast in (("mesa", "modelly"), ("mesa3", "modelly"),
                                   ("frames", "modelly"), ("modelly", "mesa3np"))
                if (r := ratio(runs, slow, fast)) is not None
            }  # fmt: skip
            print(name, size, found)


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--core", type=int, default=None)
    options = parser.parse_args()
    if options.command == "run":
        run(options.rounds, options.core)
    analyse()


if __name__ == "__main__":
    main()
