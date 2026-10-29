"""The release comparisons of data/release_gates.json as one table: tables/release_gates.tex.

    python paper/scripts/release_gates_table.py

One row per release pair ``new_vs_old``: the range of the core operations' median ratios,
the range of the playbooks' median ratios with their rounds and whether every output was
identical, and the notebook arm's paired median ratio with its per-round range. A pair
whose raw numbers were not kept (a summary string in the file) is shown from the summary
and marked so.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
SUMMARY_RANGE = re.compile(r"between ([\d.]+) and ([\d.]+)")
ROUNDS = re.compile(r"_(\d+)_rounds")


def span(values: list[float]) -> str:
    """``low to high`` with two decimals."""
    return f"{min(values):.2f} to {max(values):.2f}"


def core_cell(entry: dict) -> str:
    """The core operations: medians over sessions, a dict of medians, or a summary string."""
    if "core_operations_sessions" in entry:
        by_op: dict[str, list[float]] = {}
        for row in entry["core_operations_sessions"]:
            ratio = 1 / row["ratio"] if row.get("swapped") else row["ratio"]
            by_op.setdefault(row["operation"], []).append(ratio)
        medians = [statistics.median(v) for v in by_op.values()]
        return f"{span(medians)} ({len(by_op)} operations, {len(next(iter(by_op.values())))} sessions)"
    core = entry.get("core_operations")
    if isinstance(core, dict):
        return f"{span([v['ratio'] for v in core.values()])} ({len(core)} timings)"
    found = SUMMARY_RANGE.search(core or "")
    return f"{found.group(1)} to {found.group(2)} (summary only)" if found else "--"


def playbook_cell(entry: dict) -> str:
    """The playbooks' median ratios, their rounds, and whether outputs were identical."""
    key = next(k for k in entry if k.startswith("playbooks"))
    rows = entry[key]
    rounds = ROUNDS.search(key)
    same = all(r.get("identical", r.get("same", False)) for r in rows)
    extra = ""
    if "noisiest_three_15_rounds" in entry:
        medians = [r["median"] for r in entry["noisiest_three_15_rounds"]]
        extra = f"; three noisiest over 15 rounds {span(medians)}"
    return (
        f"{span([r['ratio'] for r in rows])} ({len(rows)} variants, "
        f"{rounds.group(1) if rounds else '?'} rounds{extra}); "
        + ("identical" if same else "differ")
    )


def notebook_cell(entry: dict) -> str:
    """The notebook arm: a paired median ratio with its range, or the kept summary."""
    key = next((k for k in entry if k.startswith("notebook") and "seconds" in k), None)
    if key is None:
        return "1.00 (summary only)" if "notebook" in entry else "--"
    old, new = entry[key].values()
    ratios = [b / a for a, b in zip(old, new, strict=True)]
    identical = entry.get("notebook_outputs_identical")
    tail = "; identical" if identical else ""
    return (
        f"{statistics.median(ratios):.2f} ({span(ratios)}, {len(ratios)} rounds){tail}"
    )


def rows(data: dict) -> list[str]:
    """One table row per release pair, in file order."""
    out = []
    for key, entry in data.items():
        if key == "note":
            continue
        new, old = key.split("_vs_")
        out.append(
            f"{new} & {old} & {core_cell(entry)} & {playbook_cell(entry)} & "
            f"{notebook_cell(entry)} \\\\"
        )
    return out


def main() -> None:
    """Write the table and print it."""
    data = json.loads((PAPER / "data" / "release_gates.json").read_text())
    head = [
        (
            "\\begin{tabular}{ll>{\\raggedright\\arraybackslash}p{0.2\\linewidth}"
            ">{\\raggedright\\arraybackslash}p{0.3\\linewidth}"
            ">{\\raggedright\\arraybackslash}p{0.2\\linewidth}}"
        ),
        "\\toprule",
        "Release & Against & Core operations & Playbooks & Notebook \\\\",
        "\\midrule",
    ]
    text = "\n".join([*head, *rows(data), "\\bottomrule", "\\end{tabular}"]) + "\n"
    (PAPER / "tables" / "release_gates.tex").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
