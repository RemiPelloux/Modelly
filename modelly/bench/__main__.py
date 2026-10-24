"""Command line for ``python -m modelly.bench`` (``modelly bench``): run the playbooks, keep a history."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from modelly.bench import history, report
from modelly.bench.pinning import Pinning, choose, pinned
from modelly.bench.playbooks import (
    PlaybookError,
    Variant,
    load_registry,
    run_once,
    select_variants,
)

EXIT_OK, EXIT_REGRESSION, EXIT_USAGE = 0, 1, 2
PROG = "python -m modelly.bench"
DEFAULT_PLAYBOOKS = Path("benchmarks") / "playbooks"
DEFAULT_ROUNDS = 3
DEFAULT_SIZE = "large"
DEFAULT_SEED = 1

DESCRIPTION = """\
Run the Modelly variants of the benchmark playbooks, each in a fresh
interpreter, for a number of rounds; the order of the variants alternates from
one round to the next, so a load spike lands on all of them. Each run's CPU
seconds (build plus run, imports excluded) come from the playbook worker.

The runs are pinned to one CPU core through psutil where the system allows it
(Linux, Windows); macOS has no affinity API, and the report says the runs were
not pinned. Every invocation appends one JSON line to the history file, then
compares each variant's median with a baseline entry: the one named by
--baseline (a --label given earlier, or an index such as 0 or -2), else the
latest entry at the same size. A variant slower than its baseline by more than
--threshold is a regression.

With MESA_PYTHON set to the interpreter of a Mesa 2.3 environment, the Mesa
variant of each playbook runs too (see benchmarks/playbooks/README.md).
"""

EPILOG = f"""\
examples:
  modelly bench                                   every playbook, size large, 3 rounds
  modelly bench --size small --rounds 5 --only grid_epidemic --only schelling:modelly
  modelly bench --label v1.2.0                    record a named baseline
  modelly bench --baseline v1.2.0 --threshold 0.05
  modelly bench --history ~/bench/modelly.jsonl --core 3
  MESA_PYTHON=.venv-mesa2/bin/python modelly bench --size small

exit codes:
  {EXIT_OK}  every variant ran; none is slower than its baseline beyond --threshold
  {EXIT_REGRESSION}  at least one regression (listed at the end of the report)
  {EXIT_USAGE}  bad command line, playbooks or baseline not found, or a run failed
"""


def positive(text: str) -> int:
    """An integer of at least 1, for --rounds."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text}")
    return value


def fraction(text: str) -> float:
    """A non-negative number, for --threshold."""
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a number >= 0, got {text}")
    return value


OPTIONS = (
    (
        ("--playbooks",),
        {
            "type": Path,
            "default": DEFAULT_PLAYBOOKS,
            "metavar": "DIR",
            "help": "the playbook directory (default: %(default)s)",
        },
    ),
    (
        ("--only",),
        {
            "action": "append",
            "default": [],
            "metavar": "PLAYBOOK[:VARIANT]",
            "help": "run only this playbook or variant; repeatable",
        },
    ),
    (
        ("--size",),
        {
            "default": DEFAULT_SIZE,
            "help": "a size of the registry (default: %(default)s)",
        },
    ),
    (
        ("--rounds",),
        {
            "type": positive,
            "default": DEFAULT_ROUNDS,
            "help": "runs per variant (default: %(default)s)",
        },
    ),
    (
        ("--seed",),
        {
            "type": int,
            "default": DEFAULT_SEED,
            "help": "the model seed (default: %(default)s)",
        },
    ),
    (
        ("--core",),
        {"type": int, "help": "the CPU core to pin to (default: the last one allowed)"},
    ),
    (("--no-pin",), {"action": "store_true", "help": "do not pin the runs"}),
    (
        ("--history",),
        {
            "type": Path,
            "default": history.DEFAULT_HISTORY,
            "metavar": "PATH",
            "help": "the JSON-lines history file (default: %(default)s)",
        },
    ),
    (("--label",), {"help": "a name for this entry, to use as a --baseline later"}),
    (("--baseline",), {"metavar": "LABEL|INDEX", "help": "the entry to compare with"}),
    (
        ("--threshold",),
        {
            "type": fraction,
            "default": history.DEFAULT_THRESHOLD,
            "help": "slowdown counted as a regression (default: %(default)s = 10%%)",
        },
    ),
    (
        ("--no-record",),
        {"action": "store_true", "help": "compare without appending to the history"},
    ),
    (("--format",), {"choices": ("text", "json"), "default": "text"}),
)


def parse_args(argv: list[str] | None, prog: str = PROG) -> argparse.Namespace:
    """Read the command line; ``prog`` names the command in --help."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for flags, options in OPTIONS:
        parser.add_argument(*flags, **options)
    return parser.parse_args(argv)


def run_rounds(
    args: argparse.Namespace, variants: list[Variant], pinning: Pinning
) -> dict[str, list[dict[str, Any]]]:
    """Every variant once per round, the order reversed on every other round."""
    runs: dict[str, list[dict[str, Any]]] = {v.key: [] for v in variants}
    with pinned(pinning):
        for index in range(args.rounds):
            order = variants if index % 2 == 0 else variants[::-1]
            for variant in order:
                row = run_once(args.playbooks, variant, args.seed, args.size)
                runs[variant.key].append(row)
    return runs


def bench(args: argparse.Namespace) -> tuple[str, bool]:
    """Run, record and compare; the report and whether a variant regressed."""
    variants = select_variants(load_registry(args.playbooks), args.only, args.size)
    if not variants:
        raise PlaybookError("no Modelly variant matches --only")
    pinning = choose(args.core, enabled=not args.no_pin)
    baseline = history.find_baseline(
        history.load(args.history), args.baseline, args.size
    )
    runs = run_rounds(args, variants, pinning)
    settings = {
        "label": args.label,
        "size": args.size,
        "seed": args.seed,
        "rounds": args.rounds,
        "pinning": pinning.note,
    }
    entry = history.make_entry(runs, settings)
    if not args.no_record:
        history.append(args.history, entry)
    changes = history.compare(entry, baseline, args.threshold)
    if args.format == "json":
        text = report.as_json(entry, changes)
    else:
        text = report.text(entry, changes, baseline, args.threshold)
    return text, any(change.regression for change in changes)


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the benchmark and write the report; the exit status."""
    args = parse_args(argv, prog)
    try:
        text, regressed = bench(args)
    except (PlaybookError, LookupError, ValueError, OSError) as error:
        sys.stderr.write(f"modelly bench: {error}\n")
        return EXIT_USAGE
    sys.stdout.write(text + "\n")
    return EXIT_REGRESSION if regressed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
