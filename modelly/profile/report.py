"""Summaries of a profile: the totals per operation, a text table, a dict and a DataFrame."""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.profile.hints import hints

if TYPE_CHECKING:
    from modelly.profile.profiler import Profiler, StepRecord

MS = 1e3
US = 1e6
PERCENT = 100
COLUMNS = (
    "step",
    "time",
    "kind",
    "owner",
    "name",
    "calls",
    "agents",
    "wall_s",
    "cpu_s",
    "births",
    "deaths",
)
TABLE_HEADER = (
    f"{'share':>7}  {'total ms':>10}  {'calls':>7}  {'agents/call':>11}  "
    f"{'us/agent':>9}  operation"
)


@dataclass(slots=True)
class Row:
    """One operation summed over the profiled steps."""

    kind: str
    owner: str
    name: str
    calls: int = 0
    agents: int = 0
    wall_s: float = 0.0
    cpu_s: float = 0.0

    @property
    def label(self) -> str:
        """``Sheep.step (shuffle_do)``, ``DataCollector.collect`` or ``event Model.f``."""
        if self.kind == "event":
            return f"event {self.name}"
        if self.kind == "collect":
            return f"{self.owner}.collect"
        return f"{self.owner}.{self.name} ({self.kind})"

    @property
    def us_per_agent(self) -> float | None:
        """Wall time per agent visited, in microseconds; None when no agent was."""
        return self.wall_s / self.agents * US if self.agents else None


def rows(records: list[StepRecord]) -> list[Row]:
    """Every operation summed over ``records``, costliest first."""
    totals: dict[tuple[str, str, str], Row] = {}
    for record in records:
        for key, (calls, agents, wall, cpu) in record.ops.items():
            row = totals.get(key)
            if row is None:
                row = totals[key] = Row(*key)
            row.calls += calls
            row.agents += agents
            row.wall_s += wall
            row.cpu_s += cpu
    return sorted(totals.values(), key=lambda r: r.wall_s, reverse=True)


def profiled_wall(records: list[StepRecord]) -> float:
    """Wall time of the steps plus the events run between them."""
    events = sum(v[2] for r in records for k, v in r.ops.items() if k[0] == "event")
    return sum(r.wall for r in records) + events


def _header(prof: Profiler) -> list[str]:
    """Lines on the run as a whole: steps, step times, population."""
    records = prof.records
    name = type(prof.model).__name__
    walls = [r.wall for r in records]
    slowest = max(records, key=lambda r: r.wall)
    first, last = records[0], records[-1]
    run = f"model time {first.time:g} to {last.time:g}"
    times = (
        f"mean {statistics.fmean(walls) * MS:.2f} ms, "
        f"median {statistics.median(walls) * MS:.2f} ms, "
        f"slowest {slowest.wall * MS:.2f} ms (step {slowest.step})"
    )
    births = sum(r.births for r in records)
    deaths = sum(r.deaths for r in records)
    lifecycle = f"{births} births, {deaths} deaths"
    return [
        f"{name}: {len(records)} step(s) profiled, one in {prof.sample_every}, {run}",
        f"step wall {sum(walls):.3f} s, CPU {sum(r.cpu for r in records):.3f} s; {times}",
        f"agents {first.agents} at the first step, {last.agents} at the last; {lifecycle}",
    ]


def _table_line(row: Row, total: float) -> str:
    """One row of the operations table."""
    share = row.wall_s / total * PERCENT if total else 0.0
    per_call = f"{row.agents / row.calls:.1f}" if row.agents else "-"
    per_agent = f"{row.us_per_agent:.2f}" if row.agents else "-"
    return (
        f"{share:6.1f}%  {row.wall_s * MS:10.2f}  {row.calls:7d}  {per_call:>11}  "
        f"{per_agent:>9}  {row.label}"
    )


def render_text(prof: Profiler, top: int) -> str:
    """The header, the ``top`` costliest operations and the hints, as text."""
    if not prof.records:
        return (
            "no step was profiled: run the model inside the `with Profiler(...)` block"
        )
    total = profiled_wall(prof.records)
    table = rows(prof.records)
    lines = [*_header(prof), "", TABLE_HEADER]
    lines += [_table_line(row, total) for row in table[:top]]
    if len(table) > top:
        lines.append(f"... {len(table) - top} more operation(s), see to_dataframe()")
    found = hints(prof.records, table, total)
    if found:
        lines += ["", "hints:"] + [f"  - {hint}" for hint in found]
    return "\n".join(lines)


def _step_dict(record: StepRecord) -> dict[str, Any]:
    """The totals of one step."""
    return {
        "step": record.step,
        "time": record.time,
        "agents": record.agents,
        "wall_s": record.wall,
        "cpu_s": record.cpu,
        "births": record.births,
        "deaths": record.deaths,
    }


def as_dict(prof: Profiler) -> dict[str, Any]:
    """Everything the text report shows, as plain data."""
    table = rows(prof.records)
    total = profiled_wall(prof.records)
    return {
        "model": type(prof.model).__name__,
        "sample_every": prof.sample_every,
        "profiled_wall_s": total,
        "operations": [
            {**asdict(r), "label": r.label, "us_per_agent": r.us_per_agent}
            for r in table
        ],
        "steps": [_step_dict(r) for r in prof.records],
        "hints": hints(prof.records, table, total),
    }


def as_dataframe(prof: Profiler) -> pd.DataFrame:
    """One row per step (kind ``step``) followed by one per operation in it."""
    model = type(prof.model).__name__
    data = []
    for r in prof.records:
        step = {**_step_dict(r), "kind": "step", "owner": model, "name": "step"}
        data.append({**step, "calls": 1})
        for (kind, owner, name), (calls, agents, wall, cpu) in r.ops.items():
            op = {"kind": kind, "owner": owner, "name": name, "calls": calls}
            times = {"agents": agents, "wall_s": wall, "cpu_s": cpu}
            data.append({"step": r.step, "time": r.time, **op, **times})
    return pd.DataFrame(data, columns=list(COLUMNS))
