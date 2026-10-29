"""The Mesa 3.5 + KD-tree flocking implementation against Mesa 3.5's own search, run by run.

    python paper/scripts/kdtree_equality.py --small 100 --large 10 --jobs 12   # data/

Both run in fresh interpreters through the playbook runner on the same seeds; the check is
that every seed gives the same summary statistics, so that the KD-tree variant's speed-up
measures the neighbour search alone (paper, Section 9).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER.parent / "benchmarks" / "playbooks"))

import compare  # noqa: E402
from environment import environment  # noqa: E402

DATA = PAPER / "data" / "flocking_kdtree.json"


def same(task: tuple[int, str]) -> bool:
    """Whether one seed gives identical statistics with both implementations."""
    seed, size = task
    a = compare.run_once("flocking", "mesa3", seed, size, None)["stats"]
    b = compare.run_once("flocking", "mesa3kd", seed, size, None)["stats"]
    return a == b


def main() -> None:
    """Compare the two implementations on the requested seeds and write the result."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--small", type=int, default=100)
    parser.add_argument("--large", type=int, default=10)
    parser.add_argument("--jobs", type=int, default=8)
    options = parser.parse_args()
    tasks = [(s, "small") for s in range(1, options.small + 1)]
    tasks += [(s, "large") for s in range(1, options.large + 1)]
    with ThreadPoolExecutor(options.jobs) as pool:
        results = list(pool.map(same, tasks))
    payload = {
        "environment": environment(PAPER.parent, compare.PYTHONS, None),
        "small": {
            "seeds": f"1-{options.small}",
            "identical": sum(results[: options.small]),
        },
        "large": {
            "seeds": f"1-{options.large}",
            "identical": sum(results[options.small :]),
        },
    }
    DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(payload["small"], payload["large"])


if __name__ == "__main__":
    main()
