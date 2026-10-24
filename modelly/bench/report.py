"""The ``modelly bench`` report: one row per variant, against the baseline when there is one."""

from __future__ import annotations

import json
from typing import Any

from modelly.bench.history import Change

PERCENT = 100.0


def _row(change: Change, rounds: list[float]) -> str:
    """One table row: median, every round, the baseline and the ratio."""
    spread = " ".join(f"{value:.3f}" for value in rounds)
    if change.baseline is None:
        return f"| {change.key} | {change.median:.3f} | {spread} | - | - | |"
    flag = "REGRESSION" if change.regression else ""
    return (
        f"| {change.key} | {change.median:.3f} | {spread} | {change.baseline:.3f}"
        f" | {change.ratio:.2f}x | {flag} |"
    )


def text(
    entry: dict[str, Any],
    changes: list[Change],
    baseline: dict[str, Any] | None,
    threshold: float,
) -> str:
    """The plain-text report: settings, the table, and the verdict."""
    native = ", ".join(name for name, on in entry["native"].items() if on) or "none"
    where = (
        f"baseline: {baseline.get('label') or baseline['time']} ({baseline['modelly']})"
        if baseline
        else "baseline: none (the first entry at this size)"
    )
    lines = [
        f"modelly {entry['modelly']} on Python {entry['python']} ({entry['platform']})",
        f"compiled modules: {native}; {entry['pinning']}",
        f"size {entry['size']}, seed {entry['seed']}, {entry['rounds']} alternating rounds; {where}",
        "",
        "| variant | median CPU s | rounds | baseline | ratio | |",
        "|---|---|---|---|---|---|",
    ]
    lines += [_row(c, entry["results"][c.key]["cpu_seconds"]) for c in changes]
    slower = [c.key for c in changes if c.regression]
    lines.append("")
    limit = f"{threshold * PERCENT:.0f}%"
    lines.append(
        f"regressions above {limit}: {', '.join(slower)}"
        if slower
        else f"no regression above {limit}"
    )
    return "\n".join(lines)


def as_json(entry: dict[str, Any], changes: list[Change]) -> str:
    """The new history entry and the comparison, as one JSON document."""
    rows = [change.__dict__ for change in changes]
    return json.dumps({"entry": entry, "changes": rows}, indent=2)
