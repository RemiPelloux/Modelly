"""Tables and the figure of the agreement study (see agreement.py)."""

from __future__ import annotations

from pathlib import Path

ALPHA = 0.05
MARGIN = (
    0.5  # the equivalence margin, in pooled standard deviations, as in agreement.py
)


def pvalue(p: float, digits: int = 2) -> str:
    """A p-value to ``digits`` decimals, or an upper bound when it would print as zero."""
    floor = 10.0**-digits
    return f"{p:.{digits}f}" if p >= floor / 2 else f"$<${floor:.{digits}f}"


def signed(x: float) -> str:
    """A signed number, in math mode so that its sign is a true minus."""
    return f"${x:+.2f}$"


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
KINDS = {
    "modelly": "columns",
    "modelly-cells": "cell lists",
    "modelly-cohorts": "cohorts",
    "mesa3": "Mesa 3.5",
    "frames": "mesa-frames",
}


def table(rows: list[dict], seeds: int) -> str:
    """One line per Modelly variant: worst effect size, lowest p-values, equivalences."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["playbook"], row["variant"]), []).append(row)
    modelly_only = all(variant.startswith("modelly") for _, variant in groups)
    who = "Modelly variant" if modelly_only else "Implementation"
    lines = [
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        (
            f"Workload & {who} & Stats & max $|d|$ & min $p_{{t}}$ & "
            "min $p_{\\mathrm{KS}}$ & Equivalent \\\\"
        ),
        "\\midrule",
    ]
    for (name, variant), group in groups.items():
        equivalent = sum(r["tost"] < ALPHA for r in group)
        lines.append(
            f"{LABELS[name]} & {KINDS[variant]} & {len(group)} & "
            f"{max(abs(r['d']) for r in group):.2f} & {pvalue(min(r['paired'] for r in group))} & "
            f"{pvalue(min(r['ks'] for r in group))} & {equivalent}/{len(group)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + f"\n% {seeds} seeds per variant\n"


def forest(rows: list[dict], out: Path) -> None:
    """Every comparison's standardised difference with its 95% interval and the margin."""
    import matplotlib  # noqa: PLC0415 - only `analyse` draws

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from figure_style import STYLE  # noqa: PLC0415

    plt.rcParams.update(STYLE)

    colours = {
        "columns": "#0072B2",
        "cell lists": "#56B4E9",
        "cohorts": "#009E73",
        "Mesa 3.5": "#9A9A9A",
        "mesa-frames": "#D55E00",
    }
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    for x, row in enumerate(rows):
        kind = KINDS[row["variant"]]
        ax.errorbar(
            x,
            row["d"],
            yerr=[[row["d"] - row["d_lo"]], [row["d_hi"] - row["d"]]],
            fmt="o",
            ms=2.5,
            lw=0.8,
            color=colours[kind],
            label=kind if kind.lower().startswith("mesa") else f"Modelly, {kind}",
        )
    for level in (-MARGIN, MARGIN):
        ax.axhline(level, color="0.5", lw=0.7, ls="--")
    ax.axhline(0, color="0.3", lw=0.6)
    starts = [
        i
        for i, r in enumerate(rows)
        if i == 0 or r["playbook"] != rows[i - 1]["playbook"]
    ]
    ends = [*starts[1:], len(rows)]
    for k, (start, end) in enumerate(zip(starts, ends, strict=True)):
        if k % 2:
            ax.axvspan(start - 0.5, end - 0.5, color="0.93", lw=0)
    centres = [(s + e - 1) / 2 for s, e in zip(starts, ends, strict=True)]
    ax.set_xticks(
        centres,
        [LABELS[rows[i]["playbook"]].replace(" ", "\n") for i in starts],
        fontsize=7,
    )
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlim(-0.8, len(rows) - 0.2)
    ax.set_ylabel("Standardised difference $d$\n(Modelly $-$ Mesa 2.3)", fontsize=8)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    ax.legend(
        unique.values(),
        unique.keys(),
        fontsize=7,
        frameon=False,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
    )
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=200)
    plt.close(fig)


COLUMNS = (
    "\\toprule",
    (
        "Workload & Modelly variant & Statistic & $d$ & 95\\% interval & $r$ & $p_t$ & "
        "$p_{\\mathrm{KS}}$ & $p_{\\mathrm{TOST}}$ \\\\"
    ),
    "\\midrule",
)


def full_table(rows: list[dict], seeds: int) -> str:
    """Every comparison: d with its paired 95% interval, r, and the p-values (longtable)."""
    head = [
        "\\begin{longtable}{lllrrrrrr}",
        (
            "\\caption{Every comparison of the agreement study at the small size"
            f" ({seeds} seeds): standardised difference $d$ with its paired 95\\% interval,"
            " correlation $r$ between the implementations' runs on the same seed, and the"
            " paired $t$, Kolmogorov--Smirnov and paired TOST $p$-values, uncorrected.}"
            "\\label{tab:agreement-all}\\\\"
        ),
        *COLUMNS,
        "\\endfirsthead",
        *COLUMNS,
        "\\endhead",
        "\\bottomrule\\endfoot",
    ]
    lines = []
    for row in rows:
        stat = row["stat"].replace("_", "\\_")
        lines.append(
            f"{LABELS[row['playbook']]} & {KINDS[row['variant']]} & \\code{{{stat}}} & "
            f"{signed(row['d'])} & [{signed(row['d_lo'])}, {signed(row['d_hi'])}] & "
            f"{signed(row['r'])} & {pvalue(row['paired'])} & {pvalue(row['ks'])} & "
            f"{pvalue(row['tost'], 3)} \\\\"
        )
    return "\n".join([*head, *lines, "\\end{longtable}"]) + "\n"
