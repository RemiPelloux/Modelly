"""Build the paper's figure and results table from the stored playbook results.

    python paper/scripts/make_figures.py

Reads benchmarks/playbooks/results/*.json (written by benchmarks/playbooks/compare.py) and
writes figures/speedups.pdf, figures/speedups.png and tables/playbooks.tex, so every number
in the paper's performance section comes from a file in the repository.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from figure_style import STYLE

plt.rcParams.update(STYLE)

PAPER = Path(__file__).resolve().parents[1]
RESULTS = PAPER.parent / "benchmarks" / "playbooks" / "results"
REFERENCE = "mesa"
ORDER = (
    "grid_epidemic",
    "predator_prey",
    "flocking",
    "network_contagion",
    "insect_cohorts",
    "schelling",
    "boltzmann_wealth",
    "sugarscape",
)
LABELS = {
    "grid_epidemic": "Grid epidemic (SIR)",
    "predator_prey": "Predator-prey",
    "flocking": "Flocking (boids)",
    "network_contagion": "Network contagion",
    "insect_cohorts": "Insect population",
    "schelling": "Schelling segregation",
    "boltzmann_wealth": "Boltzmann wealth",
    "sugarscape": "Sugarscape",
}
MESA3 = "mesa3"
VARIANTS = {
    MESA3: "Mesa 3.5",
    "frames": "mesa-frames",
    "modelly-cells": "Modelly, cell lists",
    "modelly": "Modelly, columns",
    "modelly-cohorts": "Modelly, cohorts",
}
COLOURS = {
    "Mesa 3.5": "#9A9A9A",
    "mesa-frames": "#D55E00",
    "Modelly, cell lists": "#56B4E9",
    "Modelly, columns": "#0072B2",
    "Modelly, cohorts": "#009E73",
}
SIGNIFICANCE = 0.01
BAR = 0.19
WIDTH_IN, HEIGHT_IN = 6.8, 5.0
DPI = 200
TIMES = r"$\times$"
SHORTEST = 0.0005  # seconds that would print as 0.000


def load() -> dict[str, dict]:
    """Every playbook's stored result, by playbook name, in the paper's order."""
    data = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in RESULTS.glob("*.json")
    }
    return {name: data[name] for name in ORDER if name in data}


def summarise(result: dict) -> list[dict]:
    """One row per variant: population, median run time, speed-up, lowest p, determinism."""
    timing = result["timing"]
    reference = statistics.median(timing["run_seconds"][REFERENCE])
    reference_total = reference + statistics.median(timing["build_seconds"][REFERENCE])
    mesa3 = statistics.median(timing["run_seconds"].get(MESA3, [float("nan")]))
    rows = []
    for variant, runs in timing["run_seconds"].items():
        seconds = statistics.median(runs)
        build = statistics.median(timing["build_seconds"][variant])
        # Round r runs every variant on seed r, so per-round ratios are paired.
        ratios = [
            ref / own
            for ref, own in zip(timing["run_seconds"][REFERENCE], runs, strict=True)
        ]
        p_values = [
            s[variant]["p"]
            for s in result["agreement"]["stats"].values()
            if variant in s
        ]
        rows.append(
            {
                "variant": variant,
                "population": timing["population"][variant],
                "seconds": seconds,
                "speedup": reference / seconds,
                "low": min(ratios),
                "high": max(ratios),
                "build": build,
                "total_speedup": reference_total / (seconds + build),
                "over_mesa3": mesa3 / seconds,
                "min_p": min(p_values),
                "deterministic": result["deterministic"][variant],
            }
        )
    return rows


def plot(summary: dict[str, list[dict]], out: Path) -> None:
    """Horizontal bars of the speed-up over Mesa 2.3, log scale, one group per playbook."""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    names = list(summary)
    for i, name in enumerate(names):
        variants = [r for r in summary[name] if r["variant"] != REFERENCE]
        for j, row in enumerate(variants):
            kind = VARIANTS[row["variant"]]
            y = i + (j - (len(variants) - 1) / 2) * BAR
            spread = [[row["speedup"] - row["low"]], [row["high"] - row["speedup"]]]
            ax.barh(
                y,
                row["speedup"] - 1,
                left=1,
                height=BAR,
                color=COLOURS[kind],
                label=kind,
            )
            ax.errorbar(
                row["speedup"],
                y,
                xerr=spread,
                fmt="none",
                ecolor="0.15",
                lw=1.1,
                capsize=2,
            )
            ax.text(
                row["high"] * 1.08,
                y,
                f"{row['speedup']:.1f}{TIMES}",
                va="center",
                fontsize=7,
            )
    ax.set_xscale("log")
    ax.axvline(1, color="0.4", linewidth=0.8)
    ax.set_yticks(range(len(names)), [LABELS[n] for n in names], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel(
        "Speed-up over Mesa 2.3 (CPU time of the steps, log scale)", fontsize=8
    )
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    ax.legend(
        unique.values(), unique.keys(), fontsize=7, frameon=False, loc="lower right"
    )
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=DPI)
    plt.close(fig)


def seconds_cell(value: float) -> str:
    """Seconds to three decimals; a time too short to show is written as an upper bound."""
    return f"{value:.3f}" if value >= SHORTEST else "$<$0.001"


def table(summary: dict[str, list[dict]]) -> str:
    r"""The results as a whole booktabs tabular.

    It is input outside any tabular: \input is not expandable inside one.
    """
    lines = []
    for name, rows in summary.items():
        for k, row in enumerate(rows):
            label = LABELS[name] if k == 0 else ""
            kind = (
                "Mesa 2.3" if row["variant"] == REFERENCE else VARIANTS[row["variant"]]
            )
            population = f"{row['population']:,}".replace(",", "{,}")
            over3 = (
                "--"
                if row["variant"] in (REFERENCE, MESA3)
                else f"{row['over_mesa3']:.1f}"
            )
            lines.append(
                f"{label} & {kind} & {population} & {seconds_cell(row['build'])} & "
                f"{row['seconds']:.3f} & {row['speedup']:.1f} & "
                f"{row['total_speedup']:.1f} & {over3} \\\\"
            )
        lines.append("\\addlinespace")
    head = [
        "\\begin{tabular}{llrrrrrr}",
        "\\toprule",
        (
            " & & & \\multicolumn{2}{c}{CPU time (s)} & \\multicolumn{2}{c}{over Mesa 2.3}"
            " & over Mesa 3.5 \\\\"
        ),
        "\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-8}",
        "Workload & Variant & Agents & build & steps & steps & total & steps \\\\",
        "\\midrule",
    ]
    return "\n".join([*head, *lines[:-1], "\\bottomrule", "\\end{tabular}"]) + "\n"


def setting(value: object) -> str:
    """One parameter value as text: numbers plainly, ranges as a to b, groups in braces."""
    if isinstance(value, dict):
        return "\\{" + ", ".join(f"{k} {setting(v)}" for k, v in value.items()) + "\\}"
    if isinstance(value, list) and len(value) == 2 and not isinstance(value[0], list):
        return f"{value[0]}--{value[1]}"
    if isinstance(value, list):
        return "; ".join(setting(v) for v in value)
    return (
        f"{value:g}" if isinstance(value, float) else f"{value:,}".replace(",", "{,}")
    )


def settings(table: dict) -> str:
    """A parameter table as ``name = value`` pairs, names in typewriter type."""
    return ", ".join(
        f"\\code{{{k.replace('_', '\\_')}}}~$=$~{setting(v)}" for k, v in table.items()
    )


def workloads() -> str:
    """Every playbook's steps, sizes and parameters, from the registry, as a tabularx."""
    sys.path.insert(0, str(RESULTS.parent))
    from registry import PLAYBOOKS  # noqa: PLC0415 - the harness's own definitions

    lines = [
        (
            "\\begin{tabularx}{\\linewidth}{@{}l r >{\\raggedright\\arraybackslash}"
            "p{0.24\\linewidth} >{\\raggedright\\arraybackslash}X@{}}"
        ),
        "\\toprule",
        "Workload & Steps & Small / large size & Parameters \\\\",
        "\\midrule",
    ]
    for name in ORDER:
        spec = PLAYBOOKS[name]
        sizes = (
            settings(spec["sizes"]["small"]) + " / " + settings(spec["sizes"]["large"])
        )
        lines.append(
            f"{LABELS[name]} & {spec['steps']} & {sizes} & {settings(spec['params'])} \\\\"
            " \\addlinespace"
        )
    return "\n".join([*lines, "\\bottomrule", "\\end{tabularx}"]) + "\n"


def main() -> None:
    """Write the figure and the table."""
    summary = {name: summarise(result) for name, result in load().items()}
    (PAPER / "figures").mkdir(exist_ok=True)
    (PAPER / "tables").mkdir(exist_ok=True)
    plot(summary, PAPER / "figures" / "speedups")
    (PAPER / "tables" / "playbooks.tex").write_text(table(summary), encoding="utf-8")
    (PAPER / "tables" / "workloads.tex").write_text(workloads(), encoding="utf-8")
    worst = min(
        r["min_p"]
        for rows in summary.values()
        for r in rows
        if r["variant"] != REFERENCE
    )
    print(
        f"{len(summary)} playbooks; lowest agreement p-value {worst:.2f} "
        f"({'none' if worst >= SIGNIFICANCE else 'some'} below {SIGNIFICANCE})"
    )


if __name__ == "__main__":
    main()
