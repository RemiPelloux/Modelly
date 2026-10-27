"""The GPU playbook measurement: column variant on the CPU against ``modelly-gpu``.

    python benchmarks/playbooks/gpu_speedup.py --n 10000000 --side 1000 --rounds 3
    python benchmarks/playbooks/gpu_speedup.py --equality --n 1000000 --side 300

Every run is a fresh interpreter (``--one`` runs one and prints a ``RESULT``
line). The steps are timed by the wall clock, the device synchronised before
each reading, because a GPU's time is not the process's CPU time; the CPU
time is recorded too. Rounds alternate the two variants. ``--equality`` runs
``modelly-gpu`` on numpy and on the GPU backend with the same seed and
compares the infected series and a digest of the final integer columns.

The GPU variant runs in the interpreter of ``MODELLY_GPU_PYTHON`` (default
``.gpu-venv``), the CPU variant in ``MODELLY_PYTHON`` (default ``.venv``); both
import Modelly from this checkout (``PYTHONPATH``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from registry import PLAYBOOKS  # noqa: E402

PLAYBOOK = "grid_epidemic"
CPU_VARIANT, GPU_VARIANT = "modelly", "modelly-gpu"
PYTHONS = {
    CPU_VARIANT: os.environ.get(
        "MODELLY_PYTHON", str(ROOT / ".venv" / "bin" / "python")
    ),
    GPU_VARIANT: os.environ.get(
        "MODELLY_GPU_PYTHON", str(ROOT / ".gpu-venv" / "bin" / "python")
    ),
}
RESULT = "RESULT "
PACKAGES = ("modelly-abm", "numpy", "cupy-cuda13x", "jax", "jax-cuda13-plugin")


def versions() -> dict:
    """The Python version and the installed versions of the packages that matter here."""
    import importlib.metadata as metadata  # noqa: PLC0415
    import platform  # noqa: PLC0415

    found = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return found


def digest(model) -> str:
    """SHA-256 of the final state, days and row columns of every person."""
    table = model.columns[type(next(iter(model.agents)))]
    hasher = hashlib.sha256()
    for name in ("state", "days", "row"):
        hasher.update(table[name].astype("int64").tobytes())
    return hasher.hexdigest()


def one(variant: str, n: int, side: int, steps: int, seed: int) -> dict:
    """Build and run one variant in this process; timings, statistics and digest."""
    import importlib  # noqa: PLC0415

    spec = PLAYBOOKS[PLAYBOOK]
    module = importlib.import_module(f"{PLAYBOOK}.{spec['variants'][variant]}")
    params = {**spec["params"], "n": n, "side": side}
    wall0 = time.perf_counter()
    model = module.build(seed=seed, **params)
    sync = getattr(getattr(model, "stream", None), "backend", None)
    build = time.perf_counter() - wall0
    cpu0, wall1 = time.process_time(), time.perf_counter()
    for _ in range(steps):
        model.step()
    if sync is not None:
        sync.synchronize()
    run, cpu = time.perf_counter() - wall1, time.process_time() - cpu0
    if hasattr(model, "people"):
        model.people.write_to(model.columns[module.Person])
    return {
        "variant": variant,
        "backend": sync.name if sync is not None else "numpy (columns)",
        "device": sync.device if sync is not None else "cpu",
        "n": n,
        "side": side,
        "steps": steps,
        "build_seconds": round(build, 3),
        "run_seconds": round(run, 4),
        "run_cpu_seconds": round(cpu, 4),
        "history": model.infected_history,
        "digest": digest(model),
        "versions": versions(),
    }


def launch(variant: str, args: argparse.Namespace, backend: str | None = None) -> dict:
    """Run ``one`` in a fresh interpreter and parse its RESULT line."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), env.get("PYTHONPATH")])
    )
    if backend is not None:
        env["MODELLY_BACKEND"] = backend
    command = [PYTHONS[variant], __file__, "--one", variant]
    command += ["--n", str(args.n), "--side", str(args.side)]
    command += ["--steps", str(args.steps), "--seed", str(args.seed)]
    done = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    for line in done.stdout.splitlines():
        if line.startswith(RESULT):
            return json.loads(line[len(RESULT) :])
    raise RuntimeError(f"{variant} failed:\n{done.stderr[-3000:]}")


def speedup(args: argparse.Namespace) -> dict:
    """Alternate the two variants for ``rounds`` rounds; the per-round ratios."""
    rounds = []
    warmup = launch(GPU_VARIANT, args, args.backend)  # compiles and caches the kernels
    sys.stderr.write(f"warm-up {GPU_VARIANT}: {warmup['run_seconds']} s\n")
    for index in range(args.rounds):
        order = [CPU_VARIANT, GPU_VARIANT][:: 1 if index % 2 == 0 else -1]
        rows = {
            v: launch(v, args, args.backend if v == GPU_VARIANT else None)
            for v in order
        }
        ratio = rows[CPU_VARIANT]["run_seconds"] / rows[GPU_VARIANT]["run_seconds"]
        rounds.append(
            {v: {k: r[k] for k in r if k != "history"} for v, r in rows.items()}
        )
        rounds[-1]["ratio"] = round(ratio, 2)
        sys.stderr.write(f"round {index + 1}: {ratio:.2f}x\n")
    ratios = [r["ratio"] for r in rounds]
    return {
        "rounds": rounds,
        "median_ratio": statistics.median(ratios),
        "ratios": ratios,
        "warmup_seconds": warmup["run_seconds"],
    }


def equality(args: argparse.Namespace) -> dict:
    """``modelly-gpu`` on numpy and on the GPU backend: same series and same digest."""
    cpu = launch(GPU_VARIANT, args, "numpy")
    gpu = launch(GPU_VARIANT, args, args.backend)
    return {
        "numpy": {k: cpu[k] for k in ("backend", "device", "run_seconds", "digest")},
        args.backend: {
            k: gpu[k] for k in ("backend", "device", "run_seconds", "digest")
        },
        "same_history": cpu["history"] == gpu["history"],
        "same_digest": cpu["digest"] == gpu["digest"],
        "final_infected": gpu["history"][-1],
    }


def main(argv: list[str]) -> int:
    """Parse the options and run one variant, the equality check or the speed-up."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--one", choices=[CPU_VARIANT, GPU_VARIANT])
    parser.add_argument("--equality", action="store_true")
    parser.add_argument("--n", type=int, default=10_000_000)
    parser.add_argument("--side", type=int, default=1000)
    parser.add_argument("--steps", type=int, default=PLAYBOOKS[PLAYBOOK]["steps"])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--backend", default="cupy")
    args = parser.parse_args(argv)
    if args.one:
        row = one(args.one, args.n, args.side, args.steps, args.seed)
        sys.stdout.write(RESULT + json.dumps(row) + "\n")
        return 0
    result = equality(args) if args.equality else speedup(args)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
