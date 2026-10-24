"""Command line for ``python -m modelly.dev``: the contributor gate on any operating system."""

from __future__ import annotations

import argparse
import sys

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

PROG = "python -m modelly.dev"

DESCRIPTION = """\
Contributor tools for a Modelly checkout.

gate runs the stages of scripts/ci-local.sh (lint, format, test, audit) with this
Python, so the same gate runs on Windows, macOS and Linux without bash."""

EPILOG = f"""\
examples:
  python -m modelly.dev gate               every stage
  python -m modelly.dev gate --list        the stage names
  python -m modelly.dev gate lint audit    a subset, in the order given

exit status:
  {EXIT_PASSED}  every selected stage passed
  {EXIT_FAILED}  at least one stage failed
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
    return parser


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Run the command and return its exit status."""
    args = build_parser(prog).parse_args(argv)
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


if __name__ == "__main__":
    sys.exit(main())
