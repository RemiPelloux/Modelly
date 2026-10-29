"""The step-time speed-up of Modelly's columns over Mesa 3.5 on three CPython versions.

    python paper/scripts/python_versions.py --rounds 5 --core 2     # data/python_versions.json
    python paper/scripts/python_versions.py analyse                 # tables/python_versions.tex

Every timing of the paper ran on CPython 3.15. Modelly supports 3.12 and later, and both
the per-agent code Mesa runs and the array code Modelly runs could gain differently from
one interpreter to the next. This script times the Mesa 3.5 and the Modelly column
implementation of every playbook (and the cohort form of the insect population) in three
environments, one per interpreter (.venv-py312, .venv-py314 and the paper's .venv on 3.15),
each with the same package versions (mesa 3.5.1, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1)
and Modelly's compiled modules built for that interpreter. Each run is a fresh interpreter
pinned to one core; within a round the interpreters and the variants rotate, and the
reported speed-up is the median of the per-round ratios.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))

import compare  # noqa: E402
from environment import environment  # noqa: E402
from registry import PLAYBOOKS  # noqa: E402

INTERPRETERS = {
    "3.12": ROOT / ".venv-py312" / "bin" / "python",
    "3.14": ROOT / ".venv-py314" / "bin" / "python",
    "3.15": ROOT / ".venv" / "bin" / "python",
}
VARIANTS = {
    name: ["mesa3", "modelly"]
    + (["modelly-cohorts"] if name == "insect_cohorts" else [])
    for name in PLAYBOOKS
}
DATA = PAPER / "data" / "python_versions.json"
LABELS = {
    "grid_epidemic": "Grid epidemic",
    "predator_prey": "Predator-prey",
    "flocking": "Flocking",
    "network_contagion": "Network contagion",
    "insect_cohorts": "Insect population",
    "schelling": "Schelling",
    "boltzmann_wealth": "Boltzmann wealth",
    "sugarscape": "Sugarscape",
}


def run_once(
    version: str, name: str, variant: str, seed: int, core: int | None
) -> dict:
    """One run of ``variant`` under ``version``'s interpreter."""
    compare.PYTHONS["modelly"] = str(INTERPRETERS[version])
    return compare.run_once(name, variant, seed, "large", core)


def measure(rounds: int, core: int | None) -> dict:
    """Every (interpreter, playbook, variant) ``rounds`` times, rotating the order."""
    cells = [
        (version, name, variant)
        for version in INTERPRETERS
        for name, variants in VARIANTS.items()
        for variant in variants
    ]
    times: dict = {}
    for r in range(rounds):
        shift = r % len(cells)
        for version, name, variant in cells[shift:] + cells[:shift]:
            row = run_once(version, name, variant, r, core)
            slot = (
                times.setdefault(version, {})
                .setdefault(name, {})
                .setdefault(variant, {"build": [], "run": []})
            )
            slot["build"].append(row["build_seconds"])
            slot["run"].append(row["run_seconds"])
            sys.stdout.write(
                f"  {version} {name:18s} {variant:16s} round {r + 1}: "
                f"build {row['build_seconds']:.3f} s, run {row['run_seconds']:.3f} s cpu\n"
            )
            sys.stdout.flush()
    return times


def speedups(times: dict) -> dict:
    """Per interpreter and playbook: the paired per-round speed-up of each Modelly form."""
    out: dict = {}
    for version, playbooks in times.items():
        for name, variants in playbooks.items():
            base = variants["mesa3"]["run"]
            for variant, slot in variants.items():
                if variant == "mesa3":
                    continue
                ratios = [a / b for a, b in zip(base, slot["run"], strict=True)]
                out.setdefault(name, {}).setdefault(variant, {})[version] = {
                    "median": statistics.median(ratios),
                    "low": min(ratios),
                    "high": max(ratios),
                    "mesa3_steps": statistics.median(base),
                    "modelly_steps": statistics.median(slot["run"]),
                }
    return out


def table(payload: dict) -> str:
    """One line per playbook and Modelly form: Mesa 3.5's and Modelly's median step time, and the speed-up, per interpreter."""
    versions = list(INTERPRETERS)
    lines = [
        "\\begin{tabular}{ll" + "rrr" * len(versions) + "}",
        "\\toprule",
        " & & "
        + " & ".join(f"\\multicolumn{{3}}{{c}}{{CPython {v}}}" for v in versions)
        + " \\\\",
        " ".join(
            f"\\cmidrule(lr){{{3 + 3 * i}-{5 + 3 * i}}}" for i in range(len(versions))
        ),
        "Workload & Form & "
        + " & ".join("Mesa & Modelly & $S_{\\mathrm{steps}}$" for _ in versions)
        + " \\\\",
        "\\midrule",
    ]
    for name, forms in speedups(payload["times"]).items():
        for i, (variant, per_version) in enumerate(forms.items()):
            cells = []
            for v in versions:
                s = per_version[v]
                cells.append(
                    f"{s['mesa3_steps']:.3f} & {s['modelly_steps']:.3f} & {s['median']:.1f}"
                )
            form = "cohorts" if variant.endswith("cohorts") else "columns"
            lines.append(
                f"{LABELS[name] if i == 0 else ''} & {form} & "
                + " & ".join(cells)
                + " \\\\"
            )
    lines += ["\\bottomrule", "\\end{tabular}"]
    return (
        "\n".join(lines) + f"\n% {payload['rounds']} rounds, core {payload['core']}\n"
    )


def main() -> None:
    """Parse the options; measure or only re-analyse."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="run", choices=["run", "analyse"])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--core", type=int, default=None)
    options = parser.parse_args()
    if options.command == "run":
        payload = {
            "environment": environment(
                ROOT, {k: str(v) for k, v in INTERPRETERS.items()}, options.core
            ),
            "rounds": options.rounds,
            "core": options.core,
            "times": measure(options.rounds, options.core),
        }
        DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    (PAPER / "tables" / "python_versions.tex").write_text(
        table(payload), encoding="utf-8"
    )
    print(table(payload))
    for name, forms in speedups(payload["times"]).items():
        for variant, per_version in forms.items():
            print(
                f"{name:18s} {variant:16s} "
                + "  ".join(
                    f"{v}: {s['median']:.1f} [{s['low']:.1f}, {s['high']:.1f}]"
                    for v, s in per_version.items()
                )
            )


if __name__ == "__main__":
    main()
