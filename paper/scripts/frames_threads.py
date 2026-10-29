"""mesa-frames with polars on one thread and on all of them: wall-clock seconds of a run.

    python paper/scripts/frames_threads.py --rounds 5                 # data/frames_threads.json
    python paper/scripts/frames_threads.py --rounds 5 --cores 0-3     # pinned, 1 vs 4 threads

The playbook timings give polars one thread (every implementation is timed on one core). This
measures what its thread pool buys: each round runs every mesa-frames playbook, unpinned, once
with ``POLARS_MAX_THREADS=1`` and once with polars' default, alternating, and records the
wall-clock seconds of build and steps, the only fair clock for a multi-threaded run.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
HARNESS = ROOT / "benchmarks" / "playbooks"
sys.path.insert(0, str(HARNESS))

from environment import environment  # noqa: E402

PYTHON = ROOT / ".venv-frames" / "bin" / "python"
PLAYBOOKS = ("grid_epidemic", "schelling", "boltzmann_wealth", "sugarscape")
RESULT = "RESULT "


def cpus(spec: str) -> list[int]:
    """The CPUs of a taskset list such as ``0-3`` or ``0,2``."""
    found = []
    for part in spec.split(","):
        low, _, high = part.partition("-")
        found += range(int(low), int(high or low) + 1)
    return found


def wall(name: str, seed: int, threads: str | None, cores: str | None) -> float:
    """Wall-clock seconds of one large run of the mesa-frames variant, pinned to ``cores``."""
    env = {k: v for k, v in os.environ.items() if k != "POLARS_MAX_THREADS"}
    if threads:
        env["POLARS_MAX_THREADS"] = threads
    command = [
        str(PYTHON),
        str(HARNESS / "worker.py"),
        name,
        "frames",
        str(seed),
        "large",
    ]
    if cores:
        command = ["taskset", "-c", cores, *command]
    out = subprocess.run(command, capture_output=True, text=True, env=env, check=True)
    line = next(x for x in out.stdout.splitlines() if x.startswith(RESULT))
    return json.loads(line.removeprefix(RESULT))["wall_seconds"]


def main() -> None:
    """Time each playbook both ways and write data/frames_threads.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument(
        "--cores", default=None, help="taskset CPU list; all its threads"
    )
    options = parser.parse_args()
    many = str(len(cpus(options.cores))) if options.cores else None
    out = {"environment": environment(ROOT, {"frames": str(PYTHON)}, None)}
    out["cores"], out["threads"] = options.cores, many or "polars default"
    for name in PLAYBOOKS:
        times = {"one": [], "all": []}
        for seed in range(options.rounds):
            order = ("one", "all") if seed % 2 == 0 else ("all", "one")
            for arm in order:
                threads = "1" if arm == "one" else many
                times[arm].append(wall(name, seed, threads, options.cores))
        out[name] = {arm: statistics.median(t) for arm, t in times.items()}
        print(name, json.dumps(out[name]), flush=True)
    name = "frames_threads_pinned.json" if options.cores else "frames_threads.json"
    (PAPER / "data" / name).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
