"""A cohort population of many millions of rows, in memory or memory-mapped on disk.

    python benchmarks/large_columns.py --rows 100000000 --storage memmap --dir /scratch
    python benchmarks/large_columns.py --rows 3000000 --storage memory

Every row is a cohort of a stage-structured population (count, stage, age,
patch, a float trait); each step thins every row by its stage's survival,
ages every row, moves rows past a stage's duration to the next stage and
draws offspring counts. Prints one JSON line: rows, data bytes, seconds per
step, individuals left, the peak resident set of this process and, on Linux,
the peak memory of its control group (what a ``systemd-run -p MemoryMax=``
limit is measured against).
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

from modelly.batch.cohorts import CohortTable
from modelly.core.storage import IN_MEMORY, MemoryMapped

SURVIVAL = np.array([0.9, 0.95, 0.97, 0.8])  # per stage, per step
DURATION = np.array([3, 5, 8, 1000], dtype=np.int16)  # steps spent in each stage
FECUNDITY = 0.6  # offspring per adult per step
PATCHES = 10_000
KIB = 1024


def build(rows: int, storage, seed: int) -> CohortTable:
    """A table of ``rows`` cohorts with random sizes, stages, ages and patches."""
    rng = np.random.default_rng(seed)
    table = CohortTable(
        rng,
        storage=storage,
        stage=np.int8,
        age=np.int16,
        patch=np.int32,
        trait=np.float32,
    )
    chunk = 10_000_000  # rows added per call, to bound the temporary arrays
    for start in range(0, rows, chunk):
        k = min(chunk, rows - start)
        table.add(
            rng.integers(1, 100, k),
            stage=rng.integers(0, 4, k),
            age=rng.integers(0, 3, k),
            patch=rng.integers(0, PATCHES, k),
            trait=rng.random(k, dtype=np.float32),
        )
    return table


def step(table: CohortTable) -> int:
    """One step of the life cycle; returns the offspring drawn."""
    table.thin(SURVIVAL[table["stage"]])
    table["age"] += 1
    stage = table["stage"]
    moving = (table["age"] >= DURATION[stage]) & (stage < len(DURATION) - 1)
    stage[moving] += 1
    table["age"][moving] = 0
    return int(table.draw(FECUNDITY, where=table["stage"] == len(DURATION) - 1).sum())


def cgroup_peak() -> int | None:
    """``memory.peak`` of this process's control group (cgroup v2), in bytes."""
    try:
        lines = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
        group = lines[-1].split(":", 2)[2].lstrip("/")
        return int((Path("/sys/fs/cgroup") / group / "memory.peak").read_text("ascii"))
    except (OSError, ValueError, IndexError):
        return None


def main(argv: list[str]) -> int:
    """Build, run, report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=3_000_000)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--storage", choices=("memory", "memmap"), default="memmap")
    parser.add_argument("--dir", type=Path, default=None, help="where the files go")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    storage = MemoryMapped(args.dir) if args.storage == "memmap" else IN_MEMORY
    start = time.perf_counter()
    table = build(args.rows, storage, args.seed)
    built = time.perf_counter() - start
    seconds, offspring = [], 0
    for _ in range(args.steps):
        t0 = time.perf_counter()
        offspring += step(table)
        seconds.append(round(time.perf_counter() - t0, 2))
    data = sum(column.nbytes for column in table._data.values())
    print(
        json.dumps(
            {
                "rows": len(table),
                "storage": args.storage,
                "data_bytes": data,
                "build_seconds": round(built, 1),
                "step_seconds": seconds,
                "individuals": table.total(),
                "offspring": offspring,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * KIB,
                "cgroup_peak_bytes": cgroup_peak(),
            }
        )
    )
    if isinstance(storage, MemoryMapped):
        storage.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
