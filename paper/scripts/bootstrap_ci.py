"""Bootstrap 95% intervals of the step-time speed-ups in Table 2.

    python paper/scripts/bootstrap_ci.py

Round r of a playbook runs every variant on seed r, so the rounds are resampled as pairs:
each resample draws rounds with replacement and recomputes the ratio of the reference's
median step time to the variant's. The percentile interval of 10,000 resamples is written
to tables/speedup_ci.tex, next to the point estimate the main table prints.
"""

from __future__ import annotations

import numpy as np
from make_figures import LABELS, MESA3, PAPER, REFERENCE, VARIANTS, load

RESAMPLES, SEED, LEVEL = 10_000, 20_260_101, 0.95


def interval(
    reference: list[float], own: list[float], rng
) -> tuple[float, float, float]:
    """Ratio of medians, reference over own, and its paired percentile interval."""
    ref, mine = np.asarray(reference), np.asarray(own)
    picks = rng.integers(0, ref.shape[0], (RESAMPLES, ref.shape[0]))
    ratios = np.median(ref[picks], axis=1) / np.median(mine[picks], axis=1)
    tail = (1 - LEVEL) / 2 * 100
    low, high = np.percentile(ratios, [tail, 100 - tail])
    return float(np.median(ref) / np.median(mine)), float(low), float(high)


def cell(estimate: tuple[float, float, float] | None) -> str:
    """A ratio with its interval, or a dash where the comparison does not apply."""
    if estimate is None:
        return "--"
    point, low, high = estimate
    digits = 0 if point >= 100 else 1
    return f"{point:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def rows(rng) -> list[str]:
    """One line per variant that is neither baseline, workload by workload."""
    lines = []
    for name, result in load().items():
        runs = result["timing"]["run_seconds"]
        mesa3 = interval(runs[REFERENCE], runs[MESA3], rng)
        lines.append(f"{LABELS[name]} & Mesa 3.5 & {cell(mesa3)} & -- \\\\")
        for variant, own in runs.items():
            if variant in (REFERENCE, MESA3):
                continue
            over2 = interval(runs[REFERENCE], own, rng)
            over3 = interval(runs[MESA3], own, rng) if MESA3 in runs else None
            lines.append(f" & {VARIANTS[variant]} & {cell(over2)} & {cell(over3)} \\\\")
        lines.append("\\addlinespace")
    return lines[:-1]


def pairs(rng) -> list[str]:
    """The text's other ratios: columns over mesa-frames, Mesa 3.5 + numpy over columns."""
    found = []
    for name, result in load().items():
        runs = result["timing"]["run_seconds"]
        for slow, fast, what in (
            ("frames", "modelly", "columns over mesa-frames"),
            ("modelly", "mesa3np", "Mesa 3.5 + numpy over columns"),
        ):
            if slow in runs and fast in runs:
                found.append(
                    f"{name}: {what} {cell(interval(runs[slow], runs[fast], rng))}"
                )
    return found


def main() -> None:
    """Write the interval table."""
    rng = np.random.default_rng(SEED)
    head = [
        "\\begin{tabular}{llll}",
        "\\toprule",
        "Workload & Variant & steps over Mesa 2.3 & steps over Mesa 3.5 \\\\",
        "\\midrule",
    ]
    body = [*head, *rows(rng), "\\bottomrule", "\\end{tabular}"]
    (PAPER / "tables" / "speedup_ci.tex").write_text(
        "\n".join(body) + "\n", encoding="utf-8"
    )
    print("\n".join(body))
    print("\n".join(pairs(rng)))


if __name__ == "__main__":
    main()
