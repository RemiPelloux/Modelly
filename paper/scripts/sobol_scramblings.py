"""Uncertainty of the Sobol estimates across independent scramblings: data/sobol_scramblings.json.

    python paper/scripts/sobol_scramblings.py

ishigami.py quotes one scrambled Sobol design (seed 1) with bootstrap intervals that
resample its rows as if they were independent, which the rows of a low-discrepancy design
are not. This script repeats the estimate on R independent scramblings of the sequence
(seeds 1 to R; the scrambling is drawn from the seed), at two sample sizes, and reports,
for every index: the spread of the R estimates (their standard deviation and 2.5--97.5%
range, the randomised-QMC uncertainty), the mean half-width of the row-bootstrap interval,
the ratio of the two (how much the bootstrap over- or understates the uncertainty), and
how many of the R bootstrap intervals contain the analytical value (the bootstrap
interval's coverage). It writes the data file and tables/sobol_scramblings.tex.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
from environment import environment
from ishigami import SPACE, analytical, ishigami

from modelly.sensitivity import sobol

PAPER = Path(__file__).resolve().parents[1]
SCRAMBLINGS = 32
SAMPLE_SIZES = (1024, 4096)
NAMES = ("x1", "x2", "x3")


def estimates(samples: int) -> list[dict]:
    """One row per scrambling: the point estimates and the bootstrap bounds."""
    rows = []
    for seed in range(1, SCRAMBLINGS + 1):
        table = sobol(
            ishigami, SPACE, samples=samples, seed=seed, estimator="jansen"
        ).table
        rows.append(
            {c: [float(v) for v in table[c]] for c in table.columns} | {"seed": seed}
        )
    return rows


def summarise(rows: list[dict], exact: dict[str, list[float]]) -> list[dict]:
    """Per index: spread across scramblings against the row bootstrap's half-width."""
    out = []
    for index in ("S1", "ST"):
        for k, name in enumerate(NAMES):
            points = [r[index][k] for r in rows]
            halves = [(r[f"{index}_high"][k] - r[f"{index}_low"][k]) / 2 for r in rows]
            covered = sum(
                r[f"{index}_low"][k] <= exact[index][k] <= r[f"{index}_high"][k]
                for r in rows
            )
            sd = statistics.stdev(points)
            out.append(
                {
                    "index": index,
                    "parameter": name,
                    "exact": exact[index][k],
                    "mean": statistics.fmean(points),
                    "sd": sd,
                    "low": float(np.percentile(points, 2.5)),
                    "high": float(np.percentile(points, 97.5)),
                    "bootstrap_half": statistics.fmean(halves),
                    "ratio": statistics.fmean(halves) / (1.96 * sd)
                    if sd
                    else float("inf"),
                    "covered": covered,
                    "inside_range": bool(
                        np.percentile(points, 2.5)
                        <= exact[index][k]
                        <= np.percentile(points, 97.5)
                    ),
                }
            )
    return out


def table(summary: dict[int, list[dict]]) -> str:
    """The LaTeX table of the comparison, one block per sample size."""
    lines = [
        "\\begin{tabular}{rllrrrrrr}",
        "\\toprule",
        (
            "$N$ & Index & Exact & Mean & SD across & 2.5--97.5\\% range & "
            "bootstrap $\\pm$ & ratio & covered \\\\"
        ),
        "\\midrule",
    ]
    for samples, rows in summary.items():
        for i, row in enumerate(rows):
            label = (
                ("$S_{T" if row["index"] == "ST" else "$S_{")
                + row["parameter"][1]
                + "}$"
            )
            lines.append(
                f"{samples if i == 0 else ''} & {label} & {row['exact']:.3f} & {row['mean']:.3f} & "
                f"{row['sd']:.4f} & [{row['low']:.3f}, {row['high']:.3f}] & "
                f"{row['bootstrap_half']:.4f} & {row['ratio']:.2f} & {row['covered']}/{SCRAMBLINGS} \\\\"
            )
        lines.append("\\addlinespace")
    lines.pop()
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run the scramblings, summarise, write the data file and the table."""
    exact = analytical()
    rows = {n: estimates(n) for n in SAMPLE_SIZES}
    summary = {n: summarise(rows[n], exact) for n in SAMPLE_SIZES}
    out = {
        "environment": environment(),
        "scramblings": SCRAMBLINGS,
        "sample_sizes": list(SAMPLE_SIZES),
        "estimator": "jansen",
        "analytical": exact,
        "estimates": {str(n): rows[n] for n in SAMPLE_SIZES},
        "summary": {str(n): summary[n] for n in SAMPLE_SIZES},
    }
    (PAPER / "data" / "sobol_scramblings.json").write_text(
        json.dumps(out, indent=1) + "\n"
    )
    (PAPER / "tables" / "sobol_scramblings.tex").write_text(
        table(summary), encoding="utf-8"
    )
    for n, rows_n in summary.items():
        for row in rows_n:
            print(
                f"N={n} {row['index']} {row['parameter']}: exact {row['exact']:.3f} "
                f"mean {row['mean']:.3f} sd {row['sd']:.4f} range [{row['low']:.3f}, {row['high']:.3f}] "
                f"bootstrap half {row['bootstrap_half']:.4f} ratio {row['ratio']:.2f} "
                f"covered {row['covered']}/{SCRAMBLINGS}"
            )


if __name__ == "__main__":
    main()
