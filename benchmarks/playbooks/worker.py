"""Run one playbook variant in this interpreter and print its result as JSON.

    python benchmarks/playbooks/worker.py <playbook> <variant> <seed> <size>

Started by compare.py inside the framework's own virtual environment. Reports
the CPU time of building the model and of running it, the final population and
the model's summary statistics on one ``RESULT {...}`` line.
"""

from __future__ import annotations

import gc
import importlib
import json
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from registry import PLAYBOOKS  # noqa: E402


def main(argv: list[str]) -> int:
    """Run the requested variant once and print the RESULT line."""
    playbook, variant, seed, size = argv[0], argv[1], int(argv[2]), argv[3]
    spec = PLAYBOOKS[playbook]
    module = importlib.import_module(f"{playbook}.{spec['variants'][variant]}")
    params = {**spec["params"], **spec["sizes"][size]}
    warnings.simplefilter("ignore")
    gc.collect()
    cpu0, wall0 = time.process_time(), time.perf_counter()
    model = module.build(seed=seed, **params)
    cpu1 = time.process_time()
    result = module.simulate(model, spec["steps"])
    cpu2, wall = time.process_time(), time.perf_counter() - wall0
    row = {
        "playbook": playbook,
        "variant": variant,
        "seed": seed,
        "size": size,
        "steps": spec["steps"],
        "build_seconds": round(cpu1 - cpu0, 4),
        "run_seconds": round(cpu2 - cpu1, 4),
        "cpu_seconds": round(cpu2 - cpu0, 4),
        "wall_seconds": round(wall, 4),
        **result,
    }
    sys.stdout.write("RESULT " + json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
