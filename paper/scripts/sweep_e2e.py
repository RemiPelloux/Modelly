"""A sweep end to end: from an Experiment to its persisted results, with either engine.

    python paper/scripts/sweep_e2e.py --core 2            # data/sweep_e2e.json, tables/sweep_e2e.tex

The step-time speed-ups of Section 5 measure the simulation. A study runs sweeps, and a
sweep of short runs spends time on other things too: starting workers, importing the
model, building it, reading its outputs after every step, writing them to the store.
This script times one small sweep end to end, on the grid epidemic at the small size (60
steps): a 16-point Latin hypercube over ``beta`` with 4 replicates, 64 runs, from the
creation of the ``Experiment`` to the moment its results can be queried from the Parquet
store, driven by Modelly's experiment layer with each of two simulation engines:

columns     the playbook's Modelly column implementation
Mesa 3.5    the playbook's Mesa 3.5 implementation, run by the same Experiment (it takes
            its parameters by name and steps like any model), so that the workflow's
            overhead is the same on both sides and only the engine differs

on the serial executor pinned to one core (wall-clock and CPU time), and on the process
executor with 4 workers (wall-clock, unpinned). Alongside, the simulation alone: the
median build-plus-steps CPU time of 64 in-process runs of each engine at the same size,
so that the share of the sweep that is simulation can be read off. Each configuration is
timed in a fresh interpreter, ``rounds`` times, the engines alternating.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))

from environment import environment  # noqa: E402

PYTHON = ROOT / ".venv" / "bin" / "python"
DATA = PAPER / "data" / "sweep_e2e.json"
POINTS, REPLICATES, STEPS = 16, 4, 60
ENGINES = {
    "columns": ("modelly_model", "ColumnsSweep"),
    "Mesa 3.5": ("mesa3_model", "Mesa3Sweep"),
}
ONE_SWEEP = """
import json, shutil, sys, tempfile, time, warnings
warnings.simplefilter("ignore")
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[8])
module_name, executor, workers, points, replicates, steps = sys.argv[2:8]
import importlib
module = importlib.import_module("grid_epidemic." + module_name)
import sweep_models
Sweep = getattr(sweep_models, sys.argv[9])
from registry import PLAYBOOKS
params = {**PLAYBOOKS["grid_epidemic"]["params"], **PLAYBOOKS["grid_epidemic"]["sizes"]["small"]}
from modelly.experiments import Experiment, ScenarioSpace, designs

def simulation_only(n):
    times = []
    for seed in range(n):
        t0 = time.process_time()
        model = module.build(seed=seed, **params)
        module.simulate(model, int(steps))
        times.append(time.process_time() - t0)
    return times

if __name__ == "__main__":
    store = tempfile.mkdtemp(prefix="sweep_e2e_")
    space = ScenarioSpace(beta=(0.1, 0.4), **{k: v for k, v in params.items() if k != "beta"})
    wall0, cpu0 = time.perf_counter(), time.process_time()
    experiment = Experiment(
        model=Sweep, space=space, design=designs.latin_hypercube(int(points)),
        replicates=int(replicates), steps=int(steps), outputs=["infected"],
        store=store, seed=42,
    )
    experiment.run(executor=executor, max_parallel=int(workers))
    rows = experiment.results().query("SELECT count(*) AS n FROM runs").df()["n"].iloc[0]
    wall, cpu = time.perf_counter() - wall0, time.process_time() - cpu0
    shutil.rmtree(store, ignore_errors=True)
    sim = simulation_only(int(points) * int(replicates)) if executor == "serial" else []
    import os
    print(json.dumps({"wall": wall, "cpu": cpu, "rows": int(rows), "load": os.getloadavg()[0],
                      "runs": int(points) * int(replicates), "simulation": sim}))
"""


def once(engine: str, executor: str, workers: int, core: int | None) -> dict:
    """One sweep in a fresh interpreter."""
    command = [
        str(PYTHON), "-c", ONE_SWEEP, str(ROOT / "benchmarks" / "playbooks"),
        ENGINES[engine][0], executor, str(workers), str(POINTS), str(REPLICATES), str(STEPS),
        str(PAPER / "scripts"), ENGINES[engine][1],
    ]  # fmt: skip
    if core is not None and executor == "serial":
        command = ["taskset", "-c", str(core), *command]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def measure(rounds: int, core: int | None, workers: int) -> dict:
    """Every (engine, executor) ``rounds`` times, the engines alternating."""
    results: dict = {}
    for r in range(rounds):
        engines = list(ENGINES)
        if r % 2:
            engines.reverse()
        for executor, n in (("serial", 1), ("processes", workers)):
            for engine in engines:
                row = once(engine, executor, n, core)
                slot = results.setdefault(engine, {}).setdefault(
                    executor, {"wall": [], "cpu": [], "simulation": []}
                )
                slot["wall"].append(row["wall"])
                slot["cpu"].append(row["cpu"])
                slot.setdefault("load", []).append(row["load"])
                if row["simulation"]:
                    slot["simulation"].append(statistics.median(row["simulation"]))
                assert row["rows"] == row["runs"] * (STEPS + 1), row
                sys.stdout.write(
                    f"  {engine:9s} {executor:10s} round {r + 1}: wall {row['wall']:.2f} s, "
                    f"cpu {row['cpu']:.2f} s, load {row['load']:.1f}"
                    + (
                        f", simulation {statistics.median(row['simulation']):.3f} s/run"
                        if row["simulation"]
                        else ""
                    )
                    + "\n"
                )
                sys.stdout.flush()
    return results


def table(payload: dict) -> str:
    """The sweep's wall time per run against the simulation alone, per engine and executor."""
    runs = POINTS * REPLICATES
    lines = [
        "\\begin{tabular}{llrrrr}",
        "\\toprule",
        "Engine & Executor & Sweep (s) & per run (s) & simulation per run (s) & share / gain \\\\",
        "\\midrule",
    ]
    for engine, executors in payload["results"].items():
        sim = statistics.median(executors["serial"]["simulation"])
        serial = statistics.median(executors["serial"]["wall"])
        for i, (executor, slot) in enumerate(executors.items()):
            wall = statistics.median(slot["wall"])
            if executor == "serial":
                label, last = (
                    "serial, one core",
                    f"{sim * runs / wall * 100:.0f}\\% simulation",
                )
            else:
                label, last = (
                    f"{payload['workers']} processes",
                    f"{serial / wall:.1f}$\\times$ serial",
                )
            lines.append(
                f"{engine if i == 0 else ''} & {label} & {wall:.2f} & {wall / runs:.3f} & "
                f"{sim:.3f} & {last} \\\\"
            )
        lines.append("\\addlinespace")
    lines.pop()
    lines += ["\\bottomrule", "\\end{tabular}"]
    return (
        "\n".join(lines)
        + f"\n% {runs} runs of {STEPS} steps, {payload['rounds']} rounds\n"
    )


def main() -> None:
    """Parse the options; measure or only re-analyse."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="run", choices=["run", "analyse"])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--core", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    options = parser.parse_args()
    if options.command == "run":
        payload = {
            "environment": environment(ROOT, {"modelly": str(PYTHON)}, options.core),
            "rounds": options.rounds,
            "core": options.core,
            "workers": options.workers,
            "points": POINTS,
            "replicates": REPLICATES,
            "steps": STEPS,
            "results": measure(options.rounds, options.core, options.workers),
        }
        DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    (PAPER / "tables" / "sweep_e2e.tex").write_text(table(payload), encoding="utf-8")
    print(table(payload))


if __name__ == "__main__":
    main()
