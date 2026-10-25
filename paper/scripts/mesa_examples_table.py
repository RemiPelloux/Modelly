"""Table of Mesa's own examples against their codemod ports, from data/mesa_examples.json.

    python paper/scripts/mesa_examples_table.py    # tables/mesa_examples.tex

The data come from benchmarks/mesa_examples/run.py: paired CPU time of the steps over
alternating rounds, and each summary statistic of the two arms over shared seeds.
"""

from __future__ import annotations

import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
LABELS = {
    "conways_game_of_life": "Conway's Game of Life",
    "pd_grid": "Prisoner's dilemma grid",
    "virus_on_network": "Virus on a network",
    "boid_flockers": "Boid flockers",
    "boltzmann_wealth_model": "Boltzmann wealth",
    "schelling": "Schelling",
    "wolf_sheep": "Wolf--sheep",
    "epstein_civil_violence": "Epstein civil violence",
}
MISSING = {
    "sugarscape_g1mt": "Sugarscape G1MT",
    "alliance_formation": "Alliance formation",
}
ALPHA = 0.05


def agreement(rows: list[dict]) -> str:
    """Statistics compared, equivalent within 0.5 sd, and the lowest Holm-corrected p."""
    if not rows:
        return "-- & -- & --"
    equivalent = sum(r["tost"] < ALPHA for r in rows)
    lowest = min(r["paired_holm"] for r in rows)
    shown = "$<$0.01" if lowest < 0.01 else f"{lowest:.2f}"
    return f"{len(rows)} & {equivalent}/{len(rows)} & {shown}"


def line(name: str, entry: dict, rows: list[dict]) -> str:
    """One example: step times, the port's ratio and its range, then the agreement."""
    t = entry["timing"]
    span = f"{t['min']:.2f}--{t['max']:.2f}"
    return (
        f"{LABELS[name]} & {entry['steps']} & {t['original']:.3f} & {t['port']:.3f} & "
        f"{t['ratio']:.2f} & {span} & {agreement(rows)} \\\\"
    )


def main() -> None:
    """Write the table and print its rows."""
    data = json.loads((PAPER / "data" / "mesa_examples.json").read_text())
    body = []
    for name, entry in data["examples"].items():
        rows = [r for r in data["agreement"] if r["example"] == name]
        body.append(line(name, entry, rows))
    body += [
        f"{label} & \\multicolumn{{8}}{{l}}{{does not port}} \\\\"
        for label in MISSING.values()
    ]
    head = [
        "\\begin{tabular}{lrrrrlrrr}",
        "\\toprule",
        (
            " & & \\multicolumn{2}{c}{steps (s)} & \\multicolumn{2}{c}{port / Mesa} & "
            "\\multicolumn{3}{c}{agreement} \\\\"
        ),
        "\\cmidrule(lr){3-4}\\cmidrule(lr){5-6}\\cmidrule(lr){7-9}",
        "Example & Steps & Mesa & port & median & range & stats & equiv. & min $p_{\\mathrm{Holm}}$ \\\\",
        "\\midrule",
    ]
    text = "\n".join([*head, *body, "\\bottomrule", "\\end{tabular}"]) + "\n"
    (PAPER / "tables" / "mesa_examples.tex").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
