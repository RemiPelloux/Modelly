"""``modelly bench --against VERSION``: this checkout and a release, run for run.

The release is built from its git tag in this repository into a cached virtual
environment with the same numpy, pandas, scipy and networkx as this interpreter
(``modelly.dev.perf_env``, the builder of the performance guard), so both sides
are compiled by the same toolchain and only Modelly's source differs. Every round
runs each Modelly variant once in each interpreter, in fresh processes, the order
swapped from one round to the next, with the same seed. The two runs must give
the same results (the final population and every summary statistic) for their
times to be comparable; the report gives, per variant, the median of the
per-round ratios of CPU time (checkout / release) and its interquartile range.
A variant is slower when that median exceeds 1 + threshold and even its lower
quartile is above 1, the criterion of the performance guard.
"""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from modelly.bench.pinning import Pinning, pinned
from modelly.bench.playbooks import MODELLY_PREFIX, Variant, run_once
from modelly.dev import perf_env

QUARTILES = 4
TIMING_KEYS = frozenset({"build_seconds", "run_seconds", "cpu_seconds", "wall_seconds"})
LATEST = "release"  # --against release: the last tag reachable from HEAD


@dataclass(frozen=True)
class Pairing:
    """One variant's paired rounds: CPU seconds on each side and whether results agreed."""

    key: str
    release: list[float]
    checkout: list[float]
    identical: bool

    @property
    def ratios(self) -> list[float]:
        """The ratios checkout / release, round by round."""
        return [c / r for c, r in zip(self.checkout, self.release, strict=True)]

    def quartiles(self) -> tuple[float, float, float]:
        """Lower quartile, median and upper quartile of the ratios."""
        ratios = self.ratios
        if len(ratios) == 1:
            return ratios[0], ratios[0], ratios[0]
        low, median, high = statistics.quantiles(ratios, n=QUARTILES)
        return low, median, high

    def slower(self, threshold: float) -> bool:
        """Median ratio above 1 + threshold and the lower quartile above 1."""
        low, median, _ = self.quartiles()
        return median > 1.0 + threshold and low > 1.0


@dataclass(frozen=True)
class Sides:
    """The two interpreters and their environments."""

    version: str
    release_python: str
    release_env: dict[str, str]
    checkout_env: dict[str, str]


def prepare(version: str, start: Path) -> Sides:
    """Build (or reuse) the release environment and this checkout's compiled modules."""
    root = Path(perf_env.git(start, "rev-parse", "--show-toplevel"))
    if version == LATEST:
        version = perf_env.baseline_version(root)
    release_python = perf_env.ensure_baseline(root, version)
    perf_env.ensure_native(root)
    release_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "MODELLY_PURE_PYTHON"}
    }
    return Sides(
        version, str(release_python), release_env, perf_env.candidate_env(root)
    )


def _results(row: dict[str, Any]) -> dict[str, Any]:
    """What a run computed, without its timings."""
    return {k: v for k, v in row.items() if k not in TIMING_KEYS}


def pair_rounds(
    args: Any, variants: list[Variant], pinning: Pinning, sides: Sides
) -> list[Pairing]:
    """Each Modelly variant once per side per round, the side order swapped every round."""
    chosen = [v for v in variants if v.name.startswith(MODELLY_PREFIX)]
    runs: dict[str, list[tuple[dict, dict]]] = {v.key: [] for v in chosen}
    with pinned(pinning):
        for index in range(args.rounds):
            swap = index % 2 == 1
            for variant in chosen[::-1] if swap else chosen:
                runs[variant.key].append(_paired_run(args, variant, sides, swap))
    return [_pairing(key, pairs) for key, pairs in runs.items()]


def _paired_run(
    args: Any, variant: Variant, sides: Sides, swap: bool
) -> tuple[dict, dict]:
    """One run on each side, the checkout's first when ``swap``: (release row, checkout row)."""
    release = replace(variant, python=sides.release_python)
    order = [(release, sides.release_env), (variant, sides.checkout_env)]
    if swap:
        order.reverse()
    rows = [run_once(args.playbooks, v, args.seed, args.size, env=e) for v, e in order]
    return (rows[1], rows[0]) if swap else (rows[0], rows[1])


def _pairing(key: str, pairs: list[tuple[dict, dict]]) -> Pairing:
    """Collect one variant's rounds into a Pairing."""
    release = [r["cpu_seconds"] for r, _ in pairs]
    checkout = [c["cpu_seconds"] for _, c in pairs]
    identical = all(_results(r) == _results(c) for r, c in pairs)
    return Pairing(key, release, checkout, identical)


def text(pairings: list[Pairing], sides: Sides, args: Any, pinning: Pinning) -> str:
    """The report: one row per variant, then the verdict."""
    head = (
        f"this checkout against modelly {sides.version}: size {args.size}, seed "
        f"{args.seed}, {args.rounds} rounds, sides alternating; {pinning.note}"
    )
    lines = [
        head,
        "",
        (
            f"| variant | {sides.version} median s | checkout median s | ratio median"
            " | IQR | results |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for p in pairings:
        low, median, high = p.quartiles()
        mark = " SLOWER" if p.slower(args.threshold) else ""
        lines.append(
            f"| {p.key} | {statistics.median(p.release):.3f} | "
            f"{statistics.median(p.checkout):.3f} | {median:.3f}{mark} | "
            f"{low:.3f} to {high:.3f} | {'identical' if p.identical else 'DIFFER'} |"
        )
    return "\n".join([*lines, "", verdict(pairings, sides.version, args.threshold)])


def verdict(pairings: list[Pairing], version: str, threshold: float) -> str:
    """One line: which variants are slower or disagree, or that none is."""
    slower = [p.key for p in pairings if p.slower(threshold)]
    differ = [p.key for p in pairings if not p.identical]
    parts = [f"slower than {version}: {', '.join(slower)}"] if slower else []
    parts += [f"results differ: {', '.join(differ)}"] if differ else []
    limit = f"{threshold:.0%}"
    return "; ".join(parts) or f"no variant slower than {version} by more than {limit}"


def failed(pairings: list[Pairing], threshold: float) -> bool:
    """Whether any variant is slower or gave different results."""
    return any(p.slower(threshold) or not p.identical for p in pairings)
