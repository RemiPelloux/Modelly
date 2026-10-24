"""Command line for ``python -m modelly.dev``: the contributor gate and golden digests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from modelly.dev.gate import (
    EXIT_FAILED,
    EXIT_PASSED,
    EXIT_USAGE,
    STAGES,
    GateError,
    checkout_root,
    run_gate,
    unknown_stages,
)
from modelly.dev.golden import (
    GOLDEN,
    current_digests,
    differences,
    read_golden,
    write_golden,
)

PROG = "python -m modelly.dev"

DESCRIPTION = """\
Contributor tools for a Modelly checkout.

gate runs the stages of scripts/ci-local.sh (lint, format, test, audit) with this
Python, so the same gate runs on Windows, macOS and Linux without bash.

golden runs every bundled example and compares the digest of its data and final
state with tests/determinism/golden.json (see docs/determinism.md)."""

EPILOG = f"""\
examples:
  python -m modelly.dev gate               every stage
  python -m modelly.dev gate --list        the stage names
  python -m modelly.dev gate lint audit    a subset, in the order given
  python -m modelly.dev golden             check the golden digests
  python -m modelly.dev golden --update    rewrite them after a deliberate change
  python -m modelly.dev golden --json      this build's exact digests, as JSON

exit status:
  {EXIT_PASSED}  every selected stage passed
  {EXIT_FAILED}  at least one stage failed, or a golden digest differs
  {EXIT_USAGE}  usage error: unknown stage, or not a Modelly checkout"""


def build_parser(prog: str = PROG) -> argparse.ArgumentParser:
    """The parser: one ``gate`` command with its stages."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    gate = commands.add_parser("gate", help="lint, format, test and audit, in order")
    gate.add_argument(
        "stages", nargs="*", help=f"stages to run (default: all of {', '.join(STAGES)})"
    )
    gate.add_argument("--list", action="store_true", help="print the stage names")
    golden = commands.add_parser("golden", help="check or update the golden digests")
    action = golden.add_mutually_exclusive_group()
    action.add_argument("--update", action="store_true", help="rewrite the golden file")
    action.add_argument(
        "--json", action="store_true", help="print exact (unrounded) digests as JSON"
    )
    golden.add_argument("--file", type=Path, help=f"golden file (default: {GOLDEN})")
    return parser


def _gate(args: argparse.Namespace) -> int:
    if args.list:
        sys.stdout.write("\n".join(STAGES) + "\n")
        return EXIT_PASSED
    unknown = unknown_stages(args.stages)
    if unknown:
        sys.stderr.write(f"Unknown stage: {unknown[0]} (see --list)\n")
        return EXIT_USAGE
    try:
        root = checkout_root()
    except GateError as error:
        sys.stderr.write(f"modelly.dev: {error}\n")
        return EXIT_USAGE
    return run_gate(args.stages, root, sys.stdout)


def _golden(args: argparse.Namespace) -> int:
    if args.json:
        sys.stdout.write(json.dumps(current_digests(exact=True), sort_keys=True) + "\n")
        return EXIT_PASSED
    digests = current_digests()
    try:
        path = args.file or checkout_root() / GOLDEN
    except GateError as error:
        sys.stderr.write(f"modelly.dev: {error}; pass --file\n")
        return EXIT_USAGE
    if args.update:
        write_golden(path, digests)
        sys.stdout.write(f"wrote {len(digests)} digests to {path}\n")
        return EXIT_PASSED
    lines = differences(read_golden(path), digests)
    sys.stdout.write(
        "\n".join(lines or [f"{len(digests)} golden digests match"]) + "\n"
    )
    return EXIT_FAILED if lines else EXIT_PASSED


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the command and return its exit status."""
    args = build_parser(prog).parse_args(argv)
    return _gate(args) if args.command == "gate" else _golden(args)


if __name__ == "__main__":
    sys.exit(main())
