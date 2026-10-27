"""Profile a model at several population sizes and compare the cost per agent.

Growth inside one run is only visible when the population changes during it. Building
the model at two or more sizes shows it for a fixed population: an agent that scans
every other agent costs O(N) per agent, so its microseconds per agent grow with N::

    from modelly.profile import compare_sizes

    comparison = compare_sizes(lambda n: MyModel(n=n, rng=42), [1000, 4000], steps=20)
    print(comparison.report())
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.profile.hints import GROWTH_EXPONENT, LINT
from modelly.profile.profiler import DEFAULT_TOP, Profiler
from modelly.profile.report import US, profiled_wall, rows

if TYPE_CHECKING:
    from modelly.core.model import Model

DEFAULT_STEPS = 100
MIN_SIZES = 2
# An operation below this share of the largest run's time gets no hint: too small to matter.
NOTABLE_SHARE = 0.1
STEP_LABEL = "whole step"


@dataclass(frozen=True, slots=True)
class SizeRun:
    """The profile of the model built at one size."""

    size: int
    profiler: Profiler


@dataclass(frozen=True, slots=True)
class Growth:
    """One operation's microseconds per agent at each size, smallest size first."""

    label: str
    sizes: tuple[int, ...]
    us_per_agent: tuple[float | None, ...]
    share: float  # of the profiled time at the largest size

    @property
    def ratio(self) -> float | None:
        """The us per agent at the largest size over the smallest; None if one is missing."""
        first, last = self.us_per_agent[0], self.us_per_agent[-1]
        return last / first if first and last else None

    @property
    def exponent(self) -> float | None:
        """Slope of log(us per agent) on log(N): about 1 for a per-agent scan, 0 for O(1)."""
        if not all(self.us_per_agent):
            return None
        return float(
            np.polyfit(
                np.log(self.sizes),
                np.log(np.asarray(self.us_per_agent, dtype=float)),
                1,
            )[0]
        )


def growth_hint(growth: Growth) -> str:
    """The MDL101 / MDL102 hint for an operation whose cost per agent grows with N."""
    return (
        f"{growth.label}: us per agent grows {growth.ratio:.1f}x from N={growth.sizes[0]}"
        f" to N={growth.sizes[-1]} (about N^{growth.exponent:.1f}): each agent probably"
        f" scans the population. Run {LINT} and look for MDL101 / MDL102"
    )


class SizeComparison:
    """The profiles of one model built at several sizes, compared per agent."""

    def __init__(self, model: str, runs: list[SizeRun]) -> None:
        """``runs`` are ordered by size, smallest first."""
        self.model = model
        self.runs = runs
        self.sizes = tuple(run.size for run in runs)

    def growths(self) -> list[Growth]:
        """The whole step, then each agent loop, costliest at the largest size first."""
        tables = [
            {(r.kind, r.owner, r.name): r for r in rows(run.profiler.records)}
            for run in self.runs
        ]
        total = profiled_wall(self.runs[-1].profiler.records)
        found = [self._step_growth()]
        for key, row in tables[-1].items():
            if row.agents:
                values = tuple(
                    t[key].us_per_agent if key in t else None for t in tables
                )
                share = row.wall_s / total if total else 0.0
                found.append(Growth(row.label, self.sizes, values, share))
        return found

    def _step_growth(self) -> Growth:
        """The model's whole step per agent, which also covers hand-written loops."""
        values = []
        for run in self.runs:
            records = run.profiler.records
            agents = sum(record.agents for record in records)
            wall = sum(record.wall for record in records)
            values.append(wall / agents * US if agents else None)
        return Growth(STEP_LABEL, self.sizes, tuple(values), 1.0)

    def hints(self) -> list[str]:
        """A hint per notable operation whose cost per agent grows roughly with N."""
        growing = [
            growth
            for growth in self.growths()
            if growth.share >= NOTABLE_SHARE
            and (growth.exponent or 0.0) >= GROWTH_EXPONENT
        ]
        loops = [growth for growth in growing if growth.label != STEP_LABEL]
        return [growth_hint(growth) for growth in loops or growing]

    def report(self, top: int = DEFAULT_TOP) -> str:
        """The us-per-agent table, one column per size, then the growth and the hints."""
        steps = len(self.runs[0].profiler.records)
        sizes = ", ".join(map(str, self.sizes))
        heads = [f"N={size} us/agent" for size in self.sizes]
        lines = [
            f"{self.model} profiled at N = {sizes}; {steps} step(s) each",
            "",
            "  ".join([*heads, f"{'growth':>8}", "operation"]),
        ]
        for growth in self.growths()[: top + 1]:
            cells = [
                f"{value:{len(head)}.2f}" if value else f"{'-':>{len(head)}}"
                for head, value in zip(heads, growth.us_per_agent)
            ]
            ratio = f"{growth.ratio:7.2f}x" if growth.ratio else f"{'-':>8}"
            lines.append("  ".join([*cells, ratio, growth.label]))
        found = self.hints()
        if found:
            lines += ["", "hints:"] + [f"  - {hint}" for hint in found]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """The sizes, each operation's us per agent and growth, and the hints."""
        operations = [
            {
                "operation": growth.label,
                "us_per_agent": list(growth.us_per_agent),
                "growth": growth.ratio,
                "exponent": growth.exponent,
                "share": growth.share,
            }
            for growth in self.growths()
        ]
        return {
            "model": self.model,
            "sizes": list(self.sizes),
            "operations": operations,
            "hints": self.hints(),
        }

    def to_dataframe(self) -> pd.DataFrame:
        """One row per operation and size: ``operation``, ``size``, ``us_per_agent``."""
        data = [
            {"operation": growth.label, "size": size, "us_per_agent": value}
            for growth in self.growths()
            for size, value in zip(growth.sizes, growth.us_per_agent)
        ]
        return pd.DataFrame(data, columns=["operation", "size", "us_per_agent"])


def compare_sizes(
    factory: Callable[[int], Model[Any, Any]],
    sizes: Sequence[int],
    steps: int = DEFAULT_STEPS,
    sample_every: int = 1,
) -> SizeComparison:
    """Build the model with ``factory(size)`` at each size, profile ``steps`` steps of each.

    Raises:
        ValueError: when there are fewer than two different positive sizes.
    """
    ordered = sorted(set(sizes))
    if len(ordered) < MIN_SIZES or ordered[0] < 1:
        raise ValueError(
            f"compare_sizes needs at least {MIN_SIZES} different positive sizes, got {list(sizes)}"
        )
    runs = []
    for size in ordered:
        model = factory(size)
        with Profiler(model, sample_every=sample_every) as prof:
            model.run_for(steps)
        runs.append(SizeRun(size, prof))
    return SizeComparison(type(model).__name__, runs)
