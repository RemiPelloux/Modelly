"""Time every playbook on Mesa 2.3 and Modelly, and check that the implementations agree.

    python benchmarks/playbooks/compare.py                     # every playbook
    python benchmarks/playbooks/compare.py flocking insect     # names containing the text
    python benchmarks/playbooks/compare.py --rounds 3 --seeds 6 --size large --core 5

Each run is a fresh interpreter in the framework's own virtual environment
(Modelly: ``.venv``, Mesa 2.3: ``.venv-mesa2``; override with MODELLY_PYTHON
and MESA_PYTHON), pinned to one core with ``taskset`` when ``--core`` is given.
It reports the CPU time of building and running the model. Timing rounds
alternate the variants so a load spike hits all of them. The agreement check
runs every variant on the same seeds at the small size and compares each
summary statistic with the Mesa reference by Welch's t-test; the determinism
check runs the first seed twice per variant and requires identical statistics.
Results go to ``results/<playbook>.json`` and ``results/README.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

from scipy.stats import ttest_ind

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))

from registry import PLAYBOOKS  # noqa: E402

PYTHONS = {
    "mesa": os.environ.get("MESA_PYTHON", str(ROOT / ".venv-mesa2" / "bin" / "python")),
    "modelly": os.environ.get("MODELLY_PYTHON", str(ROOT / ".venv" / "bin" / "python")),
}
RESULT_PREFIX = "RESULT "
REFERENCE = "mesa"
ALPHA = 0.01
AGREEMENT_SEED_BASE = 1000


def interpreter(variant: str) -> str:
    """The interpreter a variant runs in: the Mesa venv for ``mesa``, Modelly's otherwise."""
    return PYTHONS["mesa"] if variant == "mesa" else PYTHONS["modelly"]


def run_once(
    playbook: str, variant: str, seed: int, size: str, core: int | None
) -> dict:
    """Run one variant in a fresh interpreter and return its RESULT row."""
    command = [
        interpreter(variant),
        str(HERE / "worker.py"),
        playbook,
        variant,
        str(seed),
        size,
    ]
    if core is not None and shutil.which("taskset"):
        command = ["taskset", "-c", str(core), *command]
    completed = subprocess.run(
        command, capture_output=True, text=True, cwd=ROOT, check=False
    )
    for line in completed.stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise RuntimeError(
        f"{playbook}/{variant} seed {seed} failed:\n{completed.stderr[-2000:]}"
    )


def time_playbook(
    name: str, variants: list[str], rounds: int, size: str, core: int | None
) -> dict:
    """CPU seconds per round for every variant, rounds alternating the variants."""
    timings = {variant: [] for variant in variants}
    builds = {variant: [] for variant in variants}
    populations = {}
    for round_index in range(rounds):
        for variant in variants:
            row = run_once(name, variant, round_index, size, core)
            timings[variant].append(row["run_seconds"])
            builds[variant].append(row["build_seconds"])
            populations[variant] = row["population"]
            sys.stdout.write(
                f"  {name} {variant:16s} round {round_index + 1}: "
                f"build {row['build_seconds']:.2f} s, run {row['run_seconds']:.2f} s cpu\n"
            )
    return {
        "size": size,
        "run_seconds": timings,
        "build_seconds": builds,
        "population": populations,
    }


def welch_p(a: list[float], b: list[float]) -> float:
    """Two-sided Welch t-test p-value; 1.0 when both samples are identical constants."""
    if a == b:
        return 1.0
    p = float(ttest_ind(a, b, equal_var=False).pvalue)
    return 1.0 if p != p else p


def check_agreement(
    name: str, variants: list[str], seeds: int, core: int | None
) -> dict:
    """Summary statistics per variant over the same seeds, and their p-values against the reference."""
    samples = {variant: [] for variant in variants}
    for seed in range(AGREEMENT_SEED_BASE, AGREEMENT_SEED_BASE + seeds):
        for variant in variants:
            samples[variant].append(
                run_once(name, variant, seed, "small", core)["stats"]
            )
    stats = list(samples[REFERENCE][0])
    table = {}
    for stat in stats:
        values = {v: [row[stat] for row in samples[v]] for v in variants}
        table[stat] = {
            v: {
                "mean": statistics.fmean(values[v]),
                "sd": statistics.pstdev(values[v]),
                "p": welch_p(values[REFERENCE], values[v]),
            }
            for v in variants
        }
    return {"seeds": seeds, "stats": table}


def check_determinism(
    name: str, variants: list[str], core: int | None
) -> dict[str, bool]:
    """Whether a second run of the same seed gives the same statistics."""
    return {
        v: run_once(name, v, AGREEMENT_SEED_BASE, "small", core)["stats"]
        == run_once(name, v, AGREEMENT_SEED_BASE, "small", core)["stats"]
        for v in variants
    }


def render(name: str, spec: dict, report: dict) -> str:
    """One markdown section per playbook: timings, then the agreement table."""
    timing, agreement = report["timing"], report["agreement"]
    variants = list(timing["run_seconds"])
    rounds = len(timing["run_seconds"][REFERENCE])
    reference_run = statistics.median(timing["run_seconds"][REFERENCE])
    reference_total = reference_run + statistics.median(
        timing["build_seconds"][REFERENCE]
    )
    lines = [
        f"## {name}: {spec['title']}",
        "",
        f"Size `{timing['size']}`, {spec['steps']} steps, CPU seconds; run = the steps, build = model construction.",
        "",
        "| variant | population | build | "
        + " | ".join(f"run {i + 1}" for i in range(rounds))
        + " | run median | speed-up (run) | speed-up (build + run) | deterministic |",
        "|---|---|---|" + "---|" * (rounds + 4),
    ]
    for v in variants:
        runs = timing["run_seconds"][v]
        run_median = statistics.median(runs)
        build_median = statistics.median(timing["build_seconds"][v])
        lines.append(
            f"| {v} | {timing['population'][v]:,} | {build_median:.2f} | "
            + " | ".join(f"{r:.2f}" for r in runs)
            + f" | {run_median:.2f} | {reference_run / run_median:.1f}x"
            f" | {reference_total / (run_median + build_median):.1f}x"
            f" | {'yes' if report['deterministic'][v] else 'NO'} |"
        )
    lines += [
        "",
        f"Agreement over {agreement['seeds']} shared seeds at the small size (mean ± sd; p from Welch's t-test against Mesa, flagged below {ALPHA}).",
        "",
        "| statistic | " + " | ".join(variants) + " |",
        "|---|" + "---|" * len(variants),
    ]
    for stat, per_variant in agreement["stats"].items():
        cells = []
        for v in variants:
            entry = per_variant[v]
            flag = (
                ""
                if v == REFERENCE
                else (
                    f" (p={entry['p']:.2f})"
                    if entry["p"] >= ALPHA
                    else f" **(p={entry['p']:.3f})**"
                )
            )
            cells.append(f"{entry['mean']:,.2f} ± {entry['sd']:,.2f}{flag}")
        lines.append(f"| {stat} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def parse(argv: list[str]) -> argparse.Namespace:
    """Command-line options."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "names", nargs="*", help="run the playbooks whose name contains any of these"
    )
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--seeds",
        type=int,
        default=6,
        help="seeds for the agreement check (0 skips it)",
    )
    parser.add_argument("--size", default="large", choices=["small", "large"])
    parser.add_argument(
        "--core", type=int, default=None, help="pin every run to this core with taskset"
    )
    return parser.parse_args(argv)


def write_readme(rounds: int, core: int | None) -> None:
    """results/README.md from every stored result, so a partial run keeps the others."""
    sections = [
        render(
            name,
            spec,
            json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8")),
        )
        for name, spec in PLAYBOOKS.items()
        if (RESULTS / f"{name}.json").exists()
    ]
    header = (
        "# Playbook results\n\nGenerated by compare.py; CPU seconds of a fresh interpreter per run, "
        f"{rounds} alternating rounds, "
        + ("pinned to one core" if core is not None else "not pinned")
        + ". See ../README.md for the method.\n\n"
    )
    (RESULTS / "README.md").write_text(header + "\n".join(sections), encoding="utf-8")


def main(argv: list[str]) -> int:
    """Run the selected playbooks and write the results."""
    options = parse(argv)
    RESULTS.mkdir(exist_ok=True)
    selected = [
        n for n in PLAYBOOKS if not options.names or any(a in n for a in options.names)
    ]
    for name in selected:
        variants = list(PLAYBOOKS[name]["variants"])
        sys.stdout.write(f"{name}\n")
        report = {
            "timing": time_playbook(
                name, variants, options.rounds, options.size, options.core
            ),
            "deterministic": check_determinism(name, variants, options.core),
            "agreement": check_agreement(
                name, variants, max(options.seeds, 2), options.core
            ),
        }
        (RESULTS / f"{name}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    write_readme(options.rounds, options.core)
    sys.stdout.write(f"wrote {RESULTS.relative_to(ROOT)}/README.md\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
