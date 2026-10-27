"""The performance guard: this checkout against the last release, on the core operations.

Two persistent workers, one per interpreter, pinned to the same core where the OS allows it,
time each operation of ``benchmarks/micro/ops.py`` in short bursts, in ABBA order, so load
and frequency drift hit both alike. An operation is a regression when its median ratio
(checkout / release) is above ``threshold`` and even its fastest quarter is slower: one session
on a laptop is noisy by a few percent, so smaller differences are left to the release benchmark
(docs/performance.md, "No regression from release to release").
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

OPS_DIR = Path("benchmarks") / "micro"
BURST_SECONDS = 0.01
DEFAULT_PAIRS = 8
DEFAULT_THRESHOLD = 1.03
QUARTILES = 4
NS = 1e9
CONFIRM_FACTOR = 3  # a suspect is re-timed with this many times the pairs

WORKER = r"""
import json, sys, timeit
TARGET = float(sys.argv[2])
sys.path.insert(0, sys.argv[1])
import ops
table = ops.operations()
print(json.dumps(sorted(table)), flush=True)
for line in sys.stdin:
    name, number = json.loads(line)
    function, per = table[name]
    if number == 0:  # calibrate: calls that take about TARGET seconds
        once = min(timeit.repeat(function, number=1, repeat=3))
        print(json.dumps(max(1, int(TARGET / max(once, 1e-9)))), flush=True)
        continue
    seconds = min(timeit.repeat(function, number=number, repeat=3))
    print(json.dumps(seconds / (number * per) * 1e9), flush=True)
"""


@dataclass(frozen=True)
class Timing:
    """One operation's paired comparison."""

    name: str
    release_ns: float
    checkout_ns: float
    ratio: float
    low: float
    high: float

    def slower(self, threshold: float) -> bool:
        """Whether this is a regression: median above ``threshold`` and the low quartile above 1."""
        return self.ratio > threshold and self.low > 1.0


class Worker:
    """One interpreter running the timing loop of WORKER."""

    def __init__(
        self, python: Path | str, ops_dir: Path, env: dict[str, str] | None = None
    ) -> None:
        """Start ``python`` on the operations in ``ops_dir``, pinned to one core if possible."""
        self.process = subprocess.Popen(
            [str(python), "-c", WORKER, str(ops_dir), str(BURST_SECONDS)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            cwd=ops_dir,
        )
        assert (
            self.process.stdin is not None and self.process.stdout is not None
        )  # PIPE
        self.stdin, self.stdout = self.process.stdin, self.process.stdout
        _pin(self.process.pid)
        self.names: list[str] = json.loads(self.stdout.readline())

    def ask(self, name: str, number: float) -> float:
        """Nanoseconds per item of ``name`` over ``number`` calls (0: calibrate a burst)."""
        self.stdin.write(json.dumps([name, number]) + "\n")
        self.stdin.flush()
        answer: float = json.loads(self.stdout.readline())
        return answer

    def close(self) -> None:
        """Stop the worker and close its pipes."""
        self.stdin.close()
        self.process.wait()
        self.stdout.close()


def _pin(pid: int) -> None:
    """Pin ``pid`` to the last core where the OS allows it (Linux, Windows with psutil).

    The last core rather than core 0, which takes most interrupts.
    """
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(pid, {_core()})
        return
    try:
        import psutil  # noqa: PLC0415 - optional (modelly-abm[bench])
    except ImportError:
        return
    try:
        psutil.Process(pid).cpu_affinity([_core()])
    except (AttributeError, psutil.Error):
        return  # macOS: no CPU affinity


def compare_operation(
    release: Worker, checkout: Worker, name: str, pairs: int
) -> Timing:
    """``pairs`` ABBA bursts of ``name``; the median ratio and its quartiles."""
    number = max(1, release.ask(name, 0))
    ratios, base, mine = [], [], []
    for k in range(pairs):
        first, second = (release, checkout) if k % 2 == 0 else (checkout, release)
        a = first.ask(name, number)
        b = second.ask(name, number)
        r, c = (a, b) if first is release else (b, a)
        base.append(r)
        mine.append(c)
        ratios.append(c / r)
    q = statistics.quantiles(ratios, n=QUARTILES) if pairs > 1 else [ratios[0]] * 3
    return Timing(
        name,
        statistics.median(base),
        statistics.median(mine),
        statistics.median(ratios),
        q[0],
        q[2],
    )


def _core() -> int:
    """The core both workers are pinned to: the last one."""
    return (os.cpu_count() or 1) - 1


def _session(
    release_python: Path,
    root: Path,
    env: dict[str, str],
    pairs: int,
    names: list[str] | None = None,
    *,
    swap: bool = False,
) -> dict[str, Timing]:
    """One session: fresh workers, ``names`` (default: all) timed ``pairs`` times each."""
    ops_dir = root / OPS_DIR
    start: list[tuple[Path | str, dict[str, str] | None]] = [
        (release_python, None),
        (sys.executable, env),
    ]
    workers = [Worker(p, ops_dir, e) for p, e in (start[::-1] if swap else start)]
    release, checkout = workers[::-1] if swap else workers
    try:
        names = names or [n for n in release.names if n in checkout.names]
        return {n: compare_operation(release, checkout, n, pairs) for n in names}
    finally:
        for worker in workers:
            worker.close()


def compare(
    release_python: Path, root: Path, env: dict[str, str], pairs: int, threshold: float
) -> list[Timing]:
    """Every operation, release against checkout; a suspect is confirmed or cleared.

    An operation that looks slower in the first session is timed again in fresh workers,
    started in the other order, with CONFIRM_FACTOR times the pairs; that second result is
    the one reported, so one noisy session cannot refuse a commit.
    """
    timings = _session(release_python, root, env, pairs)
    suspects = [n for n, t in timings.items() if t.slower(threshold)]
    if suspects:
        again = _session(
            release_python, root, env, pairs * CONFIRM_FACTOR, suspects, swap=True
        )
        timings.update(again)
    return list(timings.values())


def report(timings: list[Timing], version: str, threshold: float) -> str:
    """One line per operation, regressions marked, and a verdict."""
    lines = [f"{'operation':<24}{version:>10}{'checkout':>10}{'ratio':>8}  IQR"]
    for t in timings:
        mark = "  SLOWER" if t.slower(threshold) else ""
        lines.append(
            f"{t.name:<24}{t.release_ns:>10.1f}{t.checkout_ns:>10.1f}"
            f"{t.ratio:>8.3f}  {t.low:.3f}-{t.high:.3f}{mark}"
        )
    slow = [t.name for t in timings if t.slower(threshold)]
    verdict = (
        f"slower than {version}: {', '.join(slow)}"
        if slow
        else f"no operation slower than {version} (threshold {threshold:.2f})"
    )
    lines.append(verdict)
    return "\n".join(lines)
