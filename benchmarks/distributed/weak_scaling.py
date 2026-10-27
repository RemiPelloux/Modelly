"""Weak scaling of a split run: the grid epidemic with a fixed population per worker.

For each worker count K the grid grows with K (each worker owns a block of the
same size and the same number of people), so perfect weak scaling keeps the time
per step constant; the efficiency is ``T(1) / T(K)``.

    python benchmarks/distributed/weak_scaling.py --backend mpi --workers 1 2 4 8 16
    python benchmarks/distributed/weak_scaling.py --backend dask --workers 1 2 4

Next to each split run of K workers, the script times K independent copies of
the single-process model of one block running at the same time (one per MPI
rank, no communication at all) and keeps the slowest: what K processes of this
work cost on this machine, with its shared caches, all-core clock and other
load. ``T_copies(1) / T_copies(K)`` is the machine's own weak scaling, and
``T_copies(K) / T(K)`` the share of it the split run keeps (the protocol's
efficiency).

With ``--backend mpi`` each run is a separate ``mpirun -n K`` of this script in
a rank mode (rank 0 prints the timings as JSON); with ``dask`` and ``local`` the
split run happens in this process (the copies still run under ``mpirun``).
Times are wall-clock seconds per step after one warm-up step, the build
excluded. Each worker builds only its block's people (``owns``) but holds the
whole grid. The results go to ``--out`` as JSON, with the load average before
each run, and a Markdown table is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))  # this checkout's modelly, as for the MPI ranks

from modelly.distributed import Cluster, partition  # noqa: E402
from modelly.examples.distributed.grid_epidemic import (  # noqa: E402
    EpidemicScenario,
    GridEpidemic,
)

# Split of K workers into grid blocks, as square as possible.
LAYOUTS = {
    1: (1, 1),
    2: (2, 1),
    4: (2, 2),
    6: (3, 2),
    8: (4, 2),
    12: (4, 3),
    16: (4, 4),
}
DENSITY = 1.25  # people per cell, as in the grid epidemic playbook
INFECTED_SHARE = 0.01
MPI_TIMEOUT = 3600  # seconds for one mpirun


def scenario_for(workers: int, people: int, seed: int):
    """The scenario of ``workers`` blocks of ``people`` people each, and its split."""
    rows, cols = LAYOUTS[workers]
    side = round((people / DENSITY) ** 0.5)
    total = people * workers
    scenario = EpidemicScenario(
        rng=seed,
        width=rows * side,
        height=cols * side,
        people=total,
        infected=max(1, round(total * INFECTED_SHARE)),
    )
    return scenario, partition.grid_blocks(rows, cols)


def timed_run(cluster, args: argparse.Namespace, workers: int) -> dict:
    """Build on ``cluster``, warm up one step, time ``args.steps`` steps."""
    scenario, split = scenario_for(workers, args.people, args.seed)
    start = time.perf_counter()
    model = cluster.build(GridEpidemic, scenario, split)
    built = time.perf_counter() - start
    model.step()
    start = time.perf_counter()
    model.run_for(args.steps)
    elapsed = time.perf_counter() - start
    return {
        "workers": workers,
        "people": scenario.people,
        "cells": scenario.width * scenario.height,
        "build_seconds": built,
        "step_seconds": elapsed / args.steps,
        "infected_at_end": int(model.collect()["I"].iloc[-1]),
    }


def copy_seconds(args: argparse.Namespace, rank: int) -> float:
    """Seconds per step of one block's model alone, seeded by ``rank``."""
    scenario, _ = scenario_for(1, args.people, args.seed + rank)
    model = GridEpidemic(scenario)
    model.step()
    start = time.perf_counter()
    for _ in range(args.steps):
        model.step()
    return (time.perf_counter() - start) / args.steps


def rank_run(args: argparse.Namespace) -> None:
    """One MPI run: the split model, or (``--copies``) independent copies."""
    from mpi4py import MPI  # noqa: PLC0415 - only under mpirun

    comm, workers = MPI.COMM_WORLD, args.workers[0]
    if args.copies:
        comm.barrier()
        times = comm.gather(copy_seconds(args, comm.Get_rank()))
        if comm.Get_rank() == 0:
            sys.stdout.write(json.dumps({"copy_seconds": times}) + "\n")
        return
    with Cluster(backend="mpi", workers=workers) as cluster:
        result = timed_run(cluster, args, workers)
        if cluster.is_root:
            sys.stdout.write(json.dumps(result) + "\n")


def mpirun(args: argparse.Namespace, workers: int, copies: bool) -> dict:
    """Launch ``mpirun -n workers`` of this script in rank mode; rank 0's line."""
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    command = ["mpirun", "-n", str(workers), "--bind-to", "none", "-x", "PYTHONPATH"]
    command += [sys.executable, __file__, "--rank-run", "--workers", str(workers)]
    command += ["--people", str(args.people), "--steps", str(args.steps)]
    command += ["--seed", str(args.seed)] + (["--copies"] if copies else [])
    done = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=MPI_TIMEOUT,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def measure(args: argparse.Namespace, workers: int) -> dict:
    """The split run of ``workers`` and, right after, as many independent copies."""
    load = os.getloadavg()[0]
    if args.backend == "mpi":
        run = mpirun(args, workers, copies=False)
    else:
        with Cluster(backend=args.backend, workers=workers) as cluster:
            run = timed_run(cluster, args, workers)
    copies = mpirun(args, workers, copies=True)["copy_seconds"]
    return {**run, "copies_step_seconds": max(copies), "copies": copies, "load": load}


def table(results: list[dict]) -> str:
    """The results as a Markdown table."""
    base, base_copies = results[0]["step_seconds"], results[0]["copies_step_seconds"]
    lines = [
        (
            "| workers | people | s/step split | s/step K copies (slowest) "
            "| efficiency T(1)/T(K) | machine T_copies(1)/T_copies(K) | protocol T_copies/T "
            "| load |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        split, copies = r["step_seconds"], r["copies_step_seconds"]
        lines.append(
            f"| {r['workers']} | {r['people']} | {split:.4f} | {copies:.4f} "
            f"| {base / split:.0%} | {base_copies / copies:.0%} | {copies / split:.0%} "
            f"| {r['load']:.1f} |"
        )
    return "\n".join(lines)


def main() -> None:
    """Run the series and write the results."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", default="mpi", choices=["mpi", "dask", "local"])
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--people", type=int, default=10_000, help="per worker")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=HERE / "results" / "weak.json")
    parser.add_argument("--rank-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--copies", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rank_run:
        rank_run(args)
        return
    results = []
    for workers in args.workers:
        results.append(measure(args, workers))
        sys.stdout.write(json.dumps(results[-1]) + "\n")
    report = {
        "backend": args.backend,
        "machine": {"cpus": os.cpu_count(), "platform": platform.platform()},
        "python": platform.python_version(),
        "people_per_worker": args.people,
        "steps": args.steps,
        "runs": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    sys.stdout.write(table(results) + "\n")


if __name__ == "__main__":
    main()
