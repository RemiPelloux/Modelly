"""Patterns in a profile that point at a ``python -m modelly.lint`` code or a docs page."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from modelly.profile.profiler import StepRecord
    from modelly.profile.report import Row

LOOP_KINDS = frozenset({"do", "shuffle_do", "map"})
# One loop above this share of the profiled time dominates the step.
DOMINANT_SHARE = 0.5
# Slope of log(cost per agent) on log(population) above which cost grows with N.
GROWTH_EXPONENT = 0.5
# The population must vary by this factor, over this many steps, to fit a slope.
MIN_POPULATION_RANGE = 1.5
MIN_POINTS = 3
COLLECT_SHARE = 0.3
# Below this share of the step spent in AgentSet loops, the agents run by hand.
LOOP_COVERAGE = 0.1
LINT = "`python -m modelly.lint`"


def growth_exponent(records: list[StepRecord], key: tuple) -> float | None:
    """Slope of log(us per agent) on log(agents per call), or None if N barely varied."""
    points = [
        (entry[1] / entry[0], entry[2] / entry[1])
        for record in records
        if (entry := record.ops.get(key)) and entry[1] and entry[2] > 0
    ]
    if len(points) < MIN_POINTS:
        return None
    sizes = np.log([size for size, _ in points])
    if sizes.max() - sizes.min() < math.log(MIN_POPULATION_RANGE):
        return None
    costs = np.log([cost for _, cost in points])
    return float(np.polyfit(sizes, costs, 1)[0])


def dominant_hint(records: list[StepRecord], row: Row, share: float) -> str | None:
    """A hint on the loop that takes most of the time, when its cost per agent grows with N."""
    head = (
        f"{row.label} takes {share:.0%} of the profiled time, "
        f"{row.us_per_agent:.2f} us per agent"
    )
    exponent = growth_exponent(records, (row.kind, row.owner, row.name))
    if exponent is None or exponent < GROWTH_EXPONENT:
        return None
    return (
        f"{head}, and the cost per agent grows with the population (about "
        f"N^{exponent:.1f}): each agent probably scans the population. Run {LINT} "
        "and look for MDL101 / MDL102"
    )


def hints(records: list[StepRecord], table: list[Row], total: float) -> list[str]:
    """Every hint the profile supports; ``total`` is the profiled wall time."""
    if not total:
        return []
    found = []
    loops = [row for row in table if row.kind in LOOP_KINDS]
    if loops and loops[0].agents and loops[0].wall_s / total >= DOMINANT_SHARE:
        hint = dominant_hint(records, loops[0], loops[0].wall_s / total)
        found += [hint] if hint else []
    collect = sum(row.wall_s for row in table if row.kind == "collect") / total
    if collect >= COLLECT_SHARE:
        found.append(
            f"DataCollector.collect takes {collect:.0%} of the profiled time: collect "
            "less often, record fewer agent attributes, or store them as Column "
            "if they are plain attributes (docs/performance.md, 'Columnar agent state')"
        )
    step_wall = sum(record.wall for record in records)
    coverage = sum(row.wall_s for row in loops) / step_wall if step_wall else 1.0
    if any(record.agents for record in records) and coverage < LOOP_COVERAGE:
        found.append(
            f"only {coverage:.0%} of the step runs in AgentSet do/shuffle_do/map: "
            f"if step walks the agents in a hand-written loop, see MDL103 in {LINT}"
        )
    return found
